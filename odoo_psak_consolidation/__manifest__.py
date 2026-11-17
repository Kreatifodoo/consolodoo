# -*- coding: utf-8 -*-
{
    'name': 'Konsolidasi Laporan Keuangan PSAK 65 (IFRS 10)',
    'version': '20.0.1.1.0',
    'category': 'Accounting/Accounting',
    'summary': 'Modul Konsolidasi Laporan Keuangan Multi-Entitas Berbasis PSAK 65 / IFRS 10',
    'description': """
Modul Konsolidasi Keuangan Odoo 20 — PSAK 65 / IFRS 10
=======================================================
Fitur Utama:

* Struktur kepemilikan bertingkat (langsung, tidak langsung, silang) dengan perhitungan otomatis persentase efektif graf.
* Bagan akun konsolidasi independen dengan pemetaan terpadu dan validasi akun yang belum terpetakan.
* Penarikan otomatis neraca saldo dari transaksi buku besar (account.move.line) serta opsi impor CSV/Excel.
* Mesin penjabaran valuta asing (PSAK 10) dengan pengakuan selisih kurs translasi (CTA) ke Penghasilan Komprehensif Lain (OCI).
* Rekonsiliasi transaksi & saldo antar-perusahaan (Intercompany Matching).
* Mesin Jurnal Eliminasi Otomatis (E1–E10) serta jurnal berulang (recurring) dan pembalikan otomatis (reversal).
* Atribusi Laba/Rugi & OCI kepada Kepentingan Non-Pengendali (NCI) termasuk penanganan NCI defisit.
* Mesin Laporan Keuangan Tanpa Kode (No-Code Reporting Engine):
  - Laporan Posisi Keuangan (Neraca)
  - Laporan Laba Rugi & OCI
  - Laporan Perubahan Ekuitas
  - Laporan Arus Kas (Metode Tidak Langsung)
  - Kertas Kerja Konsolidasi (Worksheet)
* Tampilan Web Interaktif OWL dengan penelusuran rincian (drill-down), ekspor Excel (.xlsx), dan cetak dokumen resmi PDF.
* Kontrol hak akses berbasis peran & jejak audit lengkap.
    """,
    'author': 'Arkana Solusi Digital',
    'website': 'https://arkanaditama.com',
    'license': 'LGPL-3',
    'depends': ['base', 'account', 'mail', 'web'],
    'data': [
        'security/consolidation_security.xml',
        'security/ir.access.csv',
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
