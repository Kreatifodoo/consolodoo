/** @odoo-module **/

import { Component, useState, onWillStart } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { rpc } from "@web/core/network/rpc";
import { standardActionServiceProps } from "@web/webclient/actions/action_service";

export class ConsolReportViewer extends Component {
    static template = "odoo_psak_consolidation.ConsolReportViewer";
    static props = { ...standardActionServiceProps };

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.notification = useService("notification");

        const actionParams = this.props.action?.params || {};
        const actionContext = this.props.action?.context || {};

        this.state = useState({
            loading: true,
            period_id: actionParams.period_id || actionContext.default_period_id || actionContext.period_id || false,
            report_id: actionParams.report_id || actionContext.default_report_id || actionContext.report_id || false,
            availablePeriods: [],
            availableReports: [],
            data: {},
        });

        onWillStart(async () => {
            await this.loadInitialMetadata();
            await this.loadReportData();
        });
    }

    async loadInitialMetadata() {
        try {
            const periods = await this.orm.searchRead(
                "consol.period",
                [],
                ["id", "name"],
                { order: "date_to desc, id desc" }
            );
            const reports = await this.orm.searchRead(
                "consol.report",
                [],
                ["id", "name", "report_type"],
                { order: "sequence, id" }
            );
            this.state.availablePeriods = periods || [];
            this.state.availableReports = reports || [];

            if (!this.state.period_id && periods.length) {
                this.state.period_id = periods[0].id;
            }
            if (!this.state.report_id && reports.length) {
                this.state.report_id = reports[0].id;
            }
        } catch (err) {
            console.error("Failed to load metadata:", err);
        }
    }

    async onReportChange(ev) {
        this.state.report_id = parseInt(ev.target.value);
        await this.loadReportData();
    }

    async onPeriodChange(ev) {
        this.state.period_id = parseInt(ev.target.value);
        await this.loadReportData();
    }

    async loadReportData() {
        this.state.loading = true;
        try {
            if (!this.state.period_id || !this.state.report_id) {
                await this.loadInitialMetadata();
            }

            if (this.state.period_id && this.state.report_id) {
                let res;
                try {
                    res = await rpc("/consolidation/report/data", {
                        period_id: this.state.period_id,
                        report_id: this.state.report_id,
                    });
                } catch (rpcErr) {
                    console.warn("RPC route fetch fallback to ORM call:", rpcErr);
                    res = await this.orm.call(
                        "consol.report",
                        "get_report_matrix",
                        [[this.state.report_id], this.state.period_id]
                    );
                }
                this.state.data = res || {};
            }
        } catch (error) {
            console.error("Failed to load consolidation report data:", error);
            this.notification.add("Failed to load consolidation report data: " + (error.message || error), { type: "danger" });
        } finally {
            this.state.loading = false;
        }
    }

    formatValue(val) {
        if (val === "" || val === undefined || val === null) {
            return "";
        }
        if (typeof val === "number") {
            return val.toLocaleString("en-US", {
                minimumFractionDigits: 2,
                maximumFractionDigits: 2,
            });
        }
        return val;
    }

    getLineClass(line) {
        const classes = [];
        if (line.bold) classes.push("o_line_bold");
        if (line.underline) classes.push("o_line_underline");
        if (line.line_type === "header") classes.push("o_line_header");
        return classes.join(" ");
    }

    async onCellClick(line, col) {
        if (!line.drilldown || typeof line.values[col.id] !== "number") {
            return;
        }

        // Buka rincian baris trial balance line
        const domain = [["period_id", "=", this.state.period_id]];
        if (col.type === "entity") {
            domain.push(["entity_id", "=", col.entity_id]);
        }

        this.action.doAction({
            type: "ir.actions.act_window",
            name: `Drill-down: ${line.name} (${col.name})`,
            res_model: "consol.trial.balance.line",
            view_mode: "list,form",
            views: [[false, "list"], [false, "form"]],
            domain: domain,
            target: "current",
        });
    }

    async refreshData() {
        await this.loadReportData();
    }

    async exportExcel() {
        this.action.doAction({
            type: "ir.actions.act_window",
            res_model: "consol.report.export.wizard",
            view_mode: "form",
            views: [[false, "form"]],
            target: "new",
            context: {
                default_period_id: this.state.period_id,
                default_report_id: this.state.report_id,
                default_export_format: "xlsx",
            },
        });
    }

    async printPdf() {
        this.action.doAction({
            type: "ir.actions.report",
            report_type: "qweb-pdf",
            report_name: "odoo_psak_consolidation.report_consolidation_document",
            context: {
                active_ids: [this.state.period_id],
                report_id: this.state.report_id,
            },
        });
    }
}

registry.category("actions").add("consol_report_viewer_action", ConsolReportViewer);
