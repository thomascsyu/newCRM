"""Google Workspace is the only interactive and HTTP authentication mechanism.

One deployment, one site, one allowed domain. There is no tenant discovery.
"""
import base64
import hashlib
import hmac
import json
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


def oauth_redirect_uri(origin):
    """Authorization request and token exchange must send this exact URI."""
    return origin + CALLBACK
START = "/api/method/crm.company_auth.start"
START_PAGE = "/company-oauth"
HEALTH = "/api/method/crm.company_auth.health"
COOKIE = "__Host-crm_oauth"
OAUTH_DONE = "company_oauth_done:"
# Shown on /company-login?error= after the Google account picker. Keys are the
# only values accepted from the query string so a forged parameter cannot
# inject copy. AuthenticationError on the callback used to render Frappe's
# generic "Session Expired" page instead of these messages.
OAUTH_ERRORS = {
    "expired": "Invalid or expired Google sign-in. Start again.",
    "cancelled": "Google sign-in was cancelled. Start again.",
    "unverified": "Google sign-in could not be verified. Start again.",
    "workspace": "Use your company Google Workspace account and try again.",
    "disabled": "Your company account has not been enabled for CRM. Contact your administrator.",
    "role": "Your account has no CRM role. Contact your administrator.",
    "identity": "This Google identity does not match the provisioned CRM account.",
    "config": "Google sign-in is not configured. Contact your administrator.",
}
OAUTH_CLOCK_SKEW_SECONDS = 10
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_USERINFO_URL = "https://openidconnect.googleapis.com/v1/userinfo"
# Frappe's own Web Form submission handler -- see crm.api.form / crm.www.crm_form,
# which build published, login_required=0 Web Forms specifically for anonymous
# prospect capture (marketing site embeds, webinar sign-ups).
PUBLIC_FORM_ACCEPT_METHOD = "/api/method/frappe.website.doctype.web_form.web_form.accept"


def configuration():
    try:
        domain = normalize_domain(os.environ.get("COMPANY_EMAIL_DOMAIN") or frappe.conf.get("company_email_domain"))
        origin = public_origin(os.environ.get("CRM_PUBLIC_URL") or frappe.conf.get("host_name"))
        client_id = (os.environ.get("GOOGLE_CLIENT_ID") or frappe.conf.get("google_client_id") or "").strip()
        secret = (os.environ.get("GOOGLE_CLIENT_SECRET") or frappe.conf.get("google_client_secret") or "").strip()
        if not client_id or not secret:
            raise WorkspaceIdentityError("Google sign-in is not configured. Contact your administrator.")
        return domain, origin, client_id, secret
    except WorkspaceIdentityError as exc:
        frappe.throw(str(exc), frappe.AuthenticationError)


def _deny(message="Sign in with your company Google Workspace account."):
    frappe.throw(message, frappe.AuthenticationError)


def _redirect(location):
    frappe.local.response.update(type="redirect", location=location)


def oauth_login_path(code=None, redirect_to=None):
    params = {}
    if code in OAUTH_ERRORS:
        params["error"] = code
    if redirect_to:
        params["redirect-to"] = safe_redirect_path(redirect_to)
    if not params:
        return "/company-login"
    return "/company-login?" + urlencode(params)


def _oauth_error_from_token_response(error_code):
    if error_code == "invalid_grant":
        return "expired"
    if error_code in ("invalid_client", "unauthorized_client", "redirect_uri_mismatch"):
        return "config"
    return "unverified"


def _log_oauth_failure(stage, detail=""):
    # Never log authorization codes, tokens, secrets or profile payloads.
    frappe.log_error(title=f"Google OAuth {stage}", message=detail or stage)


def _oauth_signing_key(secret):
    return hmac.new(b"crm-company-oauth", secret.encode(), hashlib.sha256).digest()


def _pack_oauth_state(payload, secret):
    body = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode()
    signature = hmac.new(_oauth_signing_key(secret), body, hashlib.sha256).digest()
    return base64.urlsafe_b64encode(body + b"." + signature).decode().rstrip("=")


def _unpack_oauth_state(value, secret):
    padded = value + "=" * (-len(value) % 4)
    raw = base64.urlsafe_b64decode(padded.encode())
    body, signature = raw.rsplit(b".", 1)
    expected = hmac.new(_oauth_signing_key(secret), body, hashlib.sha256).digest()
    if not hmac.compare_digest(signature, expected):
        raise ValueError("invalid oauth cookie")
    return json.loads(body.decode())


def _pending_from_cookie(state, secret):
    packed = _cookie_secret(COOKIE)
    if not packed:
        return None
    try:
        payload = _unpack_oauth_state(packed, secret)
    except (ValueError, json.JSONDecodeError, KeyError):
        return None
    if payload.get("state") != state or not payload.get("raw") or not payload.get("verifier"):
        return None
    raw = payload["raw"]
    return {
        "binding": hashlib.sha256(raw.encode()).hexdigest(),
        "nonce": payload.get("nonce") or "",
        "verifier": payload["verifier"],
        "redirect_to": payload.get("redirect_to") or "/crm",
    }


def _load_oauth_pending(state, secret):
    pending = _pending_from_cookie(state, secret)
    if pending:
        return pending
    cached = frappe.cache.get_value("company_oauth:" + state)
    return cached if isinstance(cached, dict) else None


def _verify_id_token(token, client_id):
    return id_token.verify_oauth2_token(
        token, Request(), audience=client_id, clock_skew_in_seconds=OAUTH_CLOCK_SKEW_SECONDS,
    )


def _claims_from_userinfo(access_token):
    response = requests.get(
        GOOGLE_USERINFO_URL,
        headers={"Authorization": f"Bearer {access_token}"},
        timeout=15,
    )
    response.raise_for_status()
    return response.json()


def _resolve_google_claims(body, client_id):
    """Prefer a verified ID token; fall back to Google's userinfo endpoint."""
    token = body.get("id_token")
    if token:
        try:
            return _verify_id_token(token, client_id), True
        except (GoogleAuthError, ValueError) as exc:
            _log_oauth_failure("id_token", type(exc).__name__)

    access_token = body.get("access_token")
    if not access_token:
        return None, True

    try:
        return _claims_from_userinfo(access_token), False
    except requests.RequestException as exc:
        _log_oauth_failure("userinfo", type(exc).__name__)
        return None, True


def _fail_oauth(code, pending=None):
    """Browser OAuth endpoints must not render Frappe's 401 Session Expired page."""
    _set_oauth_cookie("", max_age=0)
    redirect_to = (pending or {}).get("redirect_to")
    _redirect(oauth_login_path(code, redirect_to=redirect_to))


def _require_sign_in(message="Sign in with your company Google Workspace account."):
    # before_request runs outside the website renderer, which is the part of
    # Frappe that handles frappe.Redirect. Return a real HTTP redirect here.
    if frappe.request.method == "GET" and not frappe.request.path.startswith("/api/"):
        return_path = frappe.request.full_path.rstrip("?")
        location = "/company-login?" + urlencode({"redirect-to": return_path})
        raise HTTPException(response=redirect(location, code=302))
    _deny(message)


def _signed_in():
    return frappe.session.user != "Guest" and frappe.session.data.get("company_google_login") == frappe.session.user


def _cookie_secret(key):
    value = (frappe.request.cookies.get(key) or "").strip()
    return value if value and value != "Guest" else ""


def _binding_raw():
    # Prefer a cookie the browser already stored on /company-login. Safari often
    # drops a cookie that is first set on a 302 to accounts.google.com.
    return _cookie_secret("sid") or _cookie_secret(COOKIE) or secrets.token_urlsafe(32)


def _binding_ok(pending):
    expected = (pending or {}).get("binding") or ""
    if not expected:
        return False
    for raw in (_cookie_secret("sid"), _cookie_secret(COOKIE)):
        if raw and secrets.compare_digest(expected, hashlib.sha256(raw.encode()).hexdigest()):
            return True
    return False


def _set_oauth_cookie(value, max_age=600):
    frappe.local.cookie_manager.set_cookie(COOKIE, value, secure=True, httponly=True, samesite="Lax", max_age=max_age)


@rate_limit(limit=20, seconds=60)
def begin_google_sign_in(redirect_to: str | None = None):
    """Create PKCE state and return the Google authorization URL.

    Called from the /company-oauth HTML page so Set-Cookie happens on a 200
    document response, not on a bounce redirect to Google.
    """
    domain, origin, client_id, secret = configuration()
    redirect_path = safe_redirect_path(redirect_to or frappe.form_dict.get("redirect-to"))
    state, nonce, verifier = [secrets.token_urlsafe(32) for _ in range(3)]
    raw = _binding_raw()
    pending = {
        "binding": hashlib.sha256(raw.encode()).hexdigest(),
        "nonce": nonce, "verifier": verifier, "redirect_to": redirect_path,
    }
    frappe.cache.set_value("company_oauth:" + state, pending, expires_in_sec=600)
    _set_oauth_cookie(_pack_oauth_state({
        "raw": raw, "state": state, "nonce": nonce, "verifier": verifier, "redirect_to": redirect_path,
    }, secret))
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
    return "https://accounts.google.com/o/oauth2/v2/auth?" + urlencode({
        "client_id": client_id, "redirect_uri": oauth_redirect_uri(origin),
        "response_type": "code", "scope": "openid email profile", "state": state,
        "nonce": nonce, "hd": domain, "prompt": "select_account",
        "code_challenge": challenge, "code_challenge_method": "S256",
    })


@frappe.whitelist(allow_guest=True, methods=["GET"])
@rate_limit(limit=20, seconds=60)
def start(redirect_to: str | None = None):
    # Do not Set-Cookie on this 302: iOS Safari drops cookies first seen on a
    # bounce to a third party. The HTML start page stores the binding instead.
    redirect_path = safe_redirect_path(redirect_to or frappe.form_dict.get("redirect-to"))
    location = START_PAGE + "?" + urlencode({"redirect-to": redirect_path})
    _redirect(location)


@frappe.whitelist(allow_guest=True, methods=["GET"])
@rate_limit(limit=30, seconds=60)
def callback(code: str | None = None, state: str | None = None, error: str | None = None):
    try:
        domain, origin, client_id, secret = configuration()
    except frappe.AuthenticationError:
        _fail_oauth("config")
        return
    if not state or len(state) > 100:
        _fail_oauth("expired")
        return
    # Hold the lock through login so a second mobile callback waits, then
    # sees the completion marker instead of Frappe's 401 Session Expired page.
    with frappe.cache.lock("company_oauth_lock:" + state, timeout=10):
        pending = _load_oauth_pending(state, secret)
        if not pending:
            if frappe.cache.get_value(OAUTH_DONE + state) or _signed_in():
                _redirect("/crm")
                return
            _fail_oauth("expired")
            return
        if not _binding_ok(pending):
            _fail_oauth("expired")
            return
        if error or not code:
            frappe.cache.delete_value("company_oauth:" + state)
            _fail_oauth("cancelled", pending)
            return
        try:
            response = requests.post(GOOGLE_TOKEN_URL, data={
                "code": code, "client_id": client_id, "client_secret": secret,
                "redirect_uri": oauth_redirect_uri(origin), "grant_type": "authorization_code",
                "code_verifier": pending["verifier"],
            }, timeout=15)
            try:
                body = response.json()
            except ValueError:
                body = {}
            if body.get("error") or not response.ok:
                frappe.cache.delete_value("company_oauth:" + state)
                error_code = body.get("error") or "token_http_" + str(response.status_code)
                _log_oauth_failure("token", error_code)
                _fail_oauth(_oauth_error_from_token_response(body.get("error")), pending)
                return
            claims, require_nonce = _resolve_google_claims(body, client_id)
            if not claims:
                frappe.cache.delete_value("company_oauth:" + state)
                _fail_oauth("unverified", pending)
                return
            email = validate_claims(claims, domain, pending["nonce"], require_nonce=require_nonce)
        except WorkspaceIdentityError:
            frappe.cache.delete_value("company_oauth:" + state)
            _fail_oauth("workspace", pending)
            return
        except (requests.RequestException, KeyError) as exc:
            frappe.cache.delete_value("company_oauth:" + state)
            _log_oauth_failure("callback", type(exc).__name__)
            _fail_oauth("unverified", pending)
            return
        user = frappe.get_doc("User", email) if frappe.db.exists("User", email) else None
        if not user or not user.enabled or user.user_type != "System User":
            frappe.cache.delete_value("company_oauth:" + state)
            _fail_oauth("disabled", pending)
            return
        if not set(frappe.get_roles(email)).intersection({"System Manager", "Sales Manager", "Sales User"}):
            frappe.cache.delete_value("company_oauth:" + state)
            _fail_oauth("role", pending)
            return
        # Bind an existing provisioned user to a stable Google subject on first login.
        # A subsequently recreated Workspace mailbox cannot silently inherit access.
        if user.get("company_google_subject") and user.company_google_subject != claims["sub"]:
            frappe.cache.delete_value("company_oauth:" + state)
            _fail_oauth("identity", pending)
            return
        if not user.get("company_google_subject"):
            frappe.db.set_value("User", email, "company_google_subject", claims["sub"])
        frappe.flags.company_google_verified = email
        frappe.local.login_manager.login_as(email)
        # An expired incoming session may have queued cookie deletions during request
        # initialization. Do not erase the new verified session when cookies flush.
        cookies = frappe.local.cookie_manager
        cookies.to_delete = [key for key in cookies.to_delete if key not in cookies.cookies]
        frappe.local.flags.commit = True
        frappe.cache.delete_value("company_oauth:" + state)
        frappe.cache.set_value(OAUTH_DONE + state, True, expires_in_sec=120)
        _set_oauth_cookie("", max_age=0)
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
    public = {
        "/", "/login", "/company-login", "/company_oauth", START_PAGE, START, CALLBACK, HEALTH,
        "/api/method/logout",
    }
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
