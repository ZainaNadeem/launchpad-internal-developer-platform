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
    output = capsys.readouterr().out
    assert "WARN" in output
    assert "NEEDS_ATTENTION" in output


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


def ready_service():
    service = valid_service()
    service["image"] = "payments-api@sha256:" + "a" * 64
    service["resources"] = {
        "cpu": "100m",
        "memory": "128Mi",
    }
    service["autoscaling"] = {
        "enabled": True,
        "min_replicas": 2,
        "max_replicas": 5,
        "target_cpu": 70,
    }
    return service


def test_ready_configuration_scores_100():
    report = preflight.evaluate(ready_service())

    assert report["score"] == 100
    assert report["status"] == "READY"
    assert all(
        finding["level"] == "PASS"
        for finding in report["findings"]
    )


@pytest.mark.parametrize(
    "image",
    [
        "payments-api",
        "payments-api:latest",
        "payments-api:1.0.0",
        "localhost:5000/payments-api:1",
    ],
)
def test_mutable_image_reference_loses_image_points(image):
    service = ready_service()
    service["image"] = image

    report = preflight.evaluate(service)

    assert report["score"] == 80
    assert report["status"] == "NEEDS_ATTENTION"
    assert any(
        finding["rule"] == "image" and finding["level"] == "WARN"
        for finding in report["findings"]
    )


def test_missing_resources_have_actionable_warnings():
    service = ready_service()
    del service["resources"]

    report = preflight.evaluate(service)

    assert report["score"] == 70
    warnings = {
        finding["rule"]
        for finding in report["findings"]
        if finding["level"] == "WARN"
    }
    assert warnings == {"cpu", "memory"}


def test_autoscaling_minimum_controls_availability_score():
    service = ready_service()
    service["replicas"] = 3
    service["autoscaling"]["min_replicas"] = 1

    report = preflight.evaluate(service)

    assert report["score"] == 80
    assert any(
        finding["rule"] == "availability"
        and finding["level"] == "WARN"
        for finding in report["findings"]
    )


def test_fixed_replicas_can_pass_availability_without_autoscaling():
    service = ready_service()
    service["autoscaling"]["enabled"] = False

    report = preflight.evaluate(service)

    assert report["score"] == 85
    assert any(
        finding["rule"] == "availability"
        and finding["level"] == "PASS"
        for finding in report["findings"]
    )


def test_invalid_schema_has_no_readiness_score():
    report = preflight.evaluate({"name": "payments-api"})

    assert report["score"] is None
    assert report["status"] == "INVALID"
    assert preflight.exit_code(report) == 1


def test_evaluation_is_deterministic_and_preserves_input():
    service = ready_service()
    original = copy.deepcopy(service)

    first = preflight.evaluate(service)
    second = preflight.evaluate(service)

    assert first == second
    assert service == original


def test_warnings_only_fail_in_strict_mode():
    service = ready_service()
    service["image"] = "payments-api:latest"
    report = preflight.evaluate(service)

    assert preflight.exit_code(report) == 0
    assert preflight.exit_code(report, strict=True) == 1


def test_ready_configuration_passes_strict_mode():
    report = preflight.evaluate(ready_service())

    assert preflight.exit_code(report, strict=True) == 0


def test_cli_strict_mode_rejects_warnings(tmp_path, capsys):
    source = tmp_path / "service.yaml"
    source.write_text(
        "name: payments-api\n"
        "image: payments-api:latest\n"
        "port: 8000\n",
        encoding="utf-8",
    )

    assert preflight.main([str(source), "--strict"]) == 1

    output = capsys.readouterr().out
    assert "WARN" in output
    assert "NEEDS_ATTENTION" in output
    assert "Recommendations:" in output
