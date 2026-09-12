"""OAuth flow tests with mocked Google transport, Redis and Frappe services."""
import hashlib
import inspect
import os
import unittest
from contextlib import nullcontext
from types import SimpleNamespace as NS
from unittest.mock import Mock, patch

from crm import company_auth as auth


class Bag(dict):
    __getattr__ = dict.get
    __setattr__ = dict.__setitem__


class FakeCache:
    def __init__(self):
        self.data = {}
    def set_value(self, key, value, **kw):
        self.data[key] = value
    def get_value(self, key):
        return self.data.get(key)
    def delete_value(self, key):
        self.data.pop(key, None)
    def lock(self, *args, **kw):
        return nullcontext()


class GoogleAuthTests(unittest.TestCase):
    def setUp(self):
        self.env = patch.dict(os.environ, {"COMPANY_EMAIL_DOMAIN": "company.test", "CRM_PUBLIC_URL": "https://crm.company.test", "GOOGLE_CLIENT_ID": "client", "GOOGLE_CLIENT_SECRET": "secret"})
        self.env.start()
        self.addCleanup(self.env.stop)
        self.user = Bag(name="rep@company.test", enabled=1, user_type="System User", company_google_subject="subject")
        self.f = NS(conf=Bag(), flags=Bag(), cache=FakeCache(),
            request=NS(cookies={auth.COOKIE: "browser-binding"}, path=auth.CALLBACK, method="GET", headers={}),
            form_dict=Bag(), session=NS(user="Guest", data=Bag()),
            local=NS(response=Bag(), flags=Bag(), cookie_manager=Mock(to_delete=[], cookies={}), login_manager=Mock()),
            db=Mock(), get_doc=Mock(return_value=self.user), get_roles=Mock(return_value=["Sales User"]),
            AuthenticationError=PermissionError, throw=lambda message, exception: (_ for _ in ()).throw(exception(message)))
        self.patch = patch.object(auth, "frappe", self.f)
        self.patch.start()
        self.addCleanup(self.patch.stop)
        self.f.db.exists.return_value = True
        self.f.db.get_value.return_value = 1
        self.f.cache.set_value("company_oauth:state", {"binding": hashlib.sha256(b"browser-binding").hexdigest(), "nonce": "nonce", "verifier": "verifier"})
        self.claims = {"email": "rep@company.test", "email_verified": True, "hd": "company.test", "nonce": "nonce", "sub": "subject"}

    def callback(self, claims=None, verify_error=None):
        response = Mock()
        response.json.return_value = {"id_token": "signed-token"}
        with patch.object(auth.requests, "post", return_value=response) as post, patch.object(auth.id_token, "verify_oauth2_token", return_value=claims or self.claims, side_effect=verify_error) as verify:
            inspect.unwrap(auth.callback)(code="code", state="state")
            self.assertEqual(post.call_args.kwargs['data']['code_verifier'], 'verifier')
            self.assertEqual(verify.call_args.kwargs['audience'], 'client')

    def test_valid_login_uses_verified_email(self):
        self.callback()
        self.f.local.login_manager.login_as.assert_called_once_with("rep@company.test")
        self.assertEqual(self.f.local.response.location, "/crm")
        self.assertTrue(self.f.local.flags.commit)

    def test_expired_cookie_cannot_erase_new_session(self):
        self.f.local.cookie_manager.to_delete = ["sid", "user_id"]
        self.f.local.cookie_manager.cookies = {"sid": {"value": "new"}, "user_id": {"value": self.user.name}}
        self.callback()
        self.assertEqual(self.f.local.cookie_manager.to_delete, [])

    def test_logout_may_create_anonymous_session(self):
        auth.on_login(NS(user="Guest"))

    def test_state_cannot_be_replayed(self):
        self.callback()
        with self.assertRaises(PermissionError):
            self.callback()
        self.assertEqual(self.f.local.login_manager.login_as.call_count, 1)

    def test_wrong_browser_cookie_is_rejected(self):
        self.f.request.cookies[auth.COOKIE] = "wrong-browser"
        with self.assertRaises(PermissionError):
            self.callback()
        self.f.local.login_manager.login_as.assert_not_called()

    def test_signature_or_audience_verification_failure(self):
        with self.assertRaises(PermissionError):
            self.callback(verify_error=ValueError("bad signature"))
        self.f.local.login_manager.login_as.assert_not_called()

    def test_foreign_workspace_rejected(self):
        with self.assertRaises(PermissionError):
            self.callback({**self.claims, "email": "rep@other.test", "hd": "other.test"})
        self.f.local.login_manager.login_as.assert_not_called()

    def test_disabled_user_rejected(self):
        self.user.enabled = 0
        with self.assertRaises(PermissionError):
            self.callback()

    def test_unprovisioned_user_rejected(self):
        self.f.db.exists.return_value = False
        with self.assertRaises(PermissionError):
            self.callback()

    def test_changed_google_subject_rejected(self):
        with self.assertRaises(PermissionError):
            self.callback({**self.claims, "sub": "replacement-mailbox"})

    def test_password_login_always_rejected(self):
        with self.assertRaises(PermissionError):
            auth.before_login()

    def test_other_social_or_magic_login_rejected(self):
        with self.assertRaises(PermissionError):
            auth.on_login(NS(user="rep@company.test"))

    def test_google_verified_login_allowed(self):
        self.f.flags.company_google_verified = "rep@company.test"
        auth.on_login(NS(user="rep@company.test"))

    def test_api_token_rejected_even_on_public_path(self):
        self.f.request.headers['Authorization'] = 'token key:secret'
        with self.assertRaises(PermissionError):
            auth.before_request()

    def test_old_session_cannot_access_crm(self):
        self.f.request.path = '/api/resource/CRM Lead'
        self.f.session.user = 'rep@company.test'
        with self.assertRaises(PermissionError):
            auth.before_request()

    def test_valid_google_session_allowed(self):
        self.f.request.path = '/api/resource/CRM Lead'
        self.f.session.user = 'rep@company.test'
        self.f.session.data.company_google_login = 'rep@company.test'
        auth.before_request()

    def test_guest_command_on_public_page_rejected(self):
        self.f.request.path = '/company-login'
        self.f.form_dict.cmd = 'frappe.client.get_list'
        with self.assertRaises(PermissionError):
            auth.before_request()


if __name__ == '__main__':
    unittest.main()
