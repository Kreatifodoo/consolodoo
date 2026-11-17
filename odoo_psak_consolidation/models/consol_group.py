# -*- coding: utf-8 -*-
from odoo import models, fields, api, _

class ConsolGroup(models.Model):
    _name = 'consol.group'
    _description = 'Grup Konsolidasi Keuangan'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char(string='Nama Grup Konsolidasi', required=True, tracking=True)
    
    parent_company_id = fields.Many2one(
        'res.company',
        string='Perusahaan Induk Tertinggi',
        required=True,
        default=lambda self: self.env.company,
        tracking=True,
        help="Perusahaan Odoo yang bertindak sebagai entitas induk tertinggi dalam grup konsolidasi.")

    parent_entity_id = fields.Many2one(
        'consol.entity',
        string='Entitas Konsolidasi Induk',
        compute='_compute_parent_entity_id',
        store=True,
        readonly=False,
        tracking=True,
        help="Entitas konsolidasi yang mewakili perusahaan induk.")

    currency_id = fields.Many2one(
        'res.currency',
        string='Mata Uang Pelaporan',
        required=True,
        default=lambda self: self.env.ref('base.IDR', raise_if_not_found=False) or self.env.company.currency_id,
        tracking=True,
        help="Mata uang penyajian laporan keuangan konsolidasian.")

    chart_template_id = fields.Many2one(
        'consol.account',
        string='Bagan Akun Konsolidasi (Induk)',
        help="Akun induk bagan akun konsolidasi.")

    fiscal_year_start = fields.Selection([
        ('1', 'Januari'), ('2', 'Februari'), ('3', 'Maret'), ('4', 'April'),
        ('5', 'Mei'), ('6', 'Juni'), ('7', 'Juli'), ('8', 'Agustus'),
        ('9', 'September'), ('10', 'Oktober'), ('11', 'November'), ('12', 'Desember')
    ], string='Awal Tahun Fiskal', default='1', required=True)

    rounding = fields.Float(
        string='Faktor Pembulatan Laporan',
        default=1.0,
        help="Faktor pembagi angka laporan: 1 (Satuan Penuh), 1.000 (Ribuan), 1.000.000 (Jutaan).")

    cta_account_id = fields.Many2one(
        'consol.account',
        string='Akun Selisih Kurs Translasi (CTA - OCI)',
        domain="[('statement', 'in', ['oci', 'equity'])]",
        tracking=True,
        help="Akun penampung selisih kurs translasi mata uang asing sesuai PSAK 10 / IAS 21.")

    nci_equity_account_id = fields.Many2one(
        'consol.account',
        string='Akun Kepentingan Non-Pengendali (Ekuitas)',
        domain="[('statement', '=', 'equity')]",
        tracking=True,
        help="Akun Kepentingan Non-Pengendali dalam ekuitas konsolidasian (PSAK 65 / IFRS 10).")

    nci_pl_account_id = fields.Many2one(
        'consol.account',
        string='Akun Bagian Laba Rugi NCI',
        domain="[('statement', '=', 'pl')]",
        tracking=True,
        help="Akun atribusi laba/rugi tahun berjalan kepada Kepentingan Non-Pengendali.")

    goodwill_account_id = fields.Many2one(
        'consol.account',
        string='Akun Goodwill Konsolidasi',
        domain="[('statement', '=', 'bs')]",
        tracking=True,
        help="Akun goodwill yang timbul dari kombinasi bisnis (PSAK 22 / IFRS 3).")

    retained_earnings_account_id = fields.Many2one(
        'consol.account',
        string='Akun Saldo Laba Konsolidasi',
        domain="[('statement', '=', 'equity')]",
        tracking=True,
        help="Akun akumulasi saldo laba konsolidasian.")

    ic_tolerance = fields.Monetary(
        string='Batas Toleransi Selisih Intragrup',
        currency_field='currency_id',
        default=0.0,
        tracking=True,
        help="Batas maksimal selisih yang diperbolehkan sebelum periode dapat dikunci.")

    parent_group_id = fields.Many2one(
        'consol.group',
        string='Grup Induk (Jika Sub-Grup)',
        ondelete='restrict')

    sub_group_ids = fields.One2many(
        'consol.group',
        'parent_group_id',
        string='Sub-Grup Konsolidasi Bertingkat')

    entity_ids = fields.Many2many(
        'consol.entity',
        'consol_group_entity_rel',
        'group_id',
        'entity_id',
        string='Entitas Anggota',
        tracking=True)

    period_ids = fields.One2many(
        'consol.period',
        'group_id',
        string='Periode Konsolidasi')

    active = fields.Boolean(string='Aktif', default=True)
    note = fields.Text(string='Keterangan / Kebijakan Konsolidasi')

    @api.depends('parent_company_id')
    def _compute_parent_entity_id(self):
        for rec in self:
            if rec.parent_company_id:
                entity = self.env['consol.entity'].search([
                    ('company_id', '=', rec.parent_company_id.id)
                ], limit=1)
                if not entity:
                    entity = self.env['consol.entity'].search([
                        ('name', '=', rec.parent_company_id.name)
                    ], limit=1)
                    if entity:
                        if not entity.company_id:
                            entity.write({'company_id': rec.parent_company_id.id, 'source_type': 'odoo'})
                    else:
                        code = (rec.parent_company_id.code or rec.parent_company_id.name[:10]).strip().upper().replace(' ', '_')
                        entity = self.env['consol.entity'].create({
                            'name': rec.parent_company_id.name,
                            'code': code or 'PARENT',
                            'company_id': rec.parent_company_id.id,
                            'source_type': 'odoo',
                            'functional_currency_id': rec.parent_company_id.currency_id.id,
                            'partner_id': rec.parent_company_id.partner_id.id if rec.parent_company_id.partner_id else False,
                        })
                rec.parent_entity_id = entity.id
                if entity and entity not in rec.entity_ids:
                    rec.entity_ids = [(4, entity.id)]

    @api.onchange('parent_company_id')
    def _onchange_parent_company_id(self):
        if self.parent_company_id:
            if not self.name or self.name == 'Grup Konsolidasi Baru':
                self.name = f"{self.parent_company_id.name} Group"
            if self.parent_company_id.currency_id:
                self.currency_id = self.parent_company_id.currency_id.id

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get('parent_company_id') and vals.get('parent_entity_id'):
                entity = self.env['consol.entity'].browse(vals['parent_entity_id'])
                if entity.company_id:
                    vals['parent_company_id'] = entity.company_id.id
                else:
                    vals['parent_company_id'] = self.env.company.id
            elif vals.get('parent_company_id') and not vals.get('currency_id'):
                comp = self.env['res.company'].browse(vals['parent_company_id'])
                if comp.currency_id:
                    vals['currency_id'] = comp.currency_id.id
        return super().create(vals_list)
