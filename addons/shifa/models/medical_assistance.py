from odoo import api, fields, models
from odoo.exceptions import ValidationError

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

    @api.model
    def create(self, vals):
        rec = super(ShifaMedicalAssistance, self).create(vals)
        rec._check_eligibility_on_create()
        return rec

    def write(self, vals):
        res = super(ShifaMedicalAssistance, self).write(vals)
        for rec in self:
            rec._check_eligibility_on_create()
        return res

    def _check_eligibility_on_create(self):
        """Enforce: member must have been active for >= 2 years and not have arrears > 90 days."""
        for rec in self:
            member = rec.member_id
            if not member:
                continue

            # Check membership tenure
            if member.membership_start_date:
                try:
                    start = fields.Date.from_string(member.membership_start_date)
                except Exception:
                    start = None
                if start:
                    years = (fields.Date.today() - start).days // 365
                    if years < 2:
                        raise ValidationError('Member does not meet the 2-year qualifying period for medical assistance.')

            # Check arrears > 90 days via invoices
            today = fields.Date.today()
            if member.partner_id:
                invoices = self.env['account.move'].search([
                    ('partner_id', '=', member.partner_id.id),
                    ('move_type', '=', 'out_invoice'),
                    ('state', '=', 'posted'),
                    ('payment_state', '!=', 'paid'),
                ])
                for inv in invoices:
                    due = inv.invoice_date_due or inv.invoice_date
                    if due and (today - due).days > 90:
                        raise ValidationError('Member has arrears exceeding 90 days and is not eligible for medical assistance.')

    def action_approve(self):
        # enforce 50% annual disbursement limit and mark approved amount
        cfg = self.env['shifa.config'].sudo().get_settings()
        if not cfg:
            raise ValidationError('SHIFA configuration is not set. Please configure medical fund settings.')
        cfg = cfg[0]

        # compute current year disbursed
        start_year = fields.Date.from_string(fields.Date.today()).replace(month=1, day=1)
        disbursed = sum(rec.approved_amount for rec in self.search([('state', '=', 'approved'), ('decision_date', '>=', start_year)]))
        available = (cfg.medical_fund_amount or 0.0) * 0.5 - disbursed
        if (self.approved_amount or 0.0) > available:
            raise ValidationError('Approving this amount would exceed the 50% annual disbursement limit.')

        self.write({'state': 'approved', 'decision_date': fields.Date.today()})

    def action_reject(self):
        self.write({'state': 'rejected', 'decision_date': fields.Date.today()})


class ShifaConfig(models.Model):
    _name = 'shifa.config'
    _description = 'SHIFA Configuration'

    medical_fund_amount = fields.Monetary(string='Medical Fund Total', currency_field='currency_id')
    currency_id = fields.Many2one('res.currency', default=lambda s: s.env.company.currency_id)

    @api.model
    def get_settings(self):
        return self.search([], limit=1)
