# Gabriel Consultant CRM

An internal CRM for Gabriel Consultant, built with Python 3.14 and Vue 3. The application uses one shared company database, company Google Workspace sign-in and employee access roles.

Source repository: [thomascsyu/newCRM](https://github.com/thomascsyu/newCRM).

## Company configuration

| Setting | Value |
|---|---|
| Planned production address | `https://isocrm.pro` |
| Allowed Google Workspace email domain | `gabriel.hk` |
| Initial administrator | `thomas@gabriel.hk` |
| Internal site identifier | `crm.internal` |
| Deployment platform | Zeabur |

One site means one CRM installation shared by company employees. Client organizations are CRM records within that installation. Roles control employee access; there is no tenant signup or per-client site provisioning.

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
https://isocrm.pro/api/method/crm.company_auth.callback
```

Set `GOOGLE_CLIENT_ID` and `GOOGLE_CLIENT_SECRET` in the CRM service's environment. Keep credentials in Zeabur secret variables or an untracked local `.env` file.

Startup provisions the initial administrator if the account does not already exist. That administrator can add staff through invitations or User administration. Configure outgoing email before sending invitations. Disable the CRM User when removing an employee's access; disabling their Workspace account alone does not immediately revoke an existing CRM session.

## Deploy on Zeabur

The root [Dockerfile](Dockerfile) builds the application and its pinned backend framework from source. Nginx, Gunicorn, realtime, one queue worker and one scheduler run together through Supervisor and share the sites volume.

| Service | Configuration | Persistent mount |
|---|---|---|
| CRM | This repository's root Dockerfile; public port `8080`; **one replica** | Site storage (see deployment guide) |
| MariaDB | `mariadb:11.8`; private network only | `/var/lib/mysql` |
| Redis | `redis:7.4-alpine`; append-only persistence; private network only | `/data` |

### Import all services

The [`zeabur.yaml`](zeabur.yaml) template defines all three services, their volumes, private database connections, generated passwords, dependencies and health checks. From this repository:

```sh
npx zeabur@latest template deploy -f zeabur.yaml --var CRM_DOMAIN=isocrm.pro
```

Choose the intended project/server; the command supplies the company hostname. Authorize the Zeabur GitHub app for `thomascsyu/newCRM`. Import the template once into a new project.

After import:

1. Open **crm → Variables** and enter `GOOGLE_CLIENT_ID` and `GOOGLE_CLIENT_SECRET`, then restart CRM. Startup intentionally stops until these are supplied.
2. Bind `isocrm.pro` under **crm → Networking** and create the exact DNS record shown by Zeabur. Wait for the HTTPS certificate.
3. Keep one replica per service. Configure available runtime memory and volume capacity in the dashboard; the template does not allocate a server or set resource limits.
4. Verify `/api/method/crm.company_auth.health`, sign in as `thomas@gabriel.hk`, create a lead/task and check data after a restart.

### Exact service settings

| Setting | MariaDB | Redis | CRM |
|---|---|---|---|
| Source | `mariadb:11.8` | `redis:7.4-alpine` | `newCRM`, `main`, root Dockerfile |
| Port | `3306`, private TCP | `6379`, private TCP | `8080`, public HTTP through HTTPS |
| Public TCP forwarding | Disabled | Disabled | Disabled |
| Initial memory planning | 1 GB | 512 MB | 4 GB |
| Initial storage planning | 10 GB | 1 GB | 10 GB |
| Persistence | `/var/lib/mysql` | `/data`, AOF enabled | Site storage (see deployment guide) |
| Health check | TCP listener | TCP listener | HTTP database/Redis readiness |

Resource figures are starting estimates, not enforced limits. The Redis configuration uses a 256 MB data limit and `noeviction` to protect queued jobs. MariaDB uses UTF-8, a 512 MB buffer pool and at most 100 connections. Database and Redis passwords are generated by the template and shared through connection references; Google secrets belong only to CRM.

The [complete service setup guide](docs/zeabur-deployment.md#service-settings) includes every command, argument, variable, volume, health check, DNS step and manual-dashboard alternative. It also covers startup, backups, password handling, email setup and troubleshooting.

**Deployment status:** the template can be validated locally, and application builds/runtime checks previously passed. Live Zeabur import and real Google OAuth sign-in still require verification. The Linux Docker image has not been executed locally.

### Validate the deployment template

```sh
python3 -m venv .venv-deployment
.venv-deployment/bin/pip install -r deployment/requirements-validation.txt
.venv-deployment/bin/python scripts/validate_zeabur.py
```

This checks the official Zeabur schemas, dependency graph, variable references and private TCP settings. It does not create services or prove live deployment success.

## Local setup

Clone into a directory named `crm` so it also fits the backend's app directory convention:

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

For development within an existing Bench checkout, see [frontend development](frontend/README.md). The backend framework and CRM must be installed as sibling apps in that checkout.

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

Original copyright and license notices remain applicable; see [LICENSE](LICENSE) and [open-source attribution](THIRD_PARTY_NOTICES.md). This repository is customized for internal company use.
