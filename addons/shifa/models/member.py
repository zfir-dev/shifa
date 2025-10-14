from odoo import api, fields, models, _
from datetime import date

class ShifaMember(models.Model):
    _name = 'shifa.member'
    _description = 'SHIFA Member'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    # Identity
    name = fields.Char(required=True, tracking=True)
    partner_id = fields.Many2one('res.partner', string='Partner', ondelete='set null', tracking=True)
    national_id = fields.Char(string="National ID")
    date_of_birth = fields.Date()
    address = fields.Text()
    phone = fields.Char()
    email = fields.Char()

    # Membership lifecycle
    admission_date = fields.Date(default=fields.Date.today, tracking=True)
    membership_start_date = fields.Date(tracking=True)
    status = fields.Selection([
        ('draft', 'Pending Approval'),
        ('active', 'Active'),
        ('suspended', 'Suspended'),
        ('terminated', 'Terminated'),
        ('deceased', 'Deceased'),
    ], default='draft', tracking=True)
    payment_state = fields.Selection([
        ('pending', 'Pending'),
        ('paid', 'Paid'),
        ('arrears', 'In Arrears'),
    ], compute='_compute_payment_state', store=True, tracking=True)

    # Article 18 categories / flags
    category = fields.Selection([
        ('member', 'Member'),
        ('dependent', 'Dependent'),
        ('orphan', 'Orphan'),
    ], default='member', tracking=True)
    orphan_secondary = fields.Boolean(string="Orphan (Secondary Category)")
    is_auto_promoted = fields.Boolean(string="Auto-promoted from Dependent")
    notification_sent = fields.Boolean(string="Promotion Notification Sent", default=False)
    linked_member_id = fields.Many2one('shifa.member', string="Linked Member (for Dependents)")

    # Dependents
    dependent_ids = fields.One2many('shifa.dependent', 'member_id', string="Dependents")

    # Fees / totals
    currency_id = fields.Many2one(
        'res.currency', 
        default=lambda s: s.env.company.currency_id,
        required=True,
        string="Currency"
    )
    total_fee = fields.Monetary(compute='_compute_total_fee', string="Total Initial Fee")
    entry_fee = fields.Monetary(default=500.0)
    annual_fee = fields.Monetary(default=1000.0)
    dependent_fee = fields.Monetary(default=500.0)

    # Note: Payment references are handled by Odoo's standard payment registration
    # When registering payment against invoices, you can add references there

    # Donation (optional)
    donation_amount = fields.Monetary(string="Donation Amount")

    # Convenience computed values
    dependent_count = fields.Integer(compute='_compute_dependent_count', store=False)
    invoice_count = fields.Integer(compute='_compute_invoice_count', store=False)

    @api.depends('dependent_ids')
    def _compute_dependent_count(self):
        for rec in self:
            rec.dependent_count = len(rec.dependent_ids)

    def _compute_invoice_count(self):
        for rec in self:
            if rec.partner_id:
                rec.invoice_count = self.env['account.move'].search_count([
                    ('partner_id', '=', rec.partner_id.id),
                    ('move_type', '=', 'out_invoice')
                ])
            else:
                rec.invoice_count = 0

    @api.depends('partner_id', 'partner_id.invoice_ids.payment_state')
    def _compute_payment_state(self):
        """Compute payment state based on member's invoices"""
        for rec in self:
            if not rec.partner_id:
                rec.payment_state = 'pending'
                continue
            
            # Get all invoices for this member
            invoices = self.env['account.move'].search([
                ('partner_id', '=', rec.partner_id.id),
                ('move_type', '=', 'out_invoice'),
                ('state', '=', 'posted')
            ])
            
            if not invoices:
                rec.payment_state = 'pending'
            elif all(inv.payment_state == 'paid' for inv in invoices):
                rec.payment_state = 'paid'
            elif any(inv.payment_state == 'not_paid' and inv.invoice_date_due and inv.invoice_date_due < fields.Date.today() for inv in invoices):
                rec.payment_state = 'arrears'
            else:
                rec.payment_state = 'pending'

    @api.depends('dependent_ids', 'entry_fee', 'annual_fee', 'dependent_fee')
    def _compute_total_fee(self):
        for rec in self:
            rec.total_fee = (rec.entry_fee or 0.0) + (rec.annual_fee or 0.0) + (len(rec.dependent_ids) * (rec.dependent_fee or 0.0))

    # --------- Helpers ---------
    def _get_or_create_partner(self):
        for rec in self:
            if rec.partner_id:
                continue
            partner_vals = {
                'name': rec.name,
                'email': rec.email or False,
                'phone': rec.phone or False,
                'street': rec.address or False,
            }
            rec.partner_id = self.env['res.partner'].create(partner_vals)

    # --------- Actions ---------
    def action_view_invoices(self):
        """Open invoices for this member"""
        self.ensure_one()
        return {
            'name': 'Invoices',
            'type': 'ir.actions.act_window',
            'res_model': 'account.move',
            'view_mode': 'tree,form',
            'domain': [('partner_id', '=', self.partner_id.id), ('move_type', '=', 'out_invoice')],
            'context': {'default_partner_id': self.partner_id.id, 'default_move_type': 'out_invoice'},
        }

    def action_refresh_payment_state(self):
        """Manual action to refresh payment state"""
        self._compute_payment_state()

    def action_approve(self):
        for rec in self:
            rec._get_or_create_partner()
            rec.status = 'active'
            rec.membership_start_date = fields.Date.today()
            rec._create_initial_invoice()

    def action_suspend(self):
        self.write({'status': 'suspended'})

    def action_terminate(self):
        for rec in self:
            rec.status = 'terminated'
            rec._promote_first_dependent_if_applicable()

    def action_mark_deceased(self):
        for rec in self:
            rec.status = 'deceased'
            rec._promote_first_dependent_if_applicable()

    # --------- Invoicing ---------
    def _create_initial_invoice(self):
        """Entrance + annual + dependent fee lines (and optional donation)."""
        for rec in self:
            rec._get_or_create_partner()
            line_vals = [
                (0, 0, {'name': 'Entrance Fee', 'quantity': 1, 'price_unit': rec.entry_fee}),
                (0, 0, {'name': 'Annual Subscription', 'quantity': 1, 'price_unit': rec.annual_fee}),
            ]
            for d in rec.dependent_ids:
                # waive fee if orphan secondary (per rules you specified)
                fee = 0.0 if d.is_orphan else rec.dependent_fee
                line_vals.append((0, 0, {
                    'name': f'Dependent Fee: {d.name}',
                    'quantity': 1,
                    'price_unit': fee,
                }))

            if rec.donation_amount:
                line_vals.append((0, 0, {'name': 'Donation', 'quantity': 1, 'price_unit': rec.donation_amount}))

            inv = self.env['account.move'].create({
                'move_type': 'out_invoice',
                'partner_id': rec.partner_id.id,
                'invoice_date': fields.Date.today(),
                'invoice_line_ids': line_vals,
            })
            inv.action_post()

    def create_annual_invoice(self):
        """Annual renewal (to be called yearly, e.g. via cron).
           Adds dependent fees; keeps dependents even if unsubscribed but sets fee to 0 for unsubscribed."""
        for rec in self.filtered(lambda r: r.status == 'active'):
            rec._get_or_create_partner()
            line_vals = [(0, 0, {'name': 'Annual Subscription', 'quantity': 1, 'price_unit': rec.annual_fee})]
            for d in rec.dependent_ids:
                price = 0.0 if d.subscription_state == 'unsubscribed' else (0.0 if d.is_orphan else rec.dependent_fee)
                line_vals.append((0, 0, {'name': f'Dependent Fee: {d.name}', 'quantity': 1, 'price_unit': price}))
            inv = self.env['account.move'].create({
                'move_type': 'out_invoice',
                'partner_id': rec.partner_id.id,
                'invoice_date': fields.Date.today(),
                'invoice_line_ids': line_vals,
            })
            inv.action_post()

    # --------- Promotions / Notifications ---------
    def _promote_first_dependent_if_applicable(self):
        """If a member is off (terminated/deceased), promote first dependent to member & notify.
           If dependent declines, keep as dependent but mark unsubscribed."""
        MailTemplate = self.env['mail.template']
        tmpl = self.env.ref('shifa.email_dependent_promoted', raise_if_not_found=False)
        for rec in self:
            first_dep = False
            # Prefer spouse; else first dependent
            spouse = rec.dependent_ids.filtered(lambda d: d.relation == 'spouse' and d.subscription_state != 'unsubscribed')[:1]
            if spouse:
                first_dep = spouse
            elif rec.dependent_ids:
                first_dep = rec.dependent_ids[:1]
            if not first_dep:
                continue

            dep = first_dep[0]
            if dep.auto_promote:
                # Create a full member from dependent
                new_member = self.create({
                    'name': dep.name,
                    'email': rec.email,   # reuse main contact if desired
                    'phone': rec.phone,
                    'address': rec.address,
                    'status': 'active',
                    'category': 'member',
                    'is_auto_promoted': True,
                    'linked_member_id': rec.id,
                })
                new_member._get_or_create_partner()
                if tmpl:
                    tmpl.sudo().send_mail(new_member.id, force_send=True)
                rec.notification_sent = True
            else:
                # Dependent does not want to become member → keep but unsubscribe
                dep.subscription_state = 'unsubscribed'
                if tmpl:
                    # Notify committee that dependent declined promotion
                    tmpl_decline = self.env.ref('shifa.email_dependent_declined', raise_if_not_found=False)
                    if tmpl_decline:
                        tmpl_decline.sudo().send_mail(rec.id, force_send=True)

    # --------- CRON Jobs ---------
    @api.model
    def cron_suspend_arrears(self):
        """Suspend members with payment_state = arrears."""
        self.search([('payment_state', '=', 'arrears'), ('status', '=', 'active')]).write({'status': 'suspended'})

    @api.model
    def cron_yearly_renewal_invoicing(self):
        """Generate yearly invoices (run each January 1)."""
        self.search([('status', '=', 'active')]).create_annual_invoice()

    @api.model
    def cron_check_dependent_ages(self):
        """Dependents stay dependent at 18; can be kept up to 23 (if in education or care).
           After 23 (and not care-dependent), unsubscribe but keep record."""
        Dependents = self.env['shifa.dependent'].search([])
        today = fields.Date.today()
        for d in Dependents:
            if not d.date_of_birth:
                continue
            age = (today - d.date_of_birth).days // 365
            if age >= 23 and not d.is_care_dependent:
                d.subscription_state = 'unsubscribed'
            # NOTE: we keep them as dependents even after 18 per your rule.
