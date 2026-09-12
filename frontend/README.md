# Company CRM frontend

Vue 3, Vite, Frappe UI. Requires Node 24 and Yarn 1.22.22, plus the pinned Frappe 16 source used by the root Dockerfile.

The frontend imports `@framework/ui` from the sibling Frappe app. Keep this layout:

```
frappe-bench/
  apps/frappe/ui/
  apps/crm/frontend/
  sites/
```

From this directory:

```sh
yarn install --frozen-lockfile
yarn test:run
yarn build
```

`yarn build` writes the production assets to `crm/public/frontend` and the HTML entry to `crm/www/crm.html`. Unit tests do not need an authenticated site.

`yarn dev` proxies a local Frappe server. Use a registered HTTPS development origin for Google sign-in; do not disable CSRF. Runtime secrets belong to the backend environment, never to Vite variables or frontend bundles. See `../docs/zeabur-deployment.md` for configuration.

Phone actions open the device dialler with `tel:`. Calls are logged manually; there is no browser calling SDK or provider configuration.
