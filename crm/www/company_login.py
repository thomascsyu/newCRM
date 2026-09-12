import frappe

no_cache = 1

def get_context(context):
    context.no_cache = 1
    context.no_header = 1
    context.no_breadcrumbs = 1
    context.title = "Gabriel Consultant CRM"
    context.login_url = "/api/method/crm.company_auth.start"
    context.logged_in = frappe.session.user != "Guest" and frappe.session.data.get("company_google_login") == frappe.session.user
