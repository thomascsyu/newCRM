# Company CRM

An internal, single-company CRM built on Frappe 16, Python 3.14 and Vue 3. Deploy one application service, one MariaDB database service and one Redis service on Zeabur.

The company CRM address is `https://crm.gabrielconsultant.one`. Employees sign in with `@gabriel.hk` Google Workspace accounts; the initial administrator is `thomas@gabriel.hk`. Accounts must be provisioned and enabled by an administrator, have a CRM role, and belong to the exact configured company domain. Personal Google accounts, other domains, password login, magic links and API-token authentication cannot access CRM.

## Included workflows

- Leads, deals, contacts, client organizations, activities, notes and tasks.
- Sales roles and reporting hierarchy within the company.
- An internal product/service catalogue with standard prices and deal line totals.
- Phone links that open the employee's device dialler, plus manual call logs and private recording attachments.
- Email configuration and domain enrichment.

ERPNext, Twilio and Exotel integration code, settings, credentials and dedicated schemas have been removed. Quotation/customer/item synchronization and provider-based calls/recording downloads are unavailable. Use the internal catalogue and attach externally prepared quotations to a deal. Existing company records remain; they are not tenants.

## Setup and deployment

See [Zeabur deployment](docs/zeabur-deployment.md) for Google configuration, required variables, storage, upgrades and recovery. See [frontend development](frontend/README.md) for local build/test instructions.

The root `Dockerfile` builds both Frappe and this CRM from source. The Frappe revision is pinned in the Dockerfile. The image runs Nginx, Gunicorn, realtime, one queue worker and one scheduler through Supervisor. All application processes share the same site volume. Run exactly one replica of the application service.

For a local container installation, copy `.env.example` to `.env`, supply real settings, then run:

```sh
docker compose --env-file .env -f docker/docker-compose.yml up --build -d
```

Google sign-in requires an HTTPS hostname, including for end-to-end development. Place a TLS reverse proxy or tunnel in front of local port 8080 and register that exact HTTPS callback with Google. Do not disable CSRF protection or introduce a password-login fallback.

## Verification

```sh
# In a Bench environment with apps/frappe and apps/crm:
cd apps/crm/frontend
yarn install --frozen-lockfile
yarn test:run
yarn build

# From apps/crm, with Bench's Python:
../../env/bin/python -m unittest crm.tests.test_workspace_identity crm.tests.test_company_auth
```

Browser tests have a public authentication project and an authenticated business-workflow project. Supply `BASE_URL` for your staging site. Run the public project with `yarn test:e2e --project=public`. For business tests, first save a genuine Google-signed-in browser state as `e2e/.auth/user.json` (see the deployment guide); no test bypass exists in the deployed authentication code.

Original Frappe CRM copyright and license notices remain applicable. This repository is customized for internal company use.
