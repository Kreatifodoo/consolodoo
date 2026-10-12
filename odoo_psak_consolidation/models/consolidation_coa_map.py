from odoo import models, fields, api

class ConsolidationCoaMap(models.Model):
    _name = 'consolidation.coa.map'
    _description = 'Consolidation COA Map'

    parent_company_id = fields.Many2one('res.company', string='Parent Company', required=True, default=lambda self: self.env.company)
    group_account_id = fields.Many2one('consolidation.coa.master', string='Group Account', required=True, domain="[('company_id', '=', parent_company_id)]")
    group_account_code = fields.Char(related='group_account_id.code', string='Group Account Code', store=True)
    group_account_name = fields.Char(related='group_account_id.name', string='Group Account Name', store=True)
    subsidiary_company_ids = fields.Many2many('res.company', string='Mapped Companies (Incl. Parent)', required=True)
    subsidiary_account_ids = fields.Many2many('account.account', string='Mapped Accounts', required=True, domain="[('company_ids', 'in', subsidiary_company_ids), ('id', 'not in', mapped_account_ids)]")
    report_type_ids = fields.Many2many('consolidation.report.type', string='Report Types')

    mapped_account_ids = fields.Many2many('account.account', compute='_compute_mapped_accounts', store=False)

    @api.depends('parent_company_id')
    def _compute_mapped_accounts(self):
        for rec in self:
            all_maps = self.env['consolidation.coa.map'].search([])
            if rec.id:
                all_maps = all_maps - rec
            rec.mapped_account_ids = all_maps.mapped('subsidiary_account_ids')

    from odoo.exceptions import ValidationError
    @api.constrains('subsidiary_account_ids')
    def _check_unique_mapping(self):
        for rec in self:
            all_maps = self.env['consolidation.coa.map'].search([('id', '!=', rec.id)])
            mapped_accounts = all_maps.mapped('subsidiary_account_ids')
            overlap = rec.subsidiary_account_ids & mapped_accounts
            if overlap:
                account_names = ', '.join(overlap.mapped('display_name'))
                raise ValidationError(f"The following accounts are already mapped to another Master COA: {account_names}. \nJika coa sudah di mapping tidak bisa di mapping ke coa yg lain.")
