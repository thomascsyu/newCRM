# Copyright (c) 2024, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

from datetime import datetime

import frappe
from frappe.model.document import Document
from frappe.utils import add_to_date, get_datetime


class CRMStatusChangeLog(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		duration: DF.Duration | None
		from_date: DF.Datetime | None
		from_type: DF.Data | None
		last_status_change_log: DF.Link | None
		log_owner: DF.Link | None
		parent: DF.Data
		parentfield: DF.Data
		parenttype: DF.Data
		to: DF.Data | None
		to_date: DF.Datetime | None
		to_type: DF.Data | None
	# end: auto-generated types

	pass


def get_duration(from_date, to_date):
	if not isinstance(from_date, datetime):
		from_date = get_datetime(from_date)
	if not isinstance(to_date, datetime):
		to_date = get_datetime(to_date)
	duration = to_date - from_date
	return duration.total_seconds()


def add_status_change_log(doc):
	# Lead and Deal each have their own Status doctype (CRM Lead Status /
	# CRM Deal Status) with independent "type" values -- always looking up
	# CRM Deal Status left a Lead's log entries with the wrong/missing type.
	status_doctype = f"{doc.doctype} Status"
	to_status_type = frappe.db.get_value(status_doctype, doc.status, "type") if doc.status else None

	if not doc.is_new():
		previous_status = doc.get_doc_before_save().status if doc.get_doc_before_save() else None
		previous_status_type = (
			frappe.db.get_value(status_doctype, previous_status, "type") if previous_status else None
		)
		if not doc.status_change_log and previous_status:
			now_minus_one_minute = add_to_date(datetime.now(), minutes=-1)
			doc.append(
				"status_change_log",
				{
					"from": previous_status,
					"from_type": previous_status_type or "",
					"to": "",
					"to_type": "",
					"from_date": now_minus_one_minute,
					"to_date": "",
					"log_owner": frappe.session.user,
				},
			)
		last_status_change = doc.status_change_log[-1]
		last_status_change.to = doc.status
		last_status_change.to_type = to_status_type or ""
		last_status_change.to_date = datetime.now()
		last_status_change.log_owner = frappe.session.user
		last_status_change.duration = get_duration(last_status_change.from_date, last_status_change.to_date)

	doc.append(
		"status_change_log",
		{
			"from": doc.status,
			"from_type": to_status_type or "",
			"to": "",
			"to_type": "",
			"from_date": datetime.now(),
			"to_date": "",
			"log_owner": frappe.session.user,
		},
	)


def log_status_change_for_db_set(doc, from_status, to_status):
	"""Record a status transition applied via db_set() (e.g. Lead conversion
	forcing status to "Qualified"), which never runs validate() and so never
	triggers add_status_change_log()'s has_value_changed("status") path.

	Inserted directly as a child row rather than through doc.save(), so this
	doesn't re-run the parent's full validate() pipeline for a change that's
	already been persisted."""
	if from_status == to_status:
		return

	status_doctype = f"{doc.doctype} Status"
	from_type = frappe.db.get_value(status_doctype, from_status, "type") if from_status else None
	to_type = frappe.db.get_value(status_doctype, to_status, "type") if to_status else None
	now = datetime.now()

	last_idx = frappe.db.get_value(
		"CRM Status Change Log", {"parenttype": doc.doctype, "parent": doc.name}, "max(idx)"
	)

	frappe.get_doc(
		{
			"doctype": "CRM Status Change Log",
			"parenttype": doc.doctype,
			"parentfield": "status_change_log",
			"parent": doc.name,
			"idx": (last_idx or 0) + 1,
			"from": from_status or "",
			"from_type": from_type or "",
			"to": to_status or "",
			"to_type": to_type or "",
			"from_date": now,
			"to_date": now,
			"duration": 0,
			"log_owner": frappe.session.user,
		}
	).insert(ignore_permissions=True)
