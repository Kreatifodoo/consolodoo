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
        digits=(24, 12),
        default=1.0,
        required=True,
        help="Kurs pada akhir periode untuk mentranslasikan Aset dan Liabilitas (PSAK 10 / IAS 21 par. 39a).")

    average_rate = fields.Float(
        string='Kurs Rata-Rata (Average Rate)',
        digits=(24, 12),
        default=1.0,
        required=True,
        help="Kurs rata-rata selama periode untuk mentranslasikan Pendapatan dan Beban (PSAK 10 / IAS 21 par. 39b).")

    historical_rate = fields.Float(
        string='Kurs Historis (Historical Rate)',
        digits=(24, 12),
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
        """Ambil atau buat record kurs untuk periode dan mata uang tertentu.
        Record baru diisi otomatis dari kurs harian Odoo (res.currency.rate); dapat diubah manual."""
        if not period or not currency:
            return self.browse()
        rate = self.search([
            ('period_id', '=', period.id),
            ('currency_id', '=', currency.id)
        ], limit=1)
        if not rate:
            closing, average, historical = self._get_rates_from_odoo(period, currency)
            rate = self.create({
                'period_id': period.id,
                'group_id': period.group_id.id,
                'currency_id': currency.id,
                'closing_rate': closing,
                'average_rate': average,
                'historical_rate': historical,
            })
        return rate

    @api.model
    def _get_rates_from_odoo(self, period, currency):
        """Kurs PSAK 10 (1 unit mata uang fungsional -> mata uang pelaporan grup) dari kurs harian Odoo:
        - penutupan: kurs pada tanggal akhir periode
        - rata-rata: rata-rata kurs pada setiap tanggal fixing di dalam periode
        - historis: kurs pada tanggal kepemilikan paling awal entitas bermata uang ini (atau awal tahun buku)
        """
        target = period.group_id.currency_id
        if not target or not currency or currency == target:
            return 1.0, 1.0, 1.0
        company = (period.group_id.parent_company_id or self.env.company).root_id
        RateModel = self.env['res.currency.rate'].sudo()
        fx_currencies = (currency | target) - company.currency_id
        company_domain = ['|', ('company_id', '=', False), ('company_id', '=', company.id)]

        def fixing(cur, day):
            # Nilai fixing yang berlaku PADA tanggal tsb (inklusif). Sengaja tidak memakai
            # res.currency._get_conversion_rate: Odoo 20 memakai kurs sebelum tanggal dokumen (H-1).
            if cur == company.currency_id:
                return 1.0
            rate = RateModel.search([('currency_id', '=', cur.id), ('name', '<=', day)] + company_domain,
                                    order='company_id, name desc', limit=1)
            if not rate:
                rate = RateModel.search([('currency_id', '=', cur.id)] + company_domain, order='name asc', limit=1)
            return rate.rate or 1.0

        def conv(day):
            # rate = unit mata uang per 1 mata uang perusahaan
            return fixing(target, day) / fixing(currency, day)

        closing = conv(period.date_to)
        days = sorted(set(RateModel.search([
            ('currency_id', 'in', fx_currencies.ids),
            ('name', '>=', period.date_from),
            ('name', '<=', period.date_to),
        ] + company_domain).mapped('name')))
        average = sum(conv(day) for day in days) / len(days) if days else closing

        entities = period._get_active_entities().filtered(lambda e: e.functional_currency_id == currency)
        ownership = self.env['consol.ownership'].search(
            [('child_id', 'in', entities.ids), ('date_from', '!=', False)], order='date_from asc', limit=1)
        hist_date = ownership.date_from or period._get_fiscal_year_start()
        first_fixing = RateModel.search([('currency_id', 'in', fx_currencies.ids)] + company_domain, order='name asc', limit=1)
        if first_fixing and hist_date < first_fixing.name:
            hist_date = first_fixing.name
        historical = conv(hist_date)
        return closing, average, historical

