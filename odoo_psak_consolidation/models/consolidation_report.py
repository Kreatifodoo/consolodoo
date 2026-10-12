from odoo import models, fields, api

class ConsolidationReport(models.Model):
    _name = 'consolidation.report'
    _description = 'Consolidation Financial Report Configuration'

    name = fields.Char(string='Report Name', required=True)
    active = fields.Boolean(string='Active', default=True)
    line_ids = fields.One2many('consolidation.report.line', 'report_id', string='Report Lines')
