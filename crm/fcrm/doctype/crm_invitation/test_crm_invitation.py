"""Staff invitations provision accounts; only Google authenticates the recipient."""
import os
from unittest.mock import patch

import frappe
from frappe.tests.utils import FrappeTestCase
from crm.security.workspace import WorkspaceIdentityError


class TestCRMInvitation(FrappeTestCase):
    def setUp(self):
        super().setUp()
        self.env = patch.dict(os.environ, {
            "COMPANY_EMAIL_DOMAIN": "company.test", "CRM_PUBLIC_URL": "https://crm.company.test",
            "GOOGLE_CLIENT_ID": "test", "GOOGLE_CLIENT_SECRET": "test",
        })
        self.env.start()
        self.addCleanup(self.env.stop)
        frappe.set_user("Administrator")

    def make_invitation(self, email=None, role="Sales User"):
        email = email or f"invite-{frappe.generate_hash(length=8)}@company.test"
        with patch.object(frappe, "sendmail") as sendmail:
            invitation = frappe.get_doc(doctype="CRM Invitation", email=email, role=role).insert()
        return invitation, sendmail

    def test_invitation_provisions_company_user_without_login_token(self):
        invitation, sendmail = self.make_invitation()
        self.assertEqual(invitation.status, "Accepted")
        self.assertFalse(invitation.key)
        self.assertTrue(invitation.accepted_at)
        user = frappe.get_doc("User", invitation.email)
        self.assertEqual(user.user_type, "System User")
        self.assertIn("Sales User", [row.role for row in user.roles])
        self.assertEqual(sendmail.call_args.kwargs["args"]["invite_link"], "https://crm.company.test/company-login")

    def test_external_email_is_rejected(self):
        with self.assertRaises(WorkspaceIdentityError):
            self.make_invitation(email="outsider@elsewhere.test")

    def test_invitation_cannot_be_accepted_twice(self):
        invitation, _ = self.make_invitation()
        with self.assertRaises(frappe.ValidationError):
            invitation.accept()

    def test_sales_manager_cannot_grant_administrator(self):
        invitation, _ = self.make_invitation(role="Sales Manager")
        frappe.set_user(invitation.email)
        try:
            with self.assertRaises(frappe.PermissionError):
                self.make_invitation(role="System Manager")
        finally:
            frappe.set_user("Administrator")

    def test_disabled_user_is_not_reenabled(self):
        invitation, _ = self.make_invitation()
        frappe.db.set_value("User", invitation.email, "enabled", 0)
        self.make_invitation(email=invitation.email)
        self.assertEqual(frappe.db.get_value("User", invitation.email, "enabled"), 0)
