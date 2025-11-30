from odoo import api, fields, models, _

class ShifaMeeting(models.Model):
    _name = 'shifa.meeting'
    _description = 'SHIFA Meeting'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char(required=True, string="Meeting Title", default=lambda self: _("Meeting on %s") % fields.Date.today())
    date = fields.Datetime(required=True, default=fields.Datetime.now)
    location = fields.Char()
    meeting_type = fields.Selection([
        ('committee', 'Committee Meeting'),
        ('agm', 'Annual General Meeting'),
        ('egm', 'Extraordinary General Meeting'),
    ], default='committee', required=True)
    
    state = fields.Selection([
        ('draft', 'Draft'),
        ('confirmed', 'Confirmed'),
        ('done', 'Held'),
        ('cancelled', 'Cancelled'),
    ], default='draft', tracking=True)

    agenda = fields.Html(string="Agenda")
    minutes = fields.Html(string="Minutes of Meeting")
    
    attendee_ids = fields.Many2many('shifa.member', string="Attendees")
    attendance_count = fields.Integer(compute='_compute_attendance_count')

    # Voting / Polls
    poll_ids = fields.One2many('shifa.meeting.poll', 'meeting_id', string="Polls/Votes")

    @api.depends('attendee_ids')
    def _compute_attendance_count(self):
        for rec in self:
            rec.attendance_count = len(rec.attendee_ids)

    def action_confirm(self):
        self.state = 'confirmed'

    def action_done(self):
        self.state = 'done'

    def action_cancel(self):
        self.state = 'cancelled'

class ShifaMeetingPoll(models.Model):
    _name = 'shifa.meeting.poll'
    _description = 'SHIFA Meeting Poll'

    meeting_id = fields.Many2one('shifa.meeting', required=True, ondelete='cascade')
    question = fields.Char(required=True)
    poll_type = fields.Selection([
        ('yes_no', 'Yes/No'),
        ('options', 'Multiple Choice'),
    ], default='yes_no')
    
    # Simple result tracking
    yes_count = fields.Integer(string="Yes Votes")
    no_count = fields.Integer(string="No Votes")
    abstain_count = fields.Integer(string="Abstain")
    
    state = fields.Selection([
        ('open', 'Open'),
        ('closed', 'Closed'),
    ], default='open')

    def action_close(self):
        self.state = 'closed'
