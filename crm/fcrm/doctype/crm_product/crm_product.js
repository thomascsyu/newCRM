frappe.ui.form.on("CRM Product", {
  product_code(frm) {
    if (!frm.doc.product_name) frm.set_value("product_name", frm.doc.product_code);
  },
});
