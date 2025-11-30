from odoo import api, fields, models, _
from datetime import date

class ShifaCommitteeRole(models.Model):
    _name = 'shifa.committee.role'
    _description = 'SHIFA Committee Role'

    name = fields.Char(required=True, string="Role Name")
    is_executive = fields.Boolean(string="Executive Role", default=False)
    description = fields.Text()

class ShifaCommitteeMember(models.Model):
    _name = 'shifa.committee.member'
    _description = 'SHIFA Committee Member'
    _inherit = ['mail.thread']

    member_id = fields.Many2one('shifa.member', required=True, string="Member")
    role_id = fields.Many2one('shifa.committee.role', required=True, string="Role")
    start_date = fields.Date(required=True, default=fields.Date.today)
    end_date = fields.Date()
    active = fields.Boolean(default=True)

    @api.constrains('start_date', 'end_date')
    def _check_dates(self):
        for rec in self:
            if rec.end_date and rec.start_date > rec.end_date:
                raise models.ValidationError(_('Start Date must be before End Date.'))

    def check_expiration(self):
        """Check if role has expired (5 years max per rules)."""
        today = fields.Date.today()
        for rec in self.search([('active', '=', True)]):
            # Article 5.1: Role expiration every 5 years
            # We can either auto-expire or just flag it. Let's flag it via activity.
            if rec.start_date:
                years = (today - rec.start_date).days / 365.0
                if years >= 5:
                    rec.activity_schedule(
                        'mail.mail_activity_data_todo',
                        user_id=self.env.user.id,
                        note=_('Committee member tenure has exceeded 5 years. Please review.')
                    )
