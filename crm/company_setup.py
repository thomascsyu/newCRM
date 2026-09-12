"""Single-site setup, invoked by install/migrate and the deployment bootstrap."""
import os
import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields
from crm.security.workspace import company_email, normalize_domain


def configure():
    # Authentication itself always fails closed when configuration is missing.
    # This hook can also run while installing a database before secrets are set.
    create_custom_fields({"User": [{
        "fieldname": "company_google_subject", "label": "Google identity",
        "fieldtype": "Data", "read_only": 1, "hidden": 1, "no_copy": 1,
        "permlevel": 1, "unique": 1,
    }]})
    frappe.db.set_single_value("System Settings", {
        "disable_user_pass_login": 1, "setup_complete": 1, "app_name": "Gabriel Consultant CRM",
        "session_expiry": "08:00:00", "allow_login_using_mobile_number": 0,
        "allow_login_using_user_name": 0,
    })
    frappe.db.set_single_value("Website Settings", {"disable_signup": 1, "home_page": "company-login",
        "app_name": "Gabriel Consultant CRM", "footer_powered": "Gabriel Consultant CRM"})
    frappe.db.set_single_value("FCRM Settings", "persona_captured", 1)
    if frappe.db.exists("DocType", "Social Login Key"):
        for name in frappe.get_all("Social Login Key", pluck="name"):
            frappe.db.set_value("Social Login Key", name, "enable_social_login", 0)
    settings = frappe.get_single("FCRM Settings")
    if not settings.brand_name or settings.brand_name in ("CRM", "Frappe CRM"):
        settings.brand_name = "Gabriel Consultant CRM"
    settings.dropdown_items = [row for row in settings.dropdown_items if row.name1 not in ("app_selector", "login_to_fc")]
    settings.save(ignore_permissions=True)
    frappe.clear_cache()


def provision_admin():
    """CLI-only, idempotent initial administrator provisioning. No login is created."""
    if getattr(frappe.local, "request", None):
        frappe.throw("Administrator provisioning is CLI-only", frappe.PermissionError)
    domain = normalize_domain(os.environ.get("COMPANY_EMAIL_DOMAIN"))
    email = company_email(os.environ.get("COMPANY_ADMIN_EMAIL"), domain)
    if frappe.db.exists("User", email):
        # Never silently re-enable a disabled employee on container restart.
        return
    user = frappe.get_doc({"doctype": "User", "email": email,
        "first_name": "CRM Administrator", "enabled": 1, "user_type": "System User",
        "send_welcome_email": 0, "default_app": "crm"})
    user.append_roles("System Manager", "Sales Manager", "Sales User")
    user.insert(ignore_permissions=True)
    frappe.db.commit()
