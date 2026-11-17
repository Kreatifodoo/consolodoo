# -*- coding: utf-8 -*-
import io
import base64
from odoo import models, fields, api, _
from odoo.exceptions import UserError

try:
    import xlsxwriter
except ImportError:
    xlsxwriter = None

class ConsolReportExportWizard(models.TransientModel):
    _name = 'consol.report.export.wizard'
    _description = 'Wisard Ekspor & Cetak Laporan Keuangan Konsolidasian'

    period_id = fields.Many2one(
        'consol.period',
        string='Periode Konsolidasi',
        required=True,
        default=lambda self: self.env['consol.period'].search([], order='date_to desc, id desc', limit=1),
        help="Pilih periode konsolidasi yang ingin dicetak atau diekspor laporannya.")

    report_id = fields.Many2one(
        'consol.report',
        string='Template Laporan Keuangan',
        required=True,
        default=lambda self: self.env['consol.report'].search([('report_type', '=', 'balance_sheet')], limit=1),
        help="Pilih template laporan keuangan (misal: Neraca, Laba Rugi, Perubahan Ekuitas, Arus Kas).")

    export_format = fields.Selection([
        ('interactive', 'Tampilan Web Interaktif (OWL)'),
        ('xlsx', 'Microsoft Excel (.xlsx)'),
        ('pdf', 'Cetak Dokumen Resmi PDF')
    ], string='Format Keluaran', default='interactive', required=True,
       help="Pilih format media keluaran untuk melihat atau mengunduh laporan keuangan konsolidasian.")

    file_data = fields.Binary(string='Berkas Keluaran', readonly=True)
    filename = fields.Char(string='Nama Berkas', readonly=True)

    def action_generate_export(self):
        self.ensure_one()
        if self.export_format == 'interactive':
            return {
                'type': 'ir.actions.client',
                'tag': 'consol_report_viewer_action',
                'name': self.report_id.name or _('Laporan Konsolidasi'),
                'params': {
                    'period_id': self.period_id.id,
                    'report_id': self.report_id.id,
                },
                'context': {
                    'default_period_id': self.period_id.id,
                    'default_report_id': self.report_id.id,
                    'active_id': self.period_id.id,
                }
            }

        elif self.export_format == 'pdf':
            return self.env.ref('odoo_psak_consolidation.action_report_consolidation_qweb').report_action(self.period_id, data={
                'period_id': self.period_id.id,
                'report_id': self.report_id.id,
            })

        elif self.export_format == 'xlsx':
            if not xlsxwriter:
                raise UserError(_("Modul Python 'xlsxwriter' belum terpasang!"))

            output = io.BytesIO()
            workbook = xlsxwriter.Workbook(output, {'in_memory': True})
            sheet = workbook.add_worksheet('Laporan Konsolidasi')

            # Gaya sel
            title_format = workbook.add_format({'bold': True, 'font_size': 14, 'align': 'center'})
            header_format = workbook.add_format({'bold': True, 'bg_color': '#1f4e79', 'font_color': '#ffffff', 'align': 'center', 'border': 1})
            bold_row_format = workbook.add_format({'bold': True, 'num_format': '#,##0.00'})
            bold_underline_format = workbook.add_format({'bold': True, 'underline': True, 'num_format': '#,##0.00'})
            num_format = workbook.add_format({'num_format': '#,##0.00'})
            text_format = workbook.add_format({})

            matrix = self.report_id.get_report_matrix(self.period_id.id)
            columns = matrix['columns']
            lines = matrix['lines']

            # Judul laporan
            sheet.merge_range(0, 0, 0, len(columns) + 1, matrix['report_name'].upper(), title_format)
            sheet.merge_range(1, 0, 1, len(columns) + 1, f"Grup: {matrix['group_name']} | Periode: {matrix['period_name']}", text_format)

            # Judul kolom
            sheet.write(3, 0, 'Ref Catatan', header_format)
            sheet.write(3, 1, 'Pos Laporan Keuangan', header_format)
            sheet.set_column(0, 0, 12)
            sheet.set_column(1, 1, 45)

            col_idx = 2
            for col in columns:
                sheet.write(3, col_idx, col['name'], header_format)
                sheet.set_column(col_idx, col_idx, 18)
                col_idx += 1

            # Rows
            row_idx = 4
            for line in lines:
                fmt = text_format
                n_fmt = num_format
                if line['bold'] and line['underline']:
                    fmt = bold_underline_format
                    n_fmt = bold_underline_format
                elif line['bold']:
                    fmt = bold_row_format
                    n_fmt = bold_row_format

                indent = '  ' * (line['level'] or 0)
                sheet.write(row_idx, 0, line['note'] or '', fmt)
                sheet.write(row_idx, 1, indent + line['name'], fmt)

                col_idx = 2
                for col in columns:
                    val = line['values'].get(col['id'], '')
                    if isinstance(val, (int, float)):
                        sheet.write(row_idx, col_idx, val, n_fmt)
                    else:
                        sheet.write(row_idx, col_idx, val, fmt)
                    col_idx += 1
                row_idx += 1

            workbook.close()
            output.seek(0)
            file_data = base64.b64encode(output.read())
            output.close()

            clean_filename = f"{matrix['report_name']}_{matrix['period_name']}.xlsx".replace(' ', '_')
            self.write({
                'file_data': file_data,
                'filename': clean_filename,
            })

            return {
                'type': 'ir.actions.act_url',
                'url': f'/web/content/?model=consol.report.export.wizard&id={self.id}&field=file_data&filename={clean_filename}&download=true',
                'target': 'self',
            }
