import frappe

from crm.company_auth import OAUTH_ERRORS, START_PAGE

no_cache = 1

def get_context(context):
    context.no_cache = 1
    context.no_header = 1
    context.no_breadcrumbs = 1
    context.title = "Gabriel Consultant CRM"
    context.login_url = START_PAGE
    context.error = OAUTH_ERRORS.get((frappe.form_dict.get("error") or "").strip())
    context.logged_in = frappe.session.user != "Guest" and frappe.session.data.get("company_google_login") == frappe.session.user
