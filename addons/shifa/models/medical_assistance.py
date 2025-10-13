from odoo import fields, models

class ShifaMedicalAssistance(models.Model):
    _name = 'shifa.medical_assistance'
    _description = 'SHIFA Medical Assistance'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    member_id = fields.Many2one('shifa.member', required=True)
    dependent_id = fields.Many2one('shifa.dependent')
    claim_type = fields.Selection([
        ('hospital', 'Hospital'),
        ('dental', 'Dental'),
        ('maternity', 'Maternity'),
        ('optical', 'Optical'),
        ('other', 'Other'),
    ], required=True, default='other')
    claim_amount = fields.Monetary()
    approved_amount = fields.Monetary()
    currency_id = fields.Many2one('res.currency', default=lambda s: s.env.company.currency_id)
    state = fields.Selection([
        ('draft', 'Pending'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
    ], default='draft', tracking=True)
    decision_date = fields.Date()
    remarks = fields.Text()

    def action_approve(self):
        self.write({'state': 'approved', 'decision_date': fields.Date.today()})

    def action_reject(self):
        self.write({'state': 'rejected', 'decision_date': fields.Date.today()})
