# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import UserError

class ConsolAutoMapWizard(models.TransientModel):
    _name = 'consol.auto.map.wizard'
    _description = 'Wisard Pemetaan Otomatis Bagan Akun'

    entity_ids = fields.Many2many(
        'consol.entity',
        string='Pilih Entitas',
        required=True,
        domain="[('source_type', '=', 'odoo')]",
        help="Pilih satu atau lebih entitas yang ingin dipetakan akunnya secara otomatis.")

    match_strategy = fields.Selection([
        ('exact_code', 'Kesesuaian Kode Akun Persis'),
        ('prefix_code', 'Kesesuaian Awalan Kode Akun'),
    ], string='Metode Pencocokan Akun', default='prefix_code', required=True,
       help="Metode yang digunakan untuk mencocokkan kode akun lokal dengan kode akun konsolidasi.")

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
                'title': _('Pemetaan Otomatis Berhasil'),
                'message': _('Berhasil memetakan %s akun secara otomatis.', total_mapped),
                'sticky': False,
                'next': {'type': 'ir.actions.act_window_close'},
            }
        }
