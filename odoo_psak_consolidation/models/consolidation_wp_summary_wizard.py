from odoo import models, fields, api

class ConsolidationWPSummaryWizard(models.TransientModel):
    _name = 'consolidation.wp.summary.wizard'
    _description = 'Working Paper Summary Wizard'

    period_id = fields.Many2one('consolidation.period', string='Period', required=True)

    def action_view_html(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.client',
            'tag': 'odoo_psak_consolidation.wp_viewer',
            'name': 'Working Paper Summary',
            'context': {
                'active_id': self.period_id.id,
            }
        }

    @api.model
    def get_wp_data(self, period_id):
        period = self.env['consolidation.period'].sudo().browse(int(period_id))
        
        parent_company = period.group_id.parent_company_id
        subsidiary_records = period.group_id.company_ids
        
        companies = [
            {'id': parent_company.id, 'name': parent_company.name, 'type': 'parent'}
        ]
        
        for sub_rec in subsidiary_records:
            companies.append({'id': sub_rec.company_id.id, 'name': sub_rec.company_id.name, 'type': 'sub'})
            
        lines = self.env['consolidation.journal.line'].sudo().search([('period_id', '=', period.id)])
        group_accounts = lines.mapped('group_account_id')
        sorted_accounts = sorted(group_accounts, key=lambda a: a.code or '')
        
        rows = []
        for acc in sorted_accounts:
            acc_lines = lines.filtered(lambda l: l.group_account_id == acc)
            
            company_balances = {}
            gabung_val = 0
            
            for comp in companies:
                val = sum(acc_lines.filtered(lambda l: l.company_id.id == comp['id'] and l.line_type != 'elim').mapped('translated_balance'))
                company_balances[str(comp['id'])] = val
                gabung_val += val
                
            elim_val = sum(acc_lines.filtered(lambda l: l.line_type == 'elim').mapped('translated_balance'))
            
            final_val = gabung_val + elim_val
            
            rows.append({
                'account_code': acc.code or '',
                'account_name': acc.name or '',
                'company_balances': company_balances,
                'elimination': elim_val,
                'consolidation': final_val
            })
            
        return {
            'period_name': period.name,
            'companies': companies,
            'rows': rows
        }
