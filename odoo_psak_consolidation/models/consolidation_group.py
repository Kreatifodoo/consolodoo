from odoo import models, fields, api

class ConsolidationGroup(models.Model):
    _name = 'consolidation.group'
    _description = 'Consolidation Group'

    name = fields.Char(string='Name', required=True)
    parent_company_id = fields.Many2one('res.company', string='Parent Company', required=True)
    consolidation_currency_id = fields.Many2one('res.currency', string='Consolidation Currency', required=True)
    nci_equity_account_id = fields.Many2one(
        'consolidation.coa.master',
        string="Akun NCI - Neraca",
        domain="[('account_type', '=', 'equity'), ('company_id', '=', parent_company_id)]",
        help="Akun equity di COA konsolidasi tempat saldo NCI (Neraca) diposting setiap periode."
    )
    company_ids = fields.One2many('consolidation.group.company', 'group_id', string='Subsidiaries')

class ConsolidationGroupCompany(models.Model):
    _name = 'consolidation.group.company'
    _description = 'Consolidation Group Company'

    group_id = fields.Many2one('consolidation.group', string='Group', required=True, ondelete='cascade')
    company_id = fields.Many2one('res.company', string='Subsidiary Company', required=True)
    ownership_percentage = fields.Float(string='Ownership (%)', required=True)
    nci_percentage = fields.Float(string='NCI (%)', compute='_compute_nci_percentage', store=True)
    consolidation_method = fields.Selection([
        ('full', 'Full Consolidation'),
        ('equity', 'Equity Method')
    ], string='Method', required=True, default='full')
    equity_account_id = fields.Many2one('consolidation.coa.master', string='Equity Account (Master)', help="Master account for subsidiary's equity")
    investment_account_id = fields.Many2one('consolidation.coa.master', string='Investment Account (Master)', help="Master account for parent's investment in this subsidiary")

    currency_id = fields.Many2one('res.currency', related='group_id.consolidation_currency_id', store=True)
    acquisition_date = fields.Date(string='Acquisition Date', required=True, default=fields.Date.context_today)
    equity_at_acquisition = fields.Monetary(string='Equity at Acquisition', currency_field='currency_id')
    investment_cost = fields.Monetary(string='Investment Cost', currency_field='currency_id')
    goodwill = fields.Monetary(string='Goodwill', compute='_compute_goodwill', store=True, currency_field='currency_id')
    nci_at_acquisition = fields.Monetary(string='NCI at Acquisition', compute='_compute_nci_at_acquisition', store=True, currency_field='currency_id')

    @api.depends('ownership_percentage')
    def _compute_nci_percentage(self):
        for rec in self:
            rec.nci_percentage = 100.0 - rec.ownership_percentage

    @api.depends('investment_cost', 'ownership_percentage', 'equity_at_acquisition')
    def _compute_goodwill(self):
        for rec in self:
            rec.goodwill = rec.investment_cost - ((rec.ownership_percentage / 100.0) * rec.equity_at_acquisition)

    @api.depends('nci_percentage', 'equity_at_acquisition')
    def _compute_nci_at_acquisition(self):
        for rec in self:
            rec.nci_at_acquisition = (rec.nci_percentage / 100.0) * rec.equity_at_acquisition
