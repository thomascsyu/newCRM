"""Structured JSON audit log for authentication events, written to stdout.

Frappe's own logging (frappe.logger()/frappe.log_error) writes to files under
the sites volume, which Zeabur's log viewer cannot see without a shell into
the container. This is a separate, additive channel for the events an
operator actually needs when nothing else is available: who signed in, who
was denied, and why. It does not touch or replace Frappe's own logging.
"""
import json
import logging
import sys
import time

import frappe

_logger = logging.getLogger("crm.audit")
_logger.propagate = False
if not _logger.handlers:
    _handler = logging.StreamHandler(sys.stdout)
    _handler.setFormatter(logging.Formatter("%(message)s"))
    _logger.addHandler(_handler)
    _logger.setLevel(logging.INFO)


def _request_id():
    request = getattr(frappe.local, "request", None)
    return request.headers.get("X-Request-Id") if request else None


def event(kind: str, **fields):
    """Emit one JSON line. Never raises: logging must not affect auth flow."""
    try:
        record = {
            "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "event": kind,
            "request_id": _request_id(),
            **fields,
        }
        _logger.info(json.dumps(record, default=str))
    except Exception:
        pass
