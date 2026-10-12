from odoo import models, fields, api
from odoo.exceptions import UserError

class ConsolidationPeriod(models.Model):
    _name = 'consolidation.period'
    _description = 'Consolidation Period'

    name = fields.Char(string='Name', required=True)
    date_start = fields.Date(string='Start Date', required=True)
    date_end = fields.Date(string='End Date', required=True)
    group_id = fields.Many2one('consolidation.group', string='Consolidation Group', required=True)
    journal_line_ids = fields.One2many('consolidation.journal.line', 'period_id', string='Journal Lines')
    worksheet_line_ids = fields.One2many('consolidation.worksheet.line', 'period_id', string='Worksheet Lines')
    state = fields.Selection([
        ('draft', 'Draft'),
        ('consolidating', 'Consolidating'),
        ('generated', 'Generated'),
        ('posted', 'Posted'),
        ('done', 'Done')
    ], string='Status', default='draft', required=True)
    rate_ids = fields.One2many('consolidation.period.rate', 'period_id', string='Exchange Rates')
    
    def action_run_aggregation(self):
        self.ensure_one()
        engine = self.env['consolidation.engine'].create({'period_id': self.id})
        res = engine.action_aggregate_data()
        self._generate_worksheet()
        return res

    def action_reset_to_draft(self):
        for record in self:
            record.state = 'draft'
            record.worksheet_line_ids.unlink()

    def action_run_elimination(self):
        self.ensure_one()
        engine = self.env['consolidation.engine'].create({'period_id': self.id})
        res = engine.action_run_elimination()
        self._generate_worksheet()
        return res

    def _generate_worksheet(self):
        for period in self:
            period.worksheet_line_ids.unlink()
            lines = self.env['consolidation.journal.line'].search([('period_id', '=', period.id)])
            
            # Map accounts to their balances
            account_data = {}
            for line in lines:
                acc = line.group_account_id
                if acc.id not in account_data:
                    account_data[acc.id] = {
                        'period_id': period.id,
                        'account_id': acc.id,
                        'parent_balance': 0.0,
                        'subsidiary_balance': 0.0,
                        'elimination_debit': 0.0,
                        'elimination_credit': 0.0
                    }
                
                # Check if company is parent
                is_parent = line.company_id and line.company_id.id == period.group_id.parent_company_id.id
                
                val = line.translated_balance
                if line.line_type == 'tb':
                    if is_parent:
                        account_data[acc.id]['parent_balance'] += val
                    else:
                        account_data[acc.id]['subsidiary_balance'] += val

            # Now add Eliminations from the new models
            elim_entries = self.env['consolidation.elimination.entry'].search([('period_id', '=', period.id)])
            for entry in elim_entries:
                for eline in entry.line_ids:
                    acc_id = eline.account_id.id
                    if acc_id not in account_data:
                        account_data[acc_id] = {
                            'period_id': period.id,
                            'account_id': acc_id,
                            'parent_balance': 0.0,
                            'subsidiary_balance': 0.0,
                            'elimination_debit': 0.0,
                            'elimination_credit': 0.0
                        }
                    account_data[acc_id]['elimination_debit'] += eline.debit
                    account_data[acc_id]['elimination_credit'] += eline.credit
                        
            worksheet_vals = list(account_data.values())
            period.write({'worksheet_line_ids': [(0, 0, vals) for vals in worksheet_vals]})
            
            # RE Roll-forward
            period._roll_forward_retained_earnings()
            
            period.state = 'generated'
            
    def _roll_forward_retained_earnings(self):
        self.ensure_one()
        # Find all IS accounts in worksheet
        is_lines = self.worksheet_line_ids.filtered(lambda l: l.report_section == 'is')
        net_income = sum(l.consolidated_balance for l in is_lines)
        
        if abs(net_income) > 0.01:
            # Find Current Year Earnings account (or just RE account)
            re_account = self.env['consolidation.coa.master'].search([
                ('company_id', '=', self.group_id.parent_company_id.id),
                ('account_type', '=', 'equity_unaffected')
            ], limit=1)
            
            if re_account:
                re_line = self.worksheet_line_ids.filtered(lambda l: l.account_id.id == re_account.id)
                if not re_line:
                    # Create the line if it doesn't exist
                    self.write({'worksheet_line_ids': [(0, 0, {
                        'period_id': self.id,
                        'account_id': re_account.id,
                        'parent_balance': 0.0,
                        'subsidiary_balance': 0.0,
                        'elimination_debit': net_income if net_income > 0 else 0.0,
                        'elimination_credit': -net_income if net_income < 0 else 0.0
                    })]})
                else:
                    # Add to existing line's elimination to adjust the consol balance
                    # Note: Normally net income rolls into the consol_balance via an elimination adjustment 
                    if net_income > 0:
                        re_line.elimination_credit += net_income
                    else:
                        re_line.elimination_debit -= net_income

    def action_validate_consolidation(self):
        for record in self:
            elim_entries = self.env['consolidation.elimination.entry'].search([
                ('period_id', '=', record.id),
            ])
            total_dr = sum(l.debit for entry in elim_entries for l in entry.line_ids)
            total_cr = sum(l.credit for entry in elim_entries for l in entry.line_ids)
            diff = total_dr - total_cr
            if abs(diff) > 0.01:
                raise UserError("Elimination entries are not balanced! Difference: %.2f." % diff)
            record.state = 'done'
            for entry in elim_entries:
                entry.state = 'posted'

    def action_view_consol_journal(self):
        self.ensure_one()
        return {
            'name': 'Consolidation TB Journals',
            'type': 'ir.actions.act_window',
            'res_model': 'consolidation.journal.line',
            'view_mode': 'list,form',
            'domain': [('period_id', '=', self.id), ('line_type', '=', 'tb')],
            'context': {'search_default_group_by_account': 1}
        }

    def action_view_elim_journal(self):
        self.ensure_one()
        return {
            'name': 'Elimination Entries',
            'type': 'ir.actions.act_window',
            'res_model': 'consolidation.elimination.entry',
            'view_mode': 'list,form',
            'domain': [('period_id', '=', self.id)],
            'context': {
                'default_period_id': self.id,
            }
        }


    @api.model
    def get_matrix_data(self, period_id):
        period = self.browse(period_id)
        if not period.exists():
            return {}
            
        lines = self.env['consolidation.journal.line'].search([('period_id', '=', period_id)])
        
        # Prepare columns: Companies
        companies = {}
        for line in lines:
            if line.company_id:
                companies[line.company_id.id] = line.company_id.name
                
        # Prepare rows: Accounts
        accounts = {}
        for line in lines:
            acc_id = line.group_account_id.id
            acc_name = line.group_account_id.name
            if acc_id not in accounts:
                accounts[acc_id] = {'name': acc_name, 'balances': {}, 'manual_elim': 0.0}
                
            if line.company_id:
                if line.company_id.id not in accounts[acc_id]['balances']:
                    accounts[acc_id]['balances'][line.company_id.id] = {'tb': 0.0, 'elim': 0.0, 'nci': 0.0}
                    
                accounts[acc_id]['balances'][line.company_id.id][line.line_type] += line.translated_balance
            else:
                if line.line_type == 'elim' and line.is_manual:
                    accounts[acc_id]['manual_elim'] += line.translated_balance
            
        return {
            'period_name': period.name,
            'companies': [{'id': k, 'name': v} for k, v in companies.items()],
            'accounts': [{'id': k, 'name': v['name'], 'balances': v['balances'], 'manual_elim': v['manual_elim']} for k, v in accounts.items()]
        }

    @api.model
    def save_manual_elimination(self, period_id, account_id, amount):
        period = self.browse(period_id)
        if not period.exists() or period.state == 'done':
            return False
            
        # Find existing manual elimination for this account in this period (without company)
        domain = [
            ('period_id', '=', period_id),
            ('group_account_id', '=', account_id),
            ('company_id', '=', False),
            ('line_type', '=', 'elim'),
            ('is_manual', '=', True)
        ]

        existing_line = self.env['consolidation.journal.line'].search(domain, limit=1)
        
        if amount == 0 and existing_line:
            existing_line.unlink()
        elif existing_line:
            existing_line.write({
                'original_balance': amount,
                'translated_balance': amount
            })
        elif amount != 0:
            self.env['consolidation.journal.line'].create({
                'period_id': period_id,
                'group_account_id': account_id,
                'original_balance': amount,
                'translated_balance': amount,
                'currency_id': period.group_id.consolidation_currency_id.id,
                'exchange_rate': 1.0,
                'line_type': 'elim',
                'is_manual': True
            })

            
        return True


class ConsolidationPeriodRate(models.Model):
    _name = 'consolidation.period.rate'
    _description = 'Consolidation Period Exchange Rate'

    period_id = fields.Many2one('consolidation.period', string='Period', required=True, ondelete='cascade')
    currency_id = fields.Many2one('res.currency', string='Currency', required=True)
    closing_rate = fields.Float(string='Closing Rate', default=1.0, required=True, help='Rate at the end of the period')
    average_rate = fields.Float(string='Average Rate', default=1.0, required=True, help='Average rate during the period')
