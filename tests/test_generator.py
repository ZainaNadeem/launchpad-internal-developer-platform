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