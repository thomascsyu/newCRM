"""No database or network needed: python -m unittest crm.tests.test_workspace_identity."""
import unittest
from crm.security.workspace import WorkspaceIdentityError, company_email, normalize_domain, public_origin, validate_claims


class WorkspaceIdentityTests(unittest.TestCase):
    def claims(self, **updates):
        return {"email": "employee@company.test", "email_verified": True,
                "hd": "company.test", "nonce": "nonce", "sub": "google-user-123", **updates}

    def test_exact_domain_and_case_normalization(self):
        self.assertEqual(company_email("Employee@Company.Test", "COMPANY.TEST"), "employee@company.test")

    def test_rejects_suffix_subdomain_and_personal_accounts(self):
        for email in ("staff@evilcompany.test", "staff@company.test.evil", "staff@sub.company.test", "staff@gmail.com", "staff@company.test@evil.test", "@company.test"):
            with self.subTest(email=email), self.assertRaises(WorkspaceIdentityError):
                company_email(email, "company.test")

    def test_missing_or_wildcard_domain_fails_closed(self):
        for domain in (None, "", "*.company.test", "@company.test", "company.test,other.test", "company..test", "-company.test"):
            with self.subTest(domain=domain), self.assertRaises(WorkspaceIdentityError):
                normalize_domain(domain)

    def test_requires_verified_managed_google_identity(self):
        for update in ({"email_verified": False}, {"email_verified": "true"}, {"hd": ""}, {"hd": "other.test"}, {"nonce": "wrong"}, {"sub": ""}):
            with self.subTest(update=update), self.assertRaises(WorkspaceIdentityError):
                validate_claims(self.claims(**update), "company.test", "nonce")

    def test_valid_claims(self):
        self.assertEqual(validate_claims(self.claims(), "company.test", "nonce"), "employee@company.test")

    def test_https_canonical_origin(self):
        self.assertEqual(public_origin("https://crm.company.test/"), "https://crm.company.test")
        for origin in ("http://crm.company.test", "//crm.company.test", "https://user:pass@crm.company.test", "https://crm.company.test/path", "https://crm.company.test?redirect=evil"):
            with self.subTest(origin=origin), self.assertRaises(WorkspaceIdentityError):
                public_origin(origin)


if __name__ == '__main__':
    unittest.main()
