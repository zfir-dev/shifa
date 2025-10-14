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
        'website'
    ],
    'data': [
        'security/security_groups.xml',
        'security/ir.model.access.csv',
        'data/payment_journals.xml',
        'views/shifa_menu.xml',
        'views/shifa_member_views.xml',
        'views/shifa_dependent_views.xml',
        'views/shifa_medical_views.xml',
        'views/shifa_membership_application_form.xml',
        'views/account_payment_register_views.xml',
        'data/email_templates.xml',
        'data/cron_jobs.xml',
    ],
    'application': True,
    'installable': True,
}
