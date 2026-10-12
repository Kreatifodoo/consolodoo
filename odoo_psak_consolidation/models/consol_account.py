# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError

class ConsolAccount(models.Model):
    _name = 'consol.account'
    _description = 'Consolidation Chart of Accounts'
    _inherit = ['mail.thread']
    _order = 'code, id'

    name = fields.Char(string='Account Name', required=True, tracking=True)
    code = fields.Char(string='Account Code', required=True, tracking=True, index=True)
    
    account_type = fields.Selection([
        ('asset_receivable', 'Receivable'),
        ('asset_cash', 'Bank and Cash'),
        ('asset_current', 'Current Assets'),
        ('asset_non_current', 'Non-current Assets'),
        ('asset_prepayments', 'Prepayments'),
        ('asset_fixed', 'Fixed Assets'),
        ('liability_payable', 'Payable'),
        ('liability_credit_card', 'Credit Card'),
        ('liability_current', 'Current Liabilities'),
        ('liability_non_current', 'Non-current Liabilities'),
        ('equity', 'Equity'),
        ('equity_unaffected', 'Current Year Earnings'),
        ('income', 'Income'),
        ('income_other', 'Other Income'),
        ('expense', 'Expenses'),
        ('expense_depreciation', 'Depreciation'),
        ('expense_direct_cost', 'Cost of Goods Sold'),
        ('off_balance', 'Off-Balance Sheet')
    ], string='Account Type', required=True, tracking=True, default='asset_current')

    statement = fields.Selection([
        ('bs', 'Balance Sheet'),
        ('pl', 'Profit and Loss'),
        ('oci', 'Other Comprehensive Income (OCI)'),
        ('equity', 'Statement of Changes in Equity'),
        ('cf_memo', 'Cash Flow Memo')
    ], string='Financial Statement', required=True, tracking=True, default='bs')

    translation_rate = fields.Selection([
        ('closing', 'Closing Rate'),
        ('average', 'Average Rate'),
        ('historical', 'Historical Rate')
    ], string='Translation Rate', required=True, default='closing',
       help="Exchange rate used to translate functional currency to presentation currency (IAS 21).")

    is_intercompany = fields.Boolean(
        string='Intercompany Account',
        default=False,
        tracking=True,
        help="Check if this account must be reconciled and eliminated in intragroup transactions.")

    ic_counterpart_id = fields.Many2one(
        'consol.account',
        string='Intercompany Counterpart Account',
        help="Matching counterpart account in related entity (e.g. IC Receivable matches IC Payable).")

    parent_id = fields.Many2one(
        'consol.account',
        string='Parent Account',
        index=True,
        ondelete='restrict')

    child_ids = fields.One2many(
        'consol.account',
        'parent_id',
        string='Sub-Accounts')

    active = fields.Boolean(string='Active', default=True)
    note = fields.Text(string='Notes / Description')

    _sql_constraints = [
        ('code_unique', 'unique(code)', 'Consolidation account code must be unique!')
    ]

    @api.depends('code', 'name')
    def _compute_display_name(self):
        for rec in self:
            rec.display_name = f"[{rec.code}] {rec.name}" if rec.code else rec.name

    @api.constrains('parent_id')
    def _check_parent_recursion(self):
        if not self._check_recursion():
            raise ValidationError(_('Circular account hierarchy detected for account %s!', self.display_name))

    @api.model
    def action_open_import_company_coa_wizard(self):
        return {
            'name': _('Import Master CoA from Company & Auto-Map'),
            'type': 'ir.actions.act_window',
            'res_model': 'consol.import.company.coa.wizard',
            'view_mode': 'form',
            'target': 'new',
        }
