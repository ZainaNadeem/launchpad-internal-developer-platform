import importlib.util
from pathlib import Path

import pytest


GENERATOR_PATH = (
    Path(__file__).parent.parent
    / "platform"
    / "generator.py"
)

spec = importlib.util.spec_from_file_location(
    "launchpad_generator",
    GENERATOR_PATH,
)

generator = importlib.util.module_from_spec(spec)
spec.loader.exec_module(generator)

apply_defaults = generator.apply_defaults
build_deployment = generator.build_deployment
build_hpa = generator.build_hpa
build_service = generator.build_service
validate_service = generator.validate_service



def valid_service():
    return {
        "name": "test-api",
        "image": "test-api:latest",
        "port": 8000,
        "replicas": 2,
        "health_path": "/health",
        "resources": {
            "cpu": "100m",
            "memory": "64Mi",
        },
        "autoscaling": {
            "enabled": True,
            "min_replicas": 2,
            "max_replicas": 5,
            "target_cpu": 70,
        },
    }


def test_validate_service_accepts_valid_config():
    validate_service(valid_service())


def test_validate_service_rejects_missing_name():
    service = valid_service()
    del service["name"]

    with pytest.raises(ValueError):
        validate_service(service)


def test_apply_defaults_adds_optional_values():
    service = {
        "name": "test-api",
        "image": "test-api:latest",
        "port": 8000,
    }

    result = apply_defaults(service)

    assert result["replicas"] == 1
    assert result["health_path"] == "/health"
    assert result["autoscaling"]["enabled"] is False


def test_build_deployment():
    deployment = build_deployment(valid_service())

    assert deployment["kind"] == "Deployment"
    assert deployment["metadata"]["name"] == "test-api"
    assert deployment["spec"]["replicas"] == 2


def test_build_service():
    service = build_service(valid_service())

    assert service["kind"] == "Service"
    assert service["spec"]["ports"][0]["targetPort"] == 8000


def test_build_hpa():
    hpa = build_hpa(valid_service())

    assert hpa["kind"] == "HorizontalPodAutoscaler"
    assert hpa["spec"]["minReplicas"] == 2
    assert hpa["spec"]["maxReplicas"] == 5


def test_partial_defaults_preserve_input():
    service = {
        "name": "test-api",
        "image": "test-api:latest",
        "port": 8000,
        "resources": {"cpu": "200m"},
        "autoscaling": {"enabled": True},
    }
    result = apply_defaults(service)
    assert result["resources"] == {
        "cpu": "200m",
        "memory": "128Mi",
    }
    assert result["autoscaling"]["max_replicas"] == 3
    assert service["resources"] == {"cpu": "200m"}
    assert service["autoscaling"] == {"enabled": True}
    assert "replicas" not in service


def test_generation_allows_warnings_in_normal_mode():
    manifests, report = generator.generate(valid_service())
    assert [item["kind"] for item in manifests] == [
        "Deployment",
        "Service",
        "HorizontalPodAutoscaler",
    ]
    assert report["status"] == "NEEDS_ATTENTION"


def test_generation_rejects_warnings_in_strict_mode():
    with pytest.raises(ValueError, match="Preflight blocked generation"):
        generator.generate(valid_service(), strict=True)


@pytest.mark.parametrize(
    ("document", "flags"),
    [
        ("name: test-api\n", []),
        ("name: test-api\nimage: test-api:latest\nport: 8000\n", ["--strict"]),
    ],
)
def test_rejected_generation_preserves_existing_manifest(tmp_path, document, flags):
    source = tmp_path / "service.yaml"
    source.write_text(document, encoding="utf-8")
    output = tmp_path / "generated.yaml"
    original = b"existing manifest\n"
    output.write_bytes(original)

    assert generator.main([str(source), "-o", str(output), *flags]) == 1
    assert output.read_bytes() == original


def test_cli_creates_nested_output_and_prints_warning(tmp_path, capsys):
    source = tmp_path / "service.yaml"
    source.write_text(
        generator.yaml.safe_dump(valid_service()),
        encoding="utf-8",
    )
    output = tmp_path / "nested" / "generated.yaml"

    assert generator.main([str(source), "-o", str(output)]) == 0

    manifests = list(
        generator.yaml.safe_load_all(
            output.read_text(encoding="utf-8")
        )
    )
    assert [item["kind"] for item in manifests] == [
        "Deployment",
        "Service",
        "HorizontalPodAutoscaler",
    ]

    terminal = capsys.readouterr().out
    assert "WARN" in terminal
    assert "Fix:" in terminal


def test_strict_generation_accepts_digest_pinned_service():
    service = valid_service()
    service["image"] = "test-api@sha256:" + "a" * 64

    manifests, report = generator.generate(service, strict=True)

    assert len(manifests) == 3
    assert report["score"] == 100


def test_disabled_autoscaling_omits_hpa():
    service = valid_service()
    service["autoscaling"]["enabled"] = False

    manifests, _ = generator.generate(service)

    assert [item["kind"] for item in manifests] == [
        "Deployment",
        "Service",
    ]


def test_generation_fills_partial_resource_defaults():
    service = valid_service()
    service["resources"] = {"cpu": "200m"}

    manifests, _ = generator.generate(service)

    container = manifests[0]["spec"]["template"]["spec"]["containers"][0]
    assert container["resources"]["requests"] == {
        "cpu": "200m",
        "memory": "128Mi",
    }


def test_generation_uses_separate_requests_and_limits():
    service = valid_service()
    service["resources"] = {
        "cpu": "100m",
        "memory": "64Mi",
        "cpu_limit": "500m",
        "memory_limit": "256Mi",
    }

    manifests, _ = generator.generate(service)
    container = manifests[0]["spec"]["template"]["spec"]["containers"][0]

    assert container["resources"] == {
        "requests": {
            "cpu": "100m",
            "memory": "64Mi",
        },
        "limits": {
            "cpu": "500m",
            "memory": "256Mi",
        },
    }


def test_legacy_resources_keep_matching_limits():
    manifests, _ = generator.generate(valid_service())
    container = manifests[0]["spec"]["template"]["spec"]["containers"][0]

    assert container["resources"]["limits"] == (
        container["resources"]["requests"]
    )


def test_generation_blocks_limit_below_request():
    service = valid_service()
    service["resources"]["cpu_limit"] = "50m"

    with pytest.raises(ValueError, match="Preflight blocked generation"):
        generator.generate(service)
