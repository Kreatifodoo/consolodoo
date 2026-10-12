# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.tools.safe_eval import safe_eval
from odoo.exceptions import UserError

class ConsolReport(models.Model):
    _name = 'consol.report'
    _description = 'Consolidated Financial Statement Template (No-Code Report Engine)'
    _inherit = ['mail.thread']
    _order = 'sequence, name'

    name = fields.Char(string='Report Name', required=True, tracking=True)
    sequence = fields.Integer(string='Sequence', default=10)

    report_type = fields.Selection([
        ('balance_sheet', 'Statement of Financial Position (Balance Sheet)'),
        ('profit_loss', 'Statement of Profit or Loss & OCI'),
        ('equity_changes', 'Statement of Changes in Equity'),
        ('cash_flow', 'Statement of Cash Flows (Indirect Method)'),
        ('worksheet', 'Consolidation Worksheet'),
        ('custom', 'Custom Financial Report')
    ], string='Report Type', default='balance_sheet', required=True, tracking=True)

    group_id = fields.Many2one(
        'consol.group',
        string='Specific Consolidation Group',
        help="Leave empty if this report template applies to all consolidation groups.")

    comparison = fields.Selection([
        ('none', 'No Comparison'),
        ('previous_period', 'Previous Period'),
        ('same_period_last_year', 'Same Period Last Year'),
        ('budget', 'Budget')
    ], string='Comparison Mode', default='previous_period')

    show_entity_columns = fields.Boolean(
        string='Show Columns per Entity',
        default=True,
        help="Display separate columns for each group entity (worksheet style).")

    show_elimination_column = fields.Boolean(
        string='Show Elimination Column',
        default=True,
        help="Display intercompany elimination column.")

    show_nci_split = fields.Boolean(
        string='Split Parent vs NCI Attribution',
        default=True,
        help="Separate net income allocation between Parent Owners and Non-Controlling Interest.")

    display_currency_id = fields.Many2one(
        'res.currency',
        string='Display Currency',
        help="If empty, follows the group reporting currency.")

    rounding = fields.Float(
        string='Rounding Factor',
        default=1.0,
        help="1 for full amounts, 1,000 for thousands, 1,000,000 for millions.")

    header_text = fields.Html(string='Header Text / Official Letterhead')
    footer_text = fields.Html(string='Footer Text / Sign-off Block')

    line_ids = fields.One2many(
        'consol.report.line',
        'report_id',
        string='Financial Report Lines')

    def action_sync_accounts_to_lines(self):
        """
        Intelligently scan all existing consolidation accounts and link them
        to the appropriate report lines based on standard accounting classifications.
        """
        for report in self:
            report._sync_report_accounts()
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Accounts Synchronized'),
                'message': _('Consolidation accounts have been successfully mapped to report lines.'),
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
                    matched = all_accs.filtered(lambda a: a.statement == 'pl' or a.account_type in ['income', 'income_other', 'expense', 'expense_depreciation', 'expense_direct_cost'])

            elif self.report_type == 'profit_loss':
                if code == 'REV':
                    matched = all_accs.filtered(lambda a: a.account_type in ['income', 'income_other'] or a.code.startswith(('401', '402', '410')))
                elif code == 'COGS':
                    matched = all_accs.filtered(lambda a: a.account_type == 'expense_direct_cost' or a.code.startswith(('501', '502', '510')))
                elif code == 'OPEX':
                    matched = all_accs.filtered(lambda a: (a.account_type in ['expense', 'expense_depreciation'] or a.code.startswith(('601', '602', '611', '671'))) and a.code != '701000' and not a.code.startswith('5'))
                elif code == 'NCI_ATTRIB':
                    matched = all_accs.filtered(lambda a: a.code == '701000' or ('non-controlling' in (a.name or '').lower() and a.statement == 'pl'))

            if matched:
                line.write({'account_ids': [(6, 0, matched.ids)]})

    def get_report_matrix(self, period_id):
        """
        Generate full report table matrix:
        - Columns: Info, Entity 1..N, Elimination, Consolidated Total, etc.
        - Rows: Report rows with values per column.
        """
        self.ensure_one()
        period = self.env['consol.period'].browse(period_id)
        if not period.exists():
            raise UserError(_("Invalid consolidation period!"))

        active_entities = period._get_active_entities()
        rounding_factor = self.rounding or 1.0

        # Prepare column structure
        columns = []
        if self.show_entity_columns:
            for entity in active_entities:
                columns.append({
                    'id': f'entity_{entity.id}',
                    'name': entity.code or entity.name,
                    'type': 'entity',
                    'entity_id': entity.id,
                })

        if self.show_elimination_column:
            columns.append({
                'id': 'elimination',
                'name': 'Elimination',
                'type': 'elimination',
            })

        columns.append({
            'id': 'consolidated',
            'name': 'Consolidated Total',
            'type': 'consolidated',
        })

        # Cache TB balance per (entity_id, consol_account_id)
        tb_lines = self.env['consol.trial.balance.line'].search([('period_id', '=', period.id)])
        entity_acc_balances = {}
        for l in tb_lines:
            entity_acc_balances[(l.entity_id.id, l.consol_account_id.id)] = (
                entity_acc_balances.get((l.entity_id.id, l.consol_account_id.id), 0.0) + l.balance_rc
            )

        # Cache Elimination balance per consol_account_id
        # Net elimination = Debit (+) - Credit (-)
        journal_lines = self.env['consol.journal.line'].search([
            ('period_id', '=', period.id),
            ('journal_id.state', '=', 'posted')
        ])
        elim_acc_balances = {}
        for jl in journal_lines:
            net = jl.debit - jl.credit
            elim_acc_balances[jl.consol_account_id.id] = elim_acc_balances.get(jl.consol_account_id.id, 0.0) + net

        # Check for Comparison with Previous Period
        prev_period = False
        prev_entity_acc_balances = {}
        prev_elim_acc_balances = {}
        prev_active_entities = []

        if self.comparison == 'previous_period':
            prev_period = self.env['consol.period'].search([
                ('group_id', '=', period.group_id.id),
                ('date_to', '<', period.date_from)
            ], order='date_to desc', limit=1)

            if prev_period:
                prev_active_entities = prev_period._get_active_entities()
                prev_tb_lines = self.env['consol.trial.balance.line'].search([('period_id', '=', prev_period.id)])
                for l in prev_tb_lines:
                    prev_entity_acc_balances[(l.entity_id.id, l.consol_account_id.id)] = (
                        prev_entity_acc_balances.get((l.entity_id.id, l.consol_account_id.id), 0.0) + l.balance_rc
                    )

                prev_j_lines = self.env['consol.journal.line'].search([
                    ('period_id', '=', prev_period.id),
                    ('journal_id.state', '=', 'posted')
                ])
                for jl in prev_j_lines:
                    net = jl.debit - jl.credit
                    prev_elim_acc_balances[jl.consol_account_id.id] = prev_elim_acc_balances.get(jl.consol_account_id.id, 0.0) + net

                columns.append({
                    'id': 'prev_consolidated',
                    'name': f'Prev ({prev_period.name})',
                    'type': 'prev_consolidated',
                })
                columns.append({
                    'id': 'variance',
                    'name': 'MoM Change',
                    'type': 'variance',
                })

        # Compute rows
        lines_data = []
        code_eval_context_per_col = {col['id']: {} for col in columns}

        for rline in self.line_ids.sorted('sequence'):
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

            # Compute value per column
            for col in columns:
                val = 0.0
                if col['type'] == 'variance':
                    # Variance = current consolidated - previous consolidated
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

                # Apply rounding
                rounded_val = val / rounding_factor if rounding_factor else val
                row['values'][col['id']] = rounded_val

                if rline.code:
                    code_eval_context_per_col[col['id']][rline.code] = rounded_val

            lines_data.append(row)

        return {
            'report_name': self.name,
            'period_name': period.name,
            'group_name': period.group_id.name,
            'currency_symbol': period.currency_id.symbol or 'Rp',
            'columns': columns,
            'lines': lines_data,
        }


class ConsolReportLine(models.Model):
    _name = 'consol.report.line'
    _description = 'Report Template Configuration Line'
    _order = 'sequence, id'

    report_id = fields.Many2one(
        'consol.report',
        string='Report Template',
        required=True,
        ondelete='cascade')

    sequence = fields.Integer(string='Sequence', default=10)
    name = fields.Char(string='Line Label / Name', required=True)
    code = fields.Char(string='Line Code (For Formulas)', size=20,
                       help="Example: GP, OPEX, EBIT, NI. Can be referenced in other formula lines.")

    level = fields.Integer(
        string='Indentation Level',
        default=1,
        help="0 = Main Header, 1 = Sub-Category / Detail, 2 = Subtotal.")

    line_type = fields.Selection([
        ('header', 'Header / Title (No Numbers)'),
        ('accounts', 'Consolidation Accounts Aggregation'),
        ('formula', 'Formula / Calculation'),
        ('total', 'Subtotal / Grand Total'),
        ('blank', 'Blank Row (Separator)')
    ], string='Line Type', default='accounts', required=True)

    account_ids = fields.Many2many(
        'consol.account',
        'consol_report_line_acc_rel',
        'line_id',
        'account_id',
        string='Selected Consolidation Accounts')

    account_filter = fields.Char(
        string='Account Filter Domain',
        help="Alternative account selection via code domain (e.g. [('code', '=like', '1-1%')]).")

    formula = fields.Char(
        string='Formula',
        help="Example: GP - OPEX, NI * 0.8, REV - COGS. Supports +, -, *, / and line codes.")

    balance_sign = fields.Selection([
        ('natural', 'Natural (Debit Positive, Credit Negative)'),
        ('reverse', 'Reversed (Credit Positive - for Revenue, Liability, Equity)')
    ], string='Balance Sign Behavior', default='natural', required=True)

    bold = fields.Boolean(string='Bold', default=False)
    italic = fields.Boolean(string='Italic', default=False)
    underline = fields.Boolean(string='Underline', default=False)
    print_blank_if_zero = fields.Boolean(string='Print Blank if Zero', default=False)
    page_break = fields.Boolean(string='Page Break', default=False)
    hide_if_zero = fields.Boolean(string='Hide if Zero', default=False)
    drilldown = fields.Boolean(string='Enable Drill-down', default=True)
    note = fields.Char(string='Notes Ref No.', help="Reference note number to Notes to Financial Statements.")

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
    _description = 'Balance Sheet Account Mapping to Consolidated Cash Flow'
    _order = 'category, consol_account_id'

    consol_account_id = fields.Many2one(
        'consol.account',
        string='Consolidation Account',
        required=True,
        ondelete='cascade')

    category = fields.Selection([
        ('operating', 'Operating Activities'),
        ('investing', 'Investing Activities'),
        ('financing', 'Financing Activities')
    ], string='Cash Flow Category', required=True)

    sign = fields.Selection([
        ('1', 'Normal (+ Movement)'),
        ('-1', 'Reversed (- Movement)')
    ], string='Cash Impact Direction', default='-1', required=True)
