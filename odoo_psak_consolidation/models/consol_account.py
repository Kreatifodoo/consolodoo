# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError

class ConsolAccount(models.Model):
    _name = 'consol.account'
    _description = 'Bagan Akun Konsolidasi'
    _inherit = ['mail.thread']
    _order = 'code, id'

    name = fields.Char(string='Nama Akun', required=True, tracking=True)
    code = fields.Char(string='Kode Akun', required=True, tracking=True, index=True)
    
    account_type = fields.Selection([
        ('asset_receivable', 'Piutang Usaha'),
        ('asset_cash', 'Kas dan Bank'),
        ('asset_current', 'Aset Lancar'),
        ('asset_non_current', 'Aset Tidak Lancar'),
        ('asset_prepayments', 'Biaya Dibayar di Muka'),
        ('asset_fixed', 'Aset Tetap'),
        ('liability_payable', 'Utang Usaha'),
        ('liability_credit_card', 'Kartu Kredit'),
        ('liability_current', 'Liabilitas Jangka Pendek'),
        ('liability_non_current', 'Liabilitas Jangka Panjang'),
        ('equity', 'Ekuitas'),
        ('equity_unaffected', 'Laba Tahun Berjalan'),
        ('income', 'Pendapatan Usaha'),
        ('income_other', 'Pendapatan Lain-lain'),
        ('expense', 'Beban Operasional'),
        ('expense_depreciation', 'Penyusutan & Amortisasi'),
        ('expense_direct_cost', 'Beban Pokok Penjualan (HPP)'),
        ('off_balance', 'Di Luar Neraca (Off-Balance)')
    ], string='Tipe Akun', required=True, tracking=True, default='asset_current')

    statement = fields.Selection([
        ('bs', 'Laporan Posisi Keuangan (Neraca)'),
        ('pl', 'Laporan Laba Rugi'),
        ('oci', 'Penghasilan Komprehensif Lain (OCI)'),
        ('equity', 'Laporan Perubahan Ekuitas'),
        ('cf_memo', 'Memo Arus Kas')
    ], string='Kelompok Laporan Keuangan', required=True, tracking=True, default='bs')

    translation_rate = fields.Selection([
        ('closing', 'Kurs Penutupan (Closing Rate)'),
        ('average', 'Kurs Rata-Rata (Average Rate)'),
        ('historical', 'Kurs Historis (Historical Rate)')
    ], string='Tipe Kurs Translasi (PSAK 10)', required=True, default='closing',
       help="Jenis kurs yang digunakan untuk mentranslasikan mata uang fungsional ke mata uang penyajian sesuai PSAK 10 / IAS 21.")

    is_intercompany = fields.Boolean(
        string='Akun Antar-Perusahaan (Intercompany)',
        default=False,
        tracking=True,
        help="Centang jika akun ini wajib direkonsiliasi dan dieliminasi dalam transaksi antar-perusahaan.")

    ic_counterpart_id = fields.Many2one(
        'consol.account',
        string='Akun Lawan Antar-Perusahaan',
        help="Akun lawan yang berpasangan di entitas terkait (misal: Piutang Intragrup berpasangan dengan Utang Intragrup).")

    parent_id = fields.Many2one(
        'consol.account',
        string='Akun Induk',
        index=True,
        ondelete='restrict')

    child_ids = fields.One2many(
        'consol.account',
        'parent_id',
        string='Sub-Akun')

    active = fields.Boolean(string='Aktif', default=True)
    note = fields.Text(string='Catatan / Deskripsi Akun')

    _code_unique = models.Constraint(
        'unique(code)',
        'Kode akun konsolidasi harus unik!',
    )

    @api.depends('code', 'name')
    def _compute_display_name(self):
        for rec in self:
            rec.display_name = f"[{rec.code}] {rec.name}" if rec.code else rec.name

    @api.constrains('parent_id')
    def _check_parent_recursion(self):
        if not self._check_recursion():
            raise ValidationError(_('Terdeteksi hierarki akun melingkar (circular) pada akun %s!', self.display_name))

    @api.model
    def action_open_import_company_coa_wizard(self):
        return {
            'name': _('Salin Master Akun dari Perusahaan & Petakan Otomatis'),
            'type': 'ir.actions.act_window',
            'res_model': 'consol.import.company.coa.wizard',
            'view_mode': 'form',
            'target': 'new',
        }
