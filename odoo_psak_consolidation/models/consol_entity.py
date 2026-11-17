# -*- coding: utf-8 -*-
from odoo import models, fields, api, _

class ConsolEntity(models.Model):
    _name = 'consol.entity'
    _description = 'Entitas Anggota Grup Konsolidasi'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'code, name'

    name = fields.Char(string='Nama Entitas', required=True, tracking=True)
    code = fields.Char(string='Kode Entitas', required=True, size=15, tracking=True,
                       help="Kode singkat yang digunakan sebagai judul kolom dalam kertas kerja konsolidasi.")
    
    company_id = fields.Many2one(
        'res.company',
        string='Perusahaan Odoo (Internal)',
        help="Tautan ke perusahaan Odoo lokal jika entitas ini berada di database ini. Biarkan kosong untuk entitas eksternal.")

    source_type = fields.Selection([
        ('odoo', 'Database Odoo Lokal'),
        ('import', 'Impor Eksternal (CSV/Excel)')
    ], string='Sumber Data', default='odoo', required=True, tracking=True,
       help="Sumber penarikan data neraca saldo entitas.")

    functional_currency_id = fields.Many2one(
        'res.currency',
        string='Mata Uang Fungsional (PSAK 10)',
        required=True,
        default=lambda self: self.env.company.currency_id,
        tracking=True,
        help="Mata uang lingkungan ekonomi utama tempat entitas beroperasi sesuai PSAK 10 / IAS 21.")

    group_ids = fields.Many2many(
        'consol.group',
        'consol_group_entity_rel',
        'entity_id',
        'group_id',
        string='Grup Konsolidasi')

    partner_id = fields.Many2one(
        'res.partner',
        string='Kontak/Mitra Representasi Entitas',
        help="Kontak/partner yang mewakili entitas ini dalam pembukuan entitas lain untuk pencocokan transaksi intragrup.")

    is_investment_entity = fields.Boolean(
        string='Entitas Investasi (PSAK 65 par. 31)',
        default=False,
        tracking=True,
        help="Jika dicentang, entitas dikecualikan dari konsolidasi dan diukur pada nilai wajar melalui laba rugi.")

    parent_ownership_ids = fields.One2many(
        'consol.ownership',
        'child_id',
        string='Struktur Kepemilikan (Dimiliki Oleh)')

    child_ownership_ids = fields.One2many(
        'consol.ownership',
        'parent_id',
        string='Investasi pada Entitas Lain (Memiliki)')

    active = fields.Boolean(string='Aktif', default=True)
    note = fields.Text(string='Catatan Tambahan')

    _code_unique = models.Constraint(
        'unique(code)',
        'Kode entitas harus unik!',
    )

    @api.onchange('company_id')
    def _onchange_company_id(self):
        if self.company_id:
            self.functional_currency_id = self.company_id.currency_id
            if not self.name:
                self.name = self.company_id.name
            if not self.partner_id:
                self.partner_id = self.company_id.partner_id

    @api.depends('code', 'name')
    def _compute_display_name(self):
        for rec in self:
            rec.display_name = f"[{rec.code}] {rec.name}" if rec.code else rec.name
