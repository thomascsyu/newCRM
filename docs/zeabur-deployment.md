# Zeabur deployment and operations

## Architecture

One company, one Frappe site (`crm.internal`), one MariaDB database, and one Redis instance. Staff roles control access within that database. Client organizations are CRM records, not separate sites. Nginx fixes `X-Frappe-Site-Name` to `crm.internal`; incoming hostnames cannot select another site. No tenant signup, site selector or per-customer infrastructure is provided.

Zeabur services:

| Service | Image/build | Network | Persistent mount |
|---|---|---|---|
| CRM | Root Dockerfile in this repository | Public HTTPS to port 8080 | `/home/frappe/frappe-bench/sites` |
| MariaDB | `mariadb:11.8` | Private port 3306 only | `/var/lib/mysql` |
| Redis | `redis:7.4-alpine`, append-only persistence enabled | Private port 6379 only | `/data` |

The CRM container contains web, realtime, worker and scheduler processes because Zeabur volumes cannot be shared between services. Keep the CRM service at **one replica**. Use vertical scaling; allow downtime during deployments and database migrations. Start with sufficient memory for Frappe and its worker (4 GB for the CRM service is a practical starting allocation, to be measured against actual workload).

## Google Workspace configuration

1. Create a Google Cloud project belonging to the company Workspace organization. Configure the OAuth consent audience as **Internal**.
2. Create an OAuth client of type **Web application**.
3. Set an authorized redirect URI of:

   `https://crm.gabrielconsultant.one/api/method/crm.company_auth.callback`

   This is the exact redirect URI for the company deployment. Do not use the internal site identifier in this public URL.
4. Configure the variables below in the CRM service. Use Zeabur secret variables for credentials; never commit `.env`.
5. If Workspace app access controls restrict third-party OAuth, approve this client in the Workspace Admin console.

Login requests use OpenID Connect, state, a browser-bound HttpOnly cookie, nonce and PKCE. The server verifies Google's ID-token signature, issuer, expiry and audience, then requires both verified email and the Workspace `hd` claim to match the exact configured company domain. The `hd` authorization parameter alone is not treated as proof. The stable Google subject is bound to the provisioned account after its first successful sign-in.

## Required CRM variables

| Variable | Value |
|---|---|
| `COMPANY_EMAIL_DOMAIN` | `gabriel.hk`. No `@`, wildcard, subdomain matching or list. |
| `COMPANY_ADMIN_EMAIL` | `thomas@gabriel.hk` (initial administrator). |
| `CRM_PUBLIC_URL` | `https://crm.gabrielconsultant.one`; no path. |
| `GOOGLE_CLIENT_ID` | OAuth web client ID. |
| `GOOGLE_CLIENT_SECRET` | OAuth client secret. |
| `DB_HOST` | MariaDB service's private hostname shown by Zeabur. |
| `DB_PORT` | `3306`, unless the database uses a different private port. |
| `DB_ROOT_USER` | Database bootstrap user; defaults to `root`. |
| `DB_ROOT_PASSWORD` | Matching database bootstrap password. Required on first creation. |
| `REDIS_URL` | Private Redis URL, including password if Redis requires one; e.g. `redis://:PASSWORD@PRIVATE-HOST:6379/0`. |

On MariaDB set `MARIADB_ROOT_PASSWORD` to the same bootstrap password, and configure UTF-8 (`utf8mb4` / `utf8mb4_unicode_ci`). Do not publish database or Redis ports. The application creates its own database user; the database bootstrap credential is used only during initial site creation. It can be removed from the CRM service after successful setup, unless a fresh site must be created later.

No ERPNext, Twilio or Exotel variables are used. Remove any such variables from existing Zeabur services and revoke the retired credentials at their providers after migration.

## Deploy the complete stack from the template

The root [`zeabur.yaml`](../zeabur.yaml) creates `mariadb`, `redis` and `crm` in one project, with storage, connection references, startup dependencies and health checks. Database TCP forwarding is explicitly disabled. This template is for a **new deployment**; do not import it over an existing production installation or it may create duplicate services.

From your clone of this repository, run:

```sh
npx zeabur@latest template deploy -f zeabur.yaml --var CRM_DOMAIN=crm.gabrielconsultant.one
```

Sign in when prompted and select the intended project/server. The command supplies `crm.gabrielconsultant.one` as `CRM_DOMAIN`. This is a string setting; bind the custom hostname separately under Networking after import. Grant the Zeabur GitHub app access to `thomascsyu/newCRM` if prompted. The template uses verified GitHub repository ID `1367346335`, branch `main`, and the repository root Dockerfile.

After import, set `GOOGLE_CLIENT_ID` and `GOOGLE_CLIENT_SECRET` under **crm → Variables**, then restart CRM. They are intentionally empty in the template and are not exposed to other services. A first-start message asking for these variables is expected until they are set. Generated database and Redis passwords are wired automatically; do not replace them with literal `${PASSWORD}` strings in the dashboard.

The template can create configuration, but it cannot supply the company's Google credentials, change external DNS, choose a paid server for you, or verify a real Workspace login. The following settings complete that setup.

## Service settings

Use one project named `gabriel-crm` (suggested) and keep all three services on the same server/project network. Use an existing company server with sufficient spare capacity. For planning, start with 2 CPU cores and 4 GB RAM available to CRM, 1 GB to MariaDB and 512 MB to Redis, plus headroom for the operating system. These are initial estimates, not measured minimums; monitor actual use. Image builds run separately from service runtime and need enough build memory as well.

Set **one replica per service**. The schema does not specify CPU/RAM limits, volume capacities, replica counts or startup-probe timing; configure supported limits in the dashboard. Volume mounts are defined by the template. Allow enough space for uploads and local backups: a starting plan is 10 GB for CRM sites, 10 GB for MariaDB and 1 GB for Redis, expanded as usage grows.

### MariaDB service

| Setting | Value |
|---|---|
| Service name | `mariadb` |
| Image | `mariadb:11.8` |
| Command | `docker-entrypoint.sh` |
| Arguments | `mariadbd --character-set-server=utf8mb4 --collation-server=utf8mb4_unicode_ci --max-connections=100 --innodb-buffer-pool-size=512M` |
| Port | `3306`, TCP, private only |
| TCP forwarding | Disabled |
| Volume ID → mount | `database` → `/var/lib/mysql` |
| Health check | TCP, port ID `database` |
| `MARIADB_ROOT_PASSWORD` | Generated once by the template; store securely |
| `MARIADB_ROOT_HOST` | `%` for bootstrap from the CRM service over the private network |
| Exported `CRM_DB_HOST` | `${CONTAINER_HOSTNAME}` |
| Exported `CRM_DB_ROOT_PASSWORD` | Reference to `MARIADB_ROOT_PASSWORD` |

Keep the database initialization entrypoint. Do not set `MARIADB_DATABASE`, `MARIADB_USER` or `MARIADB_PASSWORD`: Bench creates its own site database and restricted database user. MariaDB initialization variables only initialize an empty volume; changing a password environment variable later does not rotate an existing database user's password.

### Redis service

| Setting | Value |
|---|---|
| Service name | `redis` |
| Image | `redis:7.4-alpine` |
| Command | `docker-entrypoint.sh` |
| Arguments | `redis-server /usr/local/etc/redis/company.conf` |
| Port | `6379`, TCP, private only |
| TCP forwarding | Disabled |
| Volume ID → mount | `data` → `/data` |
| Health check | TCP, port ID `database` |
| `CRM_REDIS_PASSWORD` | Generated once by the template |
| Exported `CRM_REDIS_URL` | `redis://:${CRM_REDIS_PASSWORD}@${CONTAINER_HOSTNAME}:6379/0` |

The template mounts `/usr/local/etc/redis/company.conf` with environment substitution enabled. It sets password authentication, AOF persistence (`appendonly yes`, `appendfsync everysec`), a 256 MB Redis data limit and `maxmemory-policy noeviction`. This Redis instance holds queues as well as cache: do not configure an eviction policy that discards queued jobs. Increase the data limit and service memory together if usage approaches the limit. The service requires memory above the data limit for overhead and persistence.

### CRM service

| Setting | Value |
|---|---|
| Service name | `crm` |
| Source | `thomascsyu/newCRM`, branch `main` |
| Root/build context | Repository root |
| Dockerfile | Root `Dockerfile`; automatic detection |
| Install/build/start overrides | Leave empty; preserve the Dockerfile entrypoint |
| Public HTTP port | `8080` (`PORT=8080`) |
| Public hostname | `crm.gabrielconsultant.one` |
| Volume ID → mount | `sites` → `/home/frappe/frappe-bench/sites` |
| Health check | HTTP on `web`, path `/api/method/crm.company_auth.health` |
| Dependencies | `mariadb`, `redis` |
| Replicas | Exactly `1` |

CRM variables are listed above. In the template, `DB_HOST=${CRM_DB_HOST}`, `DB_ROOT_PASSWORD=${CRM_DB_ROOT_PASSWORD}` and `REDIS_URL=${CRM_REDIS_URL}` reference the dependency services. `${CONTAINER_HOSTNAME}` is service-specific: **do not use it directly as CRM's DB_HOST** or CRM will connect to itself. The site identifier `crm.internal` is unrelated to database DNS.

After a successful initial installation, the CRM service uses the database credentials stored in its sites volume. To reduce bootstrap-credential exposure, remove `DB_ROOT_PASSWORD` from CRM and disable project exposure of `CRM_DB_ROOT_PASSWORD` on MariaDB. Keep the original password in your company secret store for recovery. Do not re-import the template to perform this change.

## Manual dashboard setup

If you prefer not to import YAML, create the services above in this order: MariaDB, Redis, CRM. Copy the Redis config from `zeabur.yaml` into its Config Files panel and enable environment substitution. Generate separate strong passwords for MariaDB and Redis, and configure them before starting each service. A command such as `openssl rand -hex 32` generates a URL-safe password.

Get each dependency's actual private hostname from **Networking → Private**; renaming a service does not necessarily rename that hostname. Enter the concrete hostname/password values into CRM's `DB_HOST`, `DB_ROOT_PASSWORD` and `REDIS_URL`, or configure the same project variable references as the template. If using a password with special URL characters, percent-encode it in `REDIS_URL`. Do not use localhost or a public forwarded database address.

## DNS, HTTPS and Google callback

1. Open **crm → Networking**, bind `crm.gabrielconsultant.one` to the HTTP `web` port, and copy the DNS instructions Zeabur displays.
2. In the DNS zone for `gabrielconsultant.one`, add the record for host `crm` with the exact type and target shown by Zeabur. For a CNAME instruction, use that CNAME target; if your server requires an A record, use its displayed address. No project-specific target/IP can be filled in before the service exists.
3. Resolve any conflicting record for `crm` and wait for Zeabur to verify the hostname and issue its HTTPS certificate. Leave other company DNS records unchanged.
4. Keep `CRM_PUBLIC_URL=https://crm.gabrielconsultant.one` and verify the Google authorized redirect URI is exactly `https://crm.gabrielconsultant.one/api/method/crm.company_auth.callback`.
5. Open `https://crm.gabrielconsultant.one/company-login`. Use `thomas@gabriel.hk`. The hostname's domain and the email domain intentionally differ.

Zeabur terminates TLS; Nginx listens on port 8080 inside the service. Do not expose Gunicorn port 8000 or realtime port 9000 separately. Nginx forwards `/socket.io` on the same public HTTPS hostname.

## Startup and acceptance checks

Bootstrap validates configuration, waits for dependency connectivity, creates `crm.internal` if absent, installs/migrates CRM, provisions the initial administrator if missing and enables the scheduler. An existing installation is backed up locally before migration. Application processes start only after bootstrap succeeds. The Docker health check allows 600 seconds for startup; that setting does not automatically control Zeabur's platform probe timing. Review platform deployment events if first installation exceeds its startup window.

Check from your workstation:

```sh
curl --fail --silent --show-error https://crm.gabrielconsultant.one/api/method/crm.company_auth.health
```

Expect a JSON response containing `"status":"ok"`. In the CRM service terminal, inspect all five supervised processes:

```sh
supervisorctl -c /etc/supervisor/crm.conf status
```

Then verify Google login with the administrator, rejection of an unrelated Google account, lead/task creation, realtime connectivity, logout, and retained data after one controlled restart. A TCP probe on MariaDB/Redis only checks their listeners; the CRM HTTP health check checks actual database/Redis connectivity. It does not prove that workers or outbound email work.

Use the application Email settings to configure an outgoing email account before inviting staff. Google login alone does not configure Gmail sending. Send an invitation to a company employee and verify delivery and Google access.

## Troubleshooting

| Symptom | Check/action |
|---|---|
| Missing Google environment variable at startup | Set both OAuth variables on CRM, then restart it. |
| MariaDB access denied | Match the stored bootstrap password on first creation; check private host/port and root host access. Changing an environment variable does not rotate an existing MariaDB password. |
| Redis NOAUTH, invalid password or connection refused | Match config-file password and CRM URL, enable env substitution, and use the private hostname. |
| Redis OOM/noeviction errors | Inspect queued jobs and memory, then increase Redis data and service memory limits. Do not discard the queue. |
| OAuth redirect_uri_mismatch | Match public HTTPS origin and the exact callback URI in the Google client. |
| Company user denied | Check provisioned/enabled User, System User type, CRM role, verified email and Workspace domain. |
| Healthy page but no background work | Check worker/scheduler process status and `bench --site crm.internal doctor` in the service. |
| Git build cannot find the repository | Give the Zeabur GitHub app access to newCRM and confirm branch main. |
| Build killed for memory | Increase build capacity separately from runtime memory. |
| Deployment waits for health | Read bootstrap/migration logs and platform events. Do not remove the health check to hide an install error. |
| Data missing after restart | Confirm the three volume mounts and original site credentials; stop before creating replacement data. |

## Employee access

The initial admin is provisioned from `COMPANY_ADMIN_EMAIL`. Additional users can be provisioned through the staff settings invitation action or Frappe's User administration. Invitations grant the selected role to a company account and email a link to Google sign-in; they never authenticate via an invitation token. Configure outgoing email before sending invitations, or provision users directly without email.

Only System Managers can grant manager/admin roles. New users need `System User`, `enabled`, and a CRM role. External client contacts can have any email address; the domain restriction applies to login Users, not Contact or Lead records.

Disable a User to revoke CRM access. Every authenticated request checks that the User is still enabled. There is no automatic Workspace directory synchronization: disabling someone only in Workspace prevents future Google logins but is not an immediate revocation of an existing CRM session. Disable their CRM User as part of offboarding. Sessions expire after eight hours.

If Google permanently recreates an employee mailbox with a new subject, a System Manager must deliberately clear that user's hidden `company_google_subject` field through an audited administrative operation before rebinding. There is no browser password recovery. CLI access to the service is the administrative recovery path; do not expose it publicly.

## Upgrading an existing CRM

Back up database and public/private files and download that backup before deploying this version. Test the upgrade on a staging copy first. The startup script also creates a local backup before each existing-site migration; this is not a substitute for an off-service backup.

The cleanup patch removes obsolete provider DocTypes/tables, encrypted provider secrets, known integration custom fields and physical columns, obsolete scheduled jobs, standard quotation scripts, and provider configuration keys. It removes deleted fields from saved CRM layouts/views. Custom form scripts referencing the retired integrations are disabled for administrator review. CRM products, leads, deals, notes, tasks and call logs remain. External recording URL references are cleared because the providers are no longer available; download recordings before upgrading if they must be retained. Existing private files are preserved.

If ERPNext is installed as a separate app on the source site, do not restore that site's full database into this CRM-only image and assume it can run. Export CRM records/files to a clean single-site deployment or remove the ERPNext app using its own documented migration/uninstall process on a staging copy first. This repository does not delete an independently installed ERP system or alter a remote ERP site.

For a restored database, preserve the original site's `encryption_key` and database credentials in `sites/crm.internal/site_config.json`. Point `DB_HOST`/`DB_PORT` at the restored database. Startup applies the configured database host/port, Redis URL, public hostname and company domain to the restored site while preserving database credentials and the encryption key. Back up and preserve email credentials and private files. Do not create a second site to represent another company.

Existing sessions must sign in again using Google. The server rejects sessions without the Google authentication marker, including previously issued administrator/password sessions.

## Backups, rollback and recovery

From the CRM service terminal:

```sh
cd /home/frappe/frappe-bench
runuser -u frappe -- bench --site crm.internal backup --with-files
```

Backups are under `sites/crm.internal/private/backups`. Download or copy encrypted backups to company-controlled storage on a regular schedule. Test restoration. Never delete the sites volume when redeploying.

Schema cleanup is irreversible without a backup. To roll back an upgrade, restore both the matching pre-upgrade database/files/config and the matching old image. An image-only rollback cannot reconstruct removed provider settings or columns.

For recovery, use the Zeabur service console as the `frappe` OS user and Bench console/execute tools. Google sign-in restrictions apply to HTTP, not CLI maintenance. Do not add a password bypass to solve an OAuth configuration issue. Fix the client ID, secret, exact redirect URI, domain or provisioned user.

## Local and browser tests

Use the same Compose stack with an HTTPS tunnel/reverse proxy. For frontend-only work, keep `apps/frappe` and `apps/crm` as siblings in a Bench checkout, then follow `frontend/README.md`.

Run focused database tests only on a disposable test site. Frappe's bundled fixtures use `example.com`, so set that domain for the test commands (never change the production domain):

```sh
COMPANY_EMAIL_DOMAIN=example.com bench --site TEST-SITE run-tests --module crm.fcrm.doctype.crm_invitation.test_crm_invitation
COMPANY_EMAIL_DOMAIN=example.com bench --site TEST-SITE run-tests --module crm.fcrm.doctype.crm_products.test_crm_products
```

Run unauthenticated checks with:

```sh
BASE_URL=https://STAGING-HOST yarn test:e2e --project=public
```

For authenticated workflow tests, run Playwright codegen against staging with `--save-storage=e2e/.auth/user.json`, complete real Google sign-in, and close the browser. Then run the Chromium project with that state. State contains session credentials: it is gitignored, must not be shared, and must be refreshed after expiration. The setup project reads this state and captures CSRF from CRM; it does not log in with a password.

## References

- [Zeabur template format](https://zeabur.com/docs/en-US/template/template-format)
- [Zeabur template schema](https://schema.zeabur.app/template.json)
- [Zeabur service schema](https://schema.zeabur.app/prebuilt.json)
- [Zeabur private networking](https://zeabur.com/docs/en-US/deploy/networking/private-networking)
- [Zeabur health checks](https://zeabur.com/docs/en-US/operations/monitoring/health-checks)
- [Zeabur Dockerfile deployments](https://zeabur.com/docs/en-US/deploy/methods/dockerfile)
- [Zeabur persistent volumes](https://zeabur.com/docs/en-US/data-management/volumes)
- [Google OpenID Connect](https://developers.google.com/identity/openid-connect/openid-connect)
