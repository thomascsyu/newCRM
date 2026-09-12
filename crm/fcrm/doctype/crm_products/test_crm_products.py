"""Internal catalogue pricing needs no external service."""
import frappe
from frappe.tests.utils import FrappeTestCase
from crm.fcrm.doctype.crm_products.crm_products import get_product_rate_details


class TestInternalProductPricing(FrappeTestCase):
    def test_catalogue_rate_is_returned(self):
        product = frappe.get_doc({"doctype": "CRM Product", "product_code": frappe.generate_hash(length=12),
            "product_name": "Internal consulting service", "standard_rate": 850}).insert()
        self.assertEqual(get_product_rate_details(product.name), {
            "product_name": "Internal consulting service", "rate": 850,
        })

    def test_zero_rate_is_preserved(self):
        product = frappe.get_doc({"doctype": "CRM Product", "product_code": frappe.generate_hash(length=12),
            "product_name": "Included service", "standard_rate": 0}).insert()
        self.assertEqual(get_product_rate_details(product.name)["rate"], 0)
