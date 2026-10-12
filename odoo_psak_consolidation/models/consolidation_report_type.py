from odoo import models, fields

class ConsolidationReportType(models.Model):
    _name = 'consolidation.report.type'
    _description = 'Consolidation Report Type'

    name = fields.Char(string='Report Type Name', required=True)
    code = fields.Char(string='Code', required=True)
