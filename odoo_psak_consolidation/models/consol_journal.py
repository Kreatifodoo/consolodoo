# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, UserError

class ConsolJournal(models.Model):
    _name = 'consol.journal'
    _description = 'Consolidation Elimination Journal (E1-E10 & Manual Adjustments)'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'period_id, code, id'

    name = fields.Char(string='Journal Description', required=True, tracking=True)
    code = fields.Char(string='Journal Code', required=True, default='MANUAL', tracking=True,
                       help="Example: E1, E2, E3, E4, E5, E6, E7, E8, E9, E10, or MANUAL.")

    period_id = fields.Many2one(
        'consol.period',
        string='Consolidation Period',
        required=True,
        ondelete='cascade',
        tracking=True)

    group_id = fields.Many2one(
        'consol.group',
        string='Consolidation Group',
        related='period_id.group_id',
        store=True)

    currency_id = fields.Many2one(
        'res.currency',
        string='Reporting Currency',
        related='period_id.currency_id')

    origin = fields.Selection([
        ('auto', 'Automated'),
        ('manual', 'Manual / User')
    ], string='Journal Source', default='manual', required=True, tracking=True)

    rule_id = fields.Many2one(
        'consol.elimination.rule',
        string='Elimination Rule',
        help="Standard rule if journal was automatically generated.")

    recurring = fields.Boolean(
        string='Recurring (Carry-Forward)',
        default=False,
        tracking=True,
        help="If checked, this journal will be carried forward to the next consolidation period as opening balance (e.g. E1, E5, E9).")

    auto_reverse = fields.Boolean(
        string='Auto-Reverse',
        default=False,
        tracking=True,
        help="If checked, this journal will be automatically reversed in the next consolidation period (e.g. E4 unrealized inventory profit).")

    reversed_from_id = fields.Many2one(
        'consol.journal',
        string='Reversed From Journal',
        readonly=True)

    line_ids = fields.One2many(
        'consol.journal.line',
        'journal_id',
        string='Elimination Journal Lines')

    total_debit = fields.Monetary(
        string='Total Debit',
        currency_field='currency_id',
        compute='_compute_totals',
        store=True)

    total_credit = fields.Monetary(
        string='Total Credit',
        currency_field='currency_id',
        compute='_compute_totals',
        store=True)

    state = fields.Selection([
        ('draft', 'Draft'),
        ('posted', 'Posted')
    ], string='Status', default='draft', required=True, tracking=True)

    note = fields.Text(string='PSAK Basis / Supporting Notes')

    @api.depends('line_ids.debit', 'line_ids.credit')
    def _compute_totals(self):
        for rec in self:
            rec.total_debit = sum(line.debit for line in rec.line_ids)
            rec.total_credit = sum(line.credit for line in rec.line_ids)

    @api.constrains('state', 'line_ids')
    def _check_balance(self):
        for rec in self:
            if rec.state == 'posted':
                if not rec.line_ids:
                    raise ValidationError(_("Journal '%s' has no lines!", rec.name))
                if round(rec.total_debit, 2) != round(rec.total_credit, 2):
                    raise ValidationError(_(
                        "Elimination journal '%s' is not balanced!\nTotal Debit: %s\nTotal Credit: %s\nDifference: %s",
                        rec.name, rec.total_debit, rec.total_credit, abs(rec.total_debit - rec.total_credit)
                    ))

    def action_post(self):
        for rec in self:
            rec._check_balance()
            rec.state = 'posted'

    def action_reset_draft(self):
        for rec in self:
            if rec.period_id.state == 'locked':
                raise UserError(_("Consolidation period is already locked!"))
            rec.state = 'draft'


class ConsolJournalLine(models.Model):
    _name = 'consol.journal.line'
    _description = 'Consolidation Elimination Journal Line'
    _order = 'journal_id, id'

    journal_id = fields.Many2one(
        'consol.journal',
        string='Elimination Journal',
        required=True,
        ondelete='cascade')

    period_id = fields.Many2one(
        'consol.period',
        string='Period',
        related='journal_id.period_id',
        store=True,
        index=True)

    currency_id = fields.Many2one(
        'res.currency',
        string='Currency',
        related='journal_id.currency_id')

    consol_account_id = fields.Many2one(
        'consol.account',
        string='Consolidation Account',
        required=True,
        index=True)

    entity_id = fields.Many2one(
        'consol.entity',
        string='Working Paper Column (Related Entity)',
        help="Leave empty if elimination applies globally to the Elimination (ELIM) column.")

    partner_entity_id = fields.Many2one(
        'consol.entity',
        string='Counterparty Entity',
        help="Transaction partner entity if relevant.")

    debit = fields.Monetary(
        string='Debit',
        currency_field='currency_id',
        default=0.0)

    credit = fields.Monetary(
        string='Credit',
        currency_field='currency_id',
        default=0.0)

    nci_share = fields.Float(
        string='NCI Share (%)',
        help="Non-controlling interest percentage affected by this line.")

    note = fields.Char(string='Line Description')
