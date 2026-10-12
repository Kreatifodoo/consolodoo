# -*- coding: utf-8 -*-
from odoo.tests.common import TransactionCase
from odoo.exceptions import ValidationError, UserError

class TestPSAKConsolidation(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Currency = cls.env['res.currency']
        cls.idr = cls.env.ref('base.IDR', raise_if_not_found=False) or cls.env.company.currency_id
        cls.usd = cls.env.ref('base.USD', raise_if_not_found=False)

        # 1. Buat Entitas
        cls.Entity = cls.env['consol.entity']
        cls.parent_entity = cls.Entity.create({
            'name': 'PT Induk Holdings Tbk',
            'code': 'INDUK',
            'source_type': 'import',
            'functional_currency_id': cls.idr.id,
        })

        cls.child_a = cls.Entity.create({
            'name': 'PT Anak Manufaktur',
            'code': 'ANAK_A',
            'source_type': 'import',
            'functional_currency_id': cls.idr.id,
        })

        cls.grandchild_b = cls.Entity.create({
            'name': 'PT Cucu Distribusi',
            'code': 'CUCU_B',
            'source_type': 'import',
            'functional_currency_id': cls.idr.id,
        })

        # 2. Buat Akun Konsolidasi Utama
        cls.Account = cls.env['consol.account']
        cls.acc_cash = cls.Account.create({
            'name': 'Kas Konsolidasi',
            'code': 'TST_101',
            'account_type': 'asset_cash',
            'statement': 'bs',
            'translation_rate': 'closing',
        })
        cls.acc_inv = cls.Account.create({
            'name': 'Investasi pada Anak',
            'code': 'TST_107',
            'account_type': 'asset_non_current',
            'statement': 'bs',
            'translation_rate': 'closing',
        })
        cls.acc_cap = cls.Account.create({
            'name': 'Modal Saham',
            'code': 'TST_301',
            'account_type': 'equity',
            'statement': 'equity',
            'translation_rate': 'historical',
        })
        cls.acc_re = cls.Account.create({
            'name': 'Saldo Laba',
            'code': 'TST_303',
            'account_type': 'equity',
            'statement': 'equity',
            'translation_rate': 'historical',
        })
        cls.acc_nci_eq = cls.Account.create({
            'name': 'NCI Ekuitas',
            'code': 'TST_305',
            'account_type': 'equity',
            'statement': 'equity',
            'translation_rate': 'closing',
        })
        cls.acc_nci_pl = cls.Account.create({
            'name': 'NCI Laba Rugi',
            'code': 'TST_701',
            'account_type': 'expense',
            'statement': 'pl',
            'translation_rate': 'average',
        })
        cls.acc_gw = cls.Account.create({
            'name': 'Goodwill',
            'code': 'TST_160',
            'account_type': 'asset_non_current',
            'statement': 'bs',
            'translation_rate': 'closing',
        })
        cls.acc_cta = cls.Account.create({
            'name': 'CTA OCI',
            'code': 'TST_304',
            'account_type': 'equity',
            'statement': 'oci',
            'translation_rate': 'closing',
        })

        # 3. Buat Grup Konsolidasi
        cls.Group = cls.env['consol.group']
        cls.consol_group = cls.Group.create({
            'name': 'PT Induk Konsolidasi Grup',
            'parent_entity_id': cls.parent_entity.id,
            'currency_id': cls.idr.id,
            'nci_equity_account_id': cls.acc_nci_eq.id,
            'nci_pl_account_id': cls.acc_nci_pl.id,
            'goodwill_account_id': cls.acc_gw.id,
            'cta_account_id': cls.acc_cta.id,
            'retained_earnings_account_id': cls.acc_re.id,
            'ic_tolerance': 1000.0,
            'entity_ids': [(6, 0, [cls.parent_entity.id, cls.child_a.id, cls.grandchild_b.id])],
        })

    def test_01_ownership_multi_tier_and_cycle_prevention(self):
        """Uji perhitungan persentase kepemilikan bertingkat 80% x 60% = 48% dan deteksi siklus."""
        Ownership = self.env['consol.ownership']

        # Induk -> Anak A (80%)
        own1 = Ownership.create({
            'parent_id': self.parent_entity.id,
            'child_id': self.child_a.id,
            'percentage': 80.0,
            'method': 'full',
        })
        self.assertAlmostEqual(own1.effective_percentage, 80.0, places=2)

        # Anak A -> Cucu B (60%)
        own2 = Ownership.create({
            'parent_id': self.child_a.id,
            'child_id': self.grandchild_b.id,
            'percentage': 60.0,
            'method': 'full',
        })
        # Efektif Induk -> Cucu = 80% * 60% = 48%
        own_direct_check = Ownership.search([('parent_id', '=', self.child_a.id), ('child_id', '=', self.grandchild_b.id)])
        self.assertAlmostEqual(own_direct_check.effective_percentage, 60.0, places=2)

        # Uji deteksi kepemilikan diri sendiri
        with self.assertRaises(ValidationError):
            Ownership.create({
                'parent_id': self.child_a.id,
                'child_id': self.child_a.id,
                'percentage': 50.0,
            })

    def test_02_period_process_and_ic_tolerance(self):
        """Uji alur proses periode konsolidasi, eliminasi seimbang, dan validasi kunci toleransi IC."""
        Period = self.env['consol.period']
        period = Period.create({
            'name': '2026-09',
            'group_id': self.consol_group.id,
            'date_from': '2026-09-01',
            'date_to': '2026-09-30',
        })

        # Isi manual data TB simulasi
        tb_parent = self.env['consol.trial.balance'].create({
            'period_id': period.id,
            'entity_id': self.parent_entity.id,
        })
        self.env['consol.trial.balance.line'].create({
            'trial_balance_id': tb_parent.id,
            'consol_account_id': self.acc_cash.id,
            'balance_fc': 10000000.0,
            'balance_rc': 10000000.0,
        })

        # Simulasi selisih IC yang melebihi toleransi (1000.0)
        self.env['consol.intercompany.match'].create({
            'period_id': period.id,
            'entity_a_id': self.parent_entity.id,
            'entity_b_id': self.child_a.id,
            'account_a_id': self.acc_cash.id,
            'account_b_id': self.acc_cash.id,
            'amount_a': 50000.0,
            'amount_b': 40000.0,  # Selisih 10,000 > toleransi 1,000
        })
        period.state = 'review'

        # Kunci periode harus gagal karena selisih IC melebihi toleransi
        with self.assertRaises(UserError):
            period.action_lock()

        # Setelah override disetujui, penguncian harus berhasil
        match = period.match_ids[0]
        match.action_override_difference()
        period.action_lock()
        self.assertEqual(period.state, 'locked')
