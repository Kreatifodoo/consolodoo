/** @odoo-module **/

import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { Component, useState, onWillStart } from "@odoo/owl";

export class WPViewer extends Component {
    setup() {
        this.orm = useService("orm");
        this.actionService = useService("action");
        
        this.state = useState({
            data: null,
        });

        // The period_id is passed in the context
        this.periodId = this.props.action.context.active_id;

        onWillStart(async () => {
            await this.loadData();
        });
    }

    async loadData() {
        if (!this.periodId) return;
        this.state.data = await this.orm.call(
            "consolidation.wp.summary.wizard",
            "get_wp_data",
            [this.periodId]
        );
    }
    
    formatCurrency(value) {
        if (!value) return '0';
        return value.toLocaleString('id-ID', { minimumFractionDigits: 0, maximumFractionDigits: 2 });
    }
    
    goBack() {
        this.actionService.doAction("odoo_psak_consolidation.action_consolidation_wp_summary_wizard");
    }
}

WPViewer.template = "odoo_psak_consolidation.WPViewer";
registry.category("actions").add("odoo_psak_consolidation.wp_viewer", WPViewer);
