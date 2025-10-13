from odoo import http
from odoo.http import request

class ShifaMembershipController(http.Controller):

    @http.route(['/shifa/membership'], type='http', auth='public', website=True)
    def membership_form(self, **kw):
        return request.render('shifa.membership_form_template')

    @http.route(['/shifa/membership/submit'], type='http', auth='public', website=True, csrf=True)
    def membership_submit(self, **post):
        # Create Member
        member = request.env['shifa.member'].sudo().create({
            'name': post.get('name'),
            'national_id': post.get('national_id'),
            'date_of_birth': post.get('dob'),
            'address': post.get('address'),
            'phone': post.get('phone'),
            'email': post.get('email'),

            'category': 'member',
            'payment_reference': post.get('payment_reference'),
            'donation_amount': float(post.get('donation_amount') or 0.0),
        })

        # Dependents (3 slots; extend as needed)
        for i in range(1, 4):
            dep_name = post.get(f'dep_name_{i}')
            if not dep_name:
                continue
            request.env['shifa.dependent'].sudo().create({
                'name': dep_name,
                'relation': post.get(f'dep_relation_{i}') or 'child',
                'date_of_birth': post.get(f'dep_dob_{i}') or False,
                'is_care_dependent': True if post.get(f'dep_care_{i}') == 'on' else False,
                'is_orphan': True if post.get(f'dep_orphan_{i}') == 'on' else False,
                'member_id': member.id,
                'auto_promote': True if post.get(f'dep_auto_{i}') == 'on' else False,
            })

        return request.render('shifa.membership_success', {'member': member})
