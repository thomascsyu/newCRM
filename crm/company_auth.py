"""Google Workspace is the only interactive and HTTP authentication mechanism.

One deployment, one site, one allowed domain. There is no tenant discovery.
"""
import base64
import hashlib
import os
import secrets
from urllib.parse import urlencode

import frappe
import requests
from google.auth.exceptions import GoogleAuthError
from google.auth.transport.requests import Request
from google.oauth2 import id_token
from frappe.rate_limiter import rate_limit
from werkzeug.exceptions import HTTPException
from werkzeug.utils import redirect

from crm.security.workspace import company_email, normalize_domain, public_origin, safe_redirect_path, validate_claims, WorkspaceIdentityError

CALLBACK = "/api/method/crm.company_auth.callback"
START = "/api/method/crm.company_auth.start"
HEALTH = "/api/method/crm.company_auth.health"
COOKIE = "__Host-crm_oauth"
# Frappe's own Web Form submission handler -- see crm.api.form / crm.www.crm_form,
# which build published, login_required=0 Web Forms specifically for anonymous
# prospect capture (marketing site embeds, webinar sign-ups).
PUBLIC_FORM_ACCEPT_METHOD = "/api/method/frappe.website.doctype.web_form.web_form.accept"


def configuration():
    try:
        domain = normalize_domain(os.environ.get("COMPANY_EMAIL_DOMAIN") or frappe.conf.get("company_email_domain"))
        origin = public_origin(os.environ.get("CRM_PUBLIC_URL") or frappe.conf.get("host_name"))
        client_id = os.environ.get("GOOGLE_CLIENT_ID") or frappe.conf.get("google_client_id")
        secret = os.environ.get("GOOGLE_CLIENT_SECRET") or frappe.conf.get("google_client_secret")
        if not client_id or not secret:
            raise WorkspaceIdentityError("Google sign-in is not configured. Contact your administrator.")
        return domain, origin, client_id, secret
    except WorkspaceIdentityError as exc:
        frappe.throw(str(exc), frappe.AuthenticationError)


def _deny(message="Sign in with your company Google Workspace account."):
    frappe.throw(message, frappe.AuthenticationError)


def _redirect(location):
    frappe.local.response.update(type="redirect", location=location)


def _require_sign_in(message="Sign in with your company Google Workspace account."):
    # before_request runs outside the website renderer, which is the part of
    # Frappe that handles frappe.Redirect. Return a real HTTP redirect here.
    if frappe.request.method == "GET" and not frappe.request.path.startswith("/api/"):
        return_path = frappe.request.full_path.rstrip("?")
        location = "/company-login?" + urlencode({"redirect-to": return_path})
        raise HTTPException(response=redirect(location, code=302))
    _deny(message)


@frappe.whitelist(allow_guest=True, methods=["GET"])
@rate_limit(limit=20, seconds=60)
def start(redirect_to: str | None = None):
    domain, origin, client_id, _ = configuration()
    redirect_path = safe_redirect_path(redirect_to or frappe.form_dict.get("redirect-to"))
    state, binding, nonce, verifier = [secrets.token_urlsafe(32) for _ in range(4)]
    frappe.cache.set_value("company_oauth:" + state, {
        "binding": hashlib.sha256(binding.encode()).hexdigest(),
        "nonce": nonce, "verifier": verifier, "redirect_to": redirect_path,
    }, expires_in_sec=600)
    frappe.local.cookie_manager.set_cookie(COOKIE, binding, secure=True, httponly=True, samesite="Lax", max_age=600)
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
    _redirect("https://accounts.google.com/o/oauth2/v2/auth?" + urlencode({
        "client_id": client_id, "redirect_uri": origin + CALLBACK,
        "response_type": "code", "scope": "openid email profile", "state": state,
        "nonce": nonce, "hd": domain, "prompt": "select_account",
        "code_challenge": challenge, "code_challenge_method": "S256",
    }))


@frappe.whitelist(allow_guest=True, methods=["GET"])
@rate_limit(limit=30, seconds=60)
def callback(code: str | None = None, state: str | None = None, error: str | None = None):
    domain, origin, client_id, secret = configuration()
    if not state or len(state) > 100:
        _deny("Invalid or expired Google sign-in. Start again.")
    # Atomically consume state, even if two callback requests arrive together.
    with frappe.cache.lock("company_oauth_lock:" + state, timeout=10):
        pending = frappe.cache.get_value("company_oauth:" + state)
        frappe.cache.delete_value("company_oauth:" + state)
    binding = frappe.request.cookies.get(COOKIE, "")
    frappe.local.cookie_manager.set_cookie(COOKIE, "", secure=True, httponly=True, max_age=0)
    if not pending or not binding or not secrets.compare_digest(pending["binding"], hashlib.sha256(binding.encode()).hexdigest()):
        _deny("Invalid or expired Google sign-in. Start again.")
    if error or not code:
        _deny("Google sign-in was cancelled. Start again.")
    try:
        response = requests.post("https://oauth2.googleapis.com/token", data={
            "code": code, "client_id": client_id, "client_secret": secret,
            "redirect_uri": origin + CALLBACK, "grant_type": "authorization_code",
            "code_verifier": pending["verifier"],
        }, timeout=15)
        response.raise_for_status()
        token = response.json()["id_token"]
        # google-auth verifies Google's signature, issuer, expiry and our audience.
        claims = id_token.verify_oauth2_token(token, Request(), audience=client_id)
        email = validate_claims(claims, domain, pending["nonce"])
    except (requests.RequestException, GoogleAuthError, ValueError, KeyError):
        # Do not expose authorization codes, tokens or secrets in errors/logs.
        _deny("Google sign-in could not be verified. Use your company account and try again.")
    user = frappe.get_doc("User", email) if frappe.db.exists("User", email) else None
    if not user or not user.enabled or user.user_type != "System User":
        _deny("Your company account has not been enabled for CRM. Contact your administrator.")
    if not set(frappe.get_roles(email)).intersection({"System Manager", "Sales Manager", "Sales User"}):
        _deny("Your account has no CRM role. Contact your administrator.")
    # Bind an existing provisioned user to a stable Google subject on first login.
    # A subsequently recreated Workspace mailbox cannot silently inherit access.
    if user.get("company_google_subject") and user.company_google_subject != claims["sub"]:
        _deny("This Google identity does not match the provisioned CRM account.")
    if not user.get("company_google_subject"):
        frappe.db.set_value("User", email, "company_google_subject", claims["sub"])
    frappe.flags.company_google_verified = email
    frappe.local.login_manager.login_as(email)
    # An expired incoming session may have queued cookie deletions during request
    # initialization. Do not erase the new verified session when cookies flush.
    cookies = frappe.local.cookie_manager
    cookies.to_delete = [key for key in cookies.to_delete if key not in cookies.cookies]
    frappe.local.flags.commit = True
    _redirect(pending.get("redirect_to") or "/crm")


def before_login(login_manager=None):
    """Runs before Frappe's password authentication, including /api/method/login."""
    _deny("Password sign-in is disabled. Use company Google sign-in.")


def on_login(login_manager):
    if login_manager.user == "Guest":
        return  # Frappe ends logout by creating an anonymous session.
    domain, *_ = configuration()
    try:
        email = company_email(login_manager.user, domain)
    except WorkspaceIdentityError:
        _deny()
    if frappe.flags.get("company_google_verified") != email:
        _deny()


def on_session_creation(login_manager):
    if login_manager.user == "Guest":
        return
    on_login(login_manager)
    frappe.session.data.company_google_login = login_manager.user
    frappe.local.session_obj.update(force=True)


def _is_published_crm_form(web_form_name):
    if not web_form_name:
        return False
    from crm.api.form import ALLOWED_DOCTYPES

    return bool(
        frappe.db.exists(
            "Web Form",
            {
                "name": web_form_name,
                "published": 1,
                "login_required": 0,
                "doc_type": ["in", ALLOWED_DOCTYPES],
            },
        )
    )


def _is_public_form_request(path, method):
    """Published CRM web forms are meant to be reachable by anonymous
    prospects. Their own page controller (crm.www.crm_form) and Frappe's Web
    Form `accept()` handler already scope themselves to published,
    login_required=0 forms -- this only opens the gate far enough for those
    two guest-safe surfaces to be reached at all; everything else stays
    behind company sign-in."""
    if method == "GET" and (path == "/crm-form" or path.startswith("/crm-form/")):
        return True
    if method == "POST" and path == PUBLIC_FORM_ACCEPT_METHOD:
        return _is_published_crm_form(frappe.form_dict.get("web_form"))
    return False


def before_request():
    request = frappe.request
    if request.method == "OPTIONS":
        _deny()
    # Reject API keys/Bearer credentials before Frappe's later validate_auth stage.
    if request.headers.get("Authorization"):
        _deny("API token authentication is disabled for this internal CRM.")
    path = request.path.rstrip("/") or "/"
    public = {"/", "/login", "/company-login", START, CALLBACK, HEALTH, "/api/method/logout"}
    # Prevent ?cmd=... dispatch from turning a public page into a guest API gateway.
    if frappe.form_dict.get("cmd") and path in public and frappe.form_dict.cmd != "logout":
        _deny()
    if path in public:
        return
    if _is_public_form_request(path, request.method):
        return
    if frappe.session.user == "Guest":
        _require_sign_in()
    domain, *_ = configuration()
    try:
        email = company_email(frappe.session.user, domain)
    except WorkspaceIdentityError:
        _require_sign_in()
    if frappe.session.data.get("company_google_login") != email:
        _require_sign_in("Your session predates company Google sign-in. Sign out and sign in again.")
    if not frappe.db.get_value("User", email, "enabled"):
        _deny("Your CRM account is disabled.")


def validate_user(doc, method=None):
    if doc.name in ("Administrator", "Guest"):
        return  # Framework service identities; HTTP login is still forbidden.
    domain = os.environ.get("COMPANY_EMAIL_DOMAIN") or frappe.conf.get("company_email_domain")
    if not domain and not getattr(frappe.local, "request", None):
        return  # Initial framework installation precedes CRM configuration.
    try:
        company_email(doc.email or doc.name, domain)
    except WorkspaceIdentityError as exc:
        frappe.throw(str(exc), frappe.ValidationError)
    doc.send_welcome_email = 0


@frappe.whitelist(allow_guest=True, methods=["GET"])
def health():
    frappe.db.sql("SELECT 1")
    frappe.cache.ping()
    return {"status": "ok"}
