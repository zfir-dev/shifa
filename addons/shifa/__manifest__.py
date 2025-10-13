{
    'name': 'SHIFA Management',
    'version': '1.0.0',
    'summary': 'Membership, Dependents, Medical Assistance & Website form for SHIFA',
    'author': 'Zafir Sk Heerah',
    'category': 'Membership',
    'depends': [
        'base',
        'contacts',
        'account',
        'sale_subscription',
        'website'
    ],
    'data': [
        'security/security_groups.xml',
        'security/ir.model.access.csv',
        'views/shifa_menu.xml',
        'views/shifa_member_views.xml',
        'views/shifa_dependent_views.xml',
        'views/shifa_medical_views.xml',
        'views/shifa_membership_application_form.xml',
        'data/email_templates.xml',
        'data/cron_jobs.xml',
    ],
    'application': True,
    'installable': True,
}
