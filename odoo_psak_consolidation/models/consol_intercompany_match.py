# -*- coding: utf-8 -*-
from odoo import models, fields, api, _

class ConsolIntercompanyMatch(models.Model):
    _name = 'consol.intercompany.match'
    _description = 'Intercompany Matching & Reconciliation'
    _order = 'period_id, status desc, difference desc'

    period_id = fields.Many2one(
        'consol.period',
        string='Consolidation Period',
        required=True,
        ondelete='cascade')

    entity_a_id = fields.Many2one(
        'consol.entity',
        string='Entity A',
        required=True)

    entity_b_id = fields.Many2one(
        'consol.entity',
        string='Entity B (Counterparty)',
        required=True)

    account_a_id = fields.Many2one(
        'consol.account',
        string='Entity A Account',
        required=True)

    account_b_id = fields.Many2one(
        'consol.account',
        string='Entity B Counterpart Account',
        required=True)

    currency_id = fields.Many2one(
        'res.currency',
        string='Reporting Currency',
        related='period_id.currency_id')

    amount_a = fields.Monetary(
        string='Entity A Balance (RC)',
        currency_field='currency_id',
        default=0.0)

    amount_b = fields.Monetary(
        string='Entity B Balance (RC)',
        currency_field='currency_id',
        default=0.0)

    difference = fields.Monetary(
        string='Discrepancy (RC)',
        currency_field='currency_id',
        compute='_compute_difference',
        store=True)

    status = fields.Selection([
        ('matched', 'Matched (Zero Difference)'),
        ('within_tolerance', 'Within Tolerance'),
        ('unmatched', 'Out of Tolerance')
    ], string='Reconciliation Status', compute='_compute_status', store=True)

    is_overridden = fields.Boolean(
        string='Manually Overridden',
        default=False,
        help="Authorized user approves discrepancy so period workflow can proceed/lock.")

    override_reason = fields.Text(string='Override Reason / Discrepancy Note')
    overridden_by = fields.Many2one('res.users', string='Overridden By')

    note = fields.Char(string='Additional Notes')

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
