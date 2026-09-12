#!/usr/bin/env python3
"""Validate the Zeabur template against official schemas and deployment constraints."""
import argparse
import json
from pathlib import Path
import re
from urllib.request import urlopen

import yaml
from jsonschema import Draft7Validator
from referencing import Registry, Resource

ROOT = Path(__file__).resolve().parents[1]
SCHEMA_BASE = "https://schema.zeabur.app/"


def validate(template, schemas):
    registry = Registry().with_resources(
        (SCHEMA_BASE + name, Resource.from_contents(schema)) for name, schema in schemas.items()
    )
    Draft7Validator(schemas["template.json"], registry=registry).validate(template)
    services = template["spec"]["services"]
    names = [service["name"] for service in services]
    if len(set(names)) != len(names):
        raise ValueError("Service names must be unique")
    exposed = {name for service in services for name, value in service["spec"].get("env", {}).items()
               if value.get("expose")}
    inputs = {item["key"] for item in template["spec"].get("variables", [])}
    for service in services:
        spec = service["spec"]
        if set(service.get("dependencies", [])) - set(names):
            raise ValueError(f"Unknown dependency in {service['name']}")
        ports = {port["id"]: port for port in spec.get("ports", [])}
        health = spec.get("healthCheck", {})
        if health.get("port") not in ports:
            raise ValueError(f"Missing or invalid health-check port in {service['name']}")
        if any(port["type"] == "TCP" for port in ports.values()) and spec.get("portForwarding", {}).get("enabled") is not False:
            raise ValueError(f"Database TCP forwarding must be disabled: {service['name']}")
        env = spec.get("env", {})
        allowed = exposed | inputs | set(env) | {"PASSWORD", "CONTAINER_HOSTNAME"}
        for name, value in env.items():
            refs = set(re.findall(r"\$\{([^}]+)\}", value.get("default", "")))
            if refs - allowed:
                raise ValueError(f"Unresolved variable reference in {service['name']}.{name}: {refs - allowed}")
            if name.startswith("GOOGLE_") and (value.get("default") or value.get("expose")):
                raise ValueError("Google credentials must be entered in CRM service settings only")
    # Check for dependency cycles, not just unknown dependency names.
    graph = {service["name"]: set(service.get("dependencies", [])) for service in services}
    done = set()
    while len(done) < len(graph):
        ready = {name for name, deps in graph.items() if name not in done and deps <= done}
        if not ready:
            raise ValueError("Service dependency cycle")
        done.update(ready)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--file", type=Path, default=ROOT / "zeabur.yaml")
    parser.add_argument("--schema-dir", type=Path, help="Directory containing template.json and prebuilt.json; otherwise download official schemas")
    args = parser.parse_args()
    schemas = {}
    for name in ("template.json", "prebuilt.json"):
        if args.schema_dir:
            schemas[name] = json.loads((args.schema_dir / name).read_text())
        else:
            with urlopen(SCHEMA_BASE + name, timeout=20) as response:
                schemas[name] = json.load(response)
    validate(yaml.safe_load(args.file.read_text()), schemas)
    print("Zeabur schema, dependency graph, variable references and private TCP settings passed.")


if __name__ == "__main__":
    main()
