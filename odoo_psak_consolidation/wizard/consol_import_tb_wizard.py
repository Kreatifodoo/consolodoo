# -*- coding: utf-8 -*-
import base64
import csv
import io
from odoo import models, fields, api, _
from odoo.exceptions import UserError

class ConsolImportTbWizard(models.TransientModel):
    _name = 'consol.import.tb.wizard'
    _description = 'External Trial Balance Import Wizard (CSV/XLSX)'

    period_id = fields.Many2one(
        'consol.period',
        string='Consolidation Period',
        required=True)

    entity_id = fields.Many2one(
        'consol.entity',
        string='Target Entity (External)',
        required=True,
        domain="[('source_type', '=', 'import')]")

    file_data = fields.Binary(string='Trial Balance File (CSV)', required=True)
    filename = fields.Char(string='File Name')

    def action_import_file(self):
        self.ensure_one()
        if not self.file_data:
            raise UserError(_("Please select a CSV file to import!"))

        decoded_data = base64.b64decode(self.file_data).decode('utf-8-sig', errors='ignore')
        reader = csv.reader(io.StringIO(decoded_data), delimiter=',')

        header = next(reader, None)
        if not header:
            raise UserError(_("CSV file is empty!"))

        tb = self.env['consol.trial.balance'].search([
            ('period_id', '=', self.period_id.id),
            ('entity_id', '=', self.entity_id.id)
        ], limit=1)
        if not tb:
            tb = self.env['consol.trial.balance'].create({
                'period_id': self.period_id.id,
                'entity_id': self.entity_id.id,
            })
        else:
            tb.line_ids.unlink()

        mappings = self.env['consol.account.mapping'].search([('entity_id', '=', self.entity_id.id)])
        mapping_by_code = {m.external_code: m.consol_account_id for m in mappings if m.external_code}

        rate_rec = self.env['consol.rate'].get_or_create_rate(self.period_id, self.entity_id.functional_currency_id)
        c_rate = rate_rec.closing_rate
        a_rate = rate_rec.average_rate

        lines_to_create = []
        for row in reader:
            if not row or len(row) < 3:
                continue
            code = row[0].strip()
            name = row[1].strip()
            try:
                bal_fc = float(row[2].replace(',', '').strip())
            except ValueError:
                continue

            consol_acc = mapping_by_code.get(code)
            if not consol_acc:
                consol_acc = self.env['consol.account'].search([('code', '=', code)], limit=1)
                if consol_acc:
                    self.env['consol.account.mapping'].create({
                        'entity_id': self.entity_id.id,
                        'external_code': code,
                        'external_name': name,
                        'consol_account_id': consol_acc.id,
                    })
                    mapping_by_code[code] = consol_acc

            if not consol_acc:
                raise UserError(_("External account code '%s' (%s) is not mapped to Consolidation Account!", code, name))

            rate_used = a_rate if consol_acc.statement in ['pl', 'oci'] else c_rate
            bal_rc = bal_fc * rate_used

            lines_to_create.append({
                'trial_balance_id': tb.id,
                'consol_account_id': consol_acc.id,
                'external_code': code,
                'external_name': name,
                'balance_fc': bal_fc,
                'movement_fc': bal_fc,
                'rate_used': rate_used,
                'balance_rc': bal_rc,
            })

        if lines_to_create:
            self.env['consol.trial.balance.line'].create(lines_to_create)

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Import Succeeded'),
                'message': _('Successfully imported %s trial balance lines for %s.', len(lines_to_create), self.entity_id.name),
                'sticky': False,
                'next': {'type': 'ir.actions.act_window_close'},
            }
        }
