import io
import xlsxwriter
from odoo import http
from odoo.http import request

class WorkingPaperController(http.Controller):
    
    @http.route('/consolidation/export_wp_excel', type='http', auth='user')
    def export_wp_excel(self, period_id, **kw):
        period = request.env['consolidation.period'].sudo().browse(int(period_id))
        
        output = io.BytesIO()
        workbook = xlsxwriter.Workbook(output, {'in_memory': True})
        sheet = workbook.add_worksheet('Working Paper')
        
        # Format styles
        bold = workbook.add_format({'bold': True})
        title_format = workbook.add_format({'bold': True, 'font_size': 12, 'color': 'red'})
        header_format = workbook.add_format({
            'bold': True,
            'align': 'center',
            'valign': 'vcenter',
            'bg_color': '#D3D3D3',
            'border': 1,
            'text_wrap': True
        })
        num_format = workbook.add_format({'num_format': '#,##0', 'border': 1})
        cell_format = workbook.add_format({'border': 1})
        
        parent_company = period.group_id.parent_company_id
        subsidiary_records = period.group_id.company_ids
        
        # Write Title
        sheet.write(0, 0, parent_company.name or 'PT. INDUK', bold)
        sheet.write(1, 0, 'LAP. KONSOLIDASIAN', bold)
        sheet.write(2, 0, f'YANG BERAKHIR PER {period.date_end}', title_format)
        sheet.write(3, 0, '(Dalam Nilai Penuh)', bold)
        
        # Define columns
        col = 1
        sheet.set_column(0, 0, 40)
        
        # Header Row 5 and 6
        # Parent
        sheet.write(5, col, 'Induk', header_format)
        sheet.write(6, col, parent_company.name, header_format)
        parent_col = col
        sheet.set_column(col, col, 18)
        col += 1
        
        # Subsidiaries
        sub_cols = []
        if subsidiary_records:
            sheet.merge_range(5, col, 5, col + len(subsidiary_records) - 1, 'Anak', header_format)
            for sub_rec in subsidiary_records:
                sheet.write(6, col, sub_rec.company_id.name, header_format)
                sub_cols.append((sub_rec.company_id.id, col))
                sheet.set_column(col, col, 18)
                col += 1
        
        # Gabung
        sheet.merge_range(5, col, 6, col, 'Gabung', header_format)
        gabung_col = col
        sheet.set_column(col, col, 18)
        col += 1
        
        # Eliminasi Db Cr
        sheet.merge_range(5, col, 5, col+1, 'Eliminasi', header_format)
        sheet.write(6, col, 'Db', header_format)
        elim_db_col = col
        sheet.set_column(col, col, 18)
        col += 1
        sheet.write(6, col, 'Cr', header_format)
        elim_cr_col = col
        sheet.set_column(col, col, 18)
        col += 1
        
        # Konsol
        sheet.merge_range(5, col, 6, col, 'Konsol INDUK', header_format)
        konsol_col = col
        sheet.set_column(col, col, 18)
        col += 1
        
        # Fetch Data
        lines = request.env['consolidation.journal.line'].sudo().search([('period_id', '=', period.id)])
        
        # Group by group_account_id
        group_accounts = lines.mapped('group_account_id')
        sorted_accounts = sorted(group_accounts, key=lambda a: a.code or '')
        
        row = 7
        for acc in sorted_accounts:
            acc_lines = lines.filtered(lambda l: l.group_account_id == acc)
            sheet.write(row, 0, f"{acc.code} {acc.name}", cell_format)
            
            gabung_val = 0
            
            # Parent Val
            parent_val = sum(acc_lines.filtered(lambda l: l.company_id == parent_company and l.line_type != 'elim').mapped('translated_balance'))
            sheet.write(row, parent_col, parent_val, num_format)
            gabung_val += parent_val
            
            # Subs Val
            for sub_id, scol in sub_cols:
                sub_val = sum(acc_lines.filtered(lambda l: l.company_id.id == sub_id and l.line_type != 'elim').mapped('translated_balance'))
                sheet.write(row, scol, sub_val, num_format)
                gabung_val += sub_val
                
            # Gabung
            sheet.write(row, gabung_col, gabung_val, num_format)
            
            # Elim
            elim_val = sum(acc_lines.filtered(lambda l: l.line_type == 'elim').mapped('translated_balance'))
            elim_db = elim_val if elim_val > 0 else 0
            elim_cr = abs(elim_val) if elim_val < 0 else 0
            
            sheet.write(row, elim_db_col, elim_db, num_format)
            sheet.write(row, elim_cr_col, elim_cr, num_format)
            
            # Konsol
            konsol_val = gabung_val + elim_val
            sheet.write(row, konsol_col, konsol_val, num_format)
            
            row += 1
            
        workbook.close()
        output.seek(0)
        
        response = request.make_response(
            output.read(),
            headers=[
                ('Content-Type', 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'),
                ('Content-Disposition', f'attachment; filename=Working_Paper_{period.name}.xlsx')
            ]
        )
        return response
