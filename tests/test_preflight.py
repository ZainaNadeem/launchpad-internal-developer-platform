import copy
import importlib.util
from pathlib import Path

import pytest


PREFLIGHT_PATH = (
    Path(__file__).resolve().parents[1]
    / "platform"
    / "preflight.py"
)

spec = importlib.util.spec_from_file_location(
    "launchpad_preflight",
    PREFLIGHT_PATH,
)
preflight = importlib.util.module_from_spec(spec)
spec.loader.exec_module(preflight)


def valid_service():
    return {
        "name": "payments-api",
        "image": "payments-api:1.0.0",
        "port": 8000,
        "replicas": 2,
        "health_path": "/health",
    }


def test_valid_schema_has_no_failures():
    assert preflight.check_schema(valid_service()) == []


@pytest.mark.parametrize("field", ["name", "image", "port"])
def test_missing_required_field_has_actionable_finding(field):
    service = valid_service()
    del service[field]

    findings = preflight.check_schema(service)

    assert any(
        finding["rule"] == field
        and finding["level"] == "FAIL"
        and finding["recommendation"]
        for finding in findings
    )


@pytest.mark.parametrize("document", [None, [], "service", 42])
def test_non_mapping_document_is_rejected(document):
    findings = preflight.check_schema(document)

    assert findings[0]["rule"] == "document"


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("name", ""),
        ("name", "Payments_API"),
        ("name", "../payments"),
        ("name", "a" * 64),
        ("image", ""),
        ("image", "payments api:1"),
        ("image", None),
        ("port", 0),
        ("port", 65536),
        ("port", True),
        ("port", "8000"),
        ("replicas", 0),
        ("replicas", -1),
        ("replicas", True),
        ("health_path", "health"),
        ("health_path", "/health check"),
        ("resources", None),
        ("autoscaling", []),
    ],
)
def test_invalid_field_is_rejected(field, value):
    service = valid_service()
    service[field] = value

    findings = preflight.check_schema(service)

    assert any(finding["rule"] == field for finding in findings)


def test_check_does_not_modify_input():
    service = valid_service()
    original = copy.deepcopy(service)

    preflight.check_schema(service)

    assert service == original


def test_cli_accepts_valid_yaml(tmp_path, capsys):
    source = tmp_path / "service.yaml"
    source.write_text(
        "name: payments-api\n"
        "image: payments-api:1.0.0\n"
        "port: 8000\n",
        encoding="utf-8",
    )

    assert preflight.main([str(source)]) == 0
    assert "PASS" in capsys.readouterr().out


def test_cli_rejects_invalid_schema(tmp_path, capsys):
    source = tmp_path / "service.yaml"
    source.write_text("name: payments-api\n", encoding="utf-8")

    assert preflight.main([str(source)]) == 1
    assert "FAIL" in capsys.readouterr().out


def test_cli_rejects_malformed_yaml(tmp_path):
    source = tmp_path / "service.yaml"
    source.write_text("name: [", encoding="utf-8")

    assert preflight.main([str(source)]) == 1


def test_cli_rejects_missing_file(tmp_path):
    assert preflight.main([str(tmp_path / "missing.yaml")]) == 1


@pytest.mark.parametrize(
    ("settings", "expected_rule"),
    [
        ({"resources": {"cpu": "0m"}}, "resources.cpu"),
        ({"resources": {"cpu": "-100m"}}, "resources.cpu"),
        ({"resources": {"cpu": True}}, "resources.cpu"),
        ({"resources": {"cpu": "100Mi"}}, "resources.cpu"),
        ({"resources": {"memory": "0Mi"}}, "resources.memory"),
        ({"resources": {"memory": "lots"}}, "resources.memory"),
        ({"resources": {"memory": None}}, "resources.memory"),
        (
            {"autoscaling": {"enabled": "false"}},
            "autoscaling.enabled",
        ),
        (
            {"autoscaling": {"min_replicas": 0}},
            "autoscaling.min_replicas",
        ),
        (
            {"autoscaling": {"max_replicas": True}},
            "autoscaling.max_replicas",
        ),
        (
            {"autoscaling": {"target_cpu": 101}},
            "autoscaling.target_cpu",
        ),
        (
            {"autoscaling": {"target_cpu": "70"}},
            "autoscaling.target_cpu",
        ),
        (
            {"autoscaling": {"min_replicas": 5, "max_replicas": 2}},
            "autoscaling.bounds",
        ),
    ],
)
def test_invalid_settings_are_rejected(settings, expected_rule):
    service = valid_service()
    service.update(settings)

    findings = preflight.check_schema(service)

    assert any(
        finding["rule"] == expected_rule and finding["level"] == "FAIL"
        for finding in findings
    )
