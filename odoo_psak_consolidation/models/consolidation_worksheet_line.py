from odoo import models, fields, api

class ConsolidationWorksheetLine(models.Model):
    _name = 'consolidation.worksheet.line'
    _description = 'Consolidation Worksheet Line'
    _order = 'report_section, sequence'

    period_id = fields.Many2one('consolidation.period', string='Period', required=True, ondelete='cascade')
    account_id = fields.Many2one('consolidation.coa.master', string='Consolidated Account', required=True)
    report_section = fields.Selection(related='account_id.report_section', store=True)
    sequence = fields.Integer(related='account_id.sequence', store=True)
    
    parent_balance = fields.Float(string='Parent Balance', default=0.0)
    subsidiary_balance = fields.Float(string='Subsidiary Balance', default=0.0)
    
    elimination_debit = fields.Float(string='Elimination Debit', default=0.0)
    elimination_credit = fields.Float(string='Elimination Credit', default=0.0)
    
    consolidated_balance = fields.Float(string='Consolidated Balance', compute='_compute_consol_balance', store=True)
    
    @api.depends('parent_balance', 'subsidiary_balance', 'elimination_debit', 'elimination_credit', 'account_id.normal_balance')
    def _compute_consol_balance(self):
        for line in self:
            normal = line.account_id.normal_balance
            base_balance = line.parent_balance + line.subsidiary_balance
            
            if normal == 'debit':
                line.consolidated_balance = base_balance + line.elimination_debit - line.elimination_credit
            else:
                line.consolidated_balance = base_balance - line.elimination_debit + line.elimination_credit
