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

## Perbaikan 20.0.1.0.1 (saat setup grup Orch AI)

1. **Wizard *Salin Master Akun dari Perusahaan***:
   - Tipe akun Odoo 20 `expense_other` (beban bunga, rugi kurs) dan `equity_retained` sekarang dikenali, dan juga ditambahkan ke pilihan tipe *Akun Konsolidasi*.
   - Sebelumnya kedua tipe ini jatuh ke `asset_current` / Neraca, sehingga beban keuangan tampil sebagai aset dan pasangan IC bunga (71200010 ↔ 72200010) masuk eliminasi neraca, bukan laba rugi.
2. **Deteksi akun intercompany** memakai kata utuh `ic`. Sebelumnya *Public Transportation* ikut ditandai IC karena mengandung "…ic ".
3. **Grup Konsolidasi**: `res.company` di Odoo 20 tidak punya field `code`. Membuat grup untuk company yang belum punya entitas sebelumnya error.
4. Sinkronisasi akun ke template standar (baris CURR_NI & OPEX) ikut memasukkan `expense_other`.

## Perbaikan 20.0.1.0.2 (engine konsolidasi untuk periode bulanan Odoo)

Odoo tidak menutup akun laba rugi ke saldo laba. Laba tahun berjalan dihitung dinamis. Akibatnya engine lama menghasilkan neraca saldo bulanan yang tidak seimbang mulai bulan kedua, dan neraca per bulan kehilangan laba bulan-bulan sebelumnya.

1. **Tarik Neraca Saldo**: laba rugi sebelum `date_from` ikut ditarik sebagai saldo ekuitas. Tahun buku berjalan masuk ke akun *Laba Tahun Berjalan* entitas (`equity_unaffected`), dan tahun buku sebelumnya ke *Akun Saldo Laba Konsolidasi* grup. Hasilnya, setiap periode seimbang.
2. **Laporan posisi** (Neraca, Perubahan Ekuitas, Kertas Kerja) memakai laba rugi periode terakhir saja, karena laba sebelumnya sudah ada di ekuitas. Laporan Laba Rugi dan Arus Kas tetap menjumlahkan periode terpilih.
3. **Drill-down** akun neraca pada mode *Semua Periode* tidak lagi menjumlahkan saldo semua bulan.
4. **E1**:
   - Hanya akun modal (nama mengandung *capital/modal*) yang dieliminasi, dengan tanda debit/kredit sesuai saldo.
   - Tidak lagi jatuh ke seluruh akun ekuitas bila entitas anak belum punya modal.
   - Jurnal kosong tidak dibuat.
5. **Generate Eliminations** bisa dijalankan ulang: seluruh jurnal otomatis lama, termasuk yang sudah terposting kecuali E10, dihapus lebih dulu, sehingga eliminasi tidak dobel. Periode terkunci ditolak.

## Perbaikan 20.0.1.0.3 (eliminasi saldo antar-perusahaan)

1. **E2 terbalik arah untuk pasangan IC non-dagang** (pinjaman, bunga, rekening koran). Engine lama hanya mengenali sisi aset dari tipe `asset_receivable`, sehingga pinjaman IC didebit (didobelkan), bukan dieliminasi. Sekarang sisi aset ditentukan dari tipe akun aset, dengan cadangan dari tanda saldo.
2. **IC Matching**:
   - Saldo dijumlah per (entitas, akun, entitas lawan).
   - Baris akun IC **tanpa partner** diatribusikan ke entitas lawan bila akun tersebut di entitas itu hanya memiliki satu lawan. Contoh baris seperti ini: jurnal revaluasi kurs akhir bulan Odoo atas pinjaman/bunga IC dalam USD.
   - Saldo yang tidak bisa diatribusikan dicatat di chatter periode.

## Fitur 20.0.1.1.0: penjabaran PSAK 10 & jurnal E10 (CTA)

Engine lama membuat jurnal E10 tanpa baris, sehingga entitas yang mata uang fungsionalnya berbeda dari mata uang grup menghasilkan neraca saldo yang tidak seimbang.

1. **Selisih kurs penjabaran (CTA)**:
   - Aset & liabilitas dijabarkan dengan kurs penutupan, laba rugi dengan kurs rata-rata, ekuitas dengan kurs historis.
   - Selisihnya dicatat pada akun kliring baru `C-CTA-TR`, sehingga neraca saldo setiap entitas yang dijabarkan tetap seimbang.
2. **Jurnal E10** (otomatis, seimbang, terposting): mengalokasikan saldo kliring ke *Akun Selisih Kurs Translasi (CTA - OCI)* grup sesuai persentase pemilik entitas induk, dan sisanya ke *Akun NCI (Ekuitas)*.
3. **Laba tahun berjalan s/d bulan lalu** pada entitas yang dijabarkan memakai jumlah laba rugi periode-periode sebelumnya yang sudah dijabarkan (masing-masing dengan kurs rata-ratanya). Dengan begitu laba di neraca sama dengan laba di laporan laba rugi.
4. **Kurs periode** (*Kurs Valuta Asing (PSAK 10)*) diisi otomatis dari tabel kurs Odoo saat record kurs dibuat:
   - penutupan = fixing pada/sebelum akhir periode;
   - rata-rata = rata-rata fixing di dalam periode;
   - historis = fixing pada tanggal kepemilikan paling awal entitas bermata uang tsb, atau fixing pertama bila tanggal itu lebih awal.

   Nilai fixing dibaca langsung dari tabel kurs, karena `_get_conversion_rate` Odoo 20 memakai kurs sebelum tanggal (H-1).
5. **Presisi kurs** dinaikkan ke 12 desimal. Ini diperlukan untuk grup dengan mata uang penyajian kuat, misalnya 1 IDR = 0,0000551 USD.

## Belum diubah

- File lama yang tidak dimuat manifest (`models/consolidation_*.py`, `views/consolidation_*.xml`, `controllers/wp_main.py`, `controllers/xbrl_export_controller.py`) dibiarkan apa adanya (tidak di-import).
- Modul `odoo_psak_consolidation_dummy_data` tidak di-porting (membuat 3 company demo tambahan).
