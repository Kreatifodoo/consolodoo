from odoo import models, fields, api

class ConsolidationCoaMaster(models.Model):
    _name = 'consolidation.coa.master'
    _description = 'Consolidation Master COA'
    _parent_store = True
    _parent_name = "parent_id"

    parent_path = fields.Char(index=True, unaccent=False)
    parent_id = fields.Many2one('consolidation.coa.master', string='Parent Account', index=True, ondelete='cascade', domain="[('company_id', '=', company_id)]")
    child_ids = fields.One2many('consolidation.coa.master', 'parent_id', string='Child Accounts')
    is_group = fields.Boolean(string='Is Group', default=False, help='Check if this is a header/group account that cannot be directly mapped to transactions.')

    code = fields.Char(string='Account Code', required=True)
    name = fields.Char(string='Account Name', required=True)
    name_en = fields.Char(string='English Account Name')
    
    @api.onchange('name')
    def _onchange_name_translate(self):
        for rec in self:
            if rec.name and not rec.name_en:
                try:
                    import requests
                    from urllib.parse import quote
                    encoded_text = quote(rec.name)
                    url = f"https://translate.googleapis.com/translate_a/single?client=gtx&sl=id&tl=en&dt=t&q={encoded_text}"
                    response = requests.get(url, timeout=5)
                    if response.status_code == 200:
                        data = response.json()
                        translated_text = data[0][0][0]
                        rec.name_en = translated_text
                except Exception as e:
                    import logging
                    logging.getLogger(__name__).warning(f"Auto-translate failed: {e}")
    report_section = fields.Selection([
        ('is', 'Laba Rugi (Income Statement)'),
        ('re', 'Saldo Laba (Retained Earnings)'),
        ('bs', 'Neraca (Balance Sheet)')
    ], string='Report Section', default='is', required=True)

    @api.onchange('code')
    def _onchange_code(self):
        for rec in self:
            if rec.code:
                first_digit = rec.code[0]
                # Report Section logic
                if first_digit in ['1', '2', '3']:
                    rec.report_section = 'bs'
                elif first_digit in ['4', '5', '6', '7', '8', '9']:
                    rec.report_section = 'is'
                
                # Normal Balance logic
                if first_digit in ['1', '5', '8']:
                    rec.normal_balance = 'debit'
                elif first_digit in ['2', '3', '4', '7']:
                    rec.normal_balance = 'credit'

    sequence = fields.Integer(string='Sequence', default=10)
    normal_balance = fields.Selection([
        ('debit', 'Debit'),
        ('credit', 'Credit')
    ], string='Normal Balance', default='debit', required=True)
    company_id = fields.Many2one('res.company', string='Owner Company', required=True, default=lambda self: self.env.company)
    is_intercompany_elimination = fields.Boolean(string='Intercompany Elimination', default=False, help="If true, this account will be automatically eliminated in consolidation rules.")
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
        ('expense_direct_cost', 'Cost of Revenue'),
        ('off_balance', 'Off-Balance Sheet'),
    ], string='Type', required=True, default='asset_current')
    currency_id = fields.Many2one('res.currency', string='Account Currency')
    
    _code_company_uniq = models.Constraint(
        'unique (code, company_id)',
        'The code of the account must be unique per company!',
    )

    @api.depends('code', 'name')
    def _compute_display_name(self):
        for rec in self:
            rec.display_name = f"[{rec.code}] {rec.name}" if rec.code and rec.name else rec.name or ""
