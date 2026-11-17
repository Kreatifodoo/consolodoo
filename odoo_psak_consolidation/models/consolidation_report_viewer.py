from odoo import models, fields, api
import re

class ConsolidationReportViewer(models.TransientModel):
    _name = 'consolidation.report.viewer'
    _description = 'Penampil Laporan Konsolidasi'

    report_id = fields.Many2one('consolidation.report', string='Laporan Keuangan', required=True, help="Pilih template laporan keuangan konsolidasi yang ingin ditampilkan.")
    period_ids = fields.Many2many('consolidation.period', string='Periode Konsolidasi', help="Pilih satu atau beberapa periode konsolidasi.")
    date_from = fields.Date(string='Dari Tanggal', help="Batas tanggal awal penarikan laporan.")
    date_to = fields.Date(string='Sampai Tanggal', help="Batas tanggal akhir penarikan laporan.")

    def action_view_report(self):
        """
        Returns a client action to open the interactive JS report viewer.
        We pass the ID of this wizard so the JS can fetch data using `get_report_data`.
        """
        self.ensure_one()
        return {
            'type': 'ir.actions.client',
            'tag': 'consolidation_report_client_action',
            'name': self.report_id.name,
            'context': {
                'wizard_id': self.id,
            }
        }

    @api.model
    def get_report_data(self, wizard_id):
        wizard = self.browse(wizard_id)
        if not wizard.exists():
            return {}

        report = wizard.report_id
        
        # 1. Find active consolidation period(s) that overlap with the date range / selected periods
        domain = [('state', 'in', ['done', 'generated'])] # Generated replaces consolidating state
        if wizard.date_from:
            domain.append(('date_start', '>=', wizard.date_from))
        if wizard.date_to:
            domain.append(('date_end', '<=', wizard.date_to))
            
        if wizard.period_ids:
            domain.append(('id', 'in', wizard.period_ids.ids))
        
        periods = self.env['consolidation.period'].search(domain)
        period_ids = periods.ids

        # 2. Pre-calculate 'accounts' lines
        line_values = {}
        lines_info = []

        for line in report.line_ids:
            val = 0.0
            if line.line_type == 'accounts' and period_ids and line.account_ids:
                journal_lines = self.env['consolidation.journal.line'].search([
                    ('period_id', 'in', period_ids),
                    ('group_account_id', 'in', line.account_ids.ids)
                ])
                val = sum(journal_lines.mapped('translated_balance')) * float(line.sign)
                
            elif line.line_type == 'nci_income' and period_ids:
                nci_records = self.env['consolidation.nci'].search([
                    ('period_id', 'in', period_ids)
                ])
                val = sum(nci_records.mapped('income_allocation')) * float(line.sign)
                
            if line.code:
                line_values[line.code] = val
                
            lines_info.append({
                'id': line.id,
                'name': line.name,
                'code': line.code,
                'type': line.line_type,
                'formula': line.formula,
                'value': val,
                'sequence': line.sequence,
                'sign': line.sign,
            })

        # 3. Calculate 'formula' lines
        # We might need multiple passes if formulas depend on other formulas
        max_passes = 5
        for _ in range(max_passes):
            for line_info in lines_info:
                if line_info['type'] == 'formula' and line_info['formula']:
                    formula_str = line_info['formula']
                    
                    try:
                        # Replace word tokens with their dictionary values
                        # Filter out falsy codes (e.g., False or None) before sorting
                        valid_line_values = {k: v for k, v in line_values.items() if k}
                        
                        import logging
                        _logger = logging.getLogger(__name__)
                        _logger.info("=== FORMULA DEBUG ===")
                        _logger.info("Evaluating formula for line: %s (Code: %s)", line_info.get('name'), line_info.get('code'))
                        _logger.info("Original formula_str: %s", formula_str)
                        _logger.info("valid_line_values keys: %s", valid_line_values.keys())
                        
                        for code, val in sorted(valid_line_values.items(), key=lambda x: len(str(x[0])), reverse=True):
                            # Ensure negative values are wrapped in parenthesis to avoid issues like '1000 - -500' -> '1000 - (-500)'
                            str_val = f"({val})" if val < 0 else str(val)
                            formula_str = re.sub(rf'\b{code}\b', str_val, formula_str)
                            
                        _logger.info("Replaced formula_str: %s", formula_str)
                        
                        # Evaluate the replaced string
                        clean_formula = re.sub(r'[^0-9\.\+\-\*\/\(\) ]', '', formula_str)
                        _logger.info("Cleaned formula for eval: '%s'", clean_formula)
                        if clean_formula and clean_formula.strip() != '':
                            result = eval(clean_formula)
                            _logger.info("Eval result: %s", result)
                            
                            # apply sign if needed on formula
                            if line_info.get('sign') == '-1':
                                result = result * -1
                                
                            line_info['value'] = result
                            if line_info['code']:
                                line_values[line_info['code']] = result
                    except Exception as e:
                        # If evaluation fails, value remains 0
                        import logging
                        logging.getLogger(__name__).error("Formula evaluation failed for line %s: %s", line_info.get('name'), e)
                        line_info['value'] = 0.0

        return {
            'report_name': report.name,
            'date_from': wizard.date_from,
            'date_to': wizard.date_to,
            'lines': lines_info,
        }
