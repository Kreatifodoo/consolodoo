# -*- coding: utf-8 -*-
{
    'name': 'PSAK 65 Consolidation Demo & Dummy Transactions',
    'version': '19.0.1.0.0',
    'category': 'Accounting/Accounting',
    'summary': 'Automated Multi-Company Setup, Real Journal Transactions, and 2-Month Consolidation Demo Data for PSAK 65 (IFRS 10)',
    'description': """
PSAK 65 Consolidation Demo & Dummy Transactions
================================================
This module automatically creates and configures complete demonstration data for multi-entity financial consolidation:
1. Creates / validates 3 Odoo companies: Indonesia Ho (Ultimate Parent), Company 1 (100% subsidiary), and Company 2 (80% subsidiary).
2. Sets up chart of accounts and intercompany accounts on all companies.
3. Automatically configures Consolidation Group, Consolidation Entities, and Ownership Structure (with NCI calculation).
4. Maps all entity accounts to Consolidation Chart of Accounts.
5. Generates real accounting journal entries (account.move) for Month 08 (August 2026) and Month 09 (September 2026).
6. Automatically processes end-to-end Consolidation Periods (2026-08 and 2026-09) with full Trial Balances, Intercompany Reconciliation, Automated Elimination Journals (E1, E2, E3, E7), and locked audit trail.
7. Connects all accounts to Consolidated Financial Statement templates (Balance Sheet & Profit/Loss with MoM comparison).
    """,
    'author': 'Arkana Solusi Digital',
    'website': 'https://arkanaditama.com',
    'license': 'LGPL-3',
    'depends': ['base', 'account', 'odoo_psak_consolidation'],
    'data': [
        'security/ir.model.access.csv',
        'wizard/consol_demo_data_wizard_views.xml',
    ],
    'post_init_hook': 'post_init_hook',
    'installable': True,
    'application': False,
    'auto_install': False,
}
