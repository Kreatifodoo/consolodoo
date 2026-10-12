from odoo import http
from odoo.http import request
import io
import xlsxwriter

class XbrlExportController(http.Controller):

    @http.route('/xbrl_report/export_excel', type='http', auth='user')
    def export_excel(self, date_from=None, date_to=None, **kw):
        # We need to render all lines for the export (unfolded conceptually not needed since we can just export everything or just XBRL lines, but let's export all coa lines so they can see detail)
        # To get all COA lines unfolded, we can pass all XBRL line IDs as unfolded.
        xbrl_lines = request.env['consolidation.xbrl.report.line'].search([])
        options = {
            'date_from': date_from,
            'date_to': date_to,
            'unfolded_lines': xbrl_lines.ids
        }
        
        lines = request.env['consolidation.xbrl.report.engine']._get_lines(options)
        
        output = io.BytesIO()
        workbook = xlsxwriter.Workbook(output, {'in_memory': True})
        sheet = workbook.add_worksheet('XBRL Consolidation')
        
        # Styles
        header_style = workbook.add_format({'bold': True, 'bg_color': '#f8f9fa', 'bottom': 1})
        bold_style = workbook.add_format({'bold': True})
        num_style = workbook.add_format({'num_format': '#,##0.00'})
        bold_num_style = workbook.add_format({'bold': True, 'num_format': '#,##0.00'})
        
        sheet.set_column(0, 0, 50)
        sheet.set_column(1, 1, 20)
        
        sheet.write(0, 0, 'XBRL Consolidation Report', bold_style)
        sheet.write(1, 0, f'Period: {date_from or "-"} to {date_to or "-"}')
        
        sheet.write(3, 0, 'Description', header_style)
        sheet.write(3, 1, 'Balance', header_style)
        
        row = 4
        for line in lines:
            indent = line.get('indent', 0)
            is_header = line.get('type') == 'xbrl_line' and (indent == 0 or line.get('has_children'))
            
            style = bold_style if is_header else None
            n_style = bold_num_style if is_header else num_style
            
            sheet.write(row, 0, (' ' * (indent * 4)) + line.get('name', ''), style)
            sheet.write(row, 1, line.get('balance', 0.0), n_style)
            row += 1
            
        workbook.close()
        output.seek(0)
        
        file_name = 'XBRL_Consolidation_Report.xlsx'
        return request.make_response(
            output.read(),
            headers=[
                ('Content-Type', 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'),
                ('Content-Disposition', f'attachment; filename={file_name}')
            ]
        )

    @http.route('/xbrl_report/export_pdf', type='http', auth='user')
    def export_pdf(self, date_from=None, date_to=None, **kw):
        xbrl_lines = request.env['consolidation.xbrl.report.line'].search([])
        options = {
            'date_from': date_from,
            'date_to': date_to,
            'unfolded_lines': xbrl_lines.ids
        }
        
        lines = request.env['consolidation.xbrl.report.engine']._get_lines(options)
        
        data = {
            'lines': lines,
            'date_from': date_from,
            'date_to': date_to
        }
        
        pdf, _ = request.env['ir.actions.report']._render_qweb_pdf('odoo_psak_consolidation.report_xbrl_consolidation', data=data)
        
        return request.make_response(
            pdf,
            headers=[
                ('Content-Type', 'application/pdf'),
                ('Content-Disposition', 'attachment; filename=XBRL_Consolidation_Report.pdf')
            ]
        )
