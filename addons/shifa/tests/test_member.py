from odoo.tests.common import TransactionCase
from odoo import fields
from unittest.mock import patch

class TestShifaMember(TransactionCase):

    def setUp(self):
        super(TestShifaMember, self).setUp()
        self.Member = self.env['shifa.member']
        self.partner_model = self.env['res.partner']

    def test_initial_invoice_due_date(self):
        m = self.Member.create({'name': 'Test User', 'email': 'test@example.com', 'status': 'draft'})
        m.action_approve()
        inv = self.env['account.move'].search([('partner_id', '=', m.partner_id.id), ('move_type', '=', 'out_invoice')], limit=1)
        self.assertTrue(inv, 'Invoice should be created on approve')
        today = fields.Date.today()
        expected_due = fields.Date.to_string(fields.Date.from_string(f"{today.year}-03-31"))
        self.assertEqual(inv.invoice_date_due, expected_due)

    def test_suspend_after_overdue_90_days(self):
        # Create member and invoice older than 100 days
        today = fields.Date.today()
        m = self.Member.create({'name': 'Overdue User', 'email': 'overdue@example.com', 'status': 'active'})
        m._get_or_create_partner()
        inv = self.env['account.move'].create({
            'move_type': 'out_invoice',
            'partner_id': m.partner_id.id,
            'invoice_date': fields.Date.to_string(today),
            'invoice_date_due': fields.Date.to_string(fields.Date.from_string(str(today)) - fields.timedelta(days=100)),
            'invoice_line_ids': [(0,0,{'name':'Test','quantity':1,'price_unit':100.0})]
        })
        inv.action_post()
        # run cron
        m.cron_suspend_arrears()
        m.refresh()
        self.assertEqual(m.status, 'suspended')

    def test_initial_invoice_due_date_after_march(self):
        # mock today's date to be after March 31
        with patch('odoo.fields.Date.today') as mock_today:
            # i.e. Apr 1
            today = fields.Date.from_string(f"{fields.Date.today().year}-04-01")
            mock_today.return_value = today

            m = self.Member.create({'name': 'Test User Post March', 'email': 'test-post-march@example.com', 'status': 'draft'})
            m.action_approve()
            inv = self.env['account.move'].search([('partner_id', '=', m.partner_id.id), ('move_type', '=', 'out_invoice')], limit=1)
            self.assertTrue(inv, 'Invoice should be created on approve')

            # if created after March 31, due date should be next year's March 31
            expected_due = fields.Date.to_string(fields.Date.from_string(f"{today.year + 1}-03-31"))
            self.assertEqual(inv.invoice_date_due, expected_due)
