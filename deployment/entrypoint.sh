#!/usr/bin/env bash
set -euo pipefail
cd /home/frappe/frappe-bench
PORT="${PORT:-8080}"
export PORT
echo "entrypoint: starting, PORT=${PORT}" >&2

mkdir -p sites logs \
  /var/log/supervisor \
  /var/lib/nginx/body /var/lib/nginx/proxy \
  /var/lib/nginx/fastcgi /var/lib/nginx/uwsgi /var/lib/nginx/scgi \
  /run/nginx

if [ "$(id -u)" = "0" ]; then
  chown frappe:frappe sites logs
  if ! runuser -u frappe -- sh -c 'test -w sites'; then
    chown -R frappe:frappe sites logs
  fi
  chown -R frappe:frappe /var/lib/nginx /run/nginx /var/log/supervisor
fi

if [ -f /etc/nginx/nginx.conf.template ]; then
  envsubst '${PORT}' < /etc/nginx/nginx.conf.template > /etc/nginx/nginx.conf
fi

# Answer probes immediately so Zeabur does not restart the pod during bootstrap.
python3 /home/frappe/frappe-bench/apps/crm/deployment/startup_probe.py &
PROBE_PID=$!
echo "entrypoint: startup probe listening on :${PORT} (pid ${PROBE_PID})" >&2
stop_probe() {
  kill "$PROBE_PID" 2>/dev/null || true
  wait "$PROBE_PID" 2>/dev/null || true
}
trap stop_probe EXIT

echo "entrypoint: running bootstrap.py" >&2
if [ "$(id -u)" = "0" ]; then
  runuser -u frappe -- env/bin/python apps/crm/deployment/bootstrap.py
else
  env/bin/python apps/crm/deployment/bootstrap.py
fi
echo "entrypoint: bootstrap.py finished" >&2

stop_probe
trap - EXIT
# nginx cannot bind until the temporary probe releases the public port
sleep 0.3
echo "entrypoint: handing off to supervisord" >&2
exec /usr/bin/supervisord -c /etc/supervisor/crm.conf
