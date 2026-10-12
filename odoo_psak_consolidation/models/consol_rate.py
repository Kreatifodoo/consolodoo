# -*- coding: utf-8 -*-
from odoo import models, fields, api, _

class ConsolRate(models.Model):
    _name = 'consol.rate'
    _description = 'Consolidation Exchange Rate per Period (IAS 21)'
    _order = 'period_id, currency_id'

    group_id = fields.Many2one(
        'consol.group',
        string='Consolidation Group',
        required=True,
        ondelete='cascade')

    reporting_currency_id = fields.Many2one(
        'res.currency',
        string='Reporting Currency',
        related='group_id.currency_id')

    currency_id = fields.Many2one(
        'res.currency',
        string='Functional Currency',
        required=True,
        ondelete='cascade',
        help="Subsidiary currency to be translated into reporting currency.")

    period_id = fields.Many2one(
        'consol.period',
        string='Consolidation Period',
        required=True,
        ondelete='cascade')

    closing_rate = fields.Float(
        string='Closing Rate',
        digits=(12, 6),
        default=1.0,
        required=True,
        help="Exchange rate at period end for translating Assets and Liabilities (IAS 21 par. 39a).")

    average_rate = fields.Float(
        string='Average Rate',
        digits=(12, 6),
        default=1.0,
        required=True,
        help="Average exchange rate for the period for translating Income and Expenses (IAS 21 par. 39b).")

    historical_rate = fields.Float(
        string='Historical Rate',
        digits=(12, 6),
        default=1.0,
        help="Exchange rate at transaction/acquisition date for Equity items.")

    is_custom = fields.Boolean(
        string='Custom Rate (Manual)',
        default=False,
        help="Indicates the rate was overridden manually by user.")

    _sql_constraints = [
        ('period_currency_unique', 'unique(period_id, currency_id)', 'Exchange rate for this currency in this period already exists!'),
    ]

    @api.model
    def get_or_create_rate(self, period, currency):
        """
        Mencari atau membuat kurs default berdasarkan data res.currency.rate Odoo.
        """
        existing = self.search([('period_id', '=', period.id), ('currency_id', '=', currency.id)], limit=1)
        if existing:
            return existing

        reporting_curr = period.group_id.currency_id
        if currency == reporting_curr:
            c_rate = 1.0
            a_rate = 1.0
        else:
            # Ambil kurs dari Odoo per date_to
            c_rate = currency._get_conversion_rate(currency, reporting_curr, period.group_id.parent_entity_id.company_id or self.env.company, period.date_to) or 1.0
            # Estimasi average rate jika ada date_from
            rate_start = currency._get_conversion_rate(currency, reporting_curr, period.group_id.parent_entity_id.company_id or self.env.company, period.date_from) or c_rate
            a_rate = (c_rate + rate_start) / 2.0

        return self.create({
            'group_id': period.group_id.id,
            'currency_id': currency.id,
            'period_id': period.id,
            'closing_rate': c_rate,
            'average_rate': a_rate,
            'historical_rate': c_rate,
        })
