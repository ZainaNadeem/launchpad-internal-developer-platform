"""Measure configuration size using LaunchPad's actual generator."""

import argparse
import importlib.util
import json
from pathlib import Path

import yaml


GENERATOR_PATH = Path(__file__).resolve().with_name("generator.py")

spec = importlib.util.spec_from_file_location(
    "launchpad_generator",
    GENERATOR_PATH,
)
generator = importlib.util.module_from_spec(spec)
spec.loader.exec_module(generator)


def count_config_lines(text):
    """Exclude blank lines, full-line comments, and YAML document markers."""
    return sum(
        1
        for line in text.splitlines()
        if line.strip()
        and not line.lstrip().startswith("#")
        and line.strip() not in {"---", "..."}
    )


def benchmark(source_text):
    service = yaml.safe_load(source_text)
    manifests, report = generator.generate(service)

    generated_text = yaml.safe_dump_all(
        manifests,
        sort_keys=False,
    )

    specification_lines = count_config_lines(source_text)
    manifest_lines = count_config_lines(generated_text)

    return {
        "specification_lines": specification_lines,
        "generated_manifest_lines": manifest_lines,
        "resource_count": len(manifests),
        "resource_kinds": [item["kind"] for item in manifests],
        "readiness_score": report["score"],
        "readiness_status": report["status"],
        "methodology": (
            "Count nonblank lines excluding full-line comments and YAML "
            "document markers. Generate manifests in memory using the "
            "current generator and PyYAML serializer."
        ),
        "limitations": (
            "Configuration size comparison only. Formatting and defaults "
            "affect line counts. This is not a timed manual-authoring "
            "study or a deployment-performance benchmark."
        ),
    }


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Measure LaunchPad specification and manifest size."
    )
    parser.add_argument("service", type=Path)
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print machine-readable results.",
    )
    args = parser.parse_args(argv)

    try:
        result = benchmark(
            args.service.read_text(encoding="utf-8")
        )
    except (OSError, UnicodeError, ValueError, yaml.YAMLError) as error:
        print(f"FAIL  Benchmark could not run: {error}")
        return 1

    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print("LaunchPad Configuration Benchmark")
        print(f"Service specification: {args.service}")
        print(
            "Specification configuration lines: "
            f"{result['specification_lines']}"
        )
        print(
            "Generated manifest configuration lines: "
            f"{result['generated_manifest_lines']}"
        )
        print(f"Resources generated: {result['resource_count']}")
        print("Resource kinds: " + ", ".join(result["resource_kinds"]))
        print(
            f"Readiness: {result['readiness_score']}/100 "
            f"({result['readiness_status']})"
        )
        print(f"\nMethod: {result['methodology']}")
        print(f"\nLimitations: {result['limitations']}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
