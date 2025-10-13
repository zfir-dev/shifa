from odoo import fields, models

class AccountMove(models.Model):
    _inherit = 'account.move'

    x_shifa_payment_reference = fields.Char(string="Payment Reference (Juice/Bank)")
