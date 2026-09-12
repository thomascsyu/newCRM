#!/usr/bin/env bash
set -euo pipefail
cd /home/frappe/frappe-bench
# The site directory is persistent; code and assets come from this image.
mkdir -p sites logs
chown -R frappe:frappe sites logs
runuser -u frappe -- env/bin/python apps/crm/deployment/bootstrap.py
exec /usr/bin/supervisord -c /etc/supervisor/crm.conf
