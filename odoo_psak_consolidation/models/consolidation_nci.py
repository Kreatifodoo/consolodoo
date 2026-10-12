from odoo import models, fields, api

class ConsolidationNci(models.Model):
    _name = 'consolidation.nci'
    _description = 'Consolidation NCI Tracking'

    member_id = fields.Many2one('consolidation.group.company', string='Subsidiary Member', required=True, ondelete='cascade')
    period_id = fields.Many2one('consolidation.period', string='Consolidation Period', required=True, ondelete='cascade')
    currency_id = fields.Many2one('res.currency', related='member_id.currency_id', store=True)
    
    opening_balance = fields.Monetary(string='Opening Balance', currency_field='currency_id')
    income_allocation = fields.Monetary(string='Income Allocation', currency_field='currency_id')
    closing_balance = fields.Monetary(string='Closing Balance', compute='_compute_closing', store=True, currency_field='currency_id')

    @api.depends('opening_balance', 'income_allocation')
    def _compute_closing(self):
        for rec in self:
            rec.closing_balance = rec.opening_balance + rec.income_allocation
