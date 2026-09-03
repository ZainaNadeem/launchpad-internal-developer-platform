import sys
from pathlib import Path

import yaml


REQUIRED_FIELDS = ["name", "image", "port"]


def load_service(path):
    with open(path, "r") as file:
        return yaml.safe_load(file)


def validate_service(service):
    missing = [
        field
        for field in REQUIRED_FIELDS
        if field not in service
    ]

    if missing:
        raise ValueError(
            f"Missing required fields: {', '.join(missing)}"
        )


def apply_defaults(service):
    service.setdefault("replicas", 1)
    service.setdefault("health_path", "/health")

    service.setdefault(
        "resources",
        {
            "cpu": "100m",
            "memory": "128Mi",
        },
    )

    service.setdefault(
        "autoscaling",
        {
            "enabled": False,
            "min_replicas": 1,
            "max_replicas": 3,
            "target_cpu": 70,
        },
    )

    return service

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

def main():
    if len(sys.argv) != 2:
        print(
            "Usage: python -m platform.generator "
            "<service.yaml>"
        )
        sys.exit(1)

    path = Path(sys.argv[1])

    service = load_service(path)
    validate_service(service)
    service = apply_defaults(service)

    deployment = build_deployment(service)
    kubernetes_service = build_service(service)
    hpa = build_hpa(service)

    manifests = [deployment, kubernetes_service]

    if hpa:
        manifests.append(hpa)

    output_path = Path("platform/generated.yaml")

    with open(output_path, "w") as file:
        yaml.safe_dump_all(
            manifests,
            file,
            sort_keys=False,
        )

    print("LaunchPad service validated successfully")
    print(f"Generated Kubernetes manifests: {output_path}")


if __name__ == "__main__":
    main()