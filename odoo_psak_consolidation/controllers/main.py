# -*- coding: utf-8 -*-
from odoo import http
from odoo.http import request

class ConsolidationReportController(http.Controller):

    @http.route('/consolidation/report/data', type='jsonrpc', auth='user')
    def get_consol_report_data(self, report_id, period_id=False, date_from=False, date_to=False, comparison=False, show_entities=True, show_elimination=True):
        try:
            r_id = int(report_id)
        except (ValueError, TypeError):
            return {'error': 'Invalid report_id'}
        report = request.env['consol.report'].browse(r_id)
        if not report.exists():
            return {'error': 'Report not found'}
        return report.get_report_matrix(
            period_id=period_id,
            date_from=date_from,
            date_to=date_to,
            comparison=comparison,
            show_entities=show_entities,
            show_elimination=show_elimination
        )

    @http.route('/consolidation/report/drilldown', type='jsonrpc', auth='user')
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
