# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.tools.safe_eval import safe_eval
from odoo.exceptions import UserError

class ConsolReport(models.Model):
    _name = 'consol.report'
    _description = 'Template Laporan Keuangan Konsolidasian (Mesin Laporan Tanpa Kode)'
    _inherit = ['mail.thread']
    _order = 'sequence, name'

    name = fields.Char(string='Nama Template Laporan', required=True, tracking=True)
    sequence = fields.Integer(string='Urutan', default=10)

    report_type = fields.Selection([
        ('balance_sheet', 'Laporan Posisi Keuangan (Neraca)'),
        ('profit_loss', 'Laporan Laba Rugi & OCI'),
        ('equity_changes', 'Laporan Perubahan Ekuitas'),
        ('cash_flow', 'Laporan Arus Kas (Metode Tidak Langsung)'),
        ('worksheet', 'Kertas Kerja Konsolidasi (Worksheet)'),
        ('custom', 'Laporan Keuangan Kustom')
    ], string='Tipe Laporan', default='balance_sheet', required=True, tracking=True)

    group_id = fields.Many2one(
        'consol.group',
        string='Grup Konsolidasi Khusus',
        help="Biarkan kosong jika template laporan ini berlaku untuk semua grup konsolidasi.")

    comparison = fields.Selection([
        ('none', 'Tanpa Perbandingan'),
        ('previous_period', 'Periode Sebelumnya (MoM)'),
        ('same_period_last_year', 'Periode Sama Tahun Lalu (YoY)'),
        ('budget', 'Anggaran')
    ], string='Mode Perbandingan', default='previous_period')

    show_entity_columns = fields.Boolean(
        string='Tampilkan Kolom per Entitas',
        default=True,
        help="Menampilkan kolom terpisah untuk setiap entitas anggota grup konsolidasi.")

    show_elimination_column = fields.Boolean(
        string='Tampilkan Kolom Eliminasi',
        default=True,
        help="Menampilkan kolom eliminasi transaksi antar-perusahaan.")

    show_nci_split = fields.Boolean(
        string='Pisahkan Alokasi Induk vs NCI',
        default=True,
        help="Memisahkan alokasi laba bersih antara Pemilik Entitas Induk dan Kepentingan Non-Pengendali.")

    display_currency_id = fields.Many2one(
        'res.currency',
        string='Mata Uang Tampilan',
        help="Jika kosong, mengikuti mata uang pelaporan grup.")

    rounding = fields.Float(
        string='Faktor Pembulatan',
        default=1.0,
        help="1 untuk angka penuh, 1.000 untuk ribuan, 1.000.000 untuk jutaan.")

    menu_id = fields.Many2one('ir.ui.menu', string='Menu Navigasi Terkait', ondelete='set null')
    action_id = fields.Many2one('ir.actions.client', string='Aksi Klien Terkait', ondelete='set null')

    header_text = fields.Html(string='Teks Kop Surat / Header Laporan')
    footer_text = fields.Html(string='Teks Catatan Kaki / Footer Laporan')

    line_ids = fields.One2many(
        'consol.report.line',
        'report_id',
        string='Baris Laporan Keuangan')

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        for rec in records:
            rec._sync_report_menu()
            rec._sync_report_accounts()
        return records

    def write(self, vals):
        res = super().write(vals)
        if any(f in vals for f in ['name', 'sequence', 'report_type']):
            for rec in self:
                rec._sync_report_menu()
        return res

    def unlink(self):
        menus = self.mapped('menu_id')
        actions = self.mapped('action_id')
        res = super().unlink()
        menus.unlink()
        actions.unlink()
        return res

    def _sync_report_menu(self):
        Menu = self.env['ir.ui.menu'].sudo()
        Action = self.env['ir.actions.client'].sudo()
        parent_menu = self.env.ref('odoo_psak_consolidation.menu_consolidation_reports', raise_if_not_found=False)
        if not parent_menu:
            parent_menu = Menu.search([('name', 'in', ['Laporan Keuangan', 'Reporting'])], limit=1)

        for report in self:
            # Periksa apakah sudah ada menu statis yang sama di XML
            xml_record = self.env['ir.model.data'].sudo().search([
                ('model', '=', 'consol.report'),
                ('res_id', '=', report.id)
            ], limit=1)

            # Jika ini template standar yang sudah dipetakan di menu_views.xml, jangan duplikat menu
            standard_report_types = ['balance_sheet', 'profit_loss', 'cash_flow', 'equity_changes', 'worksheet']
            if xml_record and report.report_type in standard_report_types:
                continue

            action_vals = {
                'name': report.name,
                'tag': 'consol_report_viewer_action',
                'target': 'current',
                'context': {
                    'default_report_id': report.id,
                    'default_report_type': report.report_type,
                    'default_period_id': 'all',
                }
            }
            if report.action_id and report.action_id.exists():
                report.action_id.write(action_vals)
                action = report.action_id
            else:
                action = Action.create(action_vals)
                report.action_id = action.id

            menu_vals = {
                'name': report.name,
                'parent_id': parent_menu.id if parent_menu else False,
                'action': f'ir.actions.client,{action.id}',
                'sequence': report.sequence or 10,
            }
            if report.menu_id and report.menu_id.exists():
                report.menu_id.write(menu_vals)
            else:
                menu = Menu.create(menu_vals)
                report.menu_id = menu.id

    def action_sync_accounts_to_lines(self):
        """
        Secara cerdas memindai seluruh akun konsolidasi dan menghubungkannya
        ke baris laporan yang sesuai berdasarkan klasifikasi standar akuntansi.
        """
        for report in self:
            report._sync_report_accounts()
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Akun Berhasil Disinkronisasi'),
                'message': _('Akun konsolidasi telah berhasil dipetakan ke baris laporan.'),
                'type': 'success',
                'sticky': False,
            }
        }

    @api.model
    def sync_all_reports_accounts(self):
        """Class method to sync all active report templates in the system."""
        reports = self.search([])
        for r in reports:
            r._sync_report_accounts()

    def _sync_report_accounts(self):
        self.ensure_one()
        all_accs = self.env['consol.account'].search([])
        if not all_accs:
            return

        for line in self.line_ids:
            if line.line_type != 'accounts':
                continue
            code = line.code
            matched = self.env['consol.account']
            if self.report_type == 'balance_sheet':
                if code == 'CASH':
                    matched = all_accs.filtered(lambda a: a.account_type == 'asset_cash' or a.code.startswith(('101', '111')))
                elif code == 'AR':
                    matched = all_accs.filtered(lambda a: a.account_type == 'asset_receivable' and not a.is_intercompany and not a.code.endswith('90'))
                elif code == 'AR_IC':
                    matched = all_accs.filtered(lambda a: a.is_intercompany and a.code.startswith(('103', '11210090', '1129')))
                elif code == 'INV':
                    matched = all_accs.filtered(lambda a: a.code.startswith(('104', '113')) and a.statement == 'bs')
                elif code == 'FA':
                    matched = all_accs.filtered(lambda a: (a.account_type in ['asset_fixed', 'asset_non_current'] or a.code.startswith(('151', '152', '122'))) and not a.code.startswith(('117', '170', '160')))
                elif code == 'GW':
                    matched = all_accs.filtered(lambda a: a.code in ['160000', 'GW'] or 'goodwill' in (a.name or '').lower())
                elif code == 'INV_SUB':
                    matched = all_accs.filtered(lambda a: a.code in ['170000', '11700010'] or 'investment in sub' in (a.name or '').lower() or 'investasi pada entitas' in (a.name or '').lower())
                elif code == 'AP':
                    matched = all_accs.filtered(lambda a: a.account_type == 'liability_payable' and not a.is_intercompany and not a.code.endswith('90'))
                elif code == 'AP_IC':
                    matched = all_accs.filtered(lambda a: a.is_intercompany and a.code.startswith(('202', '21100090', '2119')))
                elif code == 'EQ_PARENT':
                    matched = all_accs.filtered(lambda a: a.account_type in ['equity', 'equity_unaffected'] and a.code not in ['305000', '701000'] and 'non-controlling' not in (a.name or '').lower())
                elif code == 'NCI_EQ':
                    matched = all_accs.filtered(lambda a: a.code in ['305000'] or ('non-controlling' in (a.name or '').lower() and a.statement == 'bs'))
                elif code == 'CURR_NI':
                    matched = all_accs.filtered(lambda a: a.statement == 'pl' or a.account_type in ['income', 'income_other', 'expense', 'expense_other', 'expense_depreciation', 'expense_direct_cost'])

            elif self.report_type == 'profit_loss':
                if code == 'REV':
                    matched = all_accs.filtered(lambda a: a.account_type in ['income', 'income_other'] or a.code.startswith(('401', '402', '410')))
                elif code == 'COGS':
                    matched = all_accs.filtered(lambda a: a.account_type == 'expense_direct_cost' or a.code.startswith(('501', '502', '510')))
                elif code == 'OPEX':
                    matched = all_accs.filtered(lambda a: (a.account_type in ['expense', 'expense_other', 'expense_depreciation'] or a.code.startswith(('601', '602', '611', '671'))) and a.code != '701000' and not a.code.startswith('5'))
                elif code == 'NCI_ATTRIB':
                    matched = all_accs.filtered(lambda a: a.code == '701000' or ('non-controlling' in (a.name or '').lower() and a.statement == 'pl'))

            elif self.report_type == 'cash_flow':
                if code == 'CF_NI':
                    matched = all_accs.filtered(lambda a: a.statement == 'pl')
                elif code == 'CF_DEPR':
                    matched = all_accs.filtered(lambda a: a.account_type == 'expense_depreciation' or a.code.startswith(('602', '671')))

            elif self.report_type == 'equity_changes':
                if code == 'EQ_CAP':
                    matched = all_accs.filtered(lambda a: a.code == '301000' or 'share capital' in (a.name or '').lower() or 'modal saham' in (a.name or '').lower())
                elif code == 'EQ_PREM':
                    matched = all_accs.filtered(lambda a: a.code == '302000' or 'premium' in (a.name or '').lower() or 'agio' in (a.name or '').lower())
                elif code == 'EQ_RE':
                    matched = all_accs.filtered(lambda a: a.code == '303000' or 'retained' in (a.name or '').lower() or 'saldo laba' in (a.name or '').lower())
                elif code == 'EQ_NCI':
                    matched = all_accs.filtered(lambda a: a.code == '305000' or 'non-controlling' in (a.name or '').lower())

            elif self.report_type == 'worksheet':
                if code == 'WS_ASSETS':
                    matched = all_accs.filtered(lambda a: a.statement == 'bs' and (a.account_type.startswith('asset') or a.code.startswith('1')))
                elif code == 'WS_LIAB':
                    matched = all_accs.filtered(lambda a: a.statement == 'bs' and (a.account_type.startswith('liability') or a.code.startswith('2')))
                elif code == 'WS_EQ':
                    matched = all_accs.filtered(lambda a: a.statement in ['bs', 'equity'] and (a.account_type in ['equity', 'equity_unaffected'] or a.code.startswith('3')))

            if matched:
                line.write({'account_ids': [(6, 0, matched.ids)]})

    def get_report_matrix(self, period_id=False, date_from=False, date_to=False, comparison=None, show_entities=None, show_elimination=None):
        """
        Menghasilkan matriks tabel laporan keuangan konsolidasi lengkap:
        - Mendukung pilihan periode spesifik, akumulasi 'all' (periode awal s/d saat ini), atau rentang tanggal (date_from s/d date_to).
        - Kolom: Info, Entitas 1..N, Eliminasi, Total Konsolidasi, Perbandingan.
        - Baris: Struktur hirarki laporan keuangan dengan rumus dan drill-down.
        """
        self.ensure_one()

        # 1. Tentukan Periode Konsolidasi yang Terlibat
        Period = self.env['consol.period']
        periods = Period.browse()

        if period_id and str(period_id).lower() != 'all':
            try:
                p_rec = Period.browse(int(period_id))
                if p_rec.exists():
                    periods = p_rec
            except (ValueError, TypeError):
                pass

        if not periods:
            # Jika period_id == 'all' atau tidak diberikan, atau ada filter tanggal kustom
            domain = []
            if date_from:
                domain.append(('date_to', '>=', date_from))
            if date_to:
                domain.append(('date_from', '<=', date_to))

            if self.group_id:
                domain.append(('group_id', '=', self.group_id.id))

            periods = Period.search(domain, order='date_to asc, id asc')

            # Jika masih kosong, ambil seluruh periode yang ada
            if not periods:
                periods = Period.search([], order='date_to asc, id asc')

        if not periods:
            return {
                'report_id': self.id,
                'report_name': self.name,
                'report_type': self.report_type,
                'period_id': period_id or 'all',
                'period_name': 'Belum Ada Periode',
                'group_name': self.group_id.name if self.group_id else '-',
                'currency_symbol': 'Rp',
                'date_from': str(date_from or ''),
                'date_to': str(date_to or ''),
                'columns': [],
                'lines': [],
            }

        # Tentukan periode representasi dan grup
        latest_period = periods[-1]
        earliest_period = periods[0]
        group = latest_period.group_id or self.group_id or earliest_period.group_id

        # Teks label periode tampilan
        if period_id and str(period_id).lower() != 'all' and len(periods) == 1:
            period_display_name = latest_period.name
            eff_date_from = str(latest_period.date_from)
            eff_date_to = str(latest_period.date_to)
        elif date_from or date_to:
            period_display_name = f"{date_from or str(earliest_period.date_from)} s/d {date_to or str(latest_period.date_to)}"
            eff_date_from = str(date_from or earliest_period.date_from)
            eff_date_to = str(date_to or latest_period.date_to)
        else:
            period_display_name = f"Semua Periode ({earliest_period.name} s/d {latest_period.name})"
            eff_date_from = str(earliest_period.date_from)
            eff_date_to = str(latest_period.date_to)

        # 2. Entitas Terlibat
        active_entities = self.env['consol.entity']
        for p in periods:
            active_entities |= p._get_active_entities()
        if not active_entities and group:
            active_entities = group.entity_ids
            if group.parent_entity_id:
                active_entities |= group.parent_entity_id

        # Flag opsi tampilan
        do_show_entities = show_entities if show_entities is not None else self.show_entity_columns
        do_show_elim = show_elimination if show_elimination is not None else self.show_elimination_column
        mode_comparison = comparison if comparison is not None else self.comparison
        rounding_factor = self.rounding or 1.0

        # Siapkan kolom
        columns = []
        if do_show_entities:
            for entity in active_entities:
                columns.append({
                    'id': f'entity_{entity.id}',
                    'name': entity.code or entity.name,
                    'type': 'entity',
                    'entity_id': entity.id,
                })

        if do_show_elim:
            columns.append({
                'id': 'elimination',
                'name': 'Eliminasi',
                'type': 'elimination',
            })

        columns.append({
            'id': 'consolidated',
            'name': 'Total Konsolidasi',
            'type': 'consolidated',
        })

        # 3. Hitung Saldo Trial Balance per (entity_id, consol_account_id)
        entity_acc_balances = {}

        # Pos Neraca: posisi kumulatif pada periode terakhir (closing balance)
        tb_lines_bs = self.env['consol.trial.balance.line'].search([
            ('period_id', '=', latest_period.id),
            ('statement', 'in', ['bs', 'equity'])
        ])
        for l in tb_lines_bs:
            entity_acc_balances[(l.entity_id.id, l.consol_account_id.id)] = (
                entity_acc_balances.get((l.entity_id.id, l.consol_account_id.id), 0.0) + l.balance_rc
            )

        # Pos Laba Rugi & OCI: akumulasi kinerja dari seluruh periode terpilih (movement across periods)
        tb_lines_pl = self.env['consol.trial.balance.line'].search([
            ('period_id', 'in', periods.ids),
            ('statement', 'in', ['pl', 'oci'])
        ])
        for l in tb_lines_pl:
            entity_acc_balances[(l.entity_id.id, l.consol_account_id.id)] = (
                entity_acc_balances.get((l.entity_id.id, l.consol_account_id.id), 0.0) + l.balance_rc
            )

        # 4. Hitung Saldo Eliminasi
        elim_acc_balances = {}

        # Jurnal Eliminasi Neraca (E1, E2, dll pada latest period)
        j_lines_bs = self.env['consol.journal.line'].search([
            ('period_id', '=', latest_period.id),
            ('journal_id.state', '=', 'posted'),
            ('consol_account_id.statement', 'in', ['bs', 'equity'])
        ])
        for jl in j_lines_bs:
            net = jl.debit - jl.credit
            elim_acc_balances[jl.consol_account_id.id] = elim_acc_balances.get(jl.consol_account_id.id, 0.0) + net

        # Jurnal Eliminasi Laba Rugi (E3, E6, E7 pada seluruh periode terpilih)
        j_lines_pl = self.env['consol.journal.line'].search([
            ('period_id', 'in', periods.ids),
            ('journal_id.state', '=', 'posted'),
            ('consol_account_id.statement', 'in', ['pl', 'oci'])
        ])
        for jl in j_lines_pl:
            net = jl.debit - jl.credit
            elim_acc_balances[jl.consol_account_id.id] = elim_acc_balances.get(jl.consol_account_id.id, 0.0) + net

        # 5. Penanganan Perbandingan (Comparison)
        prev_entity_acc_balances = {}
        prev_elim_acc_balances = {}
        prev_active_entities = []
        has_comparison = False
        comp_label = "Sebelumnya"

        if mode_comparison == 'previous_period' and group:
            prev_p = Period.search([
                ('group_id', '=', group.id),
                ('date_to', '<', earliest_period.date_from)
            ], order='date_to desc', limit=1)
            if prev_p:
                has_comparison = True
                comp_label = f"Sebelumnya ({prev_p.name})"
                prev_active_entities = prev_p._get_active_entities()
                prev_tb = self.env['consol.trial.balance.line'].search([('period_id', '=', prev_p.id)])
                for l in prev_tb:
                    prev_entity_acc_balances[(l.entity_id.id, l.consol_account_id.id)] = (
                        prev_entity_acc_balances.get((l.entity_id.id, l.consol_account_id.id), 0.0) + l.balance_rc
                    )
                prev_jl = self.env['consol.journal.line'].search([
                    ('period_id', '=', prev_p.id),
                    ('journal_id.state', '=', 'posted')
                ])
                for jl in prev_jl:
                    net = jl.debit - jl.credit
                    prev_elim_acc_balances[jl.consol_account_id.id] = prev_elim_acc_balances.get(jl.consol_account_id.id, 0.0) + net

        elif mode_comparison == 'same_period_last_year' and group and earliest_period.date_from:
            # 1 Tahun lalu
            y_start = earliest_period.date_from.replace(year=earliest_period.date_from.year - 1)
            y_end = latest_period.date_to.replace(year=latest_period.date_to.year - 1)
            prev_p = Period.search([
                ('group_id', '=', group.id),
                ('date_to', '>=', y_start),
                ('date_from', '<=', y_end)
            ], order='date_to desc', limit=1)
            if prev_p:
                has_comparison = True
                comp_label = f"Tahun Lalu ({prev_p.name})"
                prev_active_entities = prev_p._get_active_entities()
                prev_tb = self.env['consol.trial.balance.line'].search([('period_id', '=', prev_p.id)])
                for l in prev_tb:
                    prev_entity_acc_balances[(l.entity_id.id, l.consol_account_id.id)] = (
                        prev_entity_acc_balances.get((l.entity_id.id, l.consol_account_id.id), 0.0) + l.balance_rc
                    )
                prev_jl = self.env['consol.journal.line'].search([
                    ('period_id', '=', prev_p.id),
                    ('journal_id.state', '=', 'posted')
                ])
                for jl in prev_jl:
                    net = jl.debit - jl.credit
                    prev_elim_acc_balances[jl.consol_account_id.id] = prev_elim_acc_balances.get(jl.consol_account_id.id, 0.0) + net

        if has_comparison:
            columns.append({
                'id': 'prev_consolidated',
                'name': comp_label,
                'type': 'prev_consolidated',
            })
            columns.append({
                'id': 'variance',
                'name': 'Perubahan (Selisih)',
                'type': 'variance',
            })

        # 6. Hitung Baris Laporan & Rincian Akun (Unfold Data)
        tb_source_map = {}
        tb_records = self.env['consol.trial.balance.line'].search([
            ('period_id', 'in', periods.ids)
        ])
        for tb_rec in tb_records:
            acc_id = tb_rec.consol_account_id.id
            if acc_id not in tb_source_map:
                tb_source_map[acc_id] = []
            src_name = tb_rec.source_account_id.display_name if tb_rec.source_account_id else (tb_rec.external_name or tb_rec.external_code or tb_rec.consol_account_id.name)
            existing = next((item for item in tb_source_map[acc_id] if item['entity_id'] == tb_rec.entity_id.id and item['source_name'] == src_name), None)
            if existing:
                existing['balance_rc'] += tb_rec.balance_rc
            else:
                tb_source_map[acc_id].append({
                    'entity_id': tb_rec.entity_id.id,
                    'entity_name': tb_rec.entity_id.name,
                    'source_name': src_name,
                    'balance_rc': tb_rec.balance_rc,
                })

        lines_data = []
        code_eval_context_per_col = {col['id']: {} for col in columns}
        current_headers = {}  # level -> line_id

        for rline in self.line_ids.sorted('sequence'):
            # Hirarki Header untuk Fold/Unfold
            if rline.line_type == 'header':
                keys_to_del = [lvl for lvl in current_headers if lvl >= rline.level]
                for k in keys_to_del:
                    del current_headers[k]
                parent_ids = list(current_headers.values())
                current_headers[rline.level] = rline.id
            else:
                if rline.line_type in ['formula', 'total']:
                    keys_to_del = [lvl for lvl in current_headers if lvl > rline.level]
                    for k in keys_to_del:
                        del current_headers[k]
                parent_ids = list(current_headers.values())

            row = {
                'id': rline.id,
                'name': rline.name,
                'code': rline.code or '',
                'level': rline.level,
                'line_type': rline.line_type,
                'note': rline.note or '',
                'bold': rline.bold,
                'italic': rline.italic,
                'underline': rline.underline,
                'drilldown': rline.drilldown,
                'parent_ids': parent_ids,
                'is_header': (rline.line_type == 'header'),
                'can_unfold': False,
                'account_details': [],
                'values': {},
            }

            if rline.line_type in ['header', 'blank']:
                for col in columns:
                    row['values'][col['id']] = ''
                lines_data.append(row)
                continue

            target_accounts = None
            sign_multiplier = 1.0
            if rline.line_type == 'accounts':
                target_accounts = rline.get_target_accounts()
                sign_multiplier = -1.0 if rline.balance_sign == 'reverse' else 1.0

            # Hitung nilai per kolom untuk baris utama
            for col in columns:
                val = 0.0
                if col['type'] == 'variance':
                    c_val = row['values'].get('consolidated', 0.0) or 0.0
                    p_val = row['values'].get('prev_consolidated', 0.0) or 0.0
                    val = c_val - p_val

                elif rline.line_type == 'accounts' and target_accounts:
                    if col['type'] == 'entity':
                        for acc in target_accounts:
                            val += entity_acc_balances.get((col['entity_id'], acc.id), 0.0)
                        val = val * sign_multiplier

                    elif col['type'] == 'elimination':
                        for acc in target_accounts:
                            val += elim_acc_balances.get(acc.id, 0.0)
                        val = val * sign_multiplier

                    elif col['type'] == 'consolidated':
                        tot = 0.0
                        for ent in active_entities:
                            for acc in target_accounts:
                                tot += entity_acc_balances.get((ent.id, acc.id), 0.0)
                        for acc in target_accounts:
                            tot += elim_acc_balances.get(acc.id, 0.0)
                        val = tot * sign_multiplier

                    elif col['type'] == 'prev_consolidated':
                        tot = 0.0
                        for ent in prev_active_entities:
                            for acc in target_accounts:
                                tot += prev_entity_acc_balances.get((ent.id, acc.id), 0.0)
                        for acc in target_accounts:
                            tot += prev_elim_acc_balances.get(acc.id, 0.0)
                        val = tot * sign_multiplier

                elif rline.line_type in ['formula', 'total']:
                    formula_expr = rline.formula or ''
                    if formula_expr:
                        ctx = code_eval_context_per_col[col['id']]
                        try:
                            val = float(safe_eval(formula_expr, ctx))
                        except Exception:
                            val = 0.0

                # Pembulatan
                rounded_val = val / rounding_factor if rounding_factor else val
                row['values'][col['id']] = rounded_val

                if rline.code:
                    code_eval_context_per_col[col['id']][rline.code] = rounded_val

            # Hitung rincian detail akun (account_details) untuk unfold
            if rline.line_type == 'accounts' and target_accounts:
                acc_details = []
                for acc in target_accounts:
                    acc_row = {
                        'id': f"acc_{rline.id}_{acc.id}",
                        'account_id': acc.id,
                        'code': acc.code or '',
                        'name': acc.name or '',
                        'display_name': f"[{acc.code}] {acc.name}" if acc.code else acc.name,
                        'level': rline.level + 1,
                        'values': {},
                        'source_details': [],
                    }
                    has_acc_val = False
                    for col in columns:
                        a_val = 0.0
                        if col['type'] == 'entity':
                            a_val = entity_acc_balances.get((col['entity_id'], acc.id), 0.0) * sign_multiplier
                        elif col['type'] == 'elimination':
                            a_val = elim_acc_balances.get(acc.id, 0.0) * sign_multiplier
                        elif col['type'] == 'consolidated':
                            a_tot = sum(entity_acc_balances.get((ent.id, acc.id), 0.0) for ent in active_entities)
                            a_tot += elim_acc_balances.get(acc.id, 0.0)
                            a_val = a_tot * sign_multiplier
                        elif col['type'] == 'prev_consolidated':
                            a_tot = sum(prev_entity_acc_balances.get((ent.id, acc.id), 0.0) for ent in prev_active_entities)
                            a_tot += prev_elim_acc_balances.get(acc.id, 0.0)
                            a_val = a_tot * sign_multiplier
                        elif col['type'] == 'variance':
                            c_val = acc_row['values'].get('consolidated', 0.0) or 0.0
                            p_val = acc_row['values'].get('prev_consolidated', 0.0) or 0.0
                            a_val = c_val - p_val

                        rnd_a_val = a_val / rounding_factor if rounding_factor else a_val
                        acc_row['values'][col['id']] = rnd_a_val
                        if rnd_a_val and rnd_a_val != 0:
                            has_acc_val = True

                    # Tambahkan akun sumber lokal per entitas
                    src_items = tb_source_map.get(acc.id, [])
                    if src_items:
                        acc_row['source_details'] = [
                            {
                                'entity_id': s['entity_id'],
                                'entity_name': s['entity_name'],
                                'source_name': s['source_name'],
                                'balance_rc': (s['balance_rc'] * sign_multiplier) / (rounding_factor or 1.0)
                            }
                            for s in src_items
                        ]

                    if has_acc_val or len(target_accounts) == 1:
                        acc_details.append(acc_row)

                row['account_details'] = acc_details
                row['can_unfold'] = bool(acc_details)

            lines_data.append(row)

        entity_names_str = ", ".join(active_entities.mapped('name')) if active_entities else (group.name if group else '-')

        return {
            'report_id': self.id,
            'report_name': self.name,
            'report_type': self.report_type,
            'period_id': period_id or 'all',
            'period_name': period_display_name,
            'date_from': eff_date_from,
            'date_to': eff_date_to,
            'group_name': group.name if group else '-',
            'entity_names': entity_names_str,
            'currency_symbol': group.currency_id.symbol if (group and group.currency_id) else 'Rp',
            'columns': columns,
            'lines': lines_data,
        }


class ConsolReportLine(models.Model):
    _name = 'consol.report.line'
    _description = 'Konfigurasi Baris Template Laporan'
    _order = 'sequence, id'

    report_id = fields.Many2one(
        'consol.report',
        string='Template Laporan',
        required=True,
        ondelete='cascade')

    sequence = fields.Integer(string='Urutan', default=10)
    name = fields.Char(string='Nama / Uraian Pos Baris', required=True)
    code = fields.Char(string='Kode Baris (Untuk Rumus)', size=20,
                       help="Contoh: GP, OPEX, EBIT, NI. Dapat dijadikan variabel referensi pada baris rumus lain.")

    level = fields.Integer(
        string='Tingkat Indentasi',
        default=1,
        help="0 = Judul Utama, 1 = Sub-Kategori / Rincian, 2 = Subtotal.")

    line_type = fields.Selection([
        ('header', 'Judul / Header (Tanpa Angka)'),
        ('accounts', 'Penggabungan Akun Konsolidasi'),
        ('formula', 'Rumus / Perhitungan'),
        ('total', 'Subtotal / Total Akhir'),
        ('blank', 'Baris Kosong (Pemisah)')
    ], string='Tipe Baris', default='accounts', required=True)

    account_ids = fields.Many2many(
        'consol.account',
        'consol_report_line_acc_rel',
        'line_id',
        'account_id',
        string='Akun Konsolidasi Terpilih')

    account_filter = fields.Char(
        string='Domain Filter Akun',
        help="Opsi pemilihan akun alternatif via domain kode (contoh: [('code', '=like', '1-1%')]).")

    formula = fields.Char(
        string='Rumus Perhitungan',
        help="Contoh: GP - OPEX, NI * 0.8, REV - COGS. Mendukung +, -, *, / dan kode baris.")

    balance_sign = fields.Selection([
        ('natural', 'Alami (Debit Positif, Kredit Negatif)'),
        ('reverse', 'Terbalik (Kredit Positif - untuk Pendapatan, Liabilitas, Ekuitas)')
    ], string='Sifat Tanda Saldo', default='natural', required=True)

    bold = fields.Boolean(string='Cetak Tebal', default=False)
    italic = fields.Boolean(string='Cetak Miring', default=False)
    underline = fields.Boolean(string='Garis Bawah', default=False)
    print_blank_if_zero = fields.Boolean(string='Cetak Kosong Jika Nol', default=False)
    page_break = fields.Boolean(string='Ganti Halaman (Page Break)', default=False)
    hide_if_zero = fields.Boolean(string='Sembunyikan Jika Nol', default=False)
    drilldown = fields.Boolean(string='Aktifkan Drill-Down', default=True)
    note = fields.Char(string='No. Catatan Kaki (CALK)', help="Nomor referensi Catatan atas Laporan Keuangan.")

    def get_target_accounts(self):
        self.ensure_one()
        accounts = self.account_ids
        if self.account_filter:
            try:
                domain = safe_eval(self.account_filter)
                accounts |= self.env['consol.account'].search(domain)
            except Exception:
                pass
        return accounts


class ConsolCashflowMapping(models.Model):
    _name = 'consol.cashflow.mapping'
    _description = 'Pemetaan Akun Neraca ke Laporan Arus Kas Konsolidasi'
    _order = 'category, consol_account_id'

    consol_account_id = fields.Many2one(
        'consol.account',
        string='Akun Konsolidasi',
        required=True,
        ondelete='cascade',
        help="Akun konsolidasi neraca yang dipetakan ke arus kas.")

    category = fields.Selection([
        ('operating', 'Aktivitas Operasi'),
        ('investing', 'Aktivitas Investasi'),
        ('financing', 'Aktivitas Pendanaan')
    ], string='Kategori Arus Kas', required=True)

    sign = fields.Selection([
        ('1', 'Normal (+ Pergerakan)'),
        ('-1', 'Terbalik (- Pergerakan)')
    ], string='Arah Dampak Kas', default='-1', required=True)
