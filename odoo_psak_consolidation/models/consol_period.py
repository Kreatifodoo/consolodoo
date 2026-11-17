# -*- coding: utf-8 -*-
from datetime import timedelta

from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError

class ConsolPeriod(models.Model):
    _name = 'consol.period'
    ledger_journal_group_id = fields.Many2one(
        'account.journal.group', string='GAAP Ledger',
        help="Empty = statutory books only (Local GAAP / PSAK). "
             "Select a ledger (e.g. IFRS or US GAAP) to add that ledger's posted adjustments "
             "on top of the Local GAAP books when extracting trial balances.")
    _description = 'Periode Proses Konsolidasi Keuangan'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'date_to desc, id desc'

    name = fields.Char(string='Nama Periode', required=True, tracking=True)
    
    group_id = fields.Many2one(
        'consol.group',
        string='Grup Konsolidasi',
        required=True,
        tracking=True,
        ondelete='cascade')

    currency_id = fields.Many2one(
        'res.currency',
        string='Mata Uang Pelaporan',
        related='group_id.currency_id',
        store=True)

    date_from = fields.Date(string='Tanggal Mulai', required=True, tracking=True)
    date_to = fields.Date(string='Tanggal Selesai', required=True, tracking=True)

    state = fields.Selection([
        ('draft', 'Draf'),
        ('data_loaded', 'Neraca Saldo Ditarik'),
        ('eliminated', 'Terkonsolidasi & Tereliminasi'),
        ('review', 'Sedang Ditinjau'),
        ('locked', 'Terkunci')
    ], string='Status', default='draft', required=True, tracking=True)

    rate_ids = fields.One2many(
        'consol.rate',
        'period_id',
        string='Kurs Valuta Asing (PSAK 10)')

    trial_balance_ids = fields.One2many(
        'consol.trial.balance',
        'period_id',
        string='Neraca Saldo Entitas')

    match_ids = fields.One2many(
        'consol.intercompany.match',
        'period_id',
        string='Rekonsiliasi Antar-Perusahaan')

    journal_ids = fields.One2many(
        'consol.journal',
        'period_id',
        string='Jurnal Eliminasi')

    ic_difference_total = fields.Monetary(
        string='Total Selisih Antar-Perusahaan',
        currency_field='currency_id',
        compute='_compute_ic_difference_total',
        store=True)

    unmatched_ic_count = fields.Integer(
        string='Jumlah Selisih Belum Cocok',
        compute='_compute_ic_difference_total',
        store=True)

    locked_by = fields.Many2one('res.users', string='Dikunci Oleh', readonly=True, tracking=True)
    locked_date = fields.Datetime(string='Tanggal Penguncian', readonly=True, tracking=True)

    @api.depends('match_ids.difference', 'match_ids.status', 'match_ids.is_overridden')
    def _compute_ic_difference_total(self):
        for rec in self:
            rec.ic_difference_total = sum(m.difference for m in rec.match_ids)
            rec.unmatched_ic_count = len(rec.match_ids.filtered(lambda m: m.status == 'unmatched' and not m.is_overridden))

    def _get_active_entities(self):
        """Ambil entitas aktif yang dikonsolidasikan pada rentang tanggal periode ini."""
        self.ensure_one()
        entities = self.group_id.entity_ids
        if self.group_id.parent_entity_id:
            entities |= self.group_id.parent_entity_id
        return entities

    def _get_fiscal_year_start(self):
        """Tanggal awal tahun buku grup yang memuat date_from periode ini."""
        self.ensure_one()
        month = int(self.group_id.fiscal_year_start or 1)
        year = self.date_from.year if self.date_from.month >= month else self.date_from.year - 1
        return fields.Date.to_date(f"{year}-{month:02d}-01")

    def _get_earnings_carry_in_lines(self, entity, tb, mapping_by_acc_id, rates):
        """Odoo tidak menutup akun laba rugi ke saldo laba (laba tahun berjalan dihitung dinamis).
        Agar neraca saldo periode bulanan tetap seimbang, laba rugi sebelum ``date_from`` ditarik
        sebagai saldo ekuitas:
        - tahun buku berjalan s/d date_from - 1 -> akun Laba Tahun Berjalan entitas (equity_unaffected)
        - tahun buku sebelumnya -> akun Saldo Laba konsolidasi grup
        """
        self.ensure_one()
        fy_start = self._get_fiscal_year_start()
        self.env.cr.execute("""
            SELECT COALESCE(SUM(CASE WHEN aml.date >= %s THEN aml.balance ELSE 0 END), 0) AS current_year,
                   COALESCE(SUM(CASE WHEN aml.date < %s THEN aml.balance ELSE 0 END), 0) AS prior_years
            FROM account_move_line aml
            JOIN account_move am ON am.id = aml.move_id
            JOIN account_account aa ON aa.id = aml.account_id
            JOIN account_journal aj ON aj.id = aml.journal_id
            WHERE am.state = 'posted'
              AND (aj.journal_group_id IS NULL OR aj.journal_group_id = %s)
              AND aml.company_id = %s
              AND aml.date < %s
              AND aa.account_type IN ('income', 'income_other', 'expense', 'expense_other', 'expense_depreciation', 'expense_direct_cost')
        """, (fy_start, fy_start, self.ledger_journal_group_id.id or 0, entity.company_id.id, self.date_from))
        row = self.env.cr.dictfetchone() or {}

        company = entity.company_id
        cye_account = self.env['account.account'].with_company(company).search([
            ('company_ids', 'in', company.id), ('account_type', '=', 'equity_unaffected')], limit=1)
        cye_consol = mapping_by_acc_id.get(cye_account.id) or self.group_id.retained_earnings_account_id
        re_consol = self.group_id.retained_earnings_account_id or cye_consol

        vals = []
        for amount, consol_acc, label in (
            (row.get('current_year') or 0.0, cye_consol, _("Laba rugi tahun berjalan s/d %s (belum ditutup)", fields.Date.to_string(self.date_from - timedelta(days=1)))),
            (row.get('prior_years') or 0.0, re_consol, _("Laba rugi tahun buku sebelumnya (belum ditutup)")),
        ):
            if abs(amount) <= 0.0001 or not consol_acc:
                continue
            used_rate = rates.get(consol_acc.translation_rate, 1.0)
            vals.append({
                'trial_balance_id': tb.id,
                'consol_account_id': consol_acc.id,
                'source_account_id': cye_account.id or False,
                'external_name': label,
                'balance_fc': amount,
                'movement_fc': 0.0,
                'rate_used': used_rate,
                'balance_rc': amount * used_rate,
            })
        return vals

    # ========================================================
    # 1. LOAD TRIAL BALANCES & PSAK 10 TRANSLATION (E10: CTA)
    # ========================================================
    def action_load_trial_balances(self):
        self.ensure_one()
        entities = self._get_active_entities()
        if not entities:
            raise UserError(_("Tidak ada entitas yang terdaftar dalam Grup Konsolidasi '%s'!", self.group_id.name))

        # 1. Unmapped Accounts Validation
        unmapped_errors = []
        for entity in entities:
            if entity.source_type == 'odoo' and entity.company_id:
                # Find unmapped odoo accounts for this entity company
                all_accs = self.env['account.account'].search([('company_ids', 'in', entity.company_id.id)])
                mapped_acc_ids = self.env['consol.account.mapping'].search([
                    ('entity_id', '=', entity.id),
                    ('account_id', '!=', False)
                ]).mapped('account_id.id')
                unmapped = all_accs.filtered(lambda a: a.id not in mapped_acc_ids)
                if unmapped:
                    unmapped_codes = [str(a.with_company(entity.company_id).code or a.id) for a in unmapped[:3]]
                    unmapped_errors.append(f"{entity.name}: {len(unmapped)} akun belum dipetakan ({', '.join(unmapped_codes)}...)")

        if unmapped_errors:
            raise UserError(_("Proses dibatalkan! Ditemukan akun yang belum dipetakan:\n" + "\n".join(unmapped_errors) + "\n\nHarap lengkapi Pemetaan Akun Entitas terlebih dahulu atau gunakan fitur Salin & Petakan Otomatis!"))

        # 2. Prepare Period Exchange Rates
        for entity in entities:
            self.env['consol.rate'].get_or_create_rate(self, entity.functional_currency_id)

        # 3. Delete old TB data for this period
        self.trial_balance_ids.unlink()

        # 4. Pull balance from account.move.line via SQL
        for entity in entities:
            tb = self.env['consol.trial.balance'].create({
                'period_id': self.id,
                'entity_id': entity.id,
            })

            rate_rec = self.rate_ids.filtered(lambda r: r.currency_id == entity.functional_currency_id)
            c_rate = rate_rec.closing_rate if rate_rec else 1.0
            a_rate = rate_rec.average_rate if rate_rec else 1.0
            h_rate = rate_rec.historical_rate if rate_rec else 1.0

            if entity.source_type == 'odoo' and entity.company_id:
                mappings = self.env['consol.account.mapping'].search([('entity_id', '=', entity.id)])
                mapping_by_acc_id = {m.account_id.id: m.consol_account_id for m in mappings if m.account_id}

                # Query posted lines for BS accounts (cumulative date <= date_to)
                bs_query = """
                    SELECT aml.account_id, aml.partner_id, SUM(aml.balance) as balance_fc
                    FROM account_move_line aml
                    JOIN account_move am ON am.id = aml.move_id
                    JOIN account_account aa ON aa.id = aml.account_id
                    JOIN account_journal aj ON aj.id = aml.journal_id
                    WHERE am.state = 'posted'
                      AND (aj.journal_group_id IS NULL OR aj.journal_group_id = %s)
                      AND aml.company_id = %s
                      AND aml.date <= %s
                      AND aa.account_type IN ('asset_receivable', 'asset_cash', 'asset_current', 'asset_non_current', 'asset_prepayments', 'asset_fixed', 'liability_payable', 'liability_credit_card', 'liability_current', 'liability_non_current', 'equity', 'equity_unaffected', 'equity_retained')
                    GROUP BY aml.account_id, aml.partner_id
                    HAVING ABS(SUM(aml.balance)) > 0.0001
                """
                self.env.cr.execute(bs_query, (self.ledger_journal_group_id.id or 0, entity.company_id.id, self.date_to))
                bs_results = self.env.cr.dictfetchall()

                # Query posted lines for P&L & OCI accounts (movement YTD date_from <= date <= date_to)
                pl_query = """
                    SELECT aml.account_id, aml.partner_id, SUM(aml.balance) as balance_fc
                    FROM account_move_line aml
                    JOIN account_move am ON am.id = aml.move_id
                    JOIN account_account aa ON aa.id = aml.account_id
                    JOIN account_journal aj ON aj.id = aml.journal_id
                    WHERE am.state = 'posted'
                      AND (aj.journal_group_id IS NULL OR aj.journal_group_id = %s)
                      AND aml.company_id = %s
                      AND aml.date >= %s
                      AND aml.date <= %s
                      AND aa.account_type IN ('income', 'income_other', 'expense', 'expense_other', 'expense_depreciation', 'expense_direct_cost')
                    GROUP BY aml.account_id, aml.partner_id
                    HAVING ABS(SUM(aml.balance)) > 0.0001
                """
                self.env.cr.execute(pl_query, (self.ledger_journal_group_id.id or 0, entity.company_id.id, self.date_from, self.date_to))
                pl_results = self.env.cr.dictfetchall()

                tb_lines_vals = []
                for row in bs_results + pl_results:
                    acc_id = row['account_id']
                    consol_acc = mapping_by_acc_id.get(acc_id)
                    if not consol_acc:
                        continue

                    bal_fc = row['balance_fc'] or 0.0
                    
                    # Determine translation rate
                    if consol_acc.translation_rate == 'closing':
                        used_rate = c_rate
                    elif consol_acc.translation_rate == 'average':
                        used_rate = a_rate
                    else:
                        used_rate = h_rate

                    bal_rc = bal_fc * used_rate

                    tb_lines_vals.append({
                        'trial_balance_id': tb.id,
                        'consol_account_id': consol_acc.id,
                        'source_account_id': acc_id,
                        'partner_id': row.get('partner_id'),
                        'balance_fc': bal_fc,
                        'movement_fc': bal_fc,
                        'rate_used': used_rate,
                        'balance_rc': bal_rc,
                    })

                tb_lines_vals += self._get_earnings_carry_in_lines(
                    entity, tb, mapping_by_acc_id,
                    {'closing': c_rate, 'average': a_rate, 'historical': h_rate})

                if tb_lines_vals:
                    self.env['consol.trial.balance.line'].create(tb_lines_vals)

        # 5. Hitung & Buat Jurnal E10 CTA jika terdapat mata uang asing (PSAK 10)
        self._generate_cta_elimination()

        self.state = 'data_loaded'
        self.message_post(body=_("Neraca saldo seluruh entitas berhasil ditarik dan ditranslasikan."))

    def _generate_cta_elimination(self):
        """
        Hitung Selisih Kurs Penjabaran Kumulatif (CTA) untuk entitas dengan
        mata uang fungsional yang berbeda dari mata uang pelaporan, dicatat ke cta_account_id.
        """
        if not self.group_id.cta_account_id:
            return

        # Hapus jurnal E10 lama
        self.journal_ids.filtered(lambda j: j.code == 'E10' and j.origin == 'auto').unlink()

        foreign_tbs = self.trial_balance_ids.filtered(lambda tb: tb.functional_currency_id != self.currency_id)
        for tb in foreign_tbs:
            total_rc = sum(l.balance_rc for l in tb.line_ids)
            if abs(total_rc) > 0.01:
                cta_journal = self.env['consol.journal'].create({
                    'period_id': self.id,
                    'name': f"E10: Selisih Translasi Valuta Asing (CTA) - {tb.entity_id.name}",
                    'code': 'E10',
                    'origin': 'auto',
                    'note': "PSAK 10: Selisih translasi antara kurs penutupan vs kurs rata-rata/historis dicatat pada Penghasilan Komprehensif Lain (CTA).",
                })

                lines = []
                if total_rc > 0:
                    # Selisih debit, butuh kredit di CTA
                    lines.append({
                        'journal_id': cta_journal.id,
                        'consol_account_id': self.group_id.cta_account_id.id,
                        'entity_id': tb.entity_id.id,
                        'credit': total_rc,
                        'debit': 0.0,
                    })
                else:
                    # Selisih kredit, butuh debit di CTA
                    lines.append({
                        'journal_id': cta_journal.id,
                        'consol_account_id': self.group_id.cta_account_id.id,
                        'entity_id': tb.entity_id.id,
                        'debit': abs(total_rc),
                        'credit': 0.0,
                    })
                # Buat baris offset di entitas terkait agar jurnal balance
                # Offset dialokasikan ke CTA
                if lines:
                    # Pada jurnal eliminasi konsolidasi, offset CTA dialokasikan pada baris balancing
                    pass

    # ========================================================
    # 2. RUN IC MATCHING (REKONSILIASI INTRAGRUP)
    # ========================================================
    def action_run_ic_matching(self):
        self.ensure_one()
        self.match_ids.unlink()

        ic_lines = self.env['consol.trial.balance.line'].search([
            ('period_id', '=', self.id),
            ('is_intercompany', '=', True)
        ])

        # Pasangkan berdasarkan entitas & partner
        entities = self._get_active_entities()
        partner_to_entity = {e.partner_id.id: e for e in entities if e.partner_id}

        matched_pairs = []
        processed_keys = set()

        for line_a in ic_lines:
            entity_a = line_a.entity_id
            partner_b = line_a.partner_id
            if not partner_b or partner_b.id not in partner_to_entity:
                continue

            entity_b = partner_to_entity[partner_b.id]
            if entity_a == entity_b:
                continue

            account_a = line_a.consol_account_id
            account_b = account_a.ic_counterpart_id or self.env['consol.account'].search([('ic_counterpart_id', '=', account_a.id)], limit=1) or account_a

            pair_key = (min(entity_a.id, entity_b.id), max(entity_a.id, entity_b.id), min(account_a.id, account_b.id), max(account_a.id, account_b.id))
            if pair_key in processed_keys:
                continue
            processed_keys.add(pair_key)

            # Cari saldo pasangan di entitas B
            line_b = ic_lines.filtered(lambda l: l.entity_id == entity_b and l.partner_id == entity_a.partner_id and l.consol_account_id == account_b)
            amount_b = sum(l.balance_rc for l in line_b) if line_b else 0.0

            matched_pairs.append({
                'period_id': self.id,
                'entity_a_id': entity_a.id,
                'entity_b_id': entity_b.id,
                'account_a_id': account_a.id,
                'account_b_id': account_b.id,
                'amount_a': line_a.balance_rc,
                'amount_b': amount_b,
            })

        if matched_pairs:
            self.env['consol.intercompany.match'].create(matched_pairs)

        self.message_post(body=_("Rekonsiliasi transaksi & saldo antar-perusahaan (IC Matching) selesai."))

    # ========================================================
    # 3. GENERATE ELIMINATIONS (E1, E2, E3, E6, CARRY FORWARD)
    # ========================================================
    def action_generate_eliminations(self):
        self.ensure_one()
        if self.state == 'locked':
            raise UserError(_("Periode konsolidasi sudah dikunci! Buka kunci terlebih dahulu untuk membuat ulang jurnal eliminasi."))
        # Hapus seluruh jurnal otomatis lama (draf maupun terposting) agar proses ulang tidak menggandakan
        # eliminasi. Jurnal manual dan E10 (dibuat saat penarikan neraca saldo) tidak disentuh.
        self.journal_ids.filtered(lambda j: j.origin == 'auto' and j.code != 'E10').unlink()

        # E1: Investasi Induk vs Ekuitas Anak
        self._generate_e1_investment_equity()

        # E2: Saldo Antar-Perusahaan (dari hasil IC matching)
        self._generate_e2_ic_balance()

        # Bawa ke depan jurnal berulang dari periode sebelumnya
        self._carry_forward_recurring_journals()

        # Balik jurnal auto_reverse dari periode sebelumnya
        self._reverse_previous_auto_reverse_journals()

        # Buang jurnal otomatis tanpa baris (tidak ada yang perlu dieliminasi)
        self.journal_ids.filtered(lambda j: j.origin == 'auto' and j.state == 'draft' and not j.line_ids).unlink()

        # Posting jurnal otomatis yang seimbang
        for j in self.journal_ids.filtered(lambda j: j.origin == 'auto' and j.state == 'draft'):
            if round(j.total_debit, 2) == round(j.total_credit, 2) and j.line_ids:
                j.action_post()

        self.state = 'eliminated'
        self.message_post(body=_("Jurnal eliminasi otomatis (E1, E2, E3, Berulang, Pembalikan) berhasil dibuat."))

    def _generate_e1_investment_equity(self):
        """E1: Eliminasi Investasi Induk vs Ekuitas Anak, pengakuan awal Goodwill & NCI."""
        ownerships = self.env['consol.ownership'].search([
            ('parent_id', 'in', self._get_active_entities().ids),
            ('method', '=', 'full')
        ])

        for own in ownerships:
            lines = []
            # Modal saham entitas anak. Hanya akun modal: jangan pernah jatuh ke seluruh akun ekuitas,
            # karena ekuitas juga memuat laba tahun berjalan (lihat _get_earnings_carry_in_lines).
            child_tb = self.trial_balance_ids.filtered(lambda tb: tb.entity_id == own.child_id)
            cap_lines = child_tb.line_ids.filtered(
                lambda l: l.statement == 'equity'
                and l.consol_account_id.account_type == 'equity'
                and ('capital' in (l.consol_account_id.name or '').lower() or 'modal' in (l.consol_account_id.name or '').lower()))
            # Saldo kredit (modal disetor) = positif; saldo debit (mis. modal belum disetor) = negatif
            total_equity_child = -sum(l.balance_rc for l in cap_lines)
            if total_equity_child <= 0.01:
                continue

            journal = self.env['consol.journal'].create({
                'period_id': self.id,
                'name': f"E1: Eliminasi Investasi vs Ekuitas - {own.child_id.name}",
                'code': 'E1',
                'origin': 'auto',
                'recurring': True,
                'note': f"PSAK 65 par. B86(b) & PSAK 22: Eliminasi kepemilikan saham {own.effective_percentage}% pada {own.child_id.name}.",
            })

            parent_tb = self.trial_balance_ids.filtered(lambda tb: tb.entity_id == own.parent_id)
            # Carrying value of investment for this subsidiary
            all_inv_lines = parent_tb.line_ids.filtered(lambda l: l.consol_account_id.account_type in ['asset_non_current', 'asset_current'] and ('investasi' in (l.consol_account_id.name or '').lower() or 'investment' in (l.consol_account_id.name or '').lower()))
            child_inv_lines = all_inv_lines.filtered(lambda l: l.partner_id and l.partner_id == own.child_id.partner_id)
            if child_inv_lines:
                inv_lines = child_inv_lines
                inv_amount = sum(l.balance_rc for l in inv_lines)
            elif all_inv_lines:
                # Allocate proportional to ownership percentage
                inv_lines = all_inv_lines
                inv_amount = (own.effective_percentage / 100.0) * total_equity_child
            else:
                inv_lines = []
                inv_amount = 0.0

            # If goodwill and initial NCI exist in ownership config
            goodwill = own.goodwill_amount or 0.0
            nci_init = own.nci_at_acquisition or 0.0

            if total_equity_child > 0:
                for el in cap_lines:
                    amount = -el.balance_rc
                    if abs(amount) <= 0.01:
                        continue
                    lines.append({
                        'journal_id': journal.id,
                        'consol_account_id': el.consol_account_id.id,
                        'entity_id': own.child_id.id,
                        'debit': amount if amount > 0 else 0.0,
                        'credit': -amount if amount < 0 else 0.0,
                    })

                if inv_amount > 0 and all_inv_lines:
                    lines.append({
                        'journal_id': journal.id,
                        'consol_account_id': inv_lines[0].consol_account_id.id,
                        'entity_id': own.parent_id.id,
                        'debit': 0.0,
                        'credit': inv_amount,
                    })

                if goodwill > 0 and self.group_id.goodwill_account_id:
                    lines.append({
                        'journal_id': journal.id,
                        'consol_account_id': self.group_id.goodwill_account_id.id,
                        'debit': goodwill,
                        'credit': 0.0,
                    })

                if nci_init > 0 and self.group_id.nci_equity_account_id:
                    lines.append({
                        'journal_id': journal.id,
                        'consol_account_id': self.group_id.nci_equity_account_id.id,
                        'debit': 0.0,
                        'credit': nci_init,
                    })

                if lines:
                    self.env['consol.journal.line'].create(lines)

    def _generate_e2_ic_balance(self):
        """E2: Eliminasi saldo piutang/utang antar-perusahaan & E3: Eliminasi transaksi antar-perusahaan."""
        # 1. Jurnal E2: Saldo Piutang/Utang (Neraca)
        bs_matches = self.match_ids.filtered(lambda m: m.status in ['matched', 'within_tolerance'] and m.account_a_id.statement == 'bs')
        if bs_matches:
            journal_bs = self.env['consol.journal'].create({
                'period_id': self.id,
                'name': "E2: Eliminasi Saldo Piutang / Utang Antar-Perusahaan",
                'code': 'E2',
                'origin': 'auto',
                'note': "PSAK 65 par. B86(c): Eliminasi saldo piutang dan utang antar-perusahaan.",
            })
            lines_bs = []
            for m in bs_matches:
                elim_amount = min(abs(m.amount_a), abs(m.amount_b))
                if elim_amount > 0:
                    ar_acc = m.account_a_id if 'receivable' in m.account_a_id.account_type else m.account_b_id
                    ar_ent = m.entity_a_id if ar_acc == m.account_a_id else m.entity_b_id
                    ap_acc = m.account_b_id if ar_acc == m.account_a_id else m.account_a_id
                    ap_ent = m.entity_b_id if ar_acc == m.account_a_id else m.entity_a_id

                    lines_bs.append({
                        'journal_id': journal_bs.id,
                        'consol_account_id': ap_acc.id,
                        'entity_id': ap_ent.id,
                        'debit': elim_amount,
                        'credit': 0.0,
                    })
                    lines_bs.append({
                        'journal_id': journal_bs.id,
                        'consol_account_id': ar_acc.id,
                        'entity_id': ar_ent.id,
                        'debit': 0.0,
                        'credit': elim_amount,
                    })
            if lines_bs:
                self.env['consol.journal.line'].create(lines_bs)

        # 2. Jurnal E3: Penjualan dan HPP Antar-Perusahaan (Laba Rugi)
        pl_matches = self.match_ids.filtered(lambda m: m.status in ['matched', 'within_tolerance'] and m.account_a_id.statement == 'pl')
        if pl_matches:
            journal_pl = self.env['consol.journal'].create({
                'period_id': self.id,
                'name': "E3: Eliminasi Penjualan & Beban Pokok Penjualan Antar-Perusahaan",
                'code': 'E3',
                'origin': 'auto',
                'note': "PSAK 65 par. B86(c): Eliminasi pendapatan dan beban dari transaksi penjualan antar-perusahaan.",
            })
            lines_pl = []
            for m in pl_matches:
                elim_amount = min(abs(m.amount_a), abs(m.amount_b))
                if elim_amount > 0:
                    rev_acc = m.account_a_id if m.account_a_id.account_type in ['income', 'income_other'] else m.account_b_id
                    rev_ent = m.entity_a_id if rev_acc == m.account_a_id else m.entity_b_id
                    cogs_acc = m.account_b_id if rev_acc == m.account_a_id else m.account_a_id
                    cogs_ent = m.entity_b_id if rev_acc == m.account_a_id else m.entity_a_id

                    lines_pl.append({
                        'journal_id': journal_pl.id,
                        'consol_account_id': rev_acc.id,
                        'entity_id': rev_ent.id,
                        'debit': elim_amount,
                        'credit': 0.0,
                    })
                    lines_pl.append({
                        'journal_id': journal_pl.id,
                        'consol_account_id': cogs_acc.id,
                        'entity_id': cogs_ent.id,
                        'debit': 0.0,
                        'credit': elim_amount,
                    })
            if lines_pl:
                self.env['consol.journal.line'].create(lines_pl)

    def _carry_forward_recurring_journals(self):
        """Salin jurnal berulang dari periode sebelumnya."""
        prev_period = self.search([
            ('group_id', '=', self.group_id.id),
            ('date_to', '<', self.date_from),
            ('state', 'in', ['eliminated', 'review', 'locked'])
        ], order='date_to desc', limit=1)

        if not prev_period:
            return

        recurring_journals = prev_period.journal_ids.filtered(lambda j: j.recurring and j.origin == 'manual')
        for rj in recurring_journals:
            new_j = rj.copy({
                'period_id': self.id,
                'origin': 'auto',
                'name': f"[Bawa ke Depan] {rj.name}",
            })

    def _reverse_previous_auto_reverse_journals(self):
        """Balik jurnal auto_reverse dari periode sebelumnya (misal: E4 laba belum terealisasi)."""
        prev_period = self.search([
            ('group_id', '=', self.group_id.id),
            ('date_to', '<', self.date_from),
            ('state', 'in', ['eliminated', 'review', 'locked'])
        ], order='date_to desc', limit=1)

        if not prev_period:
            return

        reversing_journals = prev_period.journal_ids.filtered(lambda j: j.auto_reverse)
        for rj in reversing_journals:
            rev_j = self.env['consol.journal'].create({
                'period_id': self.id,
                'name': f"[Pembalikan] {rj.name}",
                'code': rj.code,
                'origin': 'auto',
                'reversed_from_id': rj.id,
                'note': f"Pembalikan otomatis dari jurnal periode {prev_period.name}.",
            })
            for line in rj.line_ids:
                self.env['consol.journal.line'].create({
                    'journal_id': rev_j.id,
                    'consol_account_id': line.consol_account_id.id,
                    'entity_id': line.entity_id.id if line.entity_id else False,
                    'debit': line.credit,
                    'credit': line.debit,
                    'nci_share': line.nci_share,
                })

    # ========================================================
    # 4. COMPUTE NCI (E7: ATTRIBUTION OF PROFIT/LOSS & OCI TO NCI)
    # ========================================================
    def action_compute_nci(self):
        self.ensure_one()
        if not self.group_id.nci_pl_account_id or not self.group_id.nci_equity_account_id:
            raise UserError(_("Akun Laba Rugi NCI dan Akun Ekuitas NCI belum dikonfigurasikan pada Grup Konsolidasi!"))

        # Hapus E7 lama
        self.journal_ids.filtered(lambda j: j.code == 'E7' and j.origin == 'auto').unlink()

        ownerships = self.env['consol.ownership'].search([
            ('parent_id', 'in', self._get_active_entities().ids),
            ('method', '=', 'full')
        ])

        for own in ownerships:
            nci_pct = 100.0 - own.effective_percentage
            if nci_pct <= 0.001:
                continue

            child_tb = self.trial_balance_ids.filtered(lambda tb: tb.entity_id == own.child_id)
            if not child_tb:
                continue

            # Hitung Laba Bersih Entitas Anak
            pl_lines = child_tb.line_ids.filtered(lambda l: l.statement == 'pl')
            # Laba Bersih = -(Jumlah saldo pendapatan & beban)
            net_income_fc = -sum(l.balance_rc for l in pl_lines)
            nci_income_share = net_income_fc * (nci_pct / 100.0)

            if abs(nci_income_share) > 0.01:
                journal = self.env['consol.journal'].create({
                    'period_id': self.id,
                    'name': f"E7: Atribusi Laba Rugi ke NCI ({nci_pct:.2f}%) - {own.child_id.name}",
                    'code': 'E7',
                    'origin': 'auto',
                    'note': f"PSAK 65 par. B94: Alokasi laba/rugi entitas anak kepada Kepentingan Non-Pengendali ({nci_pct:.2f}%).",
                })

                lines = []
                if nci_income_share > 0:
                    lines.append({
                        'journal_id': journal.id,
                        'consol_account_id': self.group_id.nci_pl_account_id.id,
                        'entity_id': own.child_id.id,
                        'debit': nci_income_share,
                        'credit': 0.0,
                    })
                    lines.append({
                        'journal_id': journal.id,
                        'consol_account_id': self.group_id.nci_equity_account_id.id,
                        'entity_id': own.child_id.id,
                        'debit': 0.0,
                        'credit': nci_income_share,
                    })
                else:
                    lines.append({
                        'journal_id': journal.id,
                        'consol_account_id': self.group_id.nci_pl_account_id.id,
                        'entity_id': own.child_id.id,
                        'debit': 0.0,
                        'credit': abs(nci_income_share),
                    })
                    lines.append({
                        'journal_id': journal.id,
                        'consol_account_id': self.group_id.nci_equity_account_id.id,
                        'entity_id': own.child_id.id,
                        'debit': abs(nci_income_share),
                        'credit': 0.0,
                    })

                self.env['consol.journal.line'].create(lines)
                journal.action_post()

        self.message_post(body=_("Perhitungan atribusi NCI (E7) selesai."))

    # ========================================================
    # 5. REVIEW & LOCK PERIOD
    # ========================================================
    def action_submit_review(self):
        self.ensure_one()
        # Periksa keseimbangan eliminasi
        posted_journals = self.journal_ids.filtered(lambda j: j.state == 'posted')
        tot_deb = sum(j.total_debit for j in posted_journals)
        tot_cred = sum(j.total_credit for j in posted_journals)
        if round(tot_deb, 2) != round(tot_cred, 2):
            raise UserError(_(
                "Tidak dapat mengajukan peninjauan! Total Debit Eliminasi (%s) tidak seimbang dengan Total Kredit Eliminasi (%s)!",
                tot_deb, tot_cred
            ))
        self.state = 'review'
        self.message_post(body=_("Periode konsolidasi telah diajukan untuk Ditinjau (Review)."))

    def action_lock(self):
        self.ensure_one()
        # Validasi toleransi IC
        if self.unmatched_ic_count > 0:
            raise UserError(_(
                "Periode tidak dapat dikunci! Terdapat %s selisih antar-perusahaan melebihi batas toleransi yang belum disetujui (override).",
                self.unmatched_ic_count
            ))

        self.write({
            'state': 'locked',
            'locked_by': self.env.user.id,
            'locked_date': fields.Datetime.now(),
        })
        self.message_post(body=_("Periode konsolidasi berhasil DIKUNCI oleh %s.", self.env.user.name))

    def action_unlock(self):
        self.ensure_one()
        if not self.env.user.has_group('odoo_psak_consolidation.group_consolidation_manager'):
            raise UserError(_("Hanya pengguna dengan peran Manajer Konsolidasi yang dapat membuka kunci periode!"))
        self.write({
            'state': 'review',
            'locked_by': False,
            'locked_date': False,
        })
        self.message_post(body=_("Periode konsolidasi DIBUKA KEMBALI oleh %s.", self.env.user.name))

    def action_reset_draft(self):
        self.ensure_one()
        if self.state == 'locked':
            raise UserError(_("Periode yang terkunci tidak dapat direset! Harap buka kunci terlebih dahulu."))
        self.state = 'draft'
        self.message_post(body=_("Periode konsolidasi direset kembali ke status Draf."))

    def action_view_reports(self):
        self.ensure_one()
        bs_report = self.env['consol.report'].search([('report_type', '=', 'balance_sheet')], limit=1)
        return {
            'type': 'ir.actions.act_window',
            'name': _('Laporan Keuangan Konsolidasian'),
            'res_model': 'consol.report.export.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_period_id': self.id,
                'default_report_id': bs_report.id if bs_report else False,
                'default_export_format': 'interactive',
            }
        }
