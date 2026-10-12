from odoo import models, fields, api

class ConsolidationWPExport(models.TransientModel):
    _name = 'consolidation.wp.export'
    _description = 'Working Paper Export Wizard'

    period_id = fields.Many2one('consolidation.period', string='Consolidation Period', required=True)

    def action_export_excel(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_url',
            'url': f'/consolidation/export_wp_excel?period_id={self.period_id.id}',
            'target': 'self',
        }
