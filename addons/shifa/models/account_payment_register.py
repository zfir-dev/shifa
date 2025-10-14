from odoo import fields, models

class AccountPaymentRegister(models.TransientModel):
    _inherit = 'account.payment.register'

    payment_reference_notes = fields.Text(
        string="Payment Reference Notes",
        help="Additional notes or details about the payment (e.g., Juice TXN number, Bank transfer details, etc.)"
    )

    def _create_payments(self):
        """Override to pass payment reference notes to created payments"""
        payments = super()._create_payments()
        if self.payment_reference_notes:
            payments.write({'payment_reference_notes': self.payment_reference_notes})
        return payments

