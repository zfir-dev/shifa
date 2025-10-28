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
            'date_of_birth': post.get('dob') or False,
            'address': post.get('address'),
            'phone': post.get('phone'),
            'email': post.get('email'),
            'category': 'member',
            'donation_amount': float(post.get('donation_amount') or 0.0),
            'status': 'draft',  # Pending approval
        })

        # Dependents (dynamic - handle any number)
        # Find all dependent names from post data
        dependent_indices = []
        for key in post.keys():
            if key.startswith('dep_name_'):
                idx = key.replace('dep_name_', '')
                if post.get(key):  # Only if name is provided
                    dependent_indices.append(idx)
        
        # Create each dependent
        for i in dependent_indices:
            dep_dob = post.get(f'dep_dob_{i}')
            request.env['shifa.dependent'].sudo().create({
                'name': post.get(f'dep_name_{i}'),
                'relation': post.get(f'dep_relation_{i}') or 'child',
                'date_of_birth': dep_dob if dep_dob else False,
                'is_care_dependent': True if post.get(f'dep_care_{i}') == 'on' else False,
                'is_orphan': True if post.get(f'dep_orphan_{i}') == 'on' else False,
                'member_id': member.id,
                'auto_promote': True if post.get(f'dep_auto_{i}') == 'on' else False,
            })

        return request.render('shifa.membership_application_form_success', {'member': member})

    @http.route(['/shifa/membership/pdf/<int:member_id>'], type='http', auth='public', website=True)
    def membership_pdf_download(self, member_id, **kw):
        """Generate PDF with JavaScript disabled to prevent hanging"""
        try:
            # Get the member record
            member = request.env['shifa.member'].sudo().browse(member_id)
            if not member.exists():
                return request.not_found()
            
            # Generate PDF using the template directly with sudo permissions
            report_sudo = request.env['ir.actions.report'].sudo()
            pdf_content, _ = report_sudo.with_context(disable_javascript=True)._render_qweb_pdf(
                'shifa.membership_application_pdf_document',
                [member_id]
            )
            
            # Return PDF response
            filename = f'SHIFA_Application_{member.name or "Member"}.pdf'
            response = request.make_response(
                pdf_content,
                headers=[
                    ('Content-Type', 'application/pdf'),
                    ('Content-Disposition', f'attachment; filename="{filename}"')
                ]
            )
            return response
            
        except Exception as e:
            # Log the error and return a user-friendly message
            request.env['ir.logging'].sudo().create({
                'name': 'PDF Generation Error',
                'type': 'server',
                'level': 'ERROR',
                'message': f'Error generating PDF for member {member_id}: {str(e)}',
                'path': 'shifa.membership_controller',
                'line': '0',
                'func': 'membership_pdf_download'
            })
            return request.render('shifa.membership_pdf_error', {'error': str(e)})
