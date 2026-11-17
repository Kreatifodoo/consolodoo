# -*- coding: utf-8 -*-
from odoo import models, fields, api, _

class ConsolTrialBalance(models.Model):
    _name = 'consol.trial.balance'
    _description = 'Neraca Saldo Entitas per Periode'
    _order = 'period_id, entity_id'

    period_id = fields.Many2one(
        'consol.period',
        string='Periode Konsolidasi',
        required=True,
        ondelete='cascade')

    entity_id = fields.Many2one(
        'consol.entity',
        string='Entitas Konsolidasi',
        required=True,
        ondelete='cascade')

    functional_currency_id = fields.Many2one(
        'res.currency',
        string='Mata Uang Fungsional',
        related='entity_id.functional_currency_id')

    reporting_currency_id = fields.Many2one(
        'res.currency',
        string='Mata Uang Pelaporan',
        related='period_id.currency_id')

    line_ids = fields.One2many(
        'consol.trial.balance.line',
        'trial_balance_id',
        string='Baris Neraca Saldo')

    total_debit_rc = fields.Float(
        string='Total Debit (RC)',
        compute='_compute_totals',
        store=True)

    total_credit_rc = fields.Float(
        string='Total Kredit (RC)',
        compute='_compute_totals',
        store=True)

    total_balance_rc = fields.Float(
        string='Total Saldo (RC)',
        compute='_compute_totals',
        store=True)

    _period_entity_unique = models.Constraint(
        'unique(period_id, entity_id)',
        'Neraca saldo untuk entitas dan periode ini sudah ada!',
    )

    @api.depends('line_ids.balance_rc')
    def _compute_totals(self):
        for rec in self:
            deb = sum(line.balance_rc for line in rec.line_ids if line.balance_rc > 0)
            cred = sum(abs(line.balance_rc) for line in rec.line_ids if line.balance_rc < 0)
            rec.total_debit_rc = deb
            rec.total_credit_rc = cred
            rec.total_balance_rc = sum(line.balance_rc for line in rec.line_ids)


class ConsolTrialBalanceLine(models.Model):
    _name = 'consol.trial.balance.line'
    _description = 'Rincian Baris Saldo Akun Kertas Kerja'
    _order = 'consol_account_id, source_account_id'

    trial_balance_id = fields.Many2one(
        'consol.trial.balance',
        string='Neraca Saldo',
        required=True,
        ondelete='cascade')

    period_id = fields.Many2one(
        'consol.period',
        string='Periode',
        related='trial_balance_id.period_id',
        store=True,
        index=True)

    entity_id = fields.Many2one(
        'consol.entity',
        string='Entitas',
        related='trial_balance_id.entity_id',
        store=True,
        index=True)

    consol_account_id = fields.Many2one(
        'consol.account',
        string='Akun Konsolidasi',
        required=True,
        ondelete='restrict',
        index=True)

    source_account_id = fields.Many2one(
        'account.account',
        string='Akun Odoo Asal',
        ondelete='set null')

    external_code = fields.Char(string='Kode Akun Eksternal')
    external_name = fields.Char(string='Nama Akun Eksternal')

    partner_id = fields.Many2one(
        'res.partner',
        string='Mitra Antar-Perusahaan',
        help="Mitra/partner pada transaksi yang digunakan untuk pencocokan transaksi intragrup.")

    statement = fields.Selection(
        related='consol_account_id.statement',
        store=True,
        string='Kelompok Laporan Keuangan')

    translation_rate_type = fields.Selection(
        related='consol_account_id.translation_rate',
        store=True,
        string='Jenis Kurs')

    balance_fc = fields.Float(
        string='Saldo Mata Uang Fungsional (FC)',
        digits=(16, 2),
        default=0.0)

    movement_fc = fields.Float(
        string='Pergerakan Saldo (FC)',
        digits=(16, 2),
        default=0.0)

    rate_used = fields.Float(
        string='Kurs Diterapkan',
        digits=(24, 12),
        default=1.0)

    balance_rc = fields.Float(
        string='Saldo Mata Uang Pelaporan (RC)',
        digits=(16, 2),
        default=0.0)

    is_intercompany = fields.Boolean(
        related='consol_account_id.is_intercompany',
        store=True)
