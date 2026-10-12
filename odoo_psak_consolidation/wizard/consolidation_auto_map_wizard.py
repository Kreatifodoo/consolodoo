from odoo import models, fields, api, _
from odoo.exceptions import UserError

class ConsolidationAutoMapWizard(models.TransientModel):
    _name = 'consolidation.auto.map.wizard'
    _description = 'Consolidation Auto Map Wizard'

    consolidation_group_id = fields.Many2one('consolidation.group', string='Consolidation Group', required=True)

    def action_auto_map(self):
        self.ensure_one()
        group = self.consolidation_group_id
        parent_company = group.parent_company_id
        subsidiaries = group.company_ids.mapped('company_id') | parent_company

        if not parent_company or not subsidiaries:
            raise UserError(_("The selected consolidation group must have a parent company and at least one subsidiary."))

        # 1. Get all Master COA in Parent Company
        master_coas = self.env['consolidation.coa.master'].search([('company_id', '=', parent_company.id)])
        
        # 2. Get all currently mapped accounts across the system to avoid mapping them again
        # since an account can only be mapped once according to requirement: "jika coa sudah di maaping tidak bisa di mapping ke coa yg lain"
        mapped_accounts = self.env['consolidation.coa.map'].search([]).mapped('subsidiary_account_ids')

        mapped_count = 0
        skipped_count = 0

        for master in master_coas:
            # Look for accounts in subsidiaries with exactly the same name
            matching_accounts = self.env['account.account'].search([
                ('company_ids', 'in', subsidiaries.ids),
                ('name', '=', master.name)
            ])

            accounts_to_map = matching_accounts - mapped_accounts

            if not accounts_to_map:
                continue
            
            # Check if map already exists for this group and this master COA
            existing_map = self.env['consolidation.coa.map'].search([
                ('parent_company_id', '=', parent_company.id),
                ('group_account_id', '=', master.id)
            ], limit=1)

            if existing_map:
                # Add unmapped accounts to the existing mapping
                existing_map.write({
                    'subsidiary_account_ids': [(4, acc.id) for acc in accounts_to_map]
                })
            else:
                # Create a new mapping
                self.env['consolidation.coa.map'].create({
                    'parent_company_id': parent_company.id,
                    'group_account_id': master.id,
                    'subsidiary_company_ids': [(6, 0, subsidiaries.ids)],
                    'subsidiary_account_ids': [(6, 0, accounts_to_map.ids)],
                })
            
            mapped_count += len(accounts_to_map)
            # Update the mapped_accounts cache so they won't be mapped again in the same loop
            mapped_accounts |= accounts_to_map

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Auto Mapping Complete'),
                'message': _('Successfully mapped %d new COA accounts.') % mapped_count,
                'sticky': False,
                'type': 'success',
            }
        }
