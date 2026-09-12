# Company CRM frontend

Vue 3, Vite and the shared UI library. Requires Node 24 and Yarn 1.22.22, plus the pinned backend framework source used by the root Dockerfile.

The frontend imports `@framework/ui` from the sibling backend framework app. Keep this layout:

See the exact directory layout in the [deployment guide](../docs/zeabur-deployment.md).


From this directory:

```sh
yarn install --frozen-lockfile
yarn test:run
yarn build
```

`yarn build` writes the production assets to `crm/public/frontend` and the HTML entry to `crm/www/crm.html`. Unit tests do not need an authenticated site.

`yarn dev` proxies a local backend server. Use a registered HTTPS development origin for Google sign-in; do not disable CSRF. Runtime secrets belong to the backend environment, never to Vite variables or frontend bundles. See `../docs/zeabur-deployment.md` for configuration.

Phone actions open the device dialler with `tel:`. Calls are logged manually; there is no browser calling SDK or provider configuration.
