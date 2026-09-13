import frappe

from crm.company_auth import START_PAGE, begin_google_sign_in, oauth_login_path

no_cache = 1


def get_context(context):
    context.no_cache = 1
    context.no_header = 1
    context.no_breadcrumbs = 1
    context.title = "Sign in"
    try:
        context.google_url = begin_google_sign_in()
    except frappe.AuthenticationError:
        frappe.local.flags.redirect_location = oauth_login_path("config")
        raise frappe.Redirect
    context.login_url = START_PAGE
