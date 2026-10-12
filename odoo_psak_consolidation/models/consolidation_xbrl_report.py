from odoo import models, fields

class ConsolidationXbrlReport(models.Model):
    _name = 'consolidation.xbrl.report'
    _description = 'Consolidation XBRL Report Mapping Header'

    name = fields.Char(string='Report Name', required=True, translate=True, help="e.g., Balance Sheet 2026")
    code = fields.Char(string='Report Code', required=True)
    description = fields.Text(string='Description')
    
    line_ids = fields.One2many('consolidation.xbrl.report.line', 'report_id', string='Report Lines')
    company_id = fields.Many2one('res.company', string='Company', default=lambda self: self.env.company)
