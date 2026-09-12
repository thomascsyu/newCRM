"""The company product/service catalogue, managed entirely inside CRM."""
from frappe.model.document import Document


class CRMProduct(Document):
    def validate(self):
        self.product_name = (self.product_name or self.product_code or "").strip()
