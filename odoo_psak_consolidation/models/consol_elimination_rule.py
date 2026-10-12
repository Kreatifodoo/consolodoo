# -*- coding: utf-8 -*-
from odoo import models, fields, api, _

class ConsolEliminationRule(models.Model):
    _name = 'consol.elimination.rule'
    _description = 'Standard Elimination Rule'
    _order = 'sequence, code'

    name = fields.Char(string='Rule Name', required=True)
    code = fields.Char(string='Rule Code', required=True, size=20)

    rule_type = fields.Selection([
        ('investment_equity', 'E1: Investment in Subsidiary vs Equity'),
        ('ic_balance', 'E2: Intercompany Receivables / Payables Balance'),
        ('ic_transaction', 'E3: Intercompany Income / Expenses Transaction'),
        ('ic_dividend', 'E6: Intercompany Dividends'),
        ('nci_attribution', 'E7: Profit/Loss & OCI Attribution to NCI'),
        ('cta', 'E10: Foreign Currency Translation (CTA)')
    ], string='Standard Elimination Type', required=True)

    debit_account_ids = fields.Many2many(
        'consol.account',
        'consol_elim_rule_debit_rel',
        'rule_id',
        'account_id',
        string='Eliminated Accounts (Debit Side)')

    credit_account_ids = fields.Many2many(
        'consol.account',
        'consol_elim_rule_credit_rel',
        'rule_id',
        'account_id',
        string='Eliminated Accounts (Credit Side)')

    difference_account_id = fields.Many2one(
        'consol.account',
        string='Discrepancy Balancing Account',
        help="Account to absorb uneliminated variance if permitted (e.g. IC FX difference).")

    active = fields.Boolean(string='Active', default=True)
    sequence = fields.Integer(string='Execution Sequence', default=10)
    description = fields.Text(string='Accounting Standard / Rationale')
