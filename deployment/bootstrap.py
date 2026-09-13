"""Create/migrate precisely one site; fail startup on invalid config or migration."""
from contextlib import chdir
import json
import os
from pathlib import Path
import secrets
import shutil
import socket
import subprocess
import time

from crm.security.workspace import company_email, normalize_domain, public_origin

SITE = "crm.internal"
BENCH = Path.cwd()
SITES = BENCH / "sites"


def run(*args):
    subprocess.run(["bench", *args], check=True)


def env_value(name, environ=None):
    return (environ or os.environ).get(name, "").strip()


def required(name, environ=None):
    value = env_value(name, environ)
    if not value:
        raise RuntimeError(f"Set required environment variable {name}")
    return value


def google_credentials_configured(environ=None):
    return bool(env_value("GOOGLE_CLIENT_ID", environ) and env_value("GOOGLE_CLIENT_SECRET", environ))


def runtime_settings(environ=None):
    environ = environ or os.environ
    domain = normalize_domain(required("COMPANY_EMAIL_DOMAIN", environ))
    origin = public_origin(required("CRM_PUBLIC_URL", environ))
    company_email(required("COMPANY_ADMIN_EMAIL", environ), domain)
    return {
        "domain": domain,
        "origin": origin,
        "db_host": required("DB_HOST", environ),
        "db_port": int(environ.get("DB_PORT", "3306")),
        "redis_url": required("REDIS_URL", environ),
        "google_ready": google_credentials_configured(environ),
    }


def common_site_config(settings):
    return {
        "db_host": settings["db_host"], "db_port": settings["db_port"],
        "redis_cache": settings["redis_url"], "redis_queue": settings["redis_url"],
        "redis_socketio": settings["redis_url"],
        "socketio_port": 9000, "default_site": SITE, "serve_default_site": True,
        "dns_multitenant": False, "host_name": settings["origin"],
        "company_email_domain": settings["domain"], "developer_mode": 0,
        "server_script_enabled": 0, "disable_telemetry": True, "enable_telemetry": False,
        "maintenance_mode": 0, "pause_scheduler": 0,
    }


def wait_for_dependencies(settings, site_config, attempts=90, delay=2, environ=None):
    import redis
    last_error = None
    for attempt in range(attempts):
        try:
            redis.Redis.from_url(settings["redis_url"]).ping()
            if site_config.exists():
                with socket.create_connection((settings["db_host"], settings["db_port"]), timeout=2):
                    pass
            else:
                import pymysql
                pymysql.connect(
                    host=settings["db_host"], port=settings["db_port"],
                    user=(environ or os.environ).get("DB_ROOT_USER", "root"),
                    password=required("DB_ROOT_PASSWORD", environ),
                    connect_timeout=2,
                ).close()
            return
        except (OSError, redis.RedisError) as exc:
            last_error = exc
        except Exception as exc:
            if exc.__class__.__module__.startswith("pymysql"):
                last_error = exc
            else:
                raise
        if attempt == attempts - 1:
            raise RuntimeError("MariaDB or Redis is not reachable") from last_error
        time.sleep(delay)


def create_site(settings):
    last_error = None
    for attempt in range(5):
        try:
            run(
                "new-site", SITE, "--db-type", "mariadb",
                "--db-host", settings["db_host"], "--db-port", str(settings["db_port"]),
                "--mariadb-user-host-login-scope", "%", "--no-mariadb-socket",
                "--db-root-username", os.environ.get("DB_ROOT_USER", "root"),
                "--db-root-password", required("DB_ROOT_PASSWORD"),
                "--admin-password", secrets.token_urlsafe(48),
            )
            return
        except subprocess.CalledProcessError as exc:
            last_error = exc
            time.sleep(5)
    raise RuntimeError("bench new-site failed after retries") from last_error


def installed_apps():
    """Read the existing site's app list before deciding whether to install CRM."""
    import frappe
    # Frappe resolves bench logs as ../logs and site logs as <site>/logs.
    # An absolute sites_path does not change those working-directory-relative paths.
    # Restore the bench directory before the subsequent Bench CLI commands.
    with chdir(SITES):
        try:
            frappe.init(site=SITE, sites_path=str(SITES))
            frappe.connect()
            return frappe.get_installed_apps()
        finally:
            frappe.destroy()


def main():
    settings = runtime_settings()
    if not settings["google_ready"]:
        print(
            "GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET are unset. "
            "The site will start; Google sign-in stays disabled until both are set.",
            flush=True,
        )
    # Do not infer a site from request Host headers, and do not create a second site.
    unexpected = [p.name for p in SITES.glob("*/site_config.json") if p.parent.name != SITE]
    if unexpected:
        raise RuntimeError("Only crm.internal is supported. Restore the intended company site into this directory.")
    common = common_site_config(settings)
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
    site_config = SITES / SITE / "site_config.json"
    wait_for_dependencies(settings, site_config)
    if not site_config.exists():
        # Random service password: never used for web sign-in or printed.
        create_site(settings)
    # Environment is authoritative for a restored site's connection/security settings.
    saved = json.loads(site_config.read_text())
    saved.update({k: common[k] for k in ("db_host", "db_port", "host_name", "company_email_domain",
        "redis_cache", "redis_queue", "redis_socketio", "developer_mode", "server_script_enabled")})
    site_config.write_text(json.dumps(saved, indent=2))
    site_config.chmod(0o600)
    # Handle interrupted initial installation without creating a second database.
    installed = installed_apps()
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
