# Porting odoo_psak_consolidation 19.0 → 20.0

Tanggal: 17 Nov 2026. Basis: zip `odoo_psak_consolidation` (manifest 19.0.1.0.0).

## Perubahan wajib karena API Odoo 20

| Area | Odoo 19 | Odoo 20 | File |
|---|---|---|---|
| Versi | `19.0.1.0.0` (modul *uninstallable* di 20.0) | `20.0.1.0.0` | `__manifest__.py` |
| Hak akses | `ir.model.access.csv` + `ir.rule` | Model terpadu **`ir.access`** → `security/ir.access.csv` (`id,name,model_id,group_id/id,operation,domain`). Domain 2 record rule lama (consol.group, consol.period) dipasang di setiap baris permission model tersebut agar perilaku tetap sama | `security/ir.access.csv`, `security/consolidation_security.xml` |
| JS (OWL 3) | `standardActionServiceProps` dari `@web/webclient/actions/action_service` (file ini **tidak ada** lagi) | import dari `@web/webclient/actions/action_plugin` | `static/src/components/consol_report_viewer/consol_report_viewer.js` |
| Template | `t-esc` (deprecated) | `t-out` | template OWL & QWeb report |
| Controller | `@http.route(type='json')` (alias deprecated sejak 19.0) | `type='jsonrpc'` | `controllers/main.py` |
| Ikon tombol | Font Awesome (`fa-download`, `fa-bar-chart`, `fa-refresh`) | Material symbols (`download`, `bar_chart`, `refresh`) | `views/consol_*_views.xml` |

## Perbaikan fungsional

1. **Tipe akun Odoo 20** ditambahkan pada penarikan neraca saldo: `equity_retained` (neraca) dan `expense_other` (laba rugi). Tanpa ini, beban bunga/rugi kurs (akun 72xxxxxx) tidak ikut terkonsolidasi.
2. **Multi-ledger (multi-GAAP) Odoo 20**: field baru **GAAP Ledger** (`ledger_journal_group_id`) pada *Periode Konsolidasi*.
   - Kosong = hanya buku statutory (*Local GAAP* / PSAK).
   - Diisi (mis. IFRS / US GAAP) = Local GAAP + penyesuaian yang diposting di ledger tersebut.

   Sebelumnya semua jurnal ikut tertarik sehingga penyesuaian IFRS & US GAAP terhitung bersamaan dengan PSAK.

## Belum diubah

- File lama yang tidak dimuat manifest (`models/consolidation_*.py`, `views/consolidation_*.xml`, `controllers/wp_main.py`, `controllers/xbrl_export_controller.py`) dibiarkan apa adanya (tidak di-import).
- Modul `odoo_psak_consolidation_dummy_data` tidak di-porting (membuat 3 company demo tambahan).
