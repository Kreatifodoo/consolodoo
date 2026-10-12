from odoo import models

class ConsolidationFinancialReport(models.AbstractModel):
    _name = 'report.odoo_psak_consolidation.report_financial_pdf'
    _description = 'Consolidation Financial Report PDF'

    def _get_report_values(self, docids, data=None):
        if not data or not data.get('wizard_id'):
            # Fallback if accessed without wizard (should not happen)
            return {}
            
        wizard_id = data['wizard_id']
        wizard = self.env['consolidation.report.viewer'].browse(wizard_id)
        
        report_data = wizard.get_report_data()
        
        return {
            'doc_ids': docids,
            'doc_model': 'consolidation.report.viewer',
            'docs': wizard,
            'report_data': report_data,
        }
