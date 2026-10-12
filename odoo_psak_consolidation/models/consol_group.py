# -*- coding: utf-8 -*-
from odoo import models, fields, api, _

class ConsolGroup(models.Model):
    _name = 'consol.group'
    _description = 'Financial Consolidation Group'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char(string='Consolidation Group Name', required=True, tracking=True)
    
    parent_company_id = fields.Many2one(
        'res.company',
        string='Ultimate Parent Company',
        required=True,
        default=lambda self: self.env.company,
        tracking=True,
        help="Odoo company acting as the ultimate parent in this consolidation group (e.g. Indonesia Ho).")

    parent_entity_id = fields.Many2one(
        'consol.entity',
        string='Parent Consolidation Entity',
        compute='_compute_parent_entity_id',
        store=True,
        readonly=False,
        tracking=True,
        help="Consolidation entity representing the ultimate parent.")

    currency_id = fields.Many2one(
        'res.currency',
        string='Reporting Currency',
        required=True,
        default=lambda self: self.env.ref('base.IDR', raise_if_not_found=False) or self.env.company.currency_id,
        tracking=True,
        help="Presentation currency for consolidated financial statements (Reporting Currency - RC).")

    chart_template_id = fields.Many2one(
        'consol.account',
        string='Consolidation Chart of Accounts (Root)',
        help="Root account for the consolidation chart of accounts hierarchy.")

    fiscal_year_start = fields.Selection([
        ('1', 'January'), ('2', 'February'), ('3', 'March'), ('4', 'April'),
        ('5', 'May'), ('6', 'June'), ('7', 'July'), ('8', 'August'),
        ('9', 'September'), ('10', 'October'), ('11', 'November'), ('12', 'December')
    ], string='Fiscal Year Start', default='1', required=True)

    rounding = fields.Float(
        string='Report Rounding Factor',
        default=1.0,
        help="Factor to divide report figures: 1 (Full Units), 1,000 (Thousands), 1,000,000 (Millions).")

    cta_account_id = fields.Many2one(
        'consol.account',
        string='OCI CTA Account (Cumulative Translation Adjustment)',
        domain="[('statement', 'in', ['oci', 'equity'])]",
        tracking=True,
        help="Account for Cumulative Translation Adjustment under IAS 21.")

    nci_equity_account_id = fields.Many2one(
        'consol.account',
        string='NCI Equity Account',
        domain="[('statement', '=', 'equity')]",
        tracking=True,
        help="Account for Non-Controlling Interest in consolidated equity (IFRS 10 par. 22).")

    nci_pl_account_id = fields.Many2one(
        'consol.account',
        string='Profit/Loss Attributable to NCI Account',
        domain="[('statement', '=', 'pl')]",
        tracking=True,
        help="Account for current period profit or loss attributable to NCI (IFRS 10 par. B94).")

    goodwill_account_id = fields.Many2one(
        'consol.account',
        string='Consolidation Goodwill Account',
        domain="[('statement', '=', 'bs')]",
        tracking=True,
        help="Account for goodwill arising from business combinations (IFRS 3).")

    retained_earnings_account_id = fields.Many2one(
        'consol.account',
        string='Consolidated Retained Earnings Account',
        domain="[('statement', '=', 'equity')]",
        tracking=True,
        help="Account for consolidated accumulated retained earnings.")

    ic_tolerance = fields.Monetary(
        string='Intercompany Difference Tolerance',
        currency_field='currency_id',
        default=0.0,
        tracking=True,
        help="Maximum permitted discrepancy before a period can be locked.")

    parent_group_id = fields.Many2one(
        'consol.group',
        string='Parent Group (if Sub-Group)',
        ondelete='restrict')

    sub_group_ids = fields.One2many(
        'consol.group',
        'parent_group_id',
        string='Multi-Tier Sub-Groups')

    entity_ids = fields.Many2many(
        'consol.entity',
        'consol_group_entity_rel',
        'group_id',
        'entity_id',
        string='Member Entities',
        tracking=True)

    period_ids = fields.One2many(
        'consol.period',
        'group_id',
        string='Consolidation Periods')

    active = fields.Boolean(default=True)
    note = fields.Text(string='Description / Consolidation Policy')

    @api.depends('parent_company_id')
    def _compute_parent_entity_id(self):
        for rec in self:
            if rec.parent_company_id:
                entity = self.env['consol.entity'].search([
                    ('company_id', '=', rec.parent_company_id.id)
                ], limit=1)
                if not entity:
                    entity = self.env['consol.entity'].search([
                        ('name', '=', rec.parent_company_id.name)
                    ], limit=1)
                    if entity:
                        if not entity.company_id:
                            entity.write({'company_id': rec.parent_company_id.id, 'source_type': 'odoo'})
                    else:
                        code = (rec.parent_company_id.code or rec.parent_company_id.name[:10]).strip().upper().replace(' ', '_')
                        entity = self.env['consol.entity'].create({
                            'name': rec.parent_company_id.name,
                            'code': code or 'PARENT',
                            'company_id': rec.parent_company_id.id,
                            'source_type': 'odoo',
                            'functional_currency_id': rec.parent_company_id.currency_id.id,
                            'partner_id': rec.parent_company_id.partner_id.id if rec.parent_company_id.partner_id else False,
                        })
                rec.parent_entity_id = entity.id
                if entity and entity not in rec.entity_ids:
                    rec.entity_ids = [(4, entity.id)]

    @api.onchange('parent_company_id')
    def _onchange_parent_company_id(self):
        if self.parent_company_id:
            if not self.name or self.name == 'Grup Konsolidasi Baru':
                self.name = f"{self.parent_company_id.name} Group"
            if self.parent_company_id.currency_id:
                self.currency_id = self.parent_company_id.currency_id.id

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get('parent_company_id') and vals.get('parent_entity_id'):
                entity = self.env['consol.entity'].browse(vals['parent_entity_id'])
                if entity.company_id:
                    vals['parent_company_id'] = entity.company_id.id
                else:
                    vals['parent_company_id'] = self.env.company.id
            elif vals.get('parent_company_id') and not vals.get('currency_id'):
                comp = self.env['res.company'].browse(vals['parent_company_id'])
                if comp.currency_id:
                    vals['currency_id'] = comp.currency_id.id
        return super().create(vals_list)
