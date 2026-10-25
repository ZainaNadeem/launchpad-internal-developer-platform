import argparse
import importlib.util
from copy import deepcopy
from pathlib import Path

import yaml


PREFLIGHT_PATH = Path(__file__).resolve().with_name("preflight.py")
preflight_spec = importlib.util.spec_from_file_location(
    "launchpad_preflight",
    PREFLIGHT_PATH,
)
preflight = importlib.util.module_from_spec(preflight_spec)
preflight_spec.loader.exec_module(preflight)


def load_service(path):
    with open(path, "r") as file:
        return yaml.safe_load(file)


def validate_service(service):
    findings = preflight.check_schema(service)
    if findings:
        raise ValueError(
            "\n".join(
                f"{finding['message']} Fix: {finding['recommendation']}"
                for finding in findings
            )
        )


def apply_defaults(service):
    """Return a separate configuration with missing defaults filled in."""
    result = deepcopy(service)
    result.setdefault("replicas", 1)
    result.setdefault("health_path", "/health")
    resources = result.setdefault("resources", {})
    resources.setdefault("cpu", "100m")
    resources.setdefault("memory", "128Mi")
    autoscaling = result.setdefault("autoscaling", {})
    autoscaling.setdefault("enabled", False)
    autoscaling.setdefault("min_replicas", 1)
    autoscaling.setdefault("max_replicas", 3)
    autoscaling.setdefault("target_cpu", 70)
    return result


def build_deployment(service):
    return {
        "apiVersion": "apps/v1",
        "kind": "Deployment",
        "metadata": {
            "name": service["name"],
        },
        "spec": {
            "replicas": service["replicas"],
            "selector": {
                "matchLabels": {
                    "app": service["name"],
                }
            },
            "template": {
                "metadata": {
                    "labels": {
                        "app": service["name"],
                    }
                },
                "spec": {
                    "containers": [
                        {
                            "name": service["name"],
                            "image": service["image"],
                            "ports": [
                                {
                                    "containerPort": service["port"],
                                }
                            ],
                            "readinessProbe": {
                                "httpGet": {
                                    "path": service["health_path"],
                                    "port": service["port"],
                                }
                            },
                            "livenessProbe": {
                                "httpGet": {
                                    "path": service["health_path"],
                                    "port": service["port"],
                                }
                            },
                            "resources": {
                                "requests": {
                                    "cpu": service["resources"]["cpu"],
                                    "memory": service["resources"]["memory"],
                                },
                                "limits": {
                                    "cpu": service["resources"]["cpu"],
                                    "memory": service["resources"]["memory"],
                                },
                            },
                        }
                    ]
                },
            },
        },
    }


def build_service(service):
    return {
        "apiVersion": "v1",
        "kind": "Service",
        "metadata": {
            "name": service["name"],
        },
        "spec": {
            "selector": {
                "app": service["name"],
            },
            "ports": [
                {
                    "port": 80,
                    "targetPort": service["port"],
                }
            ],
            "type": "ClusterIP",
        },
    }


def build_hpa(service):
    autoscaling = service["autoscaling"]

    if not autoscaling["enabled"]:
        return None

    return {
        "apiVersion": "autoscaling/v2",
        "kind": "HorizontalPodAutoscaler",
        "metadata": {
            "name": service["name"],
        },
        "spec": {
            "scaleTargetRef": {
                "apiVersion": "apps/v1",
                "kind": "Deployment",
                "name": service["name"],
            },
            "minReplicas": autoscaling["min_replicas"],
            "maxReplicas": autoscaling["max_replicas"],
            "metrics": [
                {
                    "type": "Resource",
                    "resource": {
                        "name": "cpu",
                        "target": {
                            "type": "Utilization",
                            "averageUtilization": autoscaling["target_cpu"],
                        },
                    },
                }
            ],
        },
    }

def generate(service, strict=False):
    """Check the original specification before applying defaults."""
    report = preflight.evaluate(service)
    if preflight.exit_code(report, strict=strict):
        recommendations = [
            f"{finding['message']} Fix: {finding['recommendation']}"
            for finding in report["findings"]
            if finding["level"] != "PASS"
        ]
        raise ValueError(
            "Preflight blocked generation:\n"
            + "\n".join(recommendations)
        )
    config = apply_defaults(service)
    manifests = [
        build_deployment(config),
        build_service(config),
    ]
    hpa = build_hpa(config)
    if hpa is not None:
        manifests.append(hpa)
    return manifests, report


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Generate Kubernetes manifests from a LaunchPad service."
    )
    parser.add_argument("service", type=Path)
    parser.add_argument(
        "-o", "--output", type=Path, default=Path("platform/generated.yaml"),
        help="Output manifest path (default: platform/generated.yaml).",
    )
    parser.add_argument(
        "--strict", action="store_true",
        help="Block generation on readiness warnings.",
    )
    args = parser.parse_args(argv)

    try:
        service = load_service(args.service)
        manifests, report = generate(service, strict=args.strict)
        with args.output.open("w", encoding="utf-8") as file:
            yaml.safe_dump_all(manifests, file, sort_keys=False)
    except (OSError, UnicodeError, yaml.YAMLError, ValueError) as error:
        print(f"FAIL  {error}")
        return 1

    print("LaunchPad service validated successfully")
    print(f"Readiness Score: {report['score']}/100")
    print(f"Status: {report['status']}")
    print(f"Generated Kubernetes manifests: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
