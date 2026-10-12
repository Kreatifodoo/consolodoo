# -*- coding: utf-8 -*-
from odoo import models, fields, api, _

class ConsolTrialBalance(models.Model):
    _name = 'consol.trial.balance'
    _description = 'Entity Trial Balance per Period'
    _order = 'period_id, entity_id'

    period_id = fields.Many2one(
        'consol.period',
        string='Consolidation Period',
        required=True,
        ondelete='cascade')

    entity_id = fields.Many2one(
        'consol.entity',
        string='Entity',
        required=True,
        ondelete='cascade')

    functional_currency_id = fields.Many2one(
        'res.currency',
        string='Functional Currency',
        related='entity_id.functional_currency_id')

    reporting_currency_id = fields.Many2one(
        'res.currency',
        string='Reporting Currency',
        related='period_id.currency_id')

    line_ids = fields.One2many(
        'consol.trial.balance.line',
        'trial_balance_id',
        string='Trial Balance Lines')

    total_debit_rc = fields.Float(
        string='Total Debit (RC)',
        compute='_compute_totals',
        store=True)

    total_credit_rc = fields.Float(
        string='Total Credit (RC)',
        compute='_compute_totals',
        store=True)

    total_balance_rc = fields.Float(
        string='Total Balance (RC)',
        compute='_compute_totals',
        store=True)

    _sql_constraints = [
        ('period_entity_unique', 'unique(period_id, entity_id)', 'Trial balance for this entity and period already exists!'),
    ]

    @api.depends('line_ids.balance_rc')
    def _compute_totals(self):
        for rec in self:
            deb = sum(line.balance_rc for line in rec.line_ids if line.balance_rc > 0)
            cred = sum(abs(line.balance_rc) for line in rec.line_ids if line.balance_rc < 0)
            rec.total_debit_rc = deb
            rec.total_credit_rc = cred
            rec.total_balance_rc = sum(line.balance_rc for line in rec.line_ids)


class ConsolTrialBalanceLine(models.Model):
    _name = 'consol.trial.balance.line'
    _description = 'Consolidation Worksheet Account Balance Line'
    _order = 'consol_account_id, source_account_id'

    trial_balance_id = fields.Many2one(
        'consol.trial.balance',
        string='Trial Balance',
        required=True,
        ondelete='cascade')

    period_id = fields.Many2one(
        'consol.period',
        string='Period',
        related='trial_balance_id.period_id',
        store=True,
        index=True)

    entity_id = fields.Many2one(
        'consol.entity',
        string='Entity',
        related='trial_balance_id.entity_id',
        store=True,
        index=True)

    consol_account_id = fields.Many2one(
        'consol.account',
        string='Consolidation Account',
        required=True,
        ondelete='restrict',
        index=True)

    source_account_id = fields.Many2one(
        'account.account',
        string='Source Odoo Account',
        ondelete='set null')

    external_code = fields.Char(string='External Account Code')
    external_name = fields.Char(string='External Account Name')

    partner_id = fields.Many2one(
        'res.partner',
        string='Intercompany Partner',
        help="Partner recorded on transaction, used for intercompany matching.")

    statement = fields.Selection(
        related='consol_account_id.statement',
        store=True,
        string='Financial Statement')

    translation_rate_type = fields.Selection(
        related='consol_account_id.translation_rate',
        store=True,
        string='Rate Type')

    balance_fc = fields.Float(
        string='Functional Currency Balance (FC)',
        digits=(16, 2),
        default=0.0)

    movement_fc = fields.Float(
        string='YTD Movement (FC)',
        digits=(16, 2),
        default=0.0)

    rate_used = fields.Float(
        string='Rate Applied',
        digits=(12, 6),
        default=1.0)

    balance_rc = fields.Float(
        string='Reporting Currency Balance (RC)',
        digits=(16, 2),
        default=0.0)

    is_intercompany = fields.Boolean(
        related='consol_account_id.is_intercompany',
        store=True)
