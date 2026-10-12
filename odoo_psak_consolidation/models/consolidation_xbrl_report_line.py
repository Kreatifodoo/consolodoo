from odoo import models, fields, api

class ConsolidationXbrlReportLine(models.Model):
    _name = 'consolidation.xbrl.report.line'
    _description = 'Consolidation Financial Report Mapping Line'
    _order = 'sequence, id'

    name = fields.Char(string='Name', required=True, translate=True)
    code = fields.Char(string='Code', help='XBRL taxonomy code')
    sequence = fields.Integer(string='Sequence', default=10)
    
    report_id = fields.Many2one('consolidation.xbrl.report', string='Report', required=True, ondelete='cascade', index=True)
    
    parent_id = fields.Many2one('consolidation.xbrl.report.line', string='Parent Line', index=True, ondelete='cascade')
    child_ids = fields.One2many('consolidation.xbrl.report.line', 'parent_id', string='Child Lines')
    
    report_type = fields.Selection([
        ('BS', 'Balance Sheet'),
        ('PL', 'Profit & Loss'),
        ('CF', 'Cash Flow')
    ], string='Report Type', required=True)
    
    master_coa_ids = fields.Many2many(
        'consolidation.coa.master',
        string='Master COA Mapping'
    )
    
    sign = fields.Selection([
        ('1', 'Positive (1)'),
        ('-1', 'Negative (-1)')
    ], string='Sign', default='1', required=True)
    
    is_elimination_target = fields.Boolean(string='Elimination Target', help='Flag for intercompany elimination')
