# -*- coding: utf-8 -*-
from odoo import http
from odoo.http import request

class ConsolidationReportController(http.Controller):

    @http.route('/consolidation/report/data', type='json', auth='user')
    def get_consol_report_data(self, period_id, report_id):
        report = request.env['consol.report'].browse(report_id)
        if not report.exists():
            return {'error': 'Report not found'}
        return report.get_report_matrix(period_id)

    @http.route('/consolidation/report/drilldown', type='json', auth='user')
    def get_drilldown_lines(self, period_id, consol_account_id=False, entity_id=False):
        domain = [('period_id', '=', period_id)]
        if consol_account_id:
            domain.append(('consol_account_id', '=', consol_account_id))
        if entity_id:
            domain.append(('entity_id', '=', entity_id))

        lines = request.env['consol.trial.balance.line'].search_read(
            domain,
            fields=['consol_account_id', 'entity_id', 'source_account_id', 'balance_fc', 'rate_used', 'balance_rc']
        )
        return {'lines': lines}
