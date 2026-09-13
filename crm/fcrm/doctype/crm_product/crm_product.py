"""The company product/service catalogue, managed entirely inside CRM."""
from frappe.model.document import Document


class CRMProduct(Document):
    def validate(self):
        self.product_name = (self.product_name or self.product_code or "").strip()

    @staticmethod
    def default_list_data():
        columns = [
            {
                "label": "Product Code",
                "type": "Data",
                "key": "product_code",
                "width": "12rem",
            },
            {
                "label": "Product Name",
                "type": "Data",
                "key": "product_name",
                "width": "16rem",
            },
            {
                "label": "Standard Rate",
                "type": "Currency",
                "key": "standard_rate",
                "width": "9rem",
            },
            {
                "label": "Disabled",
                "type": "Check",
                "key": "disabled",
                "width": "6rem",
            },
        ]

        rows = [
            "name",
            "product_code",
            "product_name",
            "standard_rate",
            "disabled",
            "modified",
        ]
        return {"columns": columns, "rows": rows}
