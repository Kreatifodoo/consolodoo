from odoo import models, api

class ConsolidationXbrlReportEngine(models.AbstractModel):
    _name = 'consolidation.xbrl.report.engine'
    _description = 'XBRL Consolidation Report Engine'

    @api.model
    def _get_reports(self):
        reports = self.env['consolidation.xbrl.report'].search([])
        return [{'id': r.id, 'name': r.name} for r in reports]

    @api.model
    def _get_lines(self, options):
        date_from = options.get('date_from')
        date_to = options.get('date_to')
        unfolded = options.get('unfolded_lines', [])
        report_id = options.get('report_id')

        # Find matching consolidation periods
        domain = []
        if date_from:
            domain.append(('date_start', '>=', date_from))
        if date_to:
            domain.append(('date_end', '<=', date_to))
            
        periods = self.env['consolidation.period'].search(domain)
        
        # Get worksheet lines
        worksheet_lines = self.env['consolidation.worksheet.line'].search([('period_id', 'in', periods.ids)])
        
        # Aggregate balances by master_coa_id
        balances_by_coa = {}
        for wl in worksheet_lines:
            balances_by_coa[wl.account_id.id] = balances_by_coa.get(wl.account_id.id, 0.0) + wl.consolidated_balance
            
        # Get all XBRL mapping lines for the specific report
        line_domain = []
        if report_id:
            line_domain.append(('report_id', '=', report_id))
        xbrl_lines = self.env['consolidation.xbrl.report.line'].search(line_domain, order='sequence')
        
        result = []
        
        def process_line(line, indent):
            # Calculate total balance
            balance = 0.0
            for coa in line.master_coa_ids:
                balance += balances_by_coa.get(coa.id, 0.0)
                
            sign_mult = 1 if line.sign == '1' else -1
            balance *= sign_mult
            
            line_data = {
                'id': line.id,
                'name': line.name,
                'code': line.code,
                'indent': indent,
                'balance': balance,
                'has_children': bool(line.child_ids) or bool(line.master_coa_ids),
                'is_unfolded': line.id in unfolded,
                'type': 'xbrl_line',
                'master_coa_ids': line.master_coa_ids.ids
            }
            result.append(line_data)
            
            if line.id in unfolded:
                # Show master COA details
                for coa in line.master_coa_ids:
                    coa_bal = balances_by_coa.get(coa.id, 0.0) * sign_mult
                    result.append({
                        'id': f"coa_{coa.id}",
                        'name': coa.name,
                        'code': coa.code,
                        'indent': indent + 1,
                        'balance': coa_bal,
                        'has_children': False,
                        'is_unfolded': False,
                        'type': 'coa_line',
                        'master_coa_id': coa.id
                    })
            
            if line.id in unfolded or True:
                # Assuming child lines are always processed if we want a tree,
                # but if we use fold/unfold, we might only process if unfolded.
                # However, the ticket says hierarchical structure, usually we return all xbrl lines 
                # but only fold/unfold the COA master details, or we fold/unfold xbrl lines too.
                # The ticket says "Fitur Drill-down (Unfold / Fold): Pengguna dapat mengekspansi baris (unfold) untuk melihat detail consolidation.coa.master beserta porsi nilainya secara real-time."
                # So unfolding is mainly for COA master details. We should output all XBRL lines hierarchically.
                pass
                
        # To maintain hierarchy, we only start processing from root lines
        root_lines = xbrl_lines.filtered(lambda l: not l.parent_id)
        
        def traverse(lines, indent):
            for line in lines:
                process_line(line, indent)
                if line.child_ids:
                    traverse(line.child_ids, indent + 1)
                    
        traverse(root_lines, 0)
        
        return result
