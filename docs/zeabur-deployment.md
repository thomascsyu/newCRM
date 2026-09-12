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

## Deploy

1. Add the private MariaDB and Redis services and their volumes.
2. Add this repository as a Zeabur Git service. Use the repository root as the build root; Zeabur detects the root Dockerfile. Do not override the image entrypoint with `yarn start` or `bench start`.
3. Mount the CRM sites volume **before its first start**. Do not mount over the `apps` directory.
4. Add the environment variables and bind the canonical public HTTPS hostname to port 8080.
5. Set a startup allowance long enough for first database installation (at least 10 minutes). The readiness endpoint is `/api/method/crm.company_auth.health`; it returns 200 only after startup and checks database and Redis connectivity.
6. Deploy and review logs. Bootstrap creates `crm.internal` if absent, installs CRM, migrates it, provisions the initial admin if missing, and enables the scheduler. Any failure stops startup.
7. Visit `/company-login` and sign in with the configured initial administrator. Passwords and `Administrator` web login are intentionally unavailable.

Verify `/company-login` displays only Google sign-in, an unrelated Google account is denied, a provisioned employee can create a lead and task, and the data survives a restart. Verify `/socket.io` connects through the public hostname. Google OAuth needs real client credentials and a real Workspace account for this final live check.

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

- [Zeabur Dockerfile deployments](https://zeabur.com/docs/en-US/deploy/methods/dockerfile)
- [Zeabur persistent volumes](https://zeabur.com/docs/en-US/data-management/volumes)
- [Google OpenID Connect](https://developers.google.com/identity/openid-connect/openid-connect)
