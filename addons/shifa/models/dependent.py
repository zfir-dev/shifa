from odoo import api, fields, models

class ShifaDependent(models.Model):
    _name = 'shifa.dependent'
    _description = 'SHIFA Dependent'
    _inherit = ['mail.thread']

    name = fields.Char(required=True, tracking=True)
    relation = fields.Selection([
        ('spouse', 'Spouse'),
        ('child', 'Child'),
        ('relative', 'Care-dependent Relative'),
        ('disabled', 'Disabled Dependent'),
    ], required=True, tracking=True)

    date_of_birth = fields.Date()
    id_number = fields.Char(string='ID Number')
    member_id = fields.Many2one('shifa.member', required=True, ondelete='cascade')
    # Use a new name to avoid DB column type conflicts if an older boolean column 'approved' exists
    approval_state = fields.Selection([('pending', 'Pending'), ('approved', 'Approved'), ('rejected', 'Rejected')], default='pending', tracking=True)

    # Article 18: Care dependent + Orphan flags
    is_care_dependent = fields.Boolean(string="Care Dependent (Art. 18)")
    is_orphan = fields.Boolean(string="Orphan")

    # Age grouping
    age_group = fields.Char(compute='_compute_age_group', store=False)

    # Subscription state & flow
    subscription_state = fields.Selection([
        ('active', 'Active'),
        ('unsubscribed', 'Unsubscribed'),
    ], default='active', tracking=True)

    # If true -> when main member is off, auto-promote this dependent as member
    auto_promote = fields.Boolean(string="Auto-Promote to Member on Off/Deceased")

    @api.model_create_multi
    def create(self, vals_list):
        records = super(ShifaDependent, self).create(vals_list)
        # Validate each created record
        for rec in records:
            rec._validate_eligibility()
        return records

    def write(self, vals):
        res = super(ShifaDependent, self).write(vals)
        # Validate current records after write
        for rec in self:
            rec._validate_eligibility()
        return res

    def _validate_eligibility(self):
        for dep in self:
            # Example rule: child dependents over 23 (and not care-dependent) cannot be approved
            if dep.relation == 'child' and dep.date_of_birth and not dep.is_care_dependent:
                age = (fields.Date.today() - dep.date_of_birth).days // 365
                if age > 23:
                    dep.subscription_state = 'unsubscribed'
                    # keep approved state as rejected if previously pending
                    if dep.approval_state == 'pending':
                        dep.approval_state = 'rejected'

    @api.depends('date_of_birth')
    def _compute_age_group(self):
        for dep in self:
            if not dep.date_of_birth:
                dep.age_group = 'Unknown'
                continue
            age = (fields.Date.today() - dep.date_of_birth).days // 365
            if age < 14:
                dep.age_group = 'Under 14'
            elif age <= 18:
                dep.age_group = '14–18'
            else:
                dep.age_group = '18+'
