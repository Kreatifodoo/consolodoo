/** @odoo-module **/

import { Component, proxy, onWillStart, useProps } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { rpc } from "@web/core/network/rpc";
import { standardActionServiceProps } from "@web/webclient/actions/action_plugin";

export class ConsolReportViewer extends Component {
    static template = "odoo_psak_consolidation.ConsolReportViewer";
    props = useProps({ ...standardActionServiceProps });

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.notification = useService("notification");

        const actionParams = this.props.action?.params || {};
        const actionContext = this.props.action?.context || {};

        this.state = proxy({
            loading: true,
            report_id: actionParams.report_id || actionContext.default_report_id || false,
            report_type: actionParams.report_type || actionContext.default_report_type || false,
            period_id: actionParams.period_id || actionContext.default_period_id || "all",
            date_from: actionParams.date_from || actionContext.default_date_from || "",
            date_to: actionParams.date_to || actionContext.default_date_to || "",
            comparison: actionParams.comparison || actionContext.default_comparison || "none",
            show_entities: true,
            show_elimination: true,
            filter_mode: "all", // "all", "period", "custom"
            availablePeriods: [],
            availableReports: [],
            data: {},
            collapsedHeaders: {},
            unfoldedLines: {},
            unfoldedSubAccounts: {},
            allUnfolded: false,
            showDatePickerDropdown: false,
            showComparisonDropdown: false,
            showOptionsDropdown: false,
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
                ["id", "name", "date_from", "date_to", "state"],
                { order: "date_to desc, id desc" }
            );
            const reports = await this.orm.searchRead(
                "consol.report",
                [],
                ["id", "name", "report_type", "comparison", "show_entity_columns", "show_elimination_column"],
                { order: "sequence, id" }
            );
            this.state.availablePeriods = periods || [];
            this.state.availableReports = reports || [];

            // Pilih report_id berdasarkan report_type jika ada di context
            if (!this.state.report_id && this.state.report_type && reports.length) {
                const matched = reports.find(r => r.report_type === this.state.report_type);
                if (matched) {
                    this.state.report_id = matched.id;
                }
            }

            if (!this.state.report_id && reports.length) {
                this.state.report_id = reports[0].id;
            }

            // Atur default tanggal dari periode jika mode custom
            if (periods.length && !this.state.date_from && !this.state.date_to) {
                const earliest = periods[periods.length - 1];
                const latest = periods[0];
                this.state.date_from = earliest.date_from;
                this.state.date_to = latest.date_to;
            }
        } catch (err) {
            console.error("Gagal memuat metadata laporan:", err);
        }
    }

    async onReportSelect(reportId) {
        this.state.report_id = parseInt(reportId);
        const rep = this.state.availableReports.find(r => r.id === this.state.report_id);
        if (rep) {
            this.state.report_type = rep.report_type;
        }
        await this.loadReportData();
    }

    async onPeriodFilterSelect(mode, periodId = false) {
        this.state.showDatePickerDropdown = false;
        this.state.filter_mode = mode;

        if (mode === "all") {
            this.state.period_id = "all";
            this.state.date_from = "";
            this.state.date_to = "";
        } else if (mode === "period" && periodId) {
            this.state.period_id = parseInt(periodId);
            const per = this.state.availablePeriods.find(p => p.id === this.state.period_id);
            if (per) {
                this.state.date_from = per.date_from;
                this.state.date_to = per.date_to;
            }
        }
        await this.loadReportData();
    }

    async onApplyCustomDate() {
        this.state.showDatePickerDropdown = false;
        this.state.filter_mode = "custom";
        this.state.period_id = "custom";
        await this.loadReportData();
    }

    async onComparisonSelect(compMode) {
        this.state.showComparisonDropdown = false;
        this.state.comparison = compMode;
        await this.loadReportData();
    }

    async onToggleEntities() {
        this.state.show_entities = !this.state.show_entities;
        await this.loadReportData();
    }

    async onToggleElimination() {
        this.state.show_elimination = !this.state.show_elimination;
        await this.loadReportData();
    }

    isHeaderCollapsed(headerId) {
        return Boolean(this.state.collapsedHeaders[headerId]);
    }

    toggleHeader(headerId) {
        this.state.collapsedHeaders[headerId] = !this.state.collapsedHeaders[headerId];
    }

    isLineUnfolded(lineId) {
        return Boolean(this.state.unfoldedLines[lineId]);
    }

    toggleLineUnfold(lineId) {
        this.state.unfoldedLines[lineId] = !this.state.unfoldedLines[lineId];
    }

    isSubAccUnfolded(subAccId) {
        return Boolean(this.state.unfoldedSubAccounts[subAccId]);
    }

    toggleSubAcc(subAccId) {
        this.state.unfoldedSubAccounts[subAccId] = !this.state.unfoldedSubAccounts[subAccId];
    }

    onLineTitleClick(line) {
        if (line.is_header) {
            this.toggleHeader(line.id);
        } else if (line.can_unfold) {
            this.toggleLineUnfold(line.id);
        }
    }

    isLineHidden(line) {
        // Cek jika parent header line ini sedang di-collapse
        if (!line.parent_ids || !line.parent_ids.length) {
            return false;
        }
        for (const pid of line.parent_ids) {
            if (this.state.collapsedHeaders[pid]) {
                return true;
            }
        }
        return false;
    }

    toggleUnfoldAll() {
        if (this.state.allUnfolded) {
            // Tutup semua (kembali ke tampilan ringkasan standar)
            this.state.unfoldedLines = {};
            this.state.unfoldedSubAccounts = {};
            this.state.allUnfolded = false;
        } else {
            // Buka semua header dan buka semua rincian akun
            this.state.collapsedHeaders = {};
            const unfolded = {};
            const subUnfolded = {};
            (this.state.data?.lines || []).forEach(line => {
                if (line.can_unfold) {
                    unfolded[line.id] = true;
                    (line.account_details || []).forEach(acc => {
                        if (acc.source_details && acc.source_details.length) {
                            subUnfolded[acc.id] = true;
                        }
                    });
                }
            });
            this.state.unfoldedLines = unfolded;
            this.state.unfoldedSubAccounts = subUnfolded;
            this.state.allUnfolded = true;
        }
    }

    async loadReportData() {
        this.state.loading = true;
        try {
            if (!this.state.report_id) {
                await this.loadInitialMetadata();
            }

            if (this.state.report_id) {
                const params = {
                    report_id: this.state.report_id,
                    period_id: this.state.period_id,
                    date_from: this.state.date_from || false,
                    date_to: this.state.date_to || false,
                    comparison: this.state.comparison,
                    show_entities: this.state.show_entities,
                    show_elimination: this.state.show_elimination,
                };

                let res;
                try {
                    res = await rpc("/consolidation/report/data", params);
                } catch (rpcErr) {
                    console.warn("RPC route fetch fallback to ORM call:", rpcErr);
                    res = await this.orm.call(
                        "consol.report",
                        "get_report_matrix",
                        [[this.state.report_id]],
                        params
                    );
                }
                this.state.data = res || {};
            }
        } catch (error) {
            console.error("Gagal memuat data laporan konsolidasi:", error);
            this.notification.add("Gagal memuat data laporan konsolidasi: " + (error.message || error), { type: "danger" });
        } finally {
            this.state.loading = false;
        }
    }

    formatValue(val) {
        if (val === "" || val === undefined || val === null) {
            return "";
        }
        if (typeof val === "number") {
            return val.toLocaleString("id-ID", {
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
        if (line.line_type === "formula" || line.line_type === "total") classes.push("o_line_total");
        return classes.join(" ");
    }

    async onCellClick(line, col) {
        if (!line.drilldown || typeof line.values[col.id] !== "number") {
            return;
        }

        const domain = [];
        if (this.state.period_id && this.state.period_id !== "all" && this.state.period_id !== "custom") {
            domain.push(["period_id", "=", parseInt(this.state.period_id)]);
        }
        if (col.type === "entity") {
            domain.push(["entity_id", "=", col.entity_id]);
        }

        this.action.doAction({
            type: "ir.actions.act_window",
            name: `Rincian: ${line.name} (${col.name})`,
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
                default_period_id: this.state.period_id !== "all" && this.state.period_id !== "custom" ? this.state.period_id : (this.state.availablePeriods[0]?.id || false),
                default_report_id: this.state.report_id,
                default_export_format: "xlsx",
            },
        });
    }

    async printPdf() {
        const periodId = this.state.period_id !== "all" && this.state.period_id !== "custom" 
            ? this.state.period_id 
            : (this.state.availablePeriods[0]?.id || false);

        if (!periodId) {
            this.notification.add("Tidak ada periode konsolidasi yang tersedia untuk dicetak.", { type: "warning" });
            return;
        }

        this.action.doAction({
            type: "ir.actions.report",
            report_type: "qweb-pdf",
            report_name: "odoo_psak_consolidation.report_consolidation_document",
            context: {
                active_ids: [periodId],
                report_id: this.state.report_id,
                date_from: this.state.date_from,
                date_to: this.state.date_to,
            },
        });
    }
}

registry.category("actions").add("consol_report_viewer_action", ConsolReportViewer);
