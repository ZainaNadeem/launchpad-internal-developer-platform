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

    print("LaunchPad service validated successfully")
    print(yaml.safe_dump(service, sort_keys=False))


if __name__ == "__main__":
    main()