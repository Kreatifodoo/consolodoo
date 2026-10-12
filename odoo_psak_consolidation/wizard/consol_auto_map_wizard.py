# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import UserError

class ConsolAutoMapWizard(models.TransientModel):
    _name = 'consol.auto.map.wizard'
    _description = 'Chart of Accounts Auto-Map Wizard'

    entity_ids = fields.Many2many(
        'consol.entity',
        string='Select Entities',
        required=True,
        domain="[('source_type', '=', 'odoo')]")

    match_strategy = fields.Selection([
        ('exact_code', 'Exact Code Match'),
        ('prefix_code', 'Code Prefix Match'),
    ], string='Matching Method', default='prefix_code', required=True)

    def action_execute_auto_map(self):
        self.ensure_one()
        mapping_model = self.env['consol.account.mapping']
        total_mapped = 0

        for entity in self.entity_ids:
            if entity.company_id:
                count = mapping_model.auto_map_accounts(entity.id)
                total_mapped += count

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Auto-Map Succeeded'),
                'message': _('Successfully mapped %s accounts automatically.', total_mapped),
                'sticky': False,
                'next': {'type': 'ir.actions.act_window_close'},
            }
        }
