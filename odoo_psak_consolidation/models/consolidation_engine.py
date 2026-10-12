from odoo import models, fields, api

class ConsolidationEngine(models.TransientModel):
    _name = 'consolidation.engine'
    _description = 'Consolidation Execution Engine'

    period_id = fields.Many2one('consolidation.period', string='Period', required=True)

    def action_aggregate_data(self):
        self.ensure_one()
        period = self.period_id
        group = period.group_id
        
        # Clear existing TB journal lines for this period
        self.env['consolidation.journal.line'].search([
            ('period_id', '=', period.id),
            ('line_type', '=', 'tb')
        ]).unlink()
        
        journal_lines = []
        
        # Get COA mappings
        coa_maps = self.env['consolidation.coa.map'].search([])
        map_dict = {}
        for m in coa_maps:
            for sub_c in m.subsidiary_company_ids:
                for sub_a in m.subsidiary_account_ids:
                    map_dict[(sub_c.id, sub_a.id)] = m
        
        # Get rates
        rates = {r.currency_id.id: r for r in period.rate_ids}
        
        # Include parent company and all subsidiaries
        all_companies = group.parent_company_id | group.company_ids.mapped('company_id')
        
        for sub in all_companies:
            
            # Check if this sub acts as a parent in another consolidation group for the SAME date range
            sub_period = self.env['consolidation.period'].search([
                ('group_id.parent_company_id', '=', sub.id),
                ('date_start', '=', period.date_start),
                ('date_end', '=', period.date_end),
                ('state', 'in', ['done', 'consolidating'])
            ], limit=1)
            
            tb_lines = []
            if sub_period:
                self.env.cr.execute("""
                    SELECT group_account_id, SUM(translated_balance) as balance
                    FROM consolidation_journal_line
                    WHERE period_id = %s AND group_account_id IS NOT NULL
                    GROUP BY group_account_id
                """, (sub_period.id,))
                tb_lines = self.env.cr.dictfetchall()
            else:
                self.env.cr.execute("""
                    SELECT account_id, SUM(debit) as debit, SUM(credit) as credit, SUM(balance) as balance
                    FROM account_move_line
                    WHERE company_id = %s AND parent_state = 'posted' AND date >= %s AND date <= %s
                    GROUP BY account_id
                """, (sub.id, period.date_start, period.date_end))
                tb_lines = self.env.cr.dictfetchall()
            
            for line in tb_lines:
                account_id = line.get('account_id', False)
                group_account_id = line.get('group_account_id', False)
                balance = line['balance']
                
                # Default translation rate is 1.0 if same currency
                rate = 1.0
                report_type = 'bs'
                
                if account_id and not group_account_id:
                    # Map to group account
                    mapping = map_dict.get((sub.id, account_id))
                    if mapping:
                        group_account_id = mapping.group_account_id.id
                        report_types = mapping.report_type_ids.mapped('code')
                        report_type = 'pl' if 'PL' in report_types else 'bs'
                
                # Skip unmapped accounts
                if not group_account_id:
                    continue
                    
                # Apply translation if different currency
                if sub.currency_id != group.consolidation_currency_id:
                    period_rate = rates.get(sub.currency_id.id)
                    if period_rate:
                        if report_type == 'pl':
                            rate = period_rate.average_rate
                        else:
                            rate = period_rate.closing_rate
                            
                translated_balance = balance * rate
                
                journal_lines.append({
                    'period_id': period.id,
                    'company_id': sub.id,
                    'account_id': account_id if account_id else False,
                    'group_account_id': group_account_id,
                    'original_balance': balance,
                    'translated_balance': translated_balance,
                    'currency_id': sub.currency_id.id,
                    'exchange_rate': rate,
                    'line_type': 'tb'
                })
                
        if journal_lines:
            self.env['consolidation.journal.line'].create(journal_lines)
            
        period.state = 'consolidating'
        
        return {
            'type': 'ir.actions.act_window',
            'name': 'Working Paper',
            'res_model': 'consolidation.journal.line',
            'view_mode': 'list',
            'domain': [('period_id', '=', period.id)],
            'context': {'search_default_group_by_account': 1}
        }


    def action_run_elimination(self):
        self.ensure_one()
        period = self.period_id
        
        # Clear existing automatic elimination entries
        self.env['consolidation.elimination.entry'].search([
            ('period_id', '=', period.id)
        ]).unlink()
        
        rules = self.env['consolidation.rule'].search([])
        elim_entries = []

        
        for rule in rules:
            if rule.rule_type == 'intercompany_arap':
                bs_types = ['asset_receivable', 'asset_cash', 'asset_current', 'asset_non_current', 
                            'asset_prepayments', 'asset_fixed', 'liability_payable', 'liability_credit_card', 
                            'liability_current', 'liability_non_current', 'equity', 'equity_unaffected']
                lines = self.env['consolidation.journal.line'].search([
                    ('period_id', '=', period.id),
                    ('line_type', '=', 'tb'),
                    ('group_account_id.is_intercompany_elimination', '=', True),
                    ('group_account_id.account_type', 'in', bs_types)
                ])
                if lines:
                    entry = self.env['consolidation.elimination.entry'].create({
                        'period_id': period.id,
                        'type': 'intercompany_ar_ap',
                    })
                    for line in lines:
                        if line.translated_balance != 0:
                            debit = -line.translated_balance if line.translated_balance < 0 else 0.0
                            credit = line.translated_balance if line.translated_balance > 0 else 0.0
                            self.env['consolidation.elimination.line'].create({
                                'entry_id': entry.id,
                                'account_id': line.group_account_id.id,
                                'debit': debit,
                                'credit': credit,
                                'name': 'Eliminate AR/AP'
                            })
                            
            elif rule.rule_type == 'intercompany_pl':
                bs_types = ['asset_receivable', 'asset_cash', 'asset_current', 'asset_non_current', 
                            'asset_prepayments', 'asset_fixed', 'liability_payable', 'liability_credit_card', 
                            'liability_current', 'liability_non_current', 'equity', 'equity_unaffected']
                lines = self.env['consolidation.journal.line'].search([
                    ('period_id', '=', period.id),
                    ('line_type', '=', 'tb'),
                    ('group_account_id.is_intercompany_elimination', '=', True),
                    ('group_account_id.account_type', 'not in', bs_types)
                ])
                if lines:
                    entry = self.env['consolidation.elimination.entry'].create({
                        'period_id': period.id,
                        'type': 'intercompany_rev_exp',
                    })
                    for line in lines:
                        if line.translated_balance != 0:
                            debit = -line.translated_balance if line.translated_balance < 0 else 0.0
                            credit = line.translated_balance if line.translated_balance > 0 else 0.0
                            self.env['consolidation.elimination.line'].create({
                                'entry_id': entry.id,
                                'account_id': line.group_account_id.id,
                                'debit': debit,
                                'credit': credit,
                                'name': 'Eliminate Rev/Exp'
                            })
            
            elif rule.rule_type == 'equity':
                for group_company in period.group_id.company_ids:
                    entry = self.env['consolidation.elimination.entry'].create({
                        'period_id': period.id,
                        'type': 'investment_equity',
                    })
                    
                    # 1. Eliminate Equity at Acquisition
                    if group_company.equity_at_acquisition > 0 and group_company.equity_account_id:
                        self.env['consolidation.elimination.line'].create({
                            'entry_id': entry.id,
                            'account_id': group_company.equity_account_id.id,
                            'debit': group_company.equity_at_acquisition,
                            'credit': 0.0,
                            'name': 'Eliminate Equity at Acquisition'
                        })
                    
                    # 2. Eliminate Investment Cost
                    if group_company.investment_cost > 0 and group_company.investment_account_id:
                        self.env['consolidation.elimination.line'].create({
                            'entry_id': entry.id,
                            'account_id': group_company.investment_account_id.id,
                            'debit': 0.0,
                            'credit': group_company.investment_cost,
                            'name': 'Eliminate Investment Cost'
                        })
                        
                    # 3. Recognize Goodwill
                    if group_company.goodwill > 0:
                        gw_account = self.env['consolidation.coa.master'].search([
                            ('name', '=', 'Goodwill Consolidation'),
                            ('company_id', '=', period.group_id.parent_company_id.id)
                        ], limit=1)
                        if not gw_account:
                            gw_account = self.env['consolidation.coa.master'].create({
                                'name': 'Goodwill Consolidation',
                                'code': '119001',
                                'account_type': 'asset_non_current',
                                'company_id': period.group_id.parent_company_id.id
                            })
                        self.env['consolidation.elimination.line'].create({
                            'entry_id': entry.id,
                            'account_id': gw_account.id,
                            'debit': group_company.goodwill,
                            'credit': 0.0,
                            'name': 'Recognize Goodwill'
                        })
                        
                    # 4. Recognize NCI at Acquisition
                    from odoo.exceptions import UserError
                    if not period.group_id.nci_equity_account_id:
                        raise UserError("Akun NCI - Neraca belum dikonfigurasi di Consolidation Group.")
                    nci_account = period.group_id.nci_equity_account_id
                    
                    if group_company.nci_at_acquisition > 0:
                        self.env['consolidation.elimination.line'].create({
                            'entry_id': entry.id,
                            'account_id': nci_account.id,
                            'debit': 0.0,
                            'credit': group_company.nci_at_acquisition,
                            'name': 'Recognize NCI at Acquisition'
                        })
                        
                    # NCI Income Allocation (For current period)
                    if group_company.nci_percentage > 0:
                        # Find subsidiary net income
                        is_lines = self.env['consolidation.journal.line'].search([
                            ('period_id', '=', period.id),
                            ('company_id', '=', group_company.company_id.id),
                            ('line_type', '=', 'tb'),
                            ('group_account_id.report_section', '=', 'is')
                        ])
                        net_income_sub = sum(l.translated_balance for l in is_lines)
                        
                        nci_share = net_income_sub * (group_company.nci_percentage / 100.0)
                        
                        # Calculate opening NCI balance
                        nci_opening = group_company.nci_at_acquisition
                        
                        nci_record = self.env['consolidation.nci'].search([
                            ('member_id', '=', group_company.id),
                            ('period_id', '=', period.id)
                        ], limit=1)
                        if not nci_record:
                            self.env['consolidation.nci'].create({
                                'member_id': group_company.id,
                                'period_id': period.id,
                                'opening_balance': nci_opening,
                                'income_allocation': nci_share
                            })
                        else:
                            nci_record.write({
                                'opening_balance': nci_opening,
                                'income_allocation': nci_share
                            })
                            
                        # Post NCI allocation elimination entry ONLY to Equity
                        if nci_share != 0:
                            nci_entry = self.env['consolidation.elimination.entry'].create({
                                'period_id': period.id,
                                'type': 'nci_allocation',
                            })
                            self.env['consolidation.elimination.line'].create({
                                'entry_id': nci_entry.id,
                                'account_id': nci_account.id,
                                'debit': -nci_share if nci_share < 0 else 0.0,
                                'credit': nci_share if nci_share > 0 else 0.0,
                                'name': 'NCI in Equity Allocation'
                            })

            
        return {
            'type': 'ir.actions.act_window',
            'name': 'Elimination Entries',
            'res_model': 'consolidation.elimination.entry',
            'view_mode': 'list,form',
            'domain': [('period_id', '=', period.id)],
        }


class ConsolidationJournalLine(models.Model):
    _name = 'consolidation.journal.line'
    _description = 'Consolidation Working Paper Line'

    period_id = fields.Many2one('consolidation.period', string='Period', required=True, ondelete='cascade')
    company_id = fields.Many2one('res.company', string='Company')
    account_id = fields.Many2one('account.account', string='Local Account')
    group_account_id = fields.Many2one('consolidation.coa.master', string='Group Account', required=True)
    
    date_start = fields.Date(related='period_id.date_start', string='Start Date', readonly=True)
    date_end = fields.Date(related='period_id.date_end', string='End Date', readonly=True)
    
    original_balance = fields.Float(string='Local Balance')
    currency_id = fields.Many2one('res.currency', string='Local Currency')
    exchange_rate = fields.Float(string='Exchange Rate', default=1.0)
    translated_balance = fields.Float(string='Translated Balance')
    
    line_type = fields.Selection([
        ('tb', 'Trial Balance'),
        ('elim', 'Elimination'),
        ('nci', 'NCI Attribution')
    ], string='Line Type', default='tb')
    is_manual = fields.Boolean(string='Manual Entry', default=False)
