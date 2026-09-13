# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

import frappe
from frappe.utils.caching import request_cache

_OWNER_FIELD = {
	"CRM Lead": "lead_owner",
	"CRM Deal": "deal_owner",
}


def hierarchy_enabled() -> bool:
	return bool(frappe.db.get_single_value("FCRM Settings", "enable_sales_hierarchy"))


def _permission_query_conditions(user: str | None, doctype: str):
	if not user:
		user = frappe.session.user

	if user == "Administrator":
		return ""

	roles = frappe.get_roles(user)
	if "System Manager" in roles:
		return ""

	in_tree = hierarchy_enabled() and _in_hierarchy(user)

	# Sales Manager outside the tree retains the default ie sees everything
	if "Sales Manager" in roles and not in_tree:
		return ""

	owner_field = _OWNER_FIELD[doctype]
	DT = frappe.qb.DocType(doctype)
	Todo = frappe.qb.DocType("ToDo").as_("_todo")

	if in_tree:
		# Owner is the user themselves or any member of their subtree
		q1 = (DT[owner_field] == user) | DT[owner_field].isin(_team_mem_query(user))
		# Assigned to the user or any member of their subtree by ToDo
		q2 = DT.name.isin(
			frappe.qb.from_(Todo)
			.select(Todo.reference_name)
			.where(
				(Todo.reference_type == doctype)
				& (Todo.status != "Cancelled")
				& ((Todo.allocated_to == user) | (Todo.allocated_to.isin(_team_mem_query(user))))
			)
		)
		return q1 | q2

	# Sales User default: own records and records directly assigned to them
	q1 = DT[owner_field] == user
	q2 = DT.name.isin(
		frappe.qb.from_(Todo)
		.select(Todo.reference_name)
		.where((Todo.reference_type == doctype) & (Todo.status != "Cancelled") & (Todo.allocated_to == user))
	)
	return q1 | q2


def get_lead_permission_query_conditions(user=None):
	cond = _permission_query_conditions(user, "CRM Lead")
	return cond.get_sql(with_namespace=True, quote_char="`", secondary_quote_char="'") if cond else ""


def get_deal_permission_query_conditions(user=None):
	cond = _permission_query_conditions(user, "CRM Deal")
	return cond.get_sql(with_namespace=True, quote_char="`", secondary_quote_char="'") if cond else ""


def _has_permission(doc, ptype, user, doctype: str) -> bool | None:
	if not user:
		user = frappe.session.user

	if user == "Administrator":
		return True

	roles = frappe.get_roles(user)
	if "System Manager" in roles:
		return True

	if ptype == "create" or not doc.name:
		return True

	in_tree = hierarchy_enabled() and _in_hierarchy(user)
	if "Sales Manager" in roles and not in_tree:
		return True

	conditions = _permission_query_conditions(user, doctype)
	DT = frappe.qb.DocType(doctype)
	return bool(
		frappe.qb.from_(DT).select(DT.name).where(DT.name == doc.name).where(conditions).limit(1).run()
	)


def has_lead_permission(doc, ptype, user):
	return _has_permission(doc, ptype, user, "CRM Lead")


def has_deal_permission(doc, ptype, user):
	return _has_permission(doc, ptype, user, "CRM Deal")


def _activity_permission_query_conditions(user, doctype):
	"""Notes/Tasks/Call Logs linked to a CRM Lead or CRM Deal inherit that
	record's visibility; activities linked to anything else (or nothing)
	keep the doctype's own role-based permissions."""
	if not user:
		user = frappe.session.user

	if user == "Administrator":
		return ""

	roles = frappe.get_roles(user)
	if "System Manager" in roles:
		return ""

	lead_cond = _permission_query_conditions(user, "CRM Lead")
	deal_cond = _permission_query_conditions(user, "CRM Deal")

	DT = frappe.qb.DocType(doctype)
	Lead = frappe.qb.DocType("CRM Lead")
	Deal = frappe.qb.DocType("CRM Deal")

	lead_sub = frappe.qb.from_(Lead).select(Lead.name)
	if lead_cond:
		lead_sub = lead_sub.where(lead_cond)

	deal_sub = frappe.qb.from_(Deal).select(Deal.name)
	if deal_cond:
		deal_sub = deal_sub.where(deal_cond)

	unrestricted = DT.reference_doctype.isnull() | DT.reference_doctype.notin(["CRM Lead", "CRM Deal"])
	lead_ok = (DT.reference_doctype == "CRM Lead") & DT.reference_docname.isin(lead_sub)
	deal_ok = (DT.reference_doctype == "CRM Deal") & DT.reference_docname.isin(deal_sub)

	return unrestricted | lead_ok | deal_ok


def _activity_permission_query_conditions_sql(user, doctype):
	cond = _activity_permission_query_conditions(user, doctype)
	return cond.get_sql(with_namespace=True, quote_char="`", secondary_quote_char="'") if cond else ""


def get_note_permission_query_conditions(user=None):
	return _activity_permission_query_conditions_sql(user, "FCRM Note")


def get_task_permission_query_conditions(user=None):
	return _activity_permission_query_conditions_sql(user, "CRM Task")


def get_call_log_permission_query_conditions(user=None):
	return _activity_permission_query_conditions_sql(user, "CRM Call Log")


def _has_activity_permission(doc, ptype, user) -> bool:
	if not user:
		user = frappe.session.user

	if user == "Administrator":
		return True

	roles = frappe.get_roles(user)
	if "System Manager" in roles:
		return True

	if ptype == "create" or not doc.name:
		return True

	ref_doctype = doc.get("reference_doctype")
	ref_name = doc.get("reference_docname")

	if ref_doctype == "CRM Lead" and ref_name and frappe.db.exists("CRM Lead", ref_name):
		return bool(has_lead_permission(frappe.get_cached_doc("CRM Lead", ref_name), "read", user))

	if ref_doctype == "CRM Deal" and ref_name and frappe.db.exists("CRM Deal", ref_name):
		return bool(has_deal_permission(frappe.get_cached_doc("CRM Deal", ref_name), "read", user))

	return True


def has_note_permission(doc, ptype, user):
	return _has_activity_permission(doc, ptype, user)


def has_task_permission(doc, ptype, user):
	return _has_activity_permission(doc, ptype, user)


def has_call_log_permission(doc, ptype, user):
	return _has_activity_permission(doc, ptype, user)


def get_visibility_scope(user: str | None = None) -> list[str] | None:
	"""Return the list of user emails whose Lead/Deal records `user` may see
	for reporting purposes, or None if they may see every user's records
	(Administrator, System Manager, or a Sales Manager outside the hierarchy
	tree). Keeps dashboards/reports consistent with the Lead/Deal list-view
	permission query conditions instead of letting them see company-wide
	figures a list view would deny."""
	if not user:
		user = frappe.session.user

	if user == "Administrator":
		return None

	roles = frappe.get_roles(user)
	if "System Manager" in roles:
		return None

	in_tree = hierarchy_enabled() and _in_hierarchy(user)

	if "Sales Manager" in roles and not in_tree:
		return None

	if in_tree:
		return [row.user for row in _team_mem_query(user).run(as_dict=True)]

	return [user]


def _in_hierarchy(user: str) -> bool:
	return bool(frappe.db.exists("CRM Sales Hierarchy", {"user": user}))


def _team_mem_query(user: str):
	Mgr = frappe.qb.DocType("CRM Sales Hierarchy").as_("_sqmgr")
	Member = frappe.qb.DocType("CRM Sales Hierarchy").as_("_sqmem")
	return (
		frappe.qb.from_(Mgr)
		.join(Member)
		.on((Member.lft >= Mgr.lft) & (Member.lft <= Mgr.rgt))
		.select(Member.user)
		.where(Mgr.user == user)
	)
