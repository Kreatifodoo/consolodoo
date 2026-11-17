/** @odoo-module **/

import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { Component, proxy, onWillStart } from "@odoo/owl";

export class XbrlReportViewer extends Component {
    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        
        const today = new Date();
        const startOfYear = new Date(today.getFullYear(), 0, 1);
        
        this.state = proxy({
            dateFrom: startOfYear.toISOString().split('T')[0],
            dateTo: today.toISOString().split('T')[0],
            unfoldedLines: [],
            reportData: [],
            availableReports: [],
            selectedReportId: false
        });

        onWillStart(async () => {
            const reports = await this.orm.call("consolidation.xbrl.report.engine", "_get_reports", [[]]);
            this.state.availableReports = reports;
            if (reports.length > 0) {
                this.state.selectedReportId = reports[0].id;
            }
            if (this.state.selectedReportId) {
                await this.loadData();
            }
        });
    }

    async loadData() {
        if (!this.state.selectedReportId) return;
        try {
            const data = await this.orm.call(
                "consolidation.xbrl.report.engine",
                "_get_lines",
                [[]],
                {
                    options: {
                        date_from: this.state.dateFrom,
                        date_to: this.state.dateTo,
                        unfolded_lines: this.state.unfoldedLines,
                        report_id: parseInt(this.state.selectedReportId)
                    }
                }
            );
            this.state.reportData = data;
        } catch (e) {
            console.error("Error loading XBRL report", e);
        }
    }

    async toggleFold(line) {
        if (line.type !== 'xbrl_line') return;
        
        const index = this.state.unfoldedLines.indexOf(line.id);
        if (index > -1) {
            this.state.unfoldedLines.splice(index, 1);
        } else {
            this.state.unfoldedLines.push(line.id);
        }
        await this.loadData();
    }

    getLineClass(line) {
        if (line.type === 'xbrl_line' && line.indent === 0) return 'xbrl-header';
        if (line.type === 'xbrl_line' && line.has_children) return 'xbrl-header';
        if (line.type === 'coa_line') return 'coa-detail-line';
        return '';
    }

    drillDown(line) {
        if (line.type !== 'coa_line' || !line.master_coa_id) return;
        
        this.action.doAction({
            name: "Journal Items",
            type: "ir.actions.act_window",
            res_model: "account.move.line",
            view_mode: "tree,list,form",
            domain: [
                ['account_id', '=', line.master_coa_id],
                ['date', '>=', this.state.dateFrom],
                ['date', '<=', this.state.dateTo]
            ],
            target: "current"
        });
    }

    formatCurrency(value) {
        return new Intl.NumberFormat('en-US', { style: 'decimal', minimumFractionDigits: 2, maximumFractionDigits: 2 }).format(value);
    }

    exportExcel() {
        if (!this.state.selectedReportId) return;
        const url = `/xbrl_report/export_excel?date_from=${this.state.dateFrom}&date_to=${this.state.dateTo}&report_id=${this.state.selectedReportId}`;
        window.location = url;
    }

    exportPdf() {
        if (!this.state.selectedReportId) return;
        const url = `/xbrl_report/export_pdf?date_from=${this.state.dateFrom}&date_to=${this.state.dateTo}&report_id=${this.state.selectedReportId}`;
        window.location = url;
    }
}

XbrlReportViewer.template = "odoo_psak_consolidation.XbrlReportViewer";
registry.category("actions").add("consolidation_xbrl_dynamic_report", XbrlReportViewer);
