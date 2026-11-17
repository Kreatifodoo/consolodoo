# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, UserError

class ConsolJournal(models.Model):
    _name = 'consol.journal'
    _description = 'Jurnal Eliminasi Konsolidasi (E1-E10 & Penyesuaian Manual)'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'period_id, code, id'

    name = fields.Char(string='Deskripsi Jurnal', required=True, tracking=True)
    code = fields.Char(string='Kode Jurnal', required=True, default='MANUAL', tracking=True,
                       help="Contoh: E1, E2, E3, E4, E5, E6, E7, E8, E9, E10, atau MANUAL.")

    period_id = fields.Many2one(
        'consol.period',
        string='Periode Konsolidasi',
        required=True,
        ondelete='cascade',
        tracking=True)

    group_id = fields.Many2one(
        'consol.group',
        string='Grup Konsolidasi',
        related='period_id.group_id',
        store=True)

    currency_id = fields.Many2one(
        'res.currency',
        string='Mata Uang Pelaporan',
        related='period_id.currency_id')

    origin = fields.Selection([
        ('auto', 'Otomatis'),
        ('manual', 'Manual / Pengguna')
    ], string='Sumber Jurnal', default='manual', required=True, tracking=True)

    rule_id = fields.Many2one(
        'consol.elimination.rule',
        string='Aturan Eliminasi',
        help="Aturan standar jika jurnal dibuat secara otomatis oleh sistem.")

    recurring = fields.Boolean(
        string='Berulang (Dibawa ke Periode Berikutnya)',
        default=False,
        tracking=True,
        help="Jika dicentang, jurnal ini akan dibawa ke periode konsolidasi berikutnya sebagai saldo awal (misal: E1, E5, E9).")

    auto_reverse = fields.Boolean(
        string='Pembalikan Otomatis (Auto-Reverse)',
        default=False,
        tracking=True,
        help="Jika dicentang, jurnal ini akan dibalik secara otomatis pada periode konsolidasi berikutnya (misal: E4 laba belum terealisasi persediaan).")

    reversed_from_id = fields.Many2one(
        'consol.journal',
        string='Dibalik dari Jurnal',
        readonly=True)

    line_ids = fields.One2many(
        'consol.journal.line',
        'journal_id',
        string='Baris Jurnal Eliminasi')

    total_debit = fields.Monetary(
        string='Total Debit',
        currency_field='currency_id',
        compute='_compute_totals',
        store=True)

    total_credit = fields.Monetary(
        string='Total Kredit',
        currency_field='currency_id',
        compute='_compute_totals',
        store=True)

    state = fields.Selection([
        ('draft', 'Draf'),
        ('posted', 'Terposting')
    ], string='Status', default='draft', required=True, tracking=True)

    note = fields.Text(string='Dasar PSAK / Catatan Pendukung')

    @api.depends('line_ids.debit', 'line_ids.credit')
    def _compute_totals(self):
        for rec in self:
            rec.total_debit = sum(line.debit for line in rec.line_ids)
            rec.total_credit = sum(line.credit for line in rec.line_ids)

    @api.constrains('state', 'line_ids')
    def _check_balance(self):
        for rec in self:
            if rec.state == 'posted':
                if not rec.line_ids:
                    raise ValidationError(_("Jurnal '%s' tidak memiliki baris rincian!", rec.name))
                if round(rec.total_debit, 2) != round(rec.total_credit, 2):
                    raise ValidationError(_(
                        "Jurnal eliminasi '%s' tidak seimbang (balance)!\nTotal Debit: %s\nTotal Kredit: %s\nSelisih: %s",
                        rec.name, rec.total_debit, rec.total_credit, abs(rec.total_debit - rec.total_credit)
                    ))

    def action_post(self):
        for rec in self:
            rec._check_balance()
            rec.state = 'posted'

    def action_reset_draft(self):
        for rec in self:
            if rec.period_id.state == 'locked':
                raise UserError(_("Periode konsolidasi sudah dikunci! Tidak dapat mengembalikan jurnal ke draf."))
            rec.state = 'draft'


class ConsolJournalLine(models.Model):
    _name = 'consol.journal.line'
    _description = 'Baris Jurnal Eliminasi Konsolidasi'
    _order = 'journal_id, id'

    journal_id = fields.Many2one(
        'consol.journal',
        string='Jurnal Eliminasi',
        required=True,
        ondelete='cascade')

    period_id = fields.Many2one(
        'consol.period',
        string='Periode',
        related='journal_id.period_id',
        store=True,
        index=True)

    currency_id = fields.Many2one(
        'res.currency',
        string='Mata Uang',
        related='journal_id.currency_id')

    consol_account_id = fields.Many2one(
        'consol.account',
        string='Akun Konsolidasi',
        required=True,
        index=True)

    entity_id = fields.Many2one(
        'consol.entity',
        string='Kolom Kertas Kerja (Entitas Terkait)',
        help="Biarkan kosong jika eliminasi berlaku secara umum pada kolom Eliminasi (ELIM).")

    partner_entity_id = fields.Many2one(
        'consol.entity',
        string='Entitas Lawan Transaksi',
        help="Entitas mitra transaksi jika relevan.")

    debit = fields.Monetary(
        string='Debit',
        currency_field='currency_id',
        default=0.0)

    credit = fields.Monetary(
        string='Kredit',
        currency_field='currency_id',
        default=0.0)

    nci_share = fields.Float(
        string='Porsi NCI (%)',
        help="Persentase kepentingan non-pengendali yang terpengaruh oleh baris ini.")

    note = fields.Char(string='Keterangan Baris')
