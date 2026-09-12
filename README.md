# Gabriel Consultant CRM

An internal CRM for Gabriel Consultant, built on Frappe 16, Python 3.14 and Vue 3. The application uses one shared company database, company Google Workspace sign-in and employee access roles.

Source repository: [thomascsyu/newCRM](https://github.com/thomascsyu/newCRM).

## Company configuration

| Setting | Value |
|---|---|
| Planned production address | `https://crm.gabrielconsultant.one` |
| Allowed Google Workspace email domain | `gabriel.hk` |
| Initial administrator | `thomas@gabriel.hk` |
| Internal Frappe site identifier | `crm.internal` |
| Deployment platform | Zeabur |

One Frappe site means one CRM installation shared by company employees. Client organizations are CRM records within that installation. Roles control employee access; there is no tenant signup or per-client site provisioning.

## Features

- Leads, deals, contacts, client organizations, activities, notes and tasks.
- Sales roles and reporting hierarchy within the company.
- Internal product/service catalogue with standard prices and deal line totals.
- Phone links that open the employee's device dialler, manual call logs and private recording attachments.
- Email configuration and domain enrichment.

ERPNext, Twilio and Exotel integrations and their dedicated dependencies/settings have been removed. Quotation/customer/item synchronization and provider-based calling are unavailable. Use the internal catalogue and attach externally prepared quotations to deals.

## Google sign-in and employee access

Accounts must be provisioned, enabled, assigned a CRM role and belong to `@gabriel.hk`. The server verifies Google's ID token, verified email and Workspace domain. Personal Google accounts, other domains, passwords, magic links and API tokens cannot access CRM.

Create a Google OAuth **Web application** client with an **Internal** consent audience in the company Workspace organization. Register this exact authorized redirect URI:

```text
https://crm.gabrielconsultant.one/api/method/crm.company_auth.callback
```

Set `GOOGLE_CLIENT_ID` and `GOOGLE_CLIENT_SECRET` in the CRM service's environment. Keep credentials in Zeabur secret variables or an untracked local `.env` file.

Startup provisions the initial administrator if the account does not already exist. That administrator can add staff through invitations or User administration. Configure outgoing email before sending invitations. Disable the CRM User when removing an employee's access; disabling their Workspace account alone does not immediately revoke an existing CRM session.

## Deploy on Zeabur

The root [Dockerfile](Dockerfile) builds Frappe and CRM from source using a pinned Frappe revision. Nginx, Gunicorn, realtime, one queue worker and one scheduler run together through Supervisor and share the sites volume.

| Service | Configuration | Persistent mount |
|---|---|---|
| CRM | This repository's root Dockerfile; public port `8080`; **one replica** | `/home/frappe/frappe-bench/sites` |
| MariaDB | `mariadb:11.8`; private network only | `/var/lib/mysql` |
| Redis | `redis:7.4-alpine`; append-only persistence; private network only | `/data` |

1. Create MariaDB and Redis services with their persistent volumes.
2. Add this repository as a Zeabur Git service using the repository root as the build root.
3. Mount the CRM sites volume before its first start.
4. Configure the variables from [.env.example](.env.example), including the Google credentials, private database/Redis addresses and database bootstrap password.
5. Bind `crm.gabrielconsultant.one` to the CRM service with HTTPS and allow at least 10 minutes for first startup.
6. Check `/api/method/crm.company_auth.health`, then visit `/company-login` and sign in as `thomas@gabriel.hk`.
7. Verify lead/task creation, realtime connectivity and persistence after a restart.

See the [full deployment guide](docs/zeabur-deployment.md) for all variables, DNS/hostname binding steps, staff access, backups, upgrades and recovery.

**Deployment status:** application builds and local runtime checks have passed. A live Zeabur deployment and real Google OAuth sign-in have not yet been verified. The Linux Docker image has not been executed locally.

## Local setup

Clone into a directory named `crm` so it also fits Frappe Bench's app directory convention:

```sh
git clone git@github.com:thomascsyu/newCRM.git crm
cd crm
cp .env.example .env
```

Fill in the missing credentials, then start the container stack:

```sh
docker compose --env-file .env -f docker/docker-compose.yml up --build -d
```

Google sign-in requires HTTPS for local end-to-end testing too. Put a TLS reverse proxy or tunnel in front of port `8080`, set `CRM_PUBLIC_URL` to that HTTPS origin, and register its callback URI with Google. Keep CSRF protection enabled.

For development within an existing Bench checkout, see [frontend development](frontend/README.md). Frappe and CRM must be installed as sibling apps in that checkout.

## Verification

From the Bench directory:

```sh
# Frontend tests and production build
cd apps/crm/frontend
yarn install --frozen-lockfile
yarn test:run
yarn build

# Authentication tests using Bench's Python
cd ..
../../env/bin/python -m unittest crm.tests.test_workspace_identity crm.tests.test_company_auth
```

The implementation was checked with 165 frontend tests, 23 authentication tests and 29 database-backed invitation, pricing and call-log tests. Fresh installation, repeatable schema cleanup, authenticated HTTP requests and a headless browser login-page check also passed. Google transport was mocked during local OAuth flow tests.

Browser tests provide a public authentication project and an authenticated workflow project. From `apps/crm`, set `BASE_URL` to staging and run `yarn test:e2e --project=public`. For authenticated tests, save a real Google-signed-in browser state to `e2e/.auth/user.json`; see the [deployment guide](docs/zeabur-deployment.md). Do not commit browser session credentials.

## Existing installations and backups

Back up the database and public/private files before upgrading, and test the migration on a staging copy. The cleanup patch deliberately removes obsolete integration tables, columns, credentials and configuration. Core CRM records remain. External provider recording references are cleared; download recordings before migration if they must be retained.

Keep backups outside the Zeabur service and test restoration. Rollback after schema cleanup requires the matching pre-upgrade database/files and application image. See [upgrade and recovery instructions](docs/zeabur-deployment.md#upgrading-an-existing-crm).

## License

Based on [Frappe CRM](https://github.com/frappe/crm). Original copyright and license notices remain applicable; see [LICENSE](LICENSE). This repository is customized for internal company use.
