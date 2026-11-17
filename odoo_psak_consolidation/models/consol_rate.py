# -*- coding: utf-8 -*-
from odoo import models, fields, api, _

class ConsolRate(models.Model):
    _name = 'consol.rate'
    _description = 'Kurs Valuta Asing per Periode Konsolidasi (PSAK 10)'
    _order = 'period_id, currency_id'

    group_id = fields.Many2one(
        'consol.group',
        string='Grup Konsolidasi',
        required=True,
        ondelete='cascade')

    reporting_currency_id = fields.Many2one(
        'res.currency',
        string='Mata Uang Pelaporan',
        related='group_id.currency_id')

    currency_id = fields.Many2one(
        'res.currency',
        string='Mata Uang Fungsional',
        required=True,
        ondelete='cascade',
        help="Mata uang entitas anak yang akan ditranslasikan ke mata uang pelaporan.")

    period_id = fields.Many2one(
        'consol.period',
        string='Periode Konsolidasi',
        required=True,
        ondelete='cascade')

    closing_rate = fields.Float(
        string='Kurs Penutupan (Closing Rate)',
        digits=(12, 6),
        default=1.0,
        required=True,
        help="Kurs pada akhir periode untuk mentranslasikan Aset dan Liabilitas (PSAK 10 / IAS 21 par. 39a).")

    average_rate = fields.Float(
        string='Kurs Rata-Rata (Average Rate)',
        digits=(12, 6),
        default=1.0,
        required=True,
        help="Kurs rata-rata selama periode untuk mentranslasikan Pendapatan dan Beban (PSAK 10 / IAS 21 par. 39b).")

    historical_rate = fields.Float(
        string='Kurs Historis (Historical Rate)',
        digits=(12, 6),
        default=1.0,
        help="Kurs pada tanggal transaksi/akuisisi untuk pos-pos Ekuitas.")

    is_custom = fields.Boolean(
        string='Kurs Kustom (Manual)',
        default=False,
        help="Menandakan bahwa kurs dimasukkan atau diubah secara manual oleh pengguna.")

    _period_currency_unique = models.Constraint(
        'unique(period_id, currency_id)',
        'Kurs untuk mata uang ini pada periode tersebut sudah ada!',
    )

    @api.onchange('period_id')
    def _onchange_period_id(self):
        if self.period_id:
            self.group_id = self.period_id.group_id

    @api.model
    def get_or_create_rate(self, period, currency):
        """Ambil atau buat record kurs untuk periode dan mata uang tertentu."""
        if not period or not currency:
            return self.browse()
        rate = self.search([
            ('period_id', '=', period.id),
            ('currency_id', '=', currency.id)
        ], limit=1)
        if not rate:
            rate = self.create({
                'period_id': period.id,
                'group_id': period.group_id.id,
                'currency_id': currency.id,
                'closing_rate': 1.0,
                'average_rate': 1.0,
                'historical_rate': 1.0,
            })
        return rate

