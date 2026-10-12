from odoo import models, fields, api

class ConsolidationEliminationEntry(models.Model):
    _name = 'consolidation.elimination.entry'
    _description = 'Consolidation Elimination Entry'

    name = fields.Char(string='Entry Number', required=True, copy=False, readonly=True, default='New')
    period_id = fields.Many2one('consolidation.period', string='Period', required=True, ondelete='cascade')
    group_id = fields.Many2one('consolidation.group', related='period_id.group_id', store=True)
    type = fields.Selection([
        ('investment_equity', 'Investasi vs Ekuitas'),
        ('nci_allocation', 'Alokasi NCI'),
        ('intercompany_ar_ap', 'Intercompany AR/AP'),
        ('intercompany_rev_exp', 'Intercompany Rev/Exp'),
        ('other', 'Other')
    ], string='Type', required=True)
    state = fields.Selection([('draft', 'Draft'), ('posted', 'Posted')], string='Status', default='draft')
    line_ids = fields.One2many('consolidation.elimination.line', 'entry_id', string='Lines')
    currency_id = fields.Many2one('res.currency', related='group_id.consolidation_currency_id', store=True)

    @api.model
    def create(self, vals):
        if vals.get('name', 'New') == 'New':
            vals['name'] = self.env['ir.sequence'].next_by_code('consolidation.elimination') or 'New'
        return super(ConsolidationEliminationEntry, self).create(vals)

class ConsolidationEliminationLine(models.Model):
    _name = 'consolidation.elimination.line'
    _description = 'Consolidation Elimination Line'

    entry_id = fields.Many2one('consolidation.elimination.entry', string='Entry', required=True, ondelete='cascade')
    account_id = fields.Many2one('consolidation.coa.master', string='Consolidation Account', required=True)
    partner_id = fields.Many2one('res.partner', string='Partner')
    name = fields.Char(string='Description')
    debit = fields.Monetary(string='Debit', currency_field='currency_id', default=0.0)
    credit = fields.Monetary(string='Credit', currency_field='currency_id', default=0.0)
    currency_id = fields.Many2one('res.currency', related='entry_id.currency_id', store=True)
