"""Create/migrate precisely one site; fail startup on invalid config or migration."""
import json
import os
from pathlib import Path
import secrets
import shutil
import subprocess
import time

from crm.security.workspace import company_email, normalize_domain, public_origin

SITE = "crm.internal"
BENCH = Path.cwd()
SITES = BENCH / "sites"


def run(*args):
    subprocess.run(["bench", *args], check=True)


def required(name):
    value = os.environ.get(name, "").strip()
    if not value:
        raise RuntimeError(f"Set required environment variable {name}")
    return value


def main():
    domain = normalize_domain(required("COMPANY_EMAIL_DOMAIN"))
    origin = public_origin(required("CRM_PUBLIC_URL"))
    company_email(required("COMPANY_ADMIN_EMAIL"), domain)
    required("GOOGLE_CLIENT_ID")
    required("GOOGLE_CLIENT_SECRET")
    db_host = required("DB_HOST")
    db_port = int(os.environ.get("DB_PORT", "3306"))
    redis_url = required("REDIS_URL")
    # Do not infer a site from request Host headers, and do not create a second site.
    unexpected = [p.name for p in SITES.glob("*/site_config.json") if p.parent.name != SITE]
    if unexpected:
        raise RuntimeError("Only crm.internal is supported. Restore the intended company site into this directory.")
    common = {
        "db_host": db_host, "db_port": db_port,
        "redis_cache": redis_url, "redis_queue": redis_url, "redis_socketio": redis_url,
        "socketio_port": 9000, "default_site": SITE, "serve_default_site": True,
        "dns_multitenant": False, "host_name": origin,
        "company_email_domain": domain, "developer_mode": 0,
        "server_script_enabled": 0, "disable_telemetry": True, "enable_telemetry": False,
        "maintenance_mode": 0, "pause_scheduler": 0,
    }
    SITES.mkdir(exist_ok=True)
    config_file = SITES / "common_site_config.json"
    config_file.write_text(json.dumps(common, indent=2))
    config_file.chmod(0o600)
    (SITES / "apps.txt").write_text("frappe\ncrm\n")
    (SITES / "currentsite.txt").write_text(SITE + "\n")
    # Refresh image-built assets on the mounted volume on every release.
    assets = Path("/home/frappe/image-assets")
    if assets.exists():
        if (SITES / "assets").exists():
            shutil.rmtree(SITES / "assets")
        shutil.copytree(assets, SITES / "assets", symlinks=True)
    import redis
    for attempt in range(60):
        try:
            redis.Redis.from_url(redis_url).ping()
            # Merely wait for the database TCP listener; new-site checks credentials.
            import socket
            with socket.create_connection((db_host, db_port), timeout=2):
                pass
            break
        except (OSError, redis.RedisError):
            if attempt == 59:
                raise
            time.sleep(2)
    site_config = SITES / SITE / "site_config.json"
    if not site_config.exists():
        # Random service password: never used for web sign-in or printed.
        run("new-site", SITE, "--db-type", "mariadb", "--db-host", db_host,
            "--db-port", str(db_port), "--mariadb-user-host-login-scope", "%",
            "--db-root-username", os.environ.get("DB_ROOT_USER", "root"),
            "--db-root-password", required("DB_ROOT_PASSWORD"),
            "--admin-password", secrets.token_urlsafe(48))
    # Environment is authoritative for a restored site's connection/security settings.
    saved = json.loads(site_config.read_text())
    saved.update({k: common[k] for k in ("db_host", "db_port", "host_name", "company_email_domain",
        "redis_cache", "redis_queue", "redis_socketio", "developer_mode", "server_script_enabled")})
    site_config.write_text(json.dumps(saved, indent=2))
    site_config.chmod(0o600)
    # Handle interrupted initial installation without creating a second database.
    import frappe
    frappe.init(site=SITE, sites_path=str(SITES))
    frappe.connect()
    installed = frappe.get_installed_apps()
    frappe.destroy()
    if set(installed) - {"frappe", "crm"}:
        raise RuntimeError("This image supports only the Frappe and CRM apps. Migrate CRM data to a clean site before deploying.")
    if "crm" not in installed:
        run("--site", SITE, "install-app", "crm")
    else:
        # Local pre-migration backup. Copy backups off-service as documented.
        run("--site", SITE, "backup", "--with-files")
    run("--site", SITE, "migrate")
    run("--site", SITE, "execute", "crm.company_setup.provision_admin")
    run("--site", SITE, "enable-scheduler")


if __name__ == "__main__":
    main()
