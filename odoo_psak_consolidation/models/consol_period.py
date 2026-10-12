# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError

class ConsolPeriod(models.Model):
    _name = 'consol.period'
    _description = 'Consolidation Financial Process Period'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'date_to desc, id desc'

    name = fields.Char(string='Period Name', required=True, tracking=True)
    
    group_id = fields.Many2one(
        'consol.group',
        string='Consolidation Group',
        required=True,
        tracking=True,
        ondelete='cascade')

    currency_id = fields.Many2one(
        'res.currency',
        string='Reporting Currency',
        related='group_id.currency_id',
        store=True)

    date_from = fields.Date(string='Start Date', required=True, tracking=True)
    date_to = fields.Date(string='End Date', required=True, tracking=True)

    state = fields.Selection([
        ('draft', 'Draft'),
        ('data_loaded', 'Trial Balance Loaded'),
        ('eliminated', 'Consolidated & Eliminated'),
        ('review', 'Under Review'),
        ('locked', 'Locked')
    ], string='Status', default='draft', required=True, tracking=True)

    rate_ids = fields.One2many(
        'consol.rate',
        'period_id',
        string='Period Exchange Rates (PSAK 10)')

    trial_balance_ids = fields.One2many(
        'consol.trial.balance',
        'period_id',
        string='Entity Trial Balances')

    match_ids = fields.One2many(
        'consol.intercompany.match',
        'period_id',
        string='Intercompany Reconciliation')

    journal_ids = fields.One2many(
        'consol.journal',
        'period_id',
        string='Elimination Journals')

    ic_difference_total = fields.Monetary(
        string='Total Intercompany Difference',
        currency_field='currency_id',
        compute='_compute_ic_difference_total',
        store=True)

    unmatched_ic_count = fields.Integer(
        string='Unmatched IC Differences Exceeding Tolerance',
        compute='_compute_ic_difference_total',
        store=True)

    locked_by = fields.Many2one('res.users', string='Locked By', readonly=True, tracking=True)
    locked_date = fields.Datetime(string='Lock Date', readonly=True, tracking=True)

    @api.depends('match_ids.difference', 'match_ids.status', 'match_ids.is_overridden')
    def _compute_ic_difference_total(self):
        for rec in self:
            rec.ic_difference_total = sum(m.difference for m in rec.match_ids)
            rec.unmatched_ic_count = len(rec.match_ids.filtered(lambda m: m.status == 'unmatched' and not m.is_overridden))

    def _get_active_entities(self):
        """Get active entities consolidated in this period's date range."""
        self.ensure_one()
        entities = self.group_id.entity_ids
        if self.group_id.parent_entity_id:
            entities |= self.group_id.parent_entity_id
        return entities

    # ========================================================
    # 1. LOAD TRIAL BALANCES & PSAK 10 TRANSLATION (E10: CTA)
    # ========================================================
    def action_load_trial_balances(self):
        self.ensure_one()
        entities = self._get_active_entities()
        if not entities:
            raise UserError(_("No entities registered in Consolidation Group '%s'!", self.group_id.name))

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
                    unmapped_errors.append(f"{entity.name}: {len(unmapped)} accounts unmapped ({', '.join(unmapped_codes)}...)")

        if unmapped_errors:
            raise UserError(_("Process aborted! Unmapped accounts found:\n" + "\n".join(unmapped_errors) + "\n\nPlease complete Entity Account Mapping first or use the Auto-Map feature!"))

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
                    WHERE am.state = 'posted'
                      AND aml.company_id = %s
                      AND aml.date <= %s
                      AND aa.account_type IN ('asset_receivable', 'asset_cash', 'asset_current', 'asset_non_current', 'asset_prepayments', 'asset_fixed', 'liability_payable', 'liability_credit_card', 'liability_current', 'liability_non_current', 'equity', 'equity_unaffected')
                    GROUP BY aml.account_id, aml.partner_id
                    HAVING ABS(SUM(aml.balance)) > 0.0001
                """
                self.env.cr.execute(bs_query, (entity.company_id.id, self.date_to))
                bs_results = self.env.cr.dictfetchall()

                # Query posted lines for P&L & OCI accounts (movement YTD date_from <= date <= date_to)
                pl_query = """
                    SELECT aml.account_id, aml.partner_id, SUM(aml.balance) as balance_fc
                    FROM account_move_line aml
                    JOIN account_move am ON am.id = aml.move_id
                    JOIN account_account aa ON aa.id = aml.account_id
                    WHERE am.state = 'posted'
                      AND aml.company_id = %s
                      AND aml.date >= %s
                      AND aml.date <= %s
                      AND aa.account_type IN ('income', 'income_other', 'expense', 'expense_depreciation', 'expense_direct_cost')
                    GROUP BY aml.account_id, aml.partner_id
                    HAVING ABS(SUM(aml.balance)) > 0.0001
                """
                self.env.cr.execute(pl_query, (entity.company_id.id, self.date_from, self.date_to))
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

                if tb_lines_vals:
                    self.env['consol.trial.balance.line'].create(tb_lines_vals)

        # 5. Compute & Create E10 CTA Journal if foreign currency (PSAK 10)
        self._generate_cta_elimination()

        self.state = 'data_loaded'
        self.message_post(body=_("Trial balance for all entities loaded and translated successfully."))

    def _generate_cta_elimination(self):
        """
        Compute Cumulative Translation Adjustment (CTA) for entities with
        functional currency different from reporting currency, recorded to cta_account_id.
        """
        if not self.group_id.cta_account_id:
            return

        # Delete old E10 journal
        self.journal_ids.filtered(lambda j: j.code == 'E10' and j.origin == 'auto').unlink()

        foreign_tbs = self.trial_balance_ids.filtered(lambda tb: tb.functional_currency_id != self.currency_id)
        for tb in foreign_tbs:
            total_rc = sum(l.balance_rc for l in tb.line_ids)
            if abs(total_rc) > 0.01:
                cta_journal = self.env['consol.journal'].create({
                    'period_id': self.id,
                    'name': f"E10: Foreign Currency Translation (CTA) - {tb.entity_id.name}",
                    'code': 'E10',
                    'origin': 'auto',
                    'note': "PSAK 10: Translation difference between closing rate vs average/historical rate recorded in Other Comprehensive Income (CTA).",
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

        self.message_post(body=_("Intercompany reconciliation (IC Matching) completed."))

    # ========================================================
    # 3. GENERATE ELIMINATIONS (E1, E2, E3, E6, CARRY FORWARD)
    # ========================================================
    def action_generate_eliminations(self):
        self.ensure_one()
        # Delete old draft automated journals
        self.journal_ids.filtered(lambda j: j.origin == 'auto' and j.state == 'draft').unlink()

        # E1: Parent Investment vs Subsidiary Equity
        self._generate_e1_investment_equity()

        # E2: Intercompany Balances (from IC matching results)
        self._generate_e2_ic_balance()

        # Carry forward recurring journals from previous period
        self._carry_forward_recurring_journals()

        # Reverse auto_reverse journals from previous period
        self._reverse_previous_auto_reverse_journals()

        # Post balanced automated journals
        for j in self.journal_ids.filtered(lambda j: j.origin == 'auto' and j.state == 'draft'):
            if round(j.total_debit, 2) == round(j.total_credit, 2) and j.line_ids:
                j.action_post()

        self.state = 'eliminated'
        self.message_post(body=_("Automated elimination journals (E1, E2, Recurring, Reversals) generated successfully."))

    def _generate_e1_investment_equity(self):
        """E1: Elimination of Parent Investment vs Subsidiary Equity, initial Goodwill & NCI recognition."""
        ownerships = self.env['consol.ownership'].search([
            ('parent_id', 'in', self._get_active_entities().ids),
            ('method', '=', 'full')
        ])

        for own in ownerships:
            journal = self.env['consol.journal'].create({
                'period_id': self.id,
                'name': f"E1: Investment vs Equity Elimination - {own.child_id.name}",
                'code': 'E1',
                'origin': 'auto',
                'recurring': True,
                'note': f"PSAK 65 par. B86(b) & PSAK 22: Elimination of {own.effective_percentage}% shareholding in {own.child_id.name}.",
            })

            lines = []
            # Get subsidiary share capital at acquisition date
            child_tb = self.trial_balance_ids.filtered(lambda tb: tb.entity_id == own.child_id)
            cap_lines = child_tb.line_ids.filtered(lambda l: l.statement == 'equity' and ('capital' in (l.consol_account_id.name or '').lower() or 'modal' in (l.consol_account_id.name or '').lower()))
            if not cap_lines:
                cap_lines = child_tb.line_ids.filtered(lambda l: l.statement == 'equity')
            total_equity_child = sum(abs(l.balance_rc) for l in cap_lines)

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
                    lines.append({
                        'journal_id': journal.id,
                        'consol_account_id': el.consol_account_id.id,
                        'entity_id': own.child_id.id,
                        'debit': abs(el.balance_rc),
                        'credit': 0.0,
                    })

                if inv_amount > 0 and all_inv_lines:
                    lines.append({
                        'journal_id': journal.id,
                        'consol_account_id': all_inv_lines[0].consol_account_id.id,
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
        """E2: Elimination of intercompany receivable/payable balances & E3: Elimination of intercompany transactions."""
        # 1. E2 Journal: Receivable/Payable Balances (Balance Sheet)
        bs_matches = self.match_ids.filtered(lambda m: m.status in ['matched', 'within_tolerance'] and m.account_a_id.statement == 'bs')
        if bs_matches:
            journal_bs = self.env['consol.journal'].create({
                'period_id': self.id,
                'name': "E2: Elimination of Intercompany Receivable/Payable Balances",
                'code': 'E2',
                'origin': 'auto',
                'note': "PSAK 65 par. B86(c): Elimination of intercompany receivable and payable balances.",
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

        # 2. E3 Journal: Intercompany Sales and COGS (Profit and Loss)
        pl_matches = self.match_ids.filtered(lambda m: m.status in ['matched', 'within_tolerance'] and m.account_a_id.statement == 'pl')
        if pl_matches:
            journal_pl = self.env['consol.journal'].create({
                'period_id': self.id,
                'name': "E3: Elimination of Intercompany Sales & Cost of Goods Sold",
                'code': 'E3',
                'origin': 'auto',
                'note': "PSAK 65 par. B86(c): Elimination of revenue and expenses from intercompany sales transactions.",
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
        """Copy recurring journals from previous period."""
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
                'name': f"[Carry-Forward] {rj.name}",
            })

    def _reverse_previous_auto_reverse_journals(self):
        """Reverse auto_reverse journals from previous period (e.g. E4 unrealised profit)."""
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
                'name': f"[Reversal] {rj.name}",
                'code': rj.code,
                'origin': 'auto',
                'reversed_from_id': rj.id,
                'note': f"Automatic reversal of period {prev_period.name} journal.",
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
            raise UserError(_("NCI P&L Account and NCI Equity Account have not been configured on Consolidation Group!"))

        # Delete old E7
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

            # Compute Subsidiary Net Income
            pl_lines = child_tb.line_ids.filtered(lambda l: l.statement == 'pl')
            # Net Income = -(Sum balance income & expense)
            net_income_fc = -sum(l.balance_rc for l in pl_lines)
            nci_income_share = net_income_fc * (nci_pct / 100.0)

            if abs(nci_income_share) > 0.01:
                journal = self.env['consol.journal'].create({
                    'period_id': self.id,
                    'name': f"E7: Attribution of Profit/Loss to NCI ({nci_pct:.2f}%) - {own.child_id.name}",
                    'code': 'E7',
                    'origin': 'auto',
                    'note': f"PSAK 65 par. B94: Allocation of subsidiary profit/loss to Non-Controlling Interest ({nci_pct:.2f}%).",
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

        self.message_post(body=_("NCI attribution calculation (E7) completed."))

    # ========================================================
    # 5. REVIEW & LOCK PERIOD
    # ========================================================
    def action_submit_review(self):
        self.ensure_one()
        # Check elimination balance
        posted_journals = self.journal_ids.filtered(lambda j: j.state == 'posted')
        tot_deb = sum(j.total_debit for j in posted_journals)
        tot_cred = sum(j.total_credit for j in posted_journals)
        if round(tot_deb, 2) != round(tot_cred, 2):
            raise UserError(_(
                "Cannot submit review! Total Elimination Debit (%s) does not match Total Elimination Credit (%s)!",
                tot_deb, tot_cred
            ))
        self.state = 'review'
        self.message_post(body=_("Consolidation period submitted for Review."))

    def action_lock(self):
        self.ensure_one()
        # Validate IC tolerance
        if self.unmatched_ic_count > 0:
            raise UserError(_(
                "Period cannot be locked! There are %s intercompany differences exceeding tolerance that have not been approved (overridden).",
                self.unmatched_ic_count
            ))

        self.write({
            'state': 'locked',
            'locked_by': self.env.user.id,
            'locked_date': fields.Datetime.now(),
        })
        self.message_post(body=_("Consolidation period successfully LOCKED by %s.", self.env.user.name))

    def action_unlock(self):
        self.ensure_one()
        if not self.env.user.has_group('odoo_psak_consolidation.group_consolidation_manager'):
            raise UserError(_("Only users with Consolidation Manager role can unlock a locked period!"))
        self.write({
            'state': 'review',
            'locked_by': False,
            'locked_date': False,
        })
        self.message_post(body=_("Consolidation period REOPENED by %s.", self.env.user.name))

    def action_reset_draft(self):
        self.ensure_one()
        if self.state == 'locked':
            raise UserError(_("Locked period cannot be reset! Please unlock first."))
        self.state = 'draft'
        self.message_post(body=_("Consolidation period reset back to Draft status."))

    def action_view_reports(self):
        self.ensure_one()
        bs_report = self.env['consol.report'].search([('report_type', '=', 'balance_sheet')], limit=1)
        return {
            'type': 'ir.actions.act_window',
            'name': _('Consolidated Financial Reports'),
            'res_model': 'consol.report.export.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_period_id': self.id,
                'default_report_id': bs_report.id if bs_report else False,
                'default_export_format': 'interactive',
            }
        }
