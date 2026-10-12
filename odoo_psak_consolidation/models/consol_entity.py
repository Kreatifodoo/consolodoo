# -*- coding: utf-8 -*-
from odoo import models, fields, api, _

class ConsolEntity(models.Model):
    _name = 'consol.entity'
    _description = 'Consolidation Group Member Entity'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'code, name'

    name = fields.Char(string='Entity Name', required=True, tracking=True)
    code = fields.Char(string='Entity Code', required=True, size=15, tracking=True,
                       help="Short code used as column header in consolidation worksheets.")
    
    company_id = fields.Many2one(
        'res.company',
        string='Odoo Company (Internal)',
        help="Link to local Odoo company if this entity exists in this database. Leave empty for external entities.")

    source_type = fields.Selection([
        ('odoo', 'Odoo Database'),
        ('import', 'External Import (CSV/XLSX)')
    ], string='Data Source', default='odoo', required=True, tracking=True)

    functional_currency_id = fields.Many2one(
        'res.currency',
        string='Functional Currency (IAS 21)',
        required=True,
        default=lambda self: self.env.company.currency_id,
        tracking=True,
        help="Currency of the primary economic environment in which the entity operates.")

    group_ids = fields.Many2many(
        'consol.group',
        'consol_group_entity_rel',
        'entity_id',
        'group_id',
        string='Consolidation Groups')

    partner_id = fields.Many2one(
        'res.partner',
        string='Entity Partner Representation',
        help="Contact/Partner representing this entity in books of other entities for intragroup matching.")

    is_investment_entity = fields.Boolean(
        string='Investment Entity (IFRS 10 par. 31)',
        default=False,
        tracking=True,
        help="If checked, entity is exempt from consolidation and measured at fair value through profit or loss.")

    parent_ownership_ids = fields.One2many(
        'consol.ownership',
        'child_id',
        string='Ownership Structure (Owned By)')

    child_ownership_ids = fields.One2many(
        'consol.ownership',
        'parent_id',
        string='Investments in Other Entities (Owns)')

    active = fields.Boolean(string='Active', default=True)
    note = fields.Text(string='Additional Notes')

    _sql_constraints = [
        ('code_unique', 'unique(code)', 'Entity code must be unique!')
    ]

    @api.onchange('company_id')
    def _onchange_company_id(self):
        if self.company_id:
            self.functional_currency_id = self.company_id.currency_id
            if not self.name:
                self.name = self.company_id.name
            if not self.partner_id:
                self.partner_id = self.company_id.partner_id

    @api.depends('code', 'name')
    def _compute_display_name(self):
        for rec in self:
            rec.display_name = f"[{rec.code}] {rec.name}" if rec.code else rec.name
