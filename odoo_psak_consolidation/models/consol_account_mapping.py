# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError

class ConsolAccountMapping(models.Model):
    _name = 'consol.account.mapping'
    _description = 'Entity to Consolidation Account Mapping'
    _inherit = ['mail.thread']
    _order = 'entity_id, consol_account_id'

    entity_id = fields.Many2one(
        'consol.entity',
        string='Entity',
        required=True,
        ondelete='cascade',
        tracking=True)

    account_id = fields.Many2one(
        'account.account',
        string='Source Account (Odoo)',
        ondelete='cascade',
        tracking=True,
        help="Account in local Odoo Chart of Accounts.")

    external_code = fields.Char(
        string='External Account Code (Import)',
        tracking=True,
        help="Account code from external entity imported via CSV/XLSX.")

    external_name = fields.Char(
        string='External Account Name',
        help="Original account name from external entity.")

    consol_account_id = fields.Many2one(
        'consol.account',
        string='Consolidation Account (Target)',
        required=True,
        ondelete='restrict',
        tracking=True,
        help="Target consolidation account where balance will be mapped.")

    source_account_code = fields.Char(
        string='Source Account Code',
        compute='_compute_source_account_info',
        store=True)

    source_account_name = fields.Char(
        string='Source Account Name',
        compute='_compute_source_account_info',
        store=True)

    _sql_constraints = [
        ('entity_account_unique', 'unique(entity_id, account_id)', 'Account mapping for this entity and Odoo account already exists!'),
    ]

    @api.depends('account_id', 'external_code', 'external_name')
    def _compute_source_account_info(self):
        for rec in self:
            if rec.account_id:
                rec.source_account_code = rec.account_id.code
                rec.source_account_name = rec.account_id.name
            else:
                rec.source_account_code = rec.external_code or ''
                rec.source_account_name = rec.external_name or ''

    @api.constrains('account_id', 'external_code')
    def _check_source_account(self):
        for rec in self:
            if not rec.account_id and not rec.external_code:
                raise ValidationError(_("Must specify either Source Odoo Account or External Account Code!"))

    @api.model
    def auto_map_accounts(self, entity_id):
        """
        Automatically match source Odoo accounts to consolidation accounts
        based on exact code match or prefix match.
        """
        entity = self.env['consol.entity'].browse(entity_id)
        if not entity.exists():
            raise UserError(_("Entity not found!"))

        if entity.source_type == 'odoo':
            accounts = self.env['account.account'].search([])
            consol_accounts = self.env['consol.account'].search([])
            consol_acc_by_code = {ca.code: ca for ca in consol_accounts}

            created_count = 0
            for acc in accounts:
                existing = self.search([('entity_id', '=', entity.id), ('account_id', '=', acc.id)], limit=1)
                if existing:
                    continue

                matched_consol = consol_acc_by_code.get(acc.code)
                if not matched_consol:
                    # Coba cari berdasarkan awalan kode
                    for c_code, ca in consol_acc_by_code.items():
                        if acc.code.startswith(c_code) or c_code.startswith(acc.code):
                            matched_consol = ca
                            break

                if matched_consol:
                    self.create({
                        'entity_id': entity.id,
                        'account_id': acc.id,
                        'consol_account_id': matched_consol.id,
                    })
                    created_count += 1
            return created_count
        return 0
