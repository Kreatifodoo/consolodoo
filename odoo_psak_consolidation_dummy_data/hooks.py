# -*- coding: utf-8 -*-
import logging

_logger = logging.getLogger(__name__)

def post_init_hook(env):
    """
    Automatically called upon installation of odoo_psak_consolidation_dummy_data.
    Creates companies, accounts, intercompany transactions, and consolidation periods.
    """
    _logger.info("Executing post_init_hook for odoo_psak_consolidation_dummy_data...")
    env['consol.demo.installer'].install_demo_data()
