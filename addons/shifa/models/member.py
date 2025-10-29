from odoo import api, fields, models, _
from datetime import date

class ShifaMember(models.Model):
    _name = 'shifa.member'
    _description = 'SHIFA Member'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    # Identity
    name = fields.Char(required=True, tracking=True)
    partner_id = fields.Many2one('res.partner', string='Partner', ondelete='set null', tracking=True)
    user_id = fields.Many2one('res.users', string='Website User Account', ondelete='set null', tracking=True)
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
            else:
                # If all posted invoices are paid -> paid
                if all(inv.payment_state == 'paid' for inv in invoices):
                    rec.payment_state = 'paid'
                    continue

                # If there exists an invoice past due -> arrears
                past_due = False
                for inv in invoices:
                    # Use invoice_date_due when set, otherwise invoice_date
                    due = inv.invoice_date_due or inv.invoice_date
                    if due and due < fields.Date.today() and inv.payment_state != 'paid':
                        past_due = True
                        break
                if past_due:
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

    def _create_website_user(self):
        """Create a website user account using National ID as username"""
        import secrets
        import string
        
        generated_passwords = {}
        
        for rec in self:
            if rec.user_id or not rec.national_id:
                continue
                
            # Ensure partner exists first
            rec._get_or_create_partner()
            
            # Check if user with this login already exists
            existing_user = self.env['res.users'].search([('login', '=', rec.national_id)], limit=1)
            if existing_user:
                rec.user_id = existing_user
                continue
            
            # Generate a random password
            password_length = 8
            password_chars = string.ascii_letters + string.digits
            generated_password = ''.join(secrets.choice(password_chars) for _ in range(password_length))
            
            # Get the website member group
            website_member_group = self.env.ref('shifa.group_website_member', raise_if_not_found=False)
            if not website_member_group:
                # Create the group if it doesn't exist
                website_member_group = self.env['res.groups'].sudo().create({
                    'name': 'SHIFA Website Members',
                    'comment': 'Members who can access their profile on website but not admin panel',
                    'category_id': self.env.ref('base.module_category_hidden').id,
                })
            
            # Get portal user group for basic access
            portal_group = self.env.ref('base.group_portal', raise_if_not_found=False)
            groups_to_assign = [website_member_group.id]
            if portal_group:
                groups_to_assign.append(portal_group.id)
            
            # Create user account
            user_vals = {
                'name': rec.name,
                'login': rec.national_id,  # Use National ID as username
                'password': generated_password,
                'email': rec.email or False,
                'partner_id': rec.partner_id.id,
                'groups_id': [(6, 0, groups_to_assign)],  # Portal + website member groups
                'active': True,
            }
            
            try:
                user = self.env['res.users'].sudo().create(user_vals)
                rec.user_id = user
                generated_passwords[rec.id] = generated_password
            except Exception as e:
                # Log the error but don't fail the member creation
                import logging
                _logger = logging.getLogger(__name__)
                _logger.warning(f"Failed to create user account for member {rec.name}: {str(e)}")
        
        return generated_passwords

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

    def _notify_committee_arrears(self, members):
        """Send notification to Treasurer and Secretary about members in arrears.
        Expects a recordset of shifa.member."""
        if not members:
            return
        try:
            tmpl = self.env.ref('shifa.email_arrears_notification', raise_if_not_found=False)
            if not tmpl:
                return
            # send using the members model (template expects a member)
            for m in members:
                tmpl.sudo().send_mail(m.id, force_send=False)
        except Exception:
            # avoid cron failure if email template missing or error
            _logger = self.env['ir.logging']
            _logger.sudo().create({
                'name': 'shifa.arrears.notify',
                'type': 'server',
                'dbname': self.env.cr.dbname,
                'level': 'ERROR',
                'message': 'Failed to send arrears notification',
                'path': 'shifa.models.member',
                'line': '0',
                'func': '_notify_committee_arrears',
            })

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

            # Set due date for annual subscription to March 31 of current year (to align with arrears policy)
            today = fields.Date.today()
            due_date = fields.Date.to_string(fields.Date.from_string(f"{today.year}-03-31"))
            inv = self.env['account.move'].create({
                'move_type': 'out_invoice',
                'partner_id': rec.partner_id.id,
                'invoice_date': fields.Date.today(),
                'invoice_date_due': due_date,
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
            today = fields.Date.today()
            due_date = fields.Date.to_string(fields.Date.from_string(f"{today.year}-03-31"))
            inv = self.env['account.move'].create({
                'move_type': 'out_invoice',
                'partner_id': rec.partner_id.id,
                'invoice_date': fields.Date.today(),
                'invoice_date_due': due_date,
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
        # Find members with invoices overdue by more than 90 days
        today = fields.Date.today()
        members_to_suspend = self.browse()
        for m in self.search([('status', '=', 'active')]):
            if not m.partner_id:
                continue
            invoices = self.env['account.move'].search([
                ('partner_id', '=', m.partner_id.id),
                ('move_type', '=', 'out_invoice'),
                ('state', '=', 'posted'),
                ('payment_state', '!=', 'paid'),
            ])
            overdue = False
            for inv in invoices:
                due = inv.invoice_date_due or inv.invoice_date
                if due and (today - due).days > 90:
                    overdue = True
                    break
            if overdue:
                members_to_suspend |= m

        if members_to_suspend:
            members_to_suspend.write({'status': 'suspended'})
            # notify Treasurer and Secretary
            self._notify_committee_arrears(members_to_suspend)

    @api.model
    def cron_yearly_renewal_invoicing(self):
        """Generate yearly invoices (run each January 1)."""
        today = fields.Date.today()
        # Only run on January 1 to match requirement
        if today.month == 1 and today.day == 1:
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

    @api.model
    def cron_send_renewal_reminders(self):
        """Send renewal reminders to members between Jan 1 and Mar 31 for unpaid invoices."""
        today = fields.Date.today()
        if not (today.month >= 1 and today.month <= 3):
            return
        # find active members with unpaid posted invoices
        members = self.search([('status', '=', 'active')])
        tmpl = self.env.ref('shifa.email_renewal_reminder', raise_if_not_found=False)
        notified = self.browse()
        for m in members:
            if not m.partner_id:
                continue
            invoices = self.env['account.move'].search([
                ('partner_id', '=', m.partner_id.id),
                ('move_type', '=', 'out_invoice'),
                ('state', '=', 'posted'),
                ('payment_state', '!=', 'paid'),
            ])
            if invoices:
                # send reminder
                if tmpl:
                    try:
                        tmpl.sudo().send_mail(m.id, force_send=False)
                    except Exception:
                        pass
                notified |= m

        # Optionally send a summary to Treasurer
        if notified:
            summ_tmpl = self.env.ref('shifa.email_renewal_summary', raise_if_not_found=False)
            if summ_tmpl:
                try:
                    # use first member as context; template should produce a list via server-side
                    summ_tmpl.sudo().send_mail(notified[0].id, force_send=False)
                except Exception:
                    pass

    @api.model
    def cron_post_march_suspension(self):
        """On and after Apr 1, suspend active members with unpaid invoices due by Mar 31."""
        today = fields.Date.today()
        # only run on or after Apr 1
        if today.month < 4:
            return
        cutoff = fields.Date.to_string(fields.Date.from_string(f"{today.year}-03-31"))
        members_to_suspend = self.browse()
        for m in self.search([('status', '=', 'active')]):
            if not m.partner_id:
                continue
            invoices = self.env['account.move'].search([
                ('partner_id', '=', m.partner_id.id),
                ('move_type', '=', 'out_invoice'),
                ('state', '=', 'posted'),
                ('payment_state', '!=', 'paid'),
                ('invoice_date_due', '<=', cutoff),
            ])
            if invoices:
                members_to_suspend |= m

        if members_to_suspend:
            members_to_suspend.write({'status': 'suspended'})
            self._notify_committee_arrears(members_to_suspend)

    def action_download_membership_pdf(self):
        """Download membership application PDF"""
        return {
            'type': 'ir.actions.act_url',
            'url': f'/report/pdf/shifa.action_report_membership_application_pdf/{self.id}',
            'target': 'new',
        }
