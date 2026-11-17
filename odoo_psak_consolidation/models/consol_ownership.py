# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError

class ConsolOwnership(models.Model):
    _name = 'consol.ownership'
    _description = 'Struktur Kepemilikan Saham & Pengendalian'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'parent_id, child_id, date_from desc'

    parent_id = fields.Many2one(
        'consol.entity',
        string='Entitas Induk / Pemilik',
        required=True,
        tracking=True,
        ondelete='cascade')

    child_id = fields.Many2one(
        'consol.entity',
        string='Entitas Anak / Investee',
        required=True,
        tracking=True,
        ondelete='cascade')

    percentage = fields.Float(
        string='Kepemilikan Langsung (%)',
        required=True,
        default=100.0,
        tracking=True,
        help="Persentase kepemilikan modal langsung yang dimiliki entitas induk atas anak perusahaan.")

    voting_percentage = fields.Float(
        string='Hak Suara (%)',
        help="Persentase hak suara. Dapat berbeda dari persentase modal jika terdapat saham preferen tanpa hak suara.")

    method = fields.Selection([
        ('full', 'Konsolidasi Penuh (PSAK 65 / IFRS 10)'),
        ('equity', 'Metode Ekuitas (PSAK 15 / IAS 28)'),
        ('fair_value', 'Nilai Wajar melalui Laba Rugi (PSAK 71)'),
        ('none', 'Tidak Dikonsolidasi')
    ], string='Metode Akuntansi', default='full', required=True, tracking=True)

    date_from = fields.Date(
        string='Tanggal Memperoleh Pengendalian',
        tracking=True,
        help="Tanggal efektif diperolehnya pengendalian (PSAK 65 par. 20).")

    date_to = fields.Date(
        string='Tanggal Kehilangan Pengendalian',
        tracking=True,
        help="Tanggal pelepasan saham atau hilangnya pengendalian.")

    nci_measurement = fields.Selection([
        ('fair_value', 'Nilai Wajar'),
        ('proportionate', 'Bagian Proporsional Aset Bersih Teridentifikasi')
    ], string='Metode Pengukuran Awal NCI (PSAK 22)', default='proportionate', required=True)

    effective_percentage = fields.Float(
        string='Kepemilikan Efektif (%)',
        compute='_compute_effective_percentage',
        store=True,
        digits=(6, 4),
        tracking=True,
        help="Persentase kepemilikan kumulatif efektif yang memperhitungkan jalur kepemilikan bertingkat.")

    nci_percentage = fields.Float(
        string='Kepentingan Non-Pengendali / NCI (%)',
        compute='_compute_nci_percentage',
        store=True,
        digits=(6, 4),
        tracking=True,
        help="Persentase kepemilikan pihak non-pengendali di luar induk perusahaan (100% - Kepemilikan Efektif).")

    currency_id = fields.Many2one(
        'res.currency',
        string='Mata Uang',
        related='parent_id.functional_currency_id')

    goodwill_amount = fields.Monetary(
        string='Nilai Goodwill Saat Akuisisi (E1)',
        currency_field='currency_id',
        tracking=True,
        help="Goodwill yang diakui pada tanggal kombinasi bisnis (PSAK 22 / IFRS 3).")

    nci_at_acquisition = fields.Monetary(
        string='Nilai NCI Saat Akuisisi (E1)',
        currency_field='currency_id',
        tracking=True,
        help="Nilai Kepentingan Non-Pengendali yang diakui pada tanggal akuisisi.")

    note = fields.Text(string='Catatan Analisis Investasi')

    @api.constrains('parent_id', 'child_id')
    def _check_self_ownership(self):
        for rec in self:
            if rec.parent_id == rec.child_id:
                raise ValidationError(_("Entitas '%s' tidak dapat memiliki dirinya sendiri!", rec.parent_id.name))

    @api.constrains('percentage', 'voting_percentage')
    def _check_percentages(self):
        for rec in self:
            if rec.percentage < 0 or rec.percentage > 100:
                raise ValidationError(_("Persentase kepemilikan harus antara 0% dan 100%!"))
            if rec.voting_percentage and (rec.voting_percentage < 0 or rec.voting_percentage > 100):
                raise ValidationError(_("Persentase hak suara harus antara 0% dan 100%!"))

    @api.depends('parent_id', 'child_id', 'percentage', 'method')
    def _compute_effective_percentage(self):
        """
        Hitung persentase kepemilikan efektif menggunakan graf traversal.
        Mendukung jalur langsung, bertingkat, dan kepemilikan silang dengan deteksi loop melingkar.
        """
        all_ownerships = self.search([])
        graph = {}
        for own in all_ownerships:
            graph.setdefault(own.parent_id.id, []).append((own.child_id.id, own.percentage / 100.0))

        def find_all_paths(start, end, visited=None):
            if visited is None:
                visited = []
            if start in visited:
                raise ValidationError(_("Terdeteksi kepemilikan melingkar (circular loop) yang melibatkan entitas ID %s!", start))
            new_visited = visited + [start]
            if start == end:
                return [[1.0]]
            paths = []
            for neighbor, weight in graph.get(start, []):
                sub_paths = find_all_paths(neighbor, end, new_visited)
                for sp in sub_paths:
                    paths.append([weight] + sp)
            return paths

        for rec in self:
            if not rec.parent_id or not rec.child_id:
                rec.effective_percentage = rec.percentage
                continue

            try:
                # Cari semua jalur kepemilikan dari parent_id ke child_id
                paths = []
                for neighbor, weight in graph.get(rec.parent_id.id, []):
                    if neighbor == rec.child_id.id:
                        paths.append([weight])
                    else:
                        sub_paths = find_all_paths(neighbor, rec.child_id.id, [rec.parent_id.id])
                        for sp in sub_paths:
                            paths.append([weight] + sp)

                total_effective = 0.0
                for path in paths:
                    path_eff = 1.0
                    for step in path:
                        path_eff *= step
                    total_effective += path_eff

                rec.effective_percentage = round(total_effective * 100.0, 4) if total_effective > 0 else rec.percentage
            except Exception as e:
                # Default ke persentase langsung jika fallback
                rec.effective_percentage = rec.percentage

    @api.depends('effective_percentage', 'method')
    def _compute_nci_percentage(self):
        for rec in self:
            if rec.method == 'full':
                rec.nci_percentage = round(max(0.0, 100.0 - rec.effective_percentage), 4)
            else:
                rec.nci_percentage = 0.0
