# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError

class ConsolOwnership(models.Model):
    _name = 'consol.ownership'
    _description = 'Share Ownership & Control Structure'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'parent_id, child_id, date_from desc'

    parent_id = fields.Many2one(
        'consol.entity',
        string='Parent Entity / Owner',
        required=True,
        tracking=True,
        ondelete='cascade')

    child_id = fields.Many2one(
        'consol.entity',
        string='Subsidiary / Investee (Child)',
        required=True,
        tracking=True,
        ondelete='cascade')

    percentage = fields.Float(
        string='Direct Ownership (%)',
        required=True,
        default=100.0,
        tracking=True,
        help="Direct economic ownership percentage held by parent over child.")

    voting_percentage = fields.Float(
        string='Voting Rights (%)',
        help="Voting rights percentage. May differ from share capital if non-voting preference shares exist.")

    method = fields.Selection([
        ('full', 'Full Consolidation (IFRS 10)'),
        ('equity', 'Equity Method (IAS 28)'),
        ('fair_value', 'Fair Value through P&L (IFRS 9)'),
        ('none', 'Not Consolidated')
    ], string='Accounting Method', default='full', required=True, tracking=True)

    date_from = fields.Date(
        string='Control Acquisition Date',
        tracking=True,
        help="Effective date of obtaining control (IFRS 10 par. 20).")

    date_to = fields.Date(
        string='Loss of Control Date',
        tracking=True,
        help="Date of divestment or loss of control.")

    nci_measurement = fields.Selection([
        ('fair_value', 'Fair Value'),
        ('proportionate', 'Proportionate Share of Identifiable Net Assets')
    ], string='Initial NCI Measurement Method (IFRS 3)', default='proportionate', required=True)

    effective_percentage = fields.Float(
        string='Effective Ownership (%)',
        compute='_compute_effective_percentage',
        store=True,
        digits=(6, 4),
        tracking=True,
        help="Cumulative effective ownership percentage calculated across direct and multi-tier paths.")

    nci_percentage = fields.Float(
        string='Non-Controlling Interest / NCI (%)',
        compute='_compute_nci_percentage',
        store=True,
        digits=(6, 4),
        tracking=True,
        help="Ownership percentage held by non-controlling parties outside the parent entity (100% - Effective Ownership).")

    currency_id = fields.Many2one(
        'res.currency',
        string='Currency',
        related='parent_id.functional_currency_id')

    goodwill_amount = fields.Monetary(
        string='Initial Goodwill at Acquisition (E1)',
        currency_field='currency_id',
        tracking=True,
        help="Goodwill recognized at business combination acquisition date (IFRS 3).")

    nci_at_acquisition = fields.Monetary(
        string='Initial NCI at Acquisition (E1)',
        currency_field='currency_id',
        tracking=True,
        help="Non-controlling interest recognized at acquisition date.")

    note = fields.Text(string='Investment Analysis Notes')

    @api.constrains('parent_id', 'child_id')
    def _check_self_ownership(self):
        for rec in self:
            if rec.parent_id == rec.child_id:
                raise ValidationError(_("Entity '%s' cannot own itself!", rec.parent_id.name))

    @api.constrains('percentage', 'voting_percentage')
    def _check_percentages(self):
        for rec in self:
            if rec.percentage < 0 or rec.percentage > 100:
                raise ValidationError(_("Ownership percentage must be between 0% and 100%!"))
            if rec.voting_percentage and (rec.voting_percentage < 0 or rec.voting_percentage > 100):
                raise ValidationError(_("Voting rights percentage must be between 0% and 100%!"))

    @api.depends('parent_id', 'child_id', 'percentage', 'method')
    def _compute_effective_percentage(self):
        """
        Compute effective percentage using graph traversal.
        Supports direct, multi-tier, and cross-ownership paths with circular loop detection.
        """
        all_ownerships = self.search([])
        graph = {}
        for own in all_ownerships:
            graph.setdefault(own.parent_id.id, []).append((own.child_id.id, own.percentage / 100.0))

        def find_all_paths(start, end, visited=None):
            if visited is None:
                visited = []
            if start in visited:
                raise ValidationError(_("Circular ownership loop detected involving entity ID %s!", start))
            new_visited = visited + [start]
            if start == end:
                return [[1.0]]
            paths = []
            for neighbor, weight in graph.get(start, []):
                sub_paths = find_all_paths(neighbor, end, new_visited)
                for sp in sub_paths:
                    paths.append([weight] + sp)
            return paths

        for rec in self:
            if not rec.parent_id or not rec.child_id:
                rec.effective_percentage = rec.percentage
                continue

            try:
                # Cari semua jalur kepemilikan dari parent_id ke child_id
                paths = []
                for neighbor, weight in graph.get(rec.parent_id.id, []):
                    if neighbor == rec.child_id.id:
                        paths.append([weight])
                    else:
                        sub_paths = find_all_paths(neighbor, rec.child_id.id, [rec.parent_id.id])
                        for sp in sub_paths:
                            paths.append([weight] + sp)

                total_effective = 0.0
                for path in paths:
                    path_eff = 1.0
                    for step in path:
                        path_eff *= step
                    total_effective += path_eff

                rec.effective_percentage = round(total_effective * 100.0, 4) if total_effective > 0 else rec.percentage
            except Exception as e:
                # Default ke persentase langsung jika fallback
                rec.effective_percentage = rec.percentage

    @api.depends('effective_percentage', 'method')
    def _compute_nci_percentage(self):
        for rec in self:
            if rec.method == 'full':
                rec.nci_percentage = round(max(0.0, 100.0 - rec.effective_percentage), 4)
            else:
                rec.nci_percentage = 0.0
