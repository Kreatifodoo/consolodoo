from odoo import models, fields, api

class ConsolidationReportLine(models.Model):
    _name = 'consolidation.report.line'
    _description = 'Consolidation Financial Report Line'
    _order = 'sequence'

    name = fields.Char(string='Name', required=True)
    code = fields.Char(string='Code', help='Unique code used for formulas (e.g., REV, COGS)')
    sequence = fields.Integer(string='Sequence', default=10)
    report_id = fields.Many2one('consolidation.report', string='Report', required=True, ondelete='cascade')
    
    line_type = fields.Selection([
        ('view', 'View / Title'),
        ('accounts', 'Accounts'),
        ('formula', 'Formula'),
        ('nci_income', 'NCI Income Allocation (Memo)')
    ], string='Line Type', required=True, default='accounts')
    
    formula = fields.Char(string='Formula', help='E.g., REV - COGS + OTH. Use the codes of other lines.')
    
    account_ids = fields.Many2many(
        'consolidation.coa.master',
        string='Master COA Accounts',
        help='Select Master COA accounts to pull amounts from.'
    )
    
    sign = fields.Selection([
        ('1', '+ (Normal / Positif)'),
        ('-1', '- (Reverse / Negatif)')
    ], string='Sign', default='1', required=True)
