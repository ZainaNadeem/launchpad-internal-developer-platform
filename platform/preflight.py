"""Validate a LaunchPad service specification before generation."""

import argparse
import re
from decimal import Decimal
from pathlib import Path

import yaml


NAME_PATTERN = re.compile(r"[a-z]([-a-z0-9]{0,61}[a-z0-9])?")


def check_settings(service, fail):
    """Validate resource quantities and autoscaling relationships."""

    def positive_quantity(value, field, pattern):
        if isinstance(value, bool):
            match = None
        else:
            match = re.fullmatch(pattern, str(value))

        if match is None or Decimal(match.group(1)) <= 0:
            fail(
                field,
                f"{field} must be a positive supported resource quantity.",
                "Use CPU values such as '100m' or '0.5', and memory "
                "values such as '128Mi' or '1Gi'.",
            )

    resources = service.get("resources")
    if isinstance(resources, dict):
        # These patterns deliberately support a documented subset of
        # Kubernetes quantities, rather than its entire quantity grammar.
        number = r"([0-9]+(?:\.[0-9]+)?)"

        if "cpu" in resources:
            positive_quantity(
                resources["cpu"],
                "resources.cpu",
                number + r"(?:m)?",
            )

        if "memory" in resources:
            positive_quantity(
                resources["memory"],
                "resources.memory",
                number + r"(?:[KMGTPE]i|[kMGTPE])?",
            )

    scaling = service.get("autoscaling")
    if not isinstance(scaling, dict):
        return

    enabled = scaling.get("enabled", False)
    if type(enabled) is not bool:
        fail(
            "autoscaling.enabled",
            "autoscaling.enabled must be a boolean.",
            "Use true or false without quotes.",
        )

    bounds = {
        "min_replicas": (1, 1000, 1),
        "max_replicas": (1, 1000, 3),
        "target_cpu": (1, 100, 70),
    }

    valid_values = {}

    for field, (minimum, maximum, default) in bounds.items():
        value = scaling.get(field, default)

        if type(value) is not int or not minimum <= value <= maximum:
            fail(
                f"autoscaling.{field}",
                f"autoscaling.{field} must be an integer "
                f"from {minimum} to {maximum}.",
                f"Set {field} to an integer within that range.",
            )
        else:
            valid_values[field] = value

    minimum = valid_values.get("min_replicas")
    maximum = valid_values.get("max_replicas")

    if minimum is not None and maximum is not None and minimum > maximum:
        fail(
            "autoscaling.bounds",
            "min_replicas cannot exceed max_replicas.",
            "Set max_replicas greater than or equal to min_replicas.",
        )


def check_schema(service):
    """Return actionable schema failures without modifying the input."""
    findings = []

    def fail(rule, message, recommendation):
        findings.append(
            {
                "rule": rule,
                "level": "FAIL",
                "message": message,
                "recommendation": recommendation,
            }
        )

    def check_integer(value, field, minimum, maximum):
        # bool is a subclass of int, so use an exact type check.
        if type(value) is not int or not minimum <= value <= maximum:
            fail(
                field,
                f"{field} must be an integer from {minimum} to {maximum}.",
                f"Set {field} to an integer within that range.",
            )

    if not isinstance(service, dict):
        fail(
            "document",
            "The service specification must be a YAML mapping.",
            "Use top-level keys such as name, image, and port.",
        )
        return findings

    for field in ("name", "image", "port"):
        if field not in service:
            fail(
                field,
                f"Required field '{field}' is missing.",
                f"Add '{field}' to the service specification.",
            )

    if "name" in service:
        name = service["name"]
        if not isinstance(name, str) or not NAME_PATTERN.fullmatch(name):
            fail(
                "name",
                "name must be a lowercase service name of 1–63 characters.",
                "Start with a letter; use lowercase letters, digits, and "
                "hyphens; end with a letter or digit.",
            )

    if "image" in service:
        image = service["image"]
        if (
            not isinstance(image, str)
            or not image.strip()
            or any(character.isspace() for character in image)
        ):
            fail(
                "image",
                "image must be a nonempty reference without whitespace.",
                "Use an image reference such as payments-api:1.0.0.",
            )

    if "port" in service:
        check_integer(service["port"], "port", 1, 65535)

    if "replicas" in service:
        check_integer(service["replicas"], "replicas", 1, 1000)

    if "health_path" in service:
        path = service["health_path"]
        if (
            not isinstance(path, str)
            or not path.startswith("/")
            or any(character.isspace() for character in path)
        ):
            fail(
                "health_path",
                "health_path must start with / and contain no whitespace.",
                "Use an HTTP path such as /health.",
            )

    for field in ("resources", "autoscaling"):
        if field in service and not isinstance(service[field], dict):
            fail(
                field,
                f"{field} must be a YAML mapping.",
                f"Place the {field} settings under indented child keys.",
            )

    check_settings(service, fail)
    return findings


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Check a LaunchPad service specification."
    )
    parser.add_argument("service", type=Path)
    args = parser.parse_args(argv)

    try:
        with args.service.open(encoding="utf-8") as file:
            service = yaml.safe_load(file)
    except (OSError, UnicodeError, yaml.YAMLError) as error:
        print(f"FAIL  Cannot read service specification: {error}")
        return 1

    findings = check_schema(service)

    print("LaunchPad Preflight")

    if not findings:
        print("PASS  Schema checks passed")
        return 0

    for finding in findings:
        print(f"{finding['level']}  {finding['message']}")
        print(f"      Fix: {finding['recommendation']}")

    return 1


if __name__ == "__main__":
    raise SystemExit(main())
