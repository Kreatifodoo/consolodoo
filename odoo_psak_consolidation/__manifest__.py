# -*- coding: utf-8 -*-
{
    'name': 'Financial Consolidation PSAK 65 (IFRS 10)',
    'version': '19.0.1.0.0',
    'category': 'Accounting/Accounting',
    'summary': 'Multi-Entity Financial Consolidation Module based on PSAK 65 / IFRS 10',
    'description': """
Odoo 19 Financial Consolidation Module — PSAK 65 / IFRS 10
===========================================================
Key Features:
- Multi-level ownership structure (direct, step, cross-holding) with graph effective percentage computation.
- Independent consolidation chart of accounts with unified mapping and unmapped account validation.
- Automated trial balance extraction from account.move.line with CSV/XLSX import options.
- Foreign currency translation engine (PSAK 10) with CTA recognition to OCI.
- Intercompany balance & transaction reconciliation (Intercompany Matching).
- Automated Elimination Journal Engine (E1–E10) & Recurring / Reversal journals.
- Profit/Loss & OCI Attribution to Non-Controlling Interest (NCI) including deficit NCI handling.
- No-Code Financial Reporting Engine:
  * Statement of Financial Position (Balance Sheet)
  * Statement of Profit or Loss & OCI
  * Statement of Changes in Equity
  * Statement of Cash Flows (Indirect Method)
  * Consolidation Worksheet
- Interactive OWL Web UI with drill-down, XLSX Excel Export & QWeb PDF printouts.
- Role-based security access control & complete audit trail.
    """,
    'author': 'Arkana Solusi Digital',
    'website': 'https://arkanaditama.com',
    'license': 'LGPL-3',
    'depends': ['base', 'account', 'mail', 'web'],
    'data': [
        'security/consolidation_security.xml',
        'security/ir.model.access.csv',
        'data/account_type_data.xml',
        'data/elimination_rule_data.xml',
        'data/report_template_data.xml',
        'views/consol_account_views.xml',
        'views/consol_account_mapping_views.xml',
        'views/consol_entity_views.xml',
        'views/consol_ownership_views.xml',
        'views/consol_group_views.xml',
        'views/consol_rate_views.xml',
        'views/consol_elimination_rule_views.xml',
        'views/consol_trial_balance_views.xml',
        'views/consol_intercompany_match_views.xml',
        'views/consol_journal_views.xml',
        'views/consol_period_views.xml',
        'views/consol_report_views.xml',
        'wizard/consol_auto_map_wizard_views.xml',
        'wizard/consol_import_tb_wizard_views.xml',
        'wizard/consol_report_export_wizard_views.xml',
        'wizard/consol_import_company_coa_wizard_views.xml',
        'report/consol_report_templates.xml',
        'views/consol_menu_views.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'odoo_psak_consolidation/static/src/components/consol_report_viewer/consol_report_viewer.scss',
            'odoo_psak_consolidation/static/src/components/consol_report_viewer/consol_report_viewer.xml',
            'odoo_psak_consolidation/static/src/components/consol_report_viewer/consol_report_viewer.js',
        ],
    },
    'installable': True,
    'application': True,
    'auto_install': False,
}
