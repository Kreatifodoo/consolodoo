from odoo import models, fields, api, _

class ConsolidationCopyCoaWizard(models.TransientModel):
    _name = 'consolidation.copy.coa.wizard'
    _description = 'Wizard to Copy COA from a Company'

    source_company_id = fields.Many2one('res.company', string='Source Company', required=True, default=lambda self: self.env.company)

    def action_copy(self):
        self.ensure_one()
        company = self.source_company_id
        odoo_accounts = self.env['account.account'].search([('company_ids', 'in', company.id)])
        master_coas = self.env['consolidation.coa.master'].search([('company_id', '=', company.id)])
        existing_codes = master_coas.mapped('code')

        created_count = 0
        master_coa_env = self.env['consolidation.coa.master']
        code_to_master = {m.code: m for m in master_coas}

        # First pass: Create missing master COAs
        for acc in odoo_accounts:
            if acc.code not in existing_codes:
                new_master = master_coa_env.create({
                    'code': acc.code,
                    'name': acc.name,
                    'account_type': acc.account_type,
                    'company_id': company.id,
                })
                code_to_master[acc.code] = new_master
                existing_codes.append(acc.code)
                created_count += 1
        
        # Second pass: Link parent_ids based on account.account's parent
        for acc in odoo_accounts:
            if acc.parent_id and acc.code in code_to_master:
                parent_code = acc.parent_id.code
                if parent_code in code_to_master:
                    master_child = code_to_master[acc.code]
                    master_parent = code_to_master[parent_code]
                    if master_child.parent_id.id != master_parent.id:
                        master_child.parent_id = master_parent.id

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Copy COA Complete'),
                'message': _('Successfully copied %d COA from %s.') % (created_count, company.name),
                'sticky': False,
                'type': 'success',
            }
        }
