# Copyright (c) 2025, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.utils import flt


class CRMProducts(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		amount: DF.Currency
		discount_amount: DF.Currency
		discount_percentage: DF.Percent
		net_amount: DF.Currency
		parent: DF.Data
		parentfield: DF.Data
		parenttype: DF.Data
		product_code: DF.Link | None
		product_name: DF.Data
		qty: DF.Float
		rate: DF.Currency
	# end: auto-generated types

	pass


def calculate_product_amounts(row):
	"""Recompute one product row's amount/discount_amount/net_amount from
	qty, rate and discount_percentage. Server-side source of truth: the
	browser form script recomputes the same fields for a live preview, but
	imports and direct API/document writes never go through it."""
	qty = flt(row.qty)
	rate = flt(row.rate)
	amount = flt(qty * rate, row.precision("amount"))
	row.amount = amount

	if not amount:
		row.discount_amount = 0
		row.net_amount = 0
		return

	discount_percentage = flt(row.discount_percentage)
	if discount_percentage:
		discount_percentage = max(0.0, min(discount_percentage, 100.0))
		row.discount_percentage = discount_percentage
		row.discount_amount = flt(amount * discount_percentage / 100, row.precision("discount_amount"))
		row.net_amount = flt(amount - row.discount_amount, row.precision("net_amount"))
	else:
		row.discount_amount = 0
		row.net_amount = amount


def calculate_products_totals(doc):
	"""Recompute every product row plus the parent's total/net_total.
	Call from CRM Lead/CRM Deal validate() so persisted totals can never
	drift from qty/rate/discount, regardless of what the client submitted."""
	total = 0.0
	net_total = 0.0

	for row in doc.get("products") or []:
		calculate_product_amounts(row)
		total += flt(row.amount)
		net_total += flt(row.net_amount)

	doc.total = flt(total, doc.precision("total"))
	doc.net_total = flt(net_total, doc.precision("net_total"))


@frappe.whitelist()
def get_product_rate_details(product_code: str, deal: str | None = None) -> dict:
	frappe.get_doc("CRM Product", product_code).check_permission("read")
	product = (
		frappe.db.get_value("CRM Product", product_code, ["product_name", "standard_rate"], as_dict=True)
		or {}
	)
	rate = product.get("standard_rate")
	return {"product_name": product.get("product_name"), "rate": rate}


def create_product_details_script(doctype):
	name = "Product Details Script for " + doctype
	script = get_product_details_script(doctype)
	# Standard script is app-owned: keep it in sync with code on every migrate.
	if frappe.db.exists("CRM Form Script", name):
		if frappe.db.get_value("CRM Form Script", name, "script") != script:
			frappe.db.set_value("CRM Form Script", name, "script", script)
		return
	frappe.get_doc(
		{
			"doctype": "CRM Form Script",
			"name": name,
			"dt": doctype,
			"view": "Form",
			"script": script,
			"enabled": 1,
			"is_standard": 1,
		}
	).insert()


def get_product_details_script(doctype):
	doctype_class = "class " + doctype.replace(" ", "")

	return (
		doctype_class
		+ " {"
		+ """
  update_total() {
    let total = 0
    let net_total = 0

    this.doc.products.forEach((d) => {
      total += d.amount || 0
      net_total += d.net_amount || 0
    })

    this.doc.total = total
    this.doc.net_total = net_total
  }
}

class CRMProducts {
  products_add() {
    let row = this.doc.getRow('products')
    row.trigger('qty')
    this.doc.trigger('update_total')
  }

  products_remove() {
    this.doc.trigger('update_total')
  }

  async product_code(idx) {
    let row = this.doc.getRow('products', idx)
    let productCode = row.product_code

    let a = await call("crm.fcrm.doctype.crm_products.crm_products.get_product_rate_details", {
        product_code: productCode,
        deal: this.doc.name,
    })
    if (!a || row.product_code !== productCode) return

    row.product_name = a.product_name
    row.rate = a.rate ?? 0
    row.trigger("rate")
  }

  qty(idx) {
    let row = this.doc.getRow('products', idx)
    row.amount = row.qty * row.rate
    row.trigger('discount_percentage', idx)
  }

  rate() {
    let row = this.doc.getRow('products')
    row.amount = row.qty * row.rate
    row.trigger('discount_percentage')
  }

  discount_percentage(idx) {
    let row = this.doc.getRow('products', idx)
    if (!row.amount) {
      row.discount_amount = 0
      row.net_amount = 0
    } else if (row.discount_percentage) {
      row.discount_amount = (row.discount_percentage / 100) * row.amount
      row.net_amount = row.amount - row.discount_amount
    } else {
      row.net_amount = row.amount
      row.discount_amount = 0
    }
    this.doc.trigger('update_total')
  }
}"""
	)
