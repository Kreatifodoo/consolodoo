from odoo import models, fields, api

class AccountAccount(models.Model):
    _inherit = 'account.account'

    name_en = fields.Char(string='Nama Akun Bahasa Inggris', help="Nama akun dalam bahasa Inggris untuk keperluan translasi atau pelaporan internasional.")
    parent_id = fields.Many2one('account.account', string='Akun Induk', index=True, ondelete='cascade')
    child_ids = fields.One2many('account.account', 'parent_id', string='Sub-Akun')

    @api.onchange('name')
    def _onchange_name_translate(self):
        for rec in self:
            if rec.name and not rec.name_en:
                try:
                    import requests
                    from urllib.parse import quote
                    encoded_text = quote(rec.name)
                    url = f"https://translate.googleapis.com/translate_a/single?client=gtx&sl=id&tl=en&dt=t&q={encoded_text}"
                    response = requests.get(url, timeout=5)
                    if response.status_code == 200:
                        data = response.json()
                        translated_text = data[0][0][0]
                        rec.name_en = translated_text
                except Exception as e:
                    import logging
                    logging.getLogger(__name__).warning(f"Auto-translate failed: {e}")
