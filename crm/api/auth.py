import frappe

@frappe.whitelist(allow_guest=True)
def oauth_providers():
    return [{"name": "company_google", "provider_name": "Company Google Workspace",
             "auth_url": "/company-oauth", "icon": None}]
