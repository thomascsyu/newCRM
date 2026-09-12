"""Irreversible schema cleanup; take a full database/files backup before upgrading.

No ERP records or remote services are touched. Existing CRM records remain.
The integration names here are tombstones needed to upgrade old installations.
"""
import json
import frappe

OBSOLETE_DOCTYPES = (
    "ERPNext CRM Settings", "CRM Twilio Settings", "Twilio Settings",
    "CRM Exotel Settings", "CRM Telephony Agent", "CRM Telephony Phone",
    "CRM Twilio Agent", "Twilio Agents", "CRM Twilio Phone", "CRM Product Sync Issue",
)
CUSTOM_FIELDS = {
    "CRM Deal": ("erpnext_customer",),
    "CRM Product": ("erpnext_item_code",),
    "Item": ("crm_product_code",),
    "Quotation": ("crm_deal",),
    "Customer": ("crm_deal",),
}
REMOVED_CALL_FIELDS = ("telephony_medium", "medium")


def _drop_columns(doctype, fields):
    if not frappe.db.table_exists(doctype):
        return
    for field in fields:
        if frappe.db.has_column(doctype, field):
            # Only compile-time constants above reach these identifiers.
            frappe.db.sql_ddl(f"ALTER TABLE `tab{doctype}` DROP COLUMN `{field}`")


def _clean_layout(value, removed):
    if isinstance(value, list):
        return [_clean_layout(v, removed) for v in value
                if not (isinstance(v, str) and v in removed)
                and not (isinstance(v, dict) and (v.get("fieldname") or v.get("key")) in removed)
                and not (isinstance(v, list) and any(isinstance(x, str) and x in removed for x in v[:2]))]
    if isinstance(value, dict):
        return {k: _clean_layout(v, removed) for k, v in value.items() if k not in removed}
    return value


def execute():
    if frappe.db.db_type != "mariadb":
        frappe.throw("This deployment uses MariaDB. Restore the source backup into the supported single-site stack.")
    for doctype, fields in CUSTOM_FIELDS.items():
        for field in fields:
            for name in frappe.get_all("Custom Field", filters={"dt": doctype, "fieldname": field}, pluck="name"):
                frappe.delete_doc("Custom Field", name, force=True, ignore_permissions=True)
            frappe.db.delete("Property Setter", {"doc_type": doctype, "field_name": field})
        _drop_columns(doctype, fields)
    _drop_columns("CRM Call Log", REMOVED_CALL_FIELDS)
    # Old provider URLs cannot be authenticated or fetched after removing providers.
    # Local private attachments are preserved. No audio files are deleted.
    if frappe.db.has_column("CRM Call Log", "recording_url"):
        frappe.db.sql("UPDATE `tabCRM Call Log` SET recording_url=NULL WHERE recording_url NOT LIKE '/private/files/%%'")
    if frappe.db.table_exists("CRM Form Script"):
        for row in frappe.get_all("CRM Form Script", fields=["name", "script", "is_standard"]):
            if row.name == "Create Quotation from CRM Deal":
                frappe.delete_doc("CRM Form Script", row.name, force=True, ignore_permissions=True)
            elif any(word in (row.script or "").lower() for word in ("erpnext", "twilio", "exotel", "crm.integrations.api")):
                frappe.db.set_value("CRM Form Script", row.name, "enabled", 0)
    removed = {f for fields in CUSTOM_FIELDS.values() for f in fields} | set(REMOVED_CALL_FIELDS)
    for dt, json_field in (("CRM Fields Layout", "layout"), ("CRM Global Settings", "json"),
                           ("CRM View Settings", "columns"), ("CRM View Settings", "rows"),
                           ("CRM View Settings", "filters"), ("CRM View Settings", "kanban_fields")):
        if not frappe.db.table_exists(dt) or not frappe.db.has_column(dt, json_field):
            continue
        for row in frappe.get_all(dt, fields=["name", json_field]):
            raw = row.get(json_field)
            if not raw:
                continue
            try:
                value = json.loads(raw)
            except (ValueError, TypeError):
                continue
            cleaned = _clean_layout(value, removed)
            if value != cleaned:
                frappe.db.set_value(dt, row.name, json_field, json.dumps(cleaned))
    for view in frappe.get_all("CRM View Settings", fields=["name", "dt", "order_by", "group_by_field", "column_field", "title_field"]):
        if view.dt in OBSOLETE_DOCTYPES:
            frappe.delete_doc("CRM View Settings", view.name, force=True, ignore_permissions=True)
            continue
        updates = {}
        if any(field in (view.order_by or "") for field in removed):
            updates["order_by"] = "modified desc"
        for field in ("group_by_field", "column_field", "title_field"):
            if view.get(field) in removed:
                updates[field] = None
                updates["type"] = "list"
        if updates:
            frappe.db.set_value("CRM View Settings", view.name, updates)
    for dt in OBSOLETE_DOCTYPES:
        # Singles store credentials in __Auth, separate from their visible fields.
        frappe.db.delete("__Auth", {"doctype": dt})
        frappe.db.delete("Singles", {"doctype": dt})
        if frappe.db.exists("DocType", dt):
            frappe.delete_doc("DocType", dt, force=True, ignore_permissions=True)
        frappe.db.sql_ddl(f"DROP TABLE IF EXISTS `tab{dt}`")
    # Remove dead scheduled jobs so workers cannot invoke deleted modules.
    for job in frappe.get_all("Scheduled Job Type", fields=["name", "method"]):
        if any(word in (job.method or "").lower() for word in ("crm.integrations.erpnext", "crm.integrations.twilio", "crm.integrations.exotel", "crm_product.reconcile")):
            frappe.delete_doc("Scheduled Job Type", job.name, force=True, ignore_permissions=True)
    # Remove legacy secret/config entries from this site only.
    from frappe.installer import update_site_config
    for key in list(frappe.conf):
        if any(word in key.lower() for word in ("erpnext", "twilio", "exotel")):
            update_site_config(key, None)
    frappe.clear_cache()
