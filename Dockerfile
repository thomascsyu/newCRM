# One company CRM service: web, realtime, worker and scheduler share one site volume.
FROM node:24-bookworm-slim AS node
FROM python:3.14-slim-trixie
ARG FRAPPE_REF=988e54f3c4c291e2077a83809663f123731abe76
ENV DEBIAN_FRONTEND=noninteractive PYTHONUNBUFFERED=1 \
    PATH=/home/frappe/frappe-bench/env/bin:/usr/local/bin:/usr/bin:/bin
RUN apt-get update && apt-get install -y --no-install-recommends \
    git curl ca-certificates build-essential pkg-config libmariadb-dev mariadb-client \
    nginx supervisor gettext libffi-dev libssl-dev libjpeg-dev zlib1g-dev \
    libpango-1.0-0 libpangoft2-1.0-0 libharfbuzz-subset0 libgdk-pixbuf-2.0-0 \
    fonts-dejavu-core && rm -rf /var/lib/apt/lists/*
COPY --from=node /usr/local/bin/node /usr/local/bin/node
COPY --from=node /usr/local/lib/node_modules /usr/local/lib/node_modules
RUN ln -s /usr/local/lib/node_modules/npm/bin/npm-cli.js /usr/local/bin/npm \
    && ln -s /usr/local/lib/node_modules/npm/bin/npx-cli.js /usr/local/bin/npx \
    && npm install -g yarn@1.22.22 \
    && pip install --no-cache-dir frappe-bench==5.31.0 \
    && useradd -m -s /bin/bash frappe
USER frappe
WORKDIR /home/frappe
RUN git init /tmp/frappe && git -C /tmp/frappe remote add origin https://github.com/frappe/frappe.git \
    && git -C /tmp/frappe fetch --depth 1 origin ${FRAPPE_REF} \
    && git -C /tmp/frappe checkout -b version-16 FETCH_HEAD \
    && bench init frappe-bench --frappe-path /tmp/frappe --frappe-branch version-16 \
       --python /usr/local/bin/python3 --skip-assets --skip-redis-config-generation \
    && rm -rf /tmp/frappe
WORKDIR /home/frappe/frappe-bench
COPY --chown=frappe:frappe . apps/crm
RUN env/bin/pip install --no-cache-dir -e apps/crm \
    && printf '\ncrm\n' >> sites/apps.txt \
    && yarn --cwd apps/crm/frontend install --frozen-lockfile --non-interactive \
    && bench build --production \
    && mkdir -p /home/frappe/image-assets \
    && cp -a sites/assets/. /home/frappe/image-assets/
USER root
COPY deployment/nginx.conf /etc/nginx/nginx.conf
COPY deployment/supervisord.conf /etc/supervisor/crm.conf
RUN chmod +x apps/crm/deployment/entrypoint.sh \
    && mkdir -p /var/log/supervisor /var/lib/nginx /run/nginx
EXPOSE 8080
HEALTHCHECK --interval=30s --timeout=5s --start-period=600s \
  CMD curl --fail --silent http://127.0.0.1:8080/api/method/crm.company_auth.health || exit 1
ENTRYPOINT ["/home/frappe/frappe-bench/apps/crm/deployment/entrypoint.sh"]
