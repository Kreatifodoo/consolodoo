# -*- coding: utf-8 -*-
from odoo import models, fields, api, _

class ConsolEliminationRule(models.Model):
    _name = 'consol.elimination.rule'
    _description = 'Aturan Standar Eliminasi Konsolidasi (PSAK 65)'
    _order = 'sequence, code'

    name = fields.Char(string='Nama Aturan', required=True)
    code = fields.Char(string='Kode Aturan', required=True, size=20)

    rule_type = fields.Selection([
        ('investment_equity', 'E1: Investasi pada Entitas Anak vs Ekuitas'),
        ('ic_balance', 'E2: Saldo Piutang / Utang Antar-Perusahaan'),
        ('ic_transaction', 'E3: Transaksi Pendapatan / Beban Antar-Perusahaan'),
        ('ic_dividend', 'E6: Dividen Antar-Perusahaan'),
        ('nci_attribution', 'E7: Atribusi Laba Rugi & OCI ke NCI'),
        ('cta', 'E10: Selisih Kurs Translasi Valuta Asing (CTA)')
    ], string='Tipe Eliminasi Standar', required=True)

    debit_account_ids = fields.Many2many(
        'consol.account',
        'consol_elim_rule_debit_rel',
        'rule_id',
        'account_id',
        string='Akun yang Dieliminasi (Sisi Debit)')

    credit_account_ids = fields.Many2many(
        'consol.account',
        'consol_elim_rule_credit_rel',
        'rule_id',
        'account_id',
        string='Akun yang Dieliminasi (Sisi Kredit)')

    difference_account_id = fields.Many2one(
        'consol.account',
        string='Akun Penampung Selisih',
        help="Akun penampung selisih jika diperkenankan (misal: selisih kurs transaksi intragrup).")

    active = fields.Boolean(string='Aktif', default=True)
    sequence = fields.Integer(string='Urutan Eksekusi', default=10)
    description = fields.Text(string='Dasar Standar Akuntansi / Penjelasan')
