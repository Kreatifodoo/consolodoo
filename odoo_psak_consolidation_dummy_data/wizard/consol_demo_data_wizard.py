# -*- coding: utf-8 -*-
from odoo import models, fields, api, _

class ConsolDemoDataWizard(models.TransientModel):
    _name = 'consol.demo.data.wizard'
    _description = 'Generate or Reset PSAK 65 Consolidation Demo Data'

    confirm = fields.Boolean(
        string='Confirm Data Generation',
        default=True,
        required=True,
        help="Check to confirm creating/updating demo companies, transactions, and consolidation periods.")

    def action_generate_demo_data(self):
        self.ensure_one()
        self.env['consol.demo.installer'].install_demo_data()
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Demo Data Generated Successfully'),
                'message': _('Multi-company demo transactions and consolidation periods (2026-08 & 2026-09) have been successfully generated.'),
                'type': 'success',
                'sticky': False,
                'next': {'type': 'ir.actions.act_window_close'},
            }
        }
