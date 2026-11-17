# -*- coding: utf-8 -*-
from odoo import models, fields, api, _

class ConsolIntercompanyMatch(models.Model):
    _name = 'consol.intercompany.match'
    _description = 'Pencocokan & Rekonsiliasi Antar-Perusahaan'
    _order = 'period_id, status desc, difference desc'

    period_id = fields.Many2one(
        'consol.period',
        string='Periode Konsolidasi',
        required=True,
        ondelete='cascade')

    entity_a_id = fields.Many2one(
        'consol.entity',
        string='Entitas A',
        required=True)

    entity_b_id = fields.Many2one(
        'consol.entity',
        string='Entitas B (Lawan Transaksi)',
        required=True)

    account_a_id = fields.Many2one(
        'consol.account',
        string='Akun Entitas A',
        required=True)

    account_b_id = fields.Many2one(
        'consol.account',
        string='Akun Lawan Entitas B',
        required=True)

    currency_id = fields.Many2one(
        'res.currency',
        string='Mata Uang Pelaporan',
        related='period_id.currency_id')

    amount_a = fields.Monetary(
        string='Saldo Entitas A (RC)',
        currency_field='currency_id',
        default=0.0)

    amount_b = fields.Monetary(
        string='Saldo Entitas B (RC)',
        currency_field='currency_id',
        default=0.0)

    difference = fields.Monetary(
        string='Selisih Nilai (RC)',
        currency_field='currency_id',
        compute='_compute_difference',
        store=True)

    status = fields.Selection([
        ('matched', 'Cocok (Nol Selisih)'),
        ('within_tolerance', 'Dalam Batas Toleransi'),
        ('unmatched', 'Di Luar Batas Toleransi')
    ], string='Status Rekonsiliasi', compute='_compute_status', store=True)

    is_overridden = fields.Boolean(
        string='Disetujui Manual (Override)',
        default=False,
        help="Pengguna yang berwenang menyetujui selisih agar alur kerja penguncian periode dapat dilanjutkan.")

    override_reason = fields.Text(string='Alasan Persetujuan / Catatan Selisih')
    overridden_by = fields.Many2one('res.users', string='Disetujui Oleh')

    note = fields.Char(string='Catatan Tambahan')

    @api.depends('amount_a', 'amount_b')
    def _compute_difference(self):
        for rec in self:
            rec.difference = abs(abs(rec.amount_a) - abs(rec.amount_b))

    @api.depends('difference', 'period_id.group_id.ic_tolerance')
    def _compute_status(self):
        for rec in self:
            tol = rec.period_id.group_id.ic_tolerance or 0.0
            if abs(rec.difference) <= 0.01:
                rec.status = 'matched'
            elif abs(rec.difference) <= tol:
                rec.status = 'within_tolerance'
            else:
                rec.status = 'unmatched'

    def action_override_difference(self):
        self.ensure_one()
        self.write({
            'is_overridden': True,
            'overridden_by': self.env.user.id,
        })
