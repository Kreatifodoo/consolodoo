from odoo import models, fields

class ConsolidationRule(models.Model):
    _name = 'consolidation.rule'
    _description = 'Consolidation Elimination Rule'

    name = fields.Char(string='Name', required=True)
    rule_type = fields.Selection([
        ('equity', 'Equity'),
        ('intercompany_arap', 'Intercompany AR/AP'),
        ('intercompany_pl', 'Intercompany P&L'),
        ('unrealized_profit', 'Unrealized Profit')
    ], string='Rule Type', required=True)
    partner_match_type = fields.Selection([
        ('auto', 'Auto-Match by Company Partner'),
        ('manual', 'Manual Partner Mapping')
    ], string='Matching Type', default='auto')
