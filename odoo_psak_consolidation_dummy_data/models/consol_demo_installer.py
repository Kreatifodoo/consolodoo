# -*- coding: utf-8 -*-
import logging
from odoo import models, fields, api, _

_logger = logging.getLogger(__name__)

class ConsolDemoInstaller(models.AbstractModel):
    _name = 'consol.demo.installer'
    _description = 'PSAK 65 Consolidation Demo Data Installer & Generator'

    @api.model
    def install_demo_data(self):
        """
        Main entry point to create demo companies, accounts, transactions,
        consolidation setup, and 2-month consolidated financial periods.
        """
        _logger.info("=== STARTING PSAK 65 CONSOLIDATION DEMO DATA INSTALLATION ===")
        env = self.env

        # 1. SETUP CURRENCY & COMPANIES
        currency_idr = env.ref('base.IDR', raise_if_not_found=False) or env['res.currency'].search([('name', '=', 'IDR')], limit=1)
        if not currency_idr:
            currency_idr = env['res.currency'].create({
                'name': 'IDR',
                'symbol': 'Rp',
                'rounding': 1.0,
                'position': 'before',
                'currency_unit_label': 'Rupiah',
            })
        if not currency_idr.active:
            currency_idr.active = True

        country_id = env.ref('base.id', raise_if_not_found=False) or env['res.country'].search([('code', '=', 'ID')], limit=1)

        # A. Ultimate Parent: Indonesia Ho
        c_ho = env['res.company'].search([('name', '=', 'Indonesia Ho')], limit=1)
        if not c_ho:
            main_comp = env.ref('base.main_company', raise_if_not_found=False)
            if main_comp and main_comp.name in ['My Company', 'Indonesia Ho']:
                c_ho = main_comp
                c_ho.write({'name': 'Indonesia Ho', 'currency_id': currency_idr.id, 'country_id': country_id.id if country_id else False})
            else:
                c_ho = env['res.company'].create({
                    'name': 'Indonesia Ho',
                    'currency_id': currency_idr.id,
                    'country_id': country_id.id if country_id else False,
                })
        else:
            c_ho.write({'currency_id': currency_idr.id})

        # B. Subsidiary 1: Company 1 (100%)
        c_1 = env['res.company'].search([('name', '=', 'Company 1')], limit=1)
        if not c_1:
            c_1 = env['res.company'].create({
                'name': 'Company 1',
                'currency_id': currency_idr.id,
                'country_id': country_id.id if country_id else False,
            })
        else:
            c_1.write({'currency_id': currency_idr.id})

        # C. Subsidiary 2: Company 2 (80%)
        c_2 = env['res.company'].search([('name', '=', 'Company 2')], limit=1)
        if not c_2:
            c_2 = env['res.company'].create({
                'name': 'Company 2',
                'currency_id': currency_idr.id,
                'country_id': country_id.id if country_id else False,
            })
        else:
            c_2.write({'currency_id': currency_idr.id})

        # Add all companies to current user & admin
        users_to_update = env['res.users'].browse([env.uid, env.ref('base.user_admin').id])
        for u in users_to_update:
            if u.exists():
                u.write({'company_ids': [(4, c_ho.id), (4, c_1.id), (4, c_2.id)]})

        companies = [c_ho, c_1, c_2]
        _logger.info("Companies verified: %s, %s, %s", c_ho.name, c_1.name, c_2.name)

        # 2. SETUP ACCOUNTS & JOURNALS IN EACH COMPANY
        ACCOUNTS_SPEC = [
            ('11110001', 'Cash', 'asset_cash', 'bs'),
            ('11120001', 'Bank', 'asset_cash', 'bs'),
            ('11210010', 'Account Receivable', 'asset_receivable', 'bs'),
            ('11210090', 'Intercompany Receivable / Piutang Intragrup', 'asset_current', 'bs'),
            ('11300180', 'Inventory', 'asset_current', 'bs'),
            ('11700010', 'Investment in Subsidiaries / Investasi pada Entitas Anak', 'asset_non_current', 'bs'),
            ('12210010', 'Office Building', 'asset_fixed', 'bs'),
            ('12281010', 'Accumulation Building Depreciation', 'asset_fixed', 'bs'),
            ('21100010', 'Account Payable', 'liability_payable', 'bs'),
            ('21100090', 'Intercompany Payable / Utang Intragrup', 'liability_current', 'bs'),
            ('31100020', 'Paid Capital', 'equity', 'equity'),
            ('31510010', 'Past Profit & Loss', 'equity', 'equity'),
            ('41000010', 'Sales', 'income', 'pl'),
            ('41000090', 'Intercompany Sales / Pendapatan Penjualan Intragrup', 'income', 'pl'),
            ('51000010', 'Cost of Goods Sold', 'expense_direct_cost', 'pl'),
            ('51000090', 'Intercompany COGS / Beban Pokok Penjualan Intragrup', 'expense_direct_cost', 'pl'),
            ('61100010', 'Employee Salary', 'expense', 'pl'),
            ('67100010', 'Office Building Expense', 'expense_depreciation', 'pl'),
        ]

        AccountAccount = env['account.account']
        AccountJournal = env['account.journal']

        for comp in companies:
            # Ensure general journal
            j = AccountJournal.search([('company_id', '=', comp.id), ('type', '=', 'general')], limit=1)
            if not j:
                AccountJournal.create({
                    'name': 'Miscellaneous Operations',
                    'code': 'MISC',
                    'type': 'general',
                    'company_id': comp.id,
                })

            for code, name, acc_type, _ in ACCOUNTS_SPEC:
                acc = AccountAccount.with_company(comp).search([('code', '=', code), ('company_ids', 'in', comp.id)], limit=1)
                if not acc:
                    AccountAccount.create({
                        'code': code,
                        'name': name,
                        'account_type': acc_type,
                        'company_ids': [(6, 0, [comp.id])],
                    })

        # 3. SETUP CONSOLIDATION CHART OF ACCOUNTS (consol.account)
        ConsolAccount = env['consol.account']
        for code, name, acc_type, stmt in ACCOUNTS_SPEC:
            c_acc = ConsolAccount.search([('code', '=', code)], limit=1)
            is_ic = code in ['11210090', '21100090', '41000090', '51000090']
            if not c_acc:
                c_acc = ConsolAccount.create({
                    'code': code,
                    'name': name,
                    'account_type': acc_type,
                    'statement': stmt,
                    'is_intercompany': is_ic,
                })
            else:
                c_acc.write({'account_type': acc_type, 'statement': stmt, 'is_intercompany': is_ic})

        # Special consolidation accounts (Goodwill, NCI, CTA)
        acc_gw = ConsolAccount.search([('code', '=', '160000')], limit=1)
        if not acc_gw:
            acc_gw = ConsolAccount.create({
                'code': '160000',
                'name': 'Consolidated Goodwill',
                'account_type': 'asset_non_current',
                'statement': 'bs',
            })

        acc_nci_eq = ConsolAccount.search([('code', '=', '305000')], limit=1)
        if not acc_nci_eq:
            acc_nci_eq = ConsolAccount.create({
                'code': '305000',
                'name': 'Non-Controlling Interests (NCI) in Equity',
                'account_type': 'equity',
                'statement': 'bs',
            })

        acc_nci_pl = ConsolAccount.search([('code', '=', '701000')], limit=1)
        if not acc_nci_pl:
            acc_nci_pl = ConsolAccount.create({
                'code': '701000',
                'name': 'Profit/(Loss) Attributable to Non-Controlling Interests',
                'account_type': 'expense',
                'statement': 'pl',
            })

        acc_cta = ConsolAccount.search([('code', '=', '304000')], limit=1)
        if not acc_cta:
            acc_cta = ConsolAccount.create({
                'code': '304000',
                'name': 'Cumulative Translation Adjustment (CTA - OCI)',
                'account_type': 'equity',
                'statement': 'equity',
            })

        # Link IC counterparts
        acc_ic_rec = ConsolAccount.search([('code', '=', '11210090')], limit=1)
        acc_ic_pay = ConsolAccount.search([('code', '=', '21100090')], limit=1)
        acc_ic_sale = ConsolAccount.search([('code', '=', '41000090')], limit=1)
        acc_ic_cogs = ConsolAccount.search([('code', '=', '51000090')], limit=1)

        if acc_ic_rec and acc_ic_pay:
            acc_ic_rec.write({'ic_counterpart_id': acc_ic_pay.id})
            acc_ic_pay.write({'ic_counterpart_id': acc_ic_rec.id})
        if acc_ic_sale and acc_ic_cogs:
            acc_ic_sale.write({'ic_counterpart_id': acc_ic_cogs.id})
            acc_ic_cogs.write({'ic_counterpart_id': acc_ic_sale.id})

        acc_re = ConsolAccount.search([('code', '=', '31510010')], limit=1)

        # 4. SETUP CONSOLIDATION GROUP, ENTITIES, OWNERSHIP
        ConsolGroup = env['consol.group']
        group = ConsolGroup.search([('name', '=', 'Indonesia HO')], limit=1)
        if not group:
            group = ConsolGroup.create({
                'name': 'Indonesia HO',
                'code': 'GRP_IDN',
                'parent_company_id': c_ho.id,
                'currency_id': currency_idr.id,
                'goodwill_account_id': acc_gw.id,
                'nci_equity_account_id': acc_nci_eq.id,
                'nci_pl_account_id': acc_nci_pl.id,
                'cta_account_id': acc_cta.id,
                'retained_earnings_account_id': acc_re.id if acc_re else False,
                'ic_tolerance': 1000000.0,
            })
        else:
            group.write({
                'parent_company_id': c_ho.id,
                'currency_id': currency_idr.id,
                'goodwill_account_id': acc_gw.id,
                'nci_equity_account_id': acc_nci_eq.id,
                'nci_pl_account_id': acc_nci_pl.id,
                'cta_account_id': acc_cta.id,
                'retained_earnings_account_id': acc_re.id if acc_re else False,
                'ic_tolerance': 1000000.0,
            })

        ConsolEntity = env['consol.entity']
        ent_ho = ConsolEntity.search([('company_id', '=', c_ho.id)], limit=1)
        if not ent_ho:
            ent_ho = ConsolEntity.create({
                'name': 'PT Indonesia HO',
                'code': 'HOLDING',
                'company_id': c_ho.id,
                'functional_currency_id': currency_idr.id,
                'group_ids': [(4, group.id)],
            })
        else:
            ent_ho.write({'code': 'HOLDING', 'group_ids': [(4, group.id)]})

        ent_1 = ConsolEntity.search([('company_id', '=', c_1.id)], limit=1)
        if not ent_1:
            ent_1 = ConsolEntity.create({
                'name': 'Company 1',
                'code': 'ANAK_SGP',
                'company_id': c_1.id,
                'functional_currency_id': currency_idr.id,
                'group_ids': [(4, group.id)],
            })
        else:
            ent_1.write({'code': 'ANAK_SGP', 'group_ids': [(4, group.id)]})

        ent_2 = ConsolEntity.search([('company_id', '=', c_2.id)], limit=1)
        if not ent_2:
            ent_2 = ConsolEntity.create({
                'name': 'Company 2',
                'code': 'ANAK_MFG',
                'company_id': c_2.id,
                'functional_currency_id': currency_idr.id,
                'group_ids': [(4, group.id)],
            })
        else:
            ent_2.write({'code': 'ANAK_MFG', 'group_ids': [(4, group.id)]})

        # Update parent_entity_id on group
        group.write({'parent_entity_id': ent_ho.id})

        # Setup Ownership Structure
        ConsolOwnership = env['consol.ownership']
        own_1 = ConsolOwnership.search([('parent_id', '=', ent_ho.id), ('child_id', '=', ent_1.id)], limit=1)
        if not own_1:
            own_1 = ConsolOwnership.create({
                'parent_id': ent_ho.id,
                'child_id': ent_1.id,
                'percentage': 100.0,
                'method': 'full',
                'date_from': '2026-01-01',
            })
        else:
            own_1.write({'percentage': 100.0, 'method': 'full'})

        own_2 = ConsolOwnership.search([('parent_id', '=', ent_ho.id), ('child_id', '=', ent_2.id)], limit=1)
        if not own_2:
            own_2 = ConsolOwnership.create({
                'parent_id': ent_ho.id,
                'child_id': ent_2.id,
                'percentage': 80.0,
                'method': 'full',
                'goodwill_amount': 10000000.0,
                'nci_at_acquisition': 50000000.0,
                'date_from': '2026-01-01',
            })
        else:
            own_2.write({'percentage': 80.0, 'method': 'full', 'goodwill_amount': 10000000.0, 'nci_at_acquisition': 50000000.0})

        # Setup Account Mappings for each entity
        ConsolMapping = env['consol.account.mapping']
        for ent in [ent_ho, ent_1, ent_2]:
            comp = ent.company_id
            for code, _, _, _ in ACCOUNTS_SPEC:
                src_acc = AccountAccount.with_company(comp).search([('code', '=', code), ('company_ids', 'in', comp.id)], limit=1)
                tgt_acc = ConsolAccount.search([('code', '=', code)], limit=1)
                if src_acc and tgt_acc:
                    exist_map = ConsolMapping.search([('entity_id', '=', ent.id), ('account_id', '=', src_acc.id)], limit=1)
                    if not exist_map:
                        ConsolMapping.create({
                            'entity_id': ent.id,
                            'account_id': src_acc.id,
                            'consol_account_id': tgt_acc.id,
                        })
                    else:
                        exist_map.write({'consol_account_id': tgt_acc.id})

        _logger.info("Consolidation structure and mappings configured.")

        # 5. CREATE ACCOUNTING TRANSACTIONS (account.move)
        Move = env['account.move']
        # Delete old QC/demo moves if present
        old_moves = Move.search([('ref', 'ilike', 'QC-CONSOL-')])
        if old_moves:
            old_moves.button_draft()
            old_moves.unlink()

        def get_acc(comp, code):
            return AccountAccount.with_company(comp).search([('code', '=', code), ('company_ids', 'in', comp.id)], limit=1)

        def get_jrn(comp):
            return AccountJournal.search([('company_id', '=', comp.id), ('type', '=', 'general')], limit=1)

        # ==========================================
        # MONTH 08 TRANSACTIONS (2026-08)
        # ==========================================
        # Company 1
        m_c1_aug = Move.with_company(c_1).create({
            'company_id': c_1.id,
            'journal_id': get_jrn(c_1).id,
            'date': '2026-08-15',
            'ref': 'QC-CONSOL-2026-08: Operasional Company 1',
            'line_ids': [
                (0, 0, {'account_id': get_acc(c_1, '11110001').id, 'debit': 180000000.0, 'credit': 0.0}),
                (0, 0, {'account_id': get_acc(c_1, '11210010').id, 'debit': 120000000.0, 'credit': 0.0}),
                (0, 0, {'account_id': get_acc(c_1, '61100010').id, 'debit': 120000000.0, 'credit': 0.0}),
                (0, 0, {'account_id': get_acc(c_1, '21100010').id, 'debit': 0.0, 'credit': 50000000.0}),
                (0, 0, {'account_id': get_acc(c_1, '31100020').id, 'debit': 0.0, 'credit': 150000000.0}),
                (0, 0, {'account_id': get_acc(c_1, '41000010').id, 'debit': 0.0, 'credit': 220000000.0}),
            ]
        })
        m_c1_aug.action_post()

        # Company 2
        m1_c2_aug = Move.with_company(c_2).create({
            'company_id': c_2.id,
            'journal_id': get_jrn(c_2).id,
            'date': '2026-08-01',
            'ref': 'QC-CONSOL-2026-08: Saldo Awal Company 2',
            'line_ids': [
                (0, 0, {'account_id': get_acc(c_2, '11110001').id, 'debit': 100000000.0, 'credit': 0.0}),
                (0, 0, {'account_id': get_acc(c_2, '11210010').id, 'debit': 60000000.0, 'credit': 0.0}),
                (0, 0, {'account_id': get_acc(c_2, '11300180').id, 'debit': 120000000.0, 'credit': 0.0}),
                (0, 0, {'account_id': get_acc(c_2, '12210010').id, 'debit': 200000000.0, 'credit': 0.0}),
                (0, 0, {'account_id': get_acc(c_2, '12281010').id, 'debit': 0.0, 'credit': 30000000.0}),
                (0, 0, {'account_id': get_acc(c_2, '21100010').id, 'debit': 0.0, 'credit': 50000000.0}),
                (0, 0, {'account_id': get_acc(c_2, '31100020').id, 'debit': 0.0, 'credit': 200000000.0}),
                (0, 0, {'account_id': get_acc(c_2, '31510010').id, 'debit': 0.0, 'credit': 200000000.0}),
            ]
        })
        m1_c2_aug.action_post()

        m2_c2_aug = Move.with_company(c_2).create({
            'company_id': c_2.id,
            'journal_id': get_jrn(c_2).id,
            'date': '2026-08-15',
            'ref': 'QC-CONSOL-2026-08: Operasional Company 2',
            'line_ids': [
                (0, 0, {'account_id': get_acc(c_2, '11110001').id, 'debit': 150000000.0, 'credit': 0.0}),
                (0, 0, {'account_id': get_acc(c_2, '51000010').id, 'debit': 60000000.0, 'credit': 0.0}),
                (0, 0, {'account_id': get_acc(c_2, '61100010').id, 'debit': 30000000.0, 'credit': 0.0}),
                (0, 0, {'account_id': get_acc(c_2, '67100010').id, 'debit': 10000000.0, 'credit': 0.0}),
                (0, 0, {'account_id': get_acc(c_2, '41000010').id, 'debit': 0.0, 'credit': 250000000.0}),
            ]
        })
        m2_c2_aug.action_post()

        m3_c2_aug = Move.with_company(c_2).create({
            'company_id': c_2.id,
            'journal_id': get_jrn(c_2).id,
            'date': '2026-08-20',
            'ref': 'QC-CONSOL-2026-08: Pembelian Intragrup dari Holding',
            'line_ids': [
                (0, 0, {'account_id': get_acc(c_2, '51000090').id, 'partner_id': c_ho.partner_id.id, 'debit': 80000000.0, 'credit': 0.0}),
                (0, 0, {'account_id': get_acc(c_2, '21100090').id, 'partner_id': c_ho.partner_id.id, 'debit': 0.0, 'credit': 30000000.0}),
                (0, 0, {'account_id': get_acc(c_2, '11110001').id, 'debit': 0.0, 'credit': 50000000.0}),
            ]
        })
        m3_c2_aug.action_post()

        # Indonesia Ho
        m1_ho_aug = Move.with_company(c_ho).create({
            'company_id': c_ho.id,
            'journal_id': get_jrn(c_ho).id,
            'date': '2026-08-01',
            'ref': 'QC-CONSOL-2026-08: Saldo Awal & Investasi Anak Indonesia HO',
            'line_ids': [
                (0, 0, {'account_id': get_acc(c_ho, '11110001').id, 'debit': 350000000.0, 'credit': 0.0}),
                (0, 0, {'account_id': get_acc(c_ho, '11210010').id, 'debit': 170000000.0, 'credit': 0.0}),
                (0, 0, {'account_id': get_acc(c_ho, '11700010').id, 'partner_id': c_2.partner_id.id, 'debit': 160000000.0, 'credit': 0.0}),
                (0, 0, {'account_id': get_acc(c_ho, '11700010').id, 'partner_id': c_1.partner_id.id, 'debit': 150000000.0, 'credit': 0.0}),
                (0, 0, {'account_id': get_acc(c_ho, '12210010').id, 'debit': 500000000.0, 'credit': 0.0}),
                (0, 0, {'account_id': get_acc(c_ho, '12281010').id, 'debit': 0.0, 'credit': 90000000.0}),
                (0, 0, {'account_id': get_acc(c_ho, '21100010').id, 'debit': 0.0, 'credit': 100000000.0}),
                (0, 0, {'account_id': get_acc(c_ho, '31100020').id, 'debit': 0.0, 'credit': 1000000000.0}),
                (0, 0, {'account_id': get_acc(c_ho, '31510010').id, 'debit': 0.0, 'credit': 140000000.0}),
            ]
        })
        m1_ho_aug.action_post()

        m2_ho_aug = Move.with_company(c_ho).create({
            'company_id': c_ho.id,
            'journal_id': get_jrn(c_ho).id,
            'date': '2026-08-15',
            'ref': 'QC-CONSOL-2026-08: Operasional Indonesia HO',
            'line_ids': [
                (0, 0, {'account_id': get_acc(c_ho, '51000010').id, 'debit': 200000000.0, 'credit': 0.0}),
                (0, 0, {'account_id': get_acc(c_ho, '61100010').id, 'debit': 110000000.0, 'credit': 0.0}),
                (0, 0, {'account_id': get_acc(c_ho, '67100010').id, 'debit': 20000000.0, 'credit': 0.0}),
                (0, 0, {'account_id': get_acc(c_ho, '41000010').id, 'debit': 0.0, 'credit': 320000000.0}),
                (0, 0, {'account_id': get_acc(c_ho, '11110001').id, 'debit': 0.0, 'credit': 10000000.0}),
            ]
        })
        m2_ho_aug.action_post()

        m3_ho_aug = Move.with_company(c_ho).create({
            'company_id': c_ho.id,
            'journal_id': get_jrn(c_ho).id,
            'date': '2026-08-20',
            'ref': 'QC-CONSOL-2026-08: Penjualan Intragrup ke Company 2',
            'line_ids': [
                (0, 0, {'account_id': get_acc(c_ho, '11210090').id, 'partner_id': c_2.partner_id.id, 'debit': 30000000.0, 'credit': 0.0}),
                (0, 0, {'account_id': get_acc(c_ho, '11110001').id, 'debit': 50000000.0, 'credit': 0.0}),
                (0, 0, {'account_id': get_acc(c_ho, '41000090').id, 'partner_id': c_2.partner_id.id, 'debit': 0.0, 'credit': 80000000.0}),
            ]
        })
        m3_ho_aug.action_post()

        # ==========================================
        # MONTH 09 TRANSACTIONS (2026-09)
        # ==========================================
        # Company 1
        m1_c1_sep = Move.with_company(c_1).create({
            'company_id': c_1.id,
            'journal_id': get_jrn(c_1).id,
            'date': '2026-09-01',
            'ref': 'QC-CONSOL-2026-09: Saldo Awal & Operasional Company 1',
            'line_ids': [
                (0, 0, {'account_id': get_acc(c_1, '11110001').id, 'debit': 240000000.0, 'credit': 0.0}),
                (0, 0, {'account_id': get_acc(c_1, '11210010').id, 'debit': 160000000.0, 'credit': 0.0}),
                (0, 0, {'account_id': get_acc(c_1, '61100010').id, 'debit': 155000000.0, 'credit': 0.0}),
                (0, 0, {'account_id': get_acc(c_1, '21100010').id, 'debit': 0.0, 'credit': 80000000.0}),
                (0, 0, {'account_id': get_acc(c_1, '31100020').id, 'debit': 0.0, 'credit': 150000000.0}),
                (0, 0, {'account_id': get_acc(c_1, '31510010').id, 'debit': 0.0, 'credit': 15000000.0}),
                (0, 0, {'account_id': get_acc(c_1, '41000010').id, 'debit': 0.0, 'credit': 310000000.0}),
            ]
        })
        m1_c1_sep.action_post()

        # Company 2
        m1_c2_sep = Move.with_company(c_2).create({
            'company_id': c_2.id,
            'journal_id': get_jrn(c_2).id,
            'date': '2026-09-01',
            'ref': 'QC-CONSOL-2026-09: Saldo Awal Company 2',
            'line_ids': [
                (0, 0, {'account_id': get_acc(c_2, '11110001').id, 'debit': 120000000.0, 'credit': 0.0}),
                (0, 0, {'account_id': get_acc(c_2, '11210010').id, 'debit': 80000000.0, 'credit': 0.0}),
                (0, 0, {'account_id': get_acc(c_2, '11300180').id, 'debit': 150000000.0, 'credit': 0.0}),
                (0, 0, {'account_id': get_acc(c_2, '12210010').id, 'debit': 200000000.0, 'credit': 0.0}),
                (0, 0, {'account_id': get_acc(c_2, '12281010').id, 'debit': 0.0, 'credit': 40000000.0}),
                (0, 0, {'account_id': get_acc(c_2, '21100010').id, 'debit': 0.0, 'credit': 60000000.0}),
                (0, 0, {'account_id': get_acc(c_2, '31100020').id, 'debit': 0.0, 'credit': 200000000.0}),
                (0, 0, {'account_id': get_acc(c_2, '31510010').id, 'debit': 0.0, 'credit': 250000000.0}),
            ]
        })
        m1_c2_sep.action_post()

        m2_c2_sep = Move.with_company(c_2).create({
            'company_id': c_2.id,
            'journal_id': get_jrn(c_2).id,
            'date': '2026-09-15',
            'ref': 'QC-CONSOL-2026-09: Operasional Company 2',
            'line_ids': [
                (0, 0, {'account_id': get_acc(c_2, '11110001').id, 'debit': 220000000.0, 'credit': 0.0}),
                (0, 0, {'account_id': get_acc(c_2, '51000010').id, 'debit': 80000000.0, 'credit': 0.0}),
                (0, 0, {'account_id': get_acc(c_2, '61100010').id, 'debit': 40000000.0, 'credit': 0.0}),
                (0, 0, {'account_id': get_acc(c_2, '67100010').id, 'debit': 10000000.0, 'credit': 0.0}),
                (0, 0, {'account_id': get_acc(c_2, '41000010').id, 'debit': 0.0, 'credit': 350000000.0}),
            ]
        })
        m2_c2_sep.action_post()

        m3_c2_sep = Move.with_company(c_2).create({
            'company_id': c_2.id,
            'journal_id': get_jrn(c_2).id,
            'date': '2026-09-20',
            'ref': 'QC-CONSOL-2026-09: Pembelian Intragrup dari Holding',
            'line_ids': [
                (0, 0, {'account_id': get_acc(c_2, '51000090').id, 'partner_id': c_ho.partner_id.id, 'debit': 120000000.0, 'credit': 0.0}),
                (0, 0, {'account_id': get_acc(c_2, '21100090').id, 'partner_id': c_ho.partner_id.id, 'debit': 0.0, 'credit': 50000000.0}),
                (0, 0, {'account_id': get_acc(c_2, '11110001').id, 'debit': 0.0, 'credit': 70000000.0}),
            ]
        })
        m3_c2_sep.action_post()

        # Indonesia Ho
        m1_ho_sep = Move.with_company(c_ho).create({
            'company_id': c_ho.id,
            'journal_id': get_jrn(c_ho).id,
            'date': '2026-09-01',
            'ref': 'QC-CONSOL-2026-09: Saldo Awal & Investasi Anak Indonesia HO',
            'line_ids': [
                (0, 0, {'account_id': get_acc(c_ho, '11110001').id, 'debit': 450000000.0, 'credit': 0.0}),
                (0, 0, {'account_id': get_acc(c_ho, '11210010').id, 'debit': 200000000.0, 'credit': 0.0}),
                (0, 0, {'account_id': get_acc(c_ho, '11700010').id, 'partner_id': c_2.partner_id.id, 'debit': 160000000.0, 'credit': 0.0}),
                (0, 0, {'account_id': get_acc(c_ho, '11700010').id, 'partner_id': c_1.partner_id.id, 'debit': 150000000.0, 'credit': 0.0}),
                (0, 0, {'account_id': get_acc(c_ho, '12210010').id, 'debit': 500000000.0, 'credit': 0.0}),
                (0, 0, {'account_id': get_acc(c_ho, '12281010').id, 'debit': 0.0, 'credit': 100000000.0}),
                (0, 0, {'account_id': get_acc(c_ho, '21100010').id, 'debit': 0.0, 'credit': 150000000.0}),
                (0, 0, {'account_id': get_acc(c_ho, '31100020').id, 'debit': 0.0, 'credit': 1000000000.0}),
                (0, 0, {'account_id': get_acc(c_ho, '31510010').id, 'debit': 0.0, 'credit': 210000000.0}),
            ]
        })
        m1_ho_sep.action_post()

        m2_ho_sep = Move.with_company(c_ho).create({
            'company_id': c_ho.id,
            'journal_id': get_jrn(c_ho).id,
            'date': '2026-09-15',
            'ref': 'QC-CONSOL-2026-09: Operasional Indonesia HO',
            'line_ids': [
                (0, 0, {'account_id': get_acc(c_ho, '51000010').id, 'debit': 300000000.0, 'credit': 0.0}),
                (0, 0, {'account_id': get_acc(c_ho, '61100010').id, 'debit': 140000000.0, 'credit': 0.0}),
                (0, 0, {'account_id': get_acc(c_ho, '67100010').id, 'debit': 20000000.0, 'credit': 0.0}),
                (0, 0, {'account_id': get_acc(c_ho, '41000010').id, 'debit': 0.0, 'credit': 400000000.0}),
                (0, 0, {'account_id': get_acc(c_ho, '11110001').id, 'debit': 0.0, 'credit': 60000000.0}),
            ]
        })
        m2_ho_sep.action_post()

        m3_ho_sep = Move.with_company(c_ho).create({
            'company_id': c_ho.id,
            'journal_id': get_jrn(c_ho).id,
            'date': '2026-09-20',
            'ref': 'QC-CONSOL-2026-09: Penjualan Intragrup ke Company 2',
            'line_ids': [
                (0, 0, {'account_id': get_acc(c_ho, '11210090').id, 'partner_id': c_2.partner_id.id, 'debit': 50000000.0, 'credit': 0.0}),
                (0, 0, {'account_id': get_acc(c_ho, '11110001').id, 'debit': 70000000.0, 'credit': 0.0}),
                (0, 0, {'account_id': get_acc(c_ho, '41000090').id, 'partner_id': c_2.partner_id.id, 'debit': 0.0, 'credit': 120000000.0}),
            ]
        })
        m3_ho_sep.action_post()

        _logger.info("Transactions created for August and September 2026.")

        # 6. PROCESS CONSOLIDATION PERIODS
        ConsolPeriod = env['consol.period']

        def process_period(p_name, d_from, d_to):
            period = ConsolPeriod.search([('group_id', '=', group.id), ('name', '=', p_name)], limit=1)
            if period:
                if period.state == 'locked':
                    period.action_unlock()
                period.action_reset_draft()
                period.journal_ids.unlink()
                period.match_ids.unlink()
                period.trial_balance_ids.unlink()
            else:
                period = ConsolPeriod.create({
                    'name': p_name,
                    'group_id': group.id,
                    'date_from': d_from,
                    'date_to': d_to,
                })

            period.action_load_trial_balances()
            period.action_run_ic_matching()
            period.action_generate_eliminations()
            period.action_compute_nci()
            period.action_submit_review()
            period.action_lock()
            return period

        # Process August 2026
        p_aug = process_period('2026-08', '2026-08-01', '2026-08-31')
        _logger.info("Period 2026-08 processed and locked: state=%s", p_aug.state)

        # Process September 2026
        p_sep = process_period('2026-09', '2026-09-01', '2026-09-30')
        _logger.info("Period 2026-09 processed and locked: state=%s", p_sep.state)

        # 7. SYNC ACCOUNTS TO REPORT TEMPLATES & SET COMPARISON
        ConsolReport = env['consol.report']
        ConsolReport.sync_all_reports_accounts()
        for rep in ConsolReport.search([]):
            rep.write({'comparison': 'previous_period'})

        _logger.info("=== PSAK 65 CONSOLIDATION DEMO DATA INSTALLATION COMPLETED SUCCESSFULLY ===")
        return True
