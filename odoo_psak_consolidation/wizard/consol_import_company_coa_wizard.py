# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import UserError

class ConsolImportCompanyCoaWizard(models.TransientModel):
    _name = 'consol.import.company.coa.wizard'
    _description = 'Import Company Chart of Accounts & Auto-Map Wizard'

    company_id = fields.Many2one(
        'res.company',
        string='Select Source Company CoA',
        required=True,
        default=lambda self: self.env.company,
        help="The Chart of Accounts from this company will be copied to Consolidation Accounts.")

    auto_map_entities = fields.Boolean(
        string='Auto-Map to All Odoo Entities',
        default=True,
        help="If checked, consolidation accounts will be automatically mapped to all entities sharing the same account codes.")

    update_existing = fields.Boolean(
        string='Update Existing Consolidation Accounts',
        default=True,
        help="Update name, type, and statement classification if account code already exists.")

    def action_import_and_map(self):
        self.ensure_one()
        company = self.company_id
        accounts = self.env['account.account'].with_company(company).search([('company_ids', 'in', company.id)])
        if not accounts:
            raise UserError(_("No accounts found for company %s!", company.name))

        ConsolAccount = self.env['consol.account']
        ConsolMapping = self.env['consol.account.mapping']

        type_map = {
            'asset_receivable': 'asset_receivable',
            'asset_cash': 'asset_cash',
            'asset_current': 'asset_current',
            'asset_non_current': 'asset_non_current',
            'asset_prepayments': 'asset_prepayments',
            'asset_fixed': 'asset_fixed',
            'liability_payable': 'liability_payable',
            'liability_credit_card': 'liability_credit_card',
            'liability_current': 'liability_current',
            'liability_non_current': 'liability_non_current',
            'equity': 'equity',
            'equity_unaffected': 'equity_unaffected',
            'income': 'income',
            'income_other': 'income_other',
            'expense': 'expense',
            'expense_depreciation': 'expense_depreciation',
            'expense_direct_cost': 'expense_direct_cost',
            'off_balance': 'off_balance',
        }

        created_acc_count = 0
        updated_acc_count = 0

        code_to_consol = {}
        for ca in ConsolAccount.search([]):
            code_to_consol[ca.code] = ca

        for acc in accounts:
            code = (acc.code or '').strip()
            if not code:
                continue

            acc_type = type_map.get(acc.account_type, 'asset_current')

            # Financial statement classification (BS / Equity / PL)
            if acc_type.startswith('asset_') or acc_type.startswith('liability_'):
                statement = 'bs'
                translation = 'closing'
            elif acc_type in ['equity', 'equity_unaffected']:
                statement = 'equity'
                translation = 'historical'
            elif acc_type in ['income', 'income_other', 'expense', 'expense_depreciation', 'expense_direct_cost']:
                statement = 'pl'
                translation = 'average'
            else:
                statement = 'bs'
                translation = 'closing'

            # Auto-detect intercompany accounts
            name_lower = (acc.name or '').lower()
            is_ic = (
                code in ['11210090', '21100090', '41000090', '51000090'] or
                'intragrup' in name_lower or
                'intercompany' in name_lower or
                'ic ' in name_lower or
                'antar perusahaan' in name_lower
            )

            existing_ca = code_to_consol.get(code)
            if existing_ca:
                if self.update_existing:
                    existing_ca.write({
                        'name': acc.name,
                        'account_type': acc_type,
                        'statement': statement,
                        'translation_rate': translation,
                        'is_intercompany': is_ic if is_ic else existing_ca.is_intercompany,
                    })
                    updated_acc_count += 1
            else:
                new_ca = ConsolAccount.create({
                    'code': code,
                    'name': acc.name,
                    'account_type': acc_type,
                    'statement': statement,
                    'translation_rate': translation,
                    'is_intercompany': is_ic,
                })
                code_to_consol[code] = new_ca
                created_acc_count += 1

            existing_ca = code_to_consol.get(code)

        acc_ar_ic = code_to_consol.get('11210090')
        acc_ap_ic = code_to_consol.get('21100090')
        if acc_ar_ic and acc_ap_ic:
            acc_ar_ic.ic_counterpart_id = acc_ap_ic.id
            acc_ap_ic.ic_counterpart_id = acc_ar_ic.id

        acc_rev_ic = code_to_consol.get('41000090')
        acc_cogs_ic = code_to_consol.get('51000090')
        if acc_rev_ic and acc_cogs_ic:
            acc_rev_ic.ic_counterpart_id = acc_cogs_ic.id
            acc_cogs_ic.ic_counterpart_id = acc_rev_ic.id

        # 2. Auto-map to all Odoo entities
        total_mapped = 0
        if self.auto_map_entities:
            entities = self.env['consol.entity'].search([
                ('source_type', '=', 'odoo'),
                ('company_id', '!=', False)
            ])
            for entity in entities:
                ent_company = entity.company_id
                ent_accounts = self.env['account.account'].with_company(ent_company).search([('company_ids', 'in', ent_company.id)])
                for acc in ent_accounts:
                    code = (acc.code or '').strip()
                    consol_acc = code_to_consol.get(code)
                    if not consol_acc:
                        continue

                    existing_map = ConsolMapping.search([
                        ('entity_id', '=', entity.id),
                        ('account_id', '=', acc.id)
                    ], limit=1)
                    if not existing_map:
                        ConsolMapping.create({
                            'entity_id': entity.id,
                            'account_id': acc.id,
                            'consol_account_id': consol_acc.id,
                        })
                        total_mapped += 1

        # Automatically synchronize and wire imported accounts to Report Templates
        self.env['consol.report'].sync_all_reports_accounts()

        msg = _(
            "Successfully imported Chart of Accounts from %(company)s!\n"
            "- New Consolidation Accounts: %(created)d\n"
            "- Updated Consolidation Accounts: %(updated)d\n"
            "- Total Entity Account Mappings Created: %(mapped)d",
            company=company.name,
            created=created_acc_count,
            updated=updated_acc_count,
            mapped=total_mapped
        )

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('CoA Import & Mapping Succeeded'),
                'message': msg,
                'sticky': False,
                'type': 'success',
                'next': {'type': 'ir.actions.act_window_close'},
            }
        }
