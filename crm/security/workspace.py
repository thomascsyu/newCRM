"""Pure validation shared by setup, Google login and user administration."""
import re
from urllib.parse import urlparse


class WorkspaceIdentityError(ValueError):
    pass


def normalize_domain(domain: str) -> str:
    domain = (domain or "").strip().lower()
    if not re.fullmatch(r"(?=.{1,253}$)[a-z0-9](?:[a-z0-9.-]*[a-z0-9])?", domain):
        raise WorkspaceIdentityError("Set COMPANY_EMAIL_DOMAIN to your exact Workspace domain.")
    if "." not in domain or any(not label or len(label) > 63 or label.startswith("-") or label.endswith("-") for label in domain.split(".")):
        raise WorkspaceIdentityError("Invalid Workspace domain.")
    return domain


def company_email(email: str, domain: str) -> str:
    domain = normalize_domain(domain)
    email = (email or "").strip().lower()
    if email.count("@") != 1 or not email.split("@")[0] or any(c.isspace() for c in email):
        raise WorkspaceIdentityError("A company email address is required.")
    if email.rsplit("@", 1)[1] != domain:
        raise WorkspaceIdentityError("Use an account from the company Google Workspace domain.")
    return email


def validate_claims(claims: dict, domain: str, nonce: str, *, require_nonce: bool = True) -> str:
    """Called only AFTER Google identity verification (ID token or userinfo)."""
    email = company_email(claims.get("email"), domain)
    verified = claims.get("email_verified")
    if verified is not True and verified != "true":
        raise WorkspaceIdentityError("Google has not verified this email address.")
    # Email suffix alone does not prove membership of a managed Workspace.
    hosted_domain = (claims.get("hd") or "").strip().lower()
    if hosted_domain != normalize_domain(domain):
        raise WorkspaceIdentityError("A managed company Google Workspace account is required.")
    if not claims.get("sub"):
        raise WorkspaceIdentityError("Invalid Google identity response.")
    if require_nonce and (not nonce or claims.get("nonce") != nonce):
        raise WorkspaceIdentityError("Invalid Google identity response.")
    return email


def public_origin(value: str) -> str:
    parsed = urlparse(value or "")
    if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment or parsed.path not in ("", "/"):
        raise WorkspaceIdentityError("CRM_PUBLIC_URL must be an HTTPS origin without a path.")
    return value.rstrip("/")


def safe_redirect_path(value: str | None, default: str = "/crm") -> str:
    """Return a same-origin CRM path; reject open redirects."""
    path = (value or "").strip()
    if not path:
        return default
    if not path.startswith("/") or path.startswith("//") or "://" in path:
        return default
    if path == "/crm" or path.startswith("/crm/"):
        return path
    return default
