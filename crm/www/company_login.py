import frappe
from urllib.parse import urlencode

from crm.company_auth import START
from crm.security.workspace import safe_redirect_path

no_cache = 1

def get_context(context):
    context.no_cache = 1
    context.no_header = 1
    context.no_breadcrumbs = 1
    context.title = "Gabriel Consultant CRM"
    redirect_to = safe_redirect_path(frappe.form_dict.get("redirect-to"))
    context.redirect_to = redirect_to
    context.login_url = START + "?" + urlencode({"redirect_to": redirect_to})
    context.logged_in = frappe.session.user != "Guest" and frappe.session.data.get("company_google_login") == frappe.session.user
