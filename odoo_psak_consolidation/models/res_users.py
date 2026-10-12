# -*- coding: utf-8 -*-
from odoo import models, fields

class ResUsers(models.Model):
    _inherit = 'res.users'

    consol_group_ids = fields.Many2many(
        'consol.group',
        'res_users_consol_group_rel',
        'user_id',
        'group_id',
        string='Akses Grup Konsolidasi',
        help="Grup konsolidasi yang diizinkan untuk diakses oleh pengguna ini.")
