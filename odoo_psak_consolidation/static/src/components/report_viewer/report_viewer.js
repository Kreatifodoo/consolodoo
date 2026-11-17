/** @odoo-module **/
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { Component, onWillStart, proxy } from "@odoo/owl";

export class ConsolidationReportViewer extends Component {
    static template = "odoo_psak_consolidation.ReportViewer";

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.state = proxy({
            reportData: null,
            loading: true,
        });

        onWillStart(async () => {
            await this.loadData();
        });
    }

    async loadData() {
        const wizardId = this.props.action.context.wizard_id;
        if (wizardId) {
            this.state.reportData = await this.orm.call(
                "consolidation.report.viewer",
                "get_report_data",
                [wizardId]
            );
        }
        this.state.loading = false;
    }

    formatCurrency(value) {
        return new Intl.NumberFormat('id-ID', { style: 'currency', currency: 'IDR' }).format(value || 0);
    }
    
    downloadPdf() {
        const wizardId = this.props.action.context.wizard_id;
        if (!wizardId) return;
        this.action.doAction({
            type: 'ir.actions.report',
            report_type: 'qweb-pdf',
            report_name: 'odoo_psak_consolidation.report_financial_pdf',
            report_file: 'odoo_psak_consolidation.report_financial_pdf',
            data: { wizard_id: wizardId }
        });
    }
    
    downloadXls() {
        const wizardId = this.props.action.context.wizard_id;
        if (!wizardId) return;
        window.location.href = `/consolidation/download_xls/${wizardId}`;
    }
}

registry.category("actions").add("consolidation_report_client_action", ConsolidationReportViewer);
