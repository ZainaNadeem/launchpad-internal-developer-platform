import importlib.util
import json
from pathlib import Path

import pytest


BENCHMARK_PATH = (
    Path(__file__).resolve().parents[1]
    / "platform"
    / "benchmark.py"
)

spec = importlib.util.spec_from_file_location(
    "launchpad_benchmark",
    BENCHMARK_PATH,
)
benchmark_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(benchmark_module)


def service_text(enabled=True):
    return (
        "name: benchmark-api\n"
        "image: benchmark-api:latest\n"
        "port: 8000\n"
        "autoscaling:\n"
        f"  enabled: {str(enabled).lower()}\n"
    )


def test_line_count_excludes_comments_blanks_and_document_markers():
    text = (
        "# Service configuration\n"
        "\n"
        "---\n"
        "name: benchmark-api\n"
        "  # Indented comment\n"
        "port: 8000  # Inline comment\n"
        "...\n"
    )

    assert benchmark_module.count_config_lines(text) == 2


def test_benchmark_counts_generated_resources():
    result = benchmark_module.benchmark(service_text())

    assert result["specification_lines"] == 5
    assert result["resource_count"] == 3
    assert result["resource_kinds"] == [
        "Deployment",
        "Service",
        "HorizontalPodAutoscaler",
    ]
    assert result["generated_manifest_lines"] > 0


def test_disabled_autoscaling_generates_two_resources():
    result = benchmark_module.benchmark(service_text(enabled=False))

    assert result["resource_count"] == 2
    assert result["resource_kinds"] == ["Deployment", "Service"]


def test_benchmark_is_repeatable():
    source = service_text()

    assert benchmark_module.benchmark(source) == (
        benchmark_module.benchmark(source)
    )


def test_benchmark_rejects_invalid_specification():
    with pytest.raises(ValueError, match="Preflight blocked generation"):
        benchmark_module.benchmark("name: benchmark-api\n")


def test_json_cli_reports_measurements(tmp_path, capsys):
    source = tmp_path / "service.yaml"
    source.write_text(service_text(), encoding="utf-8")

    result = benchmark_module.main([str(source), "--json"])

    assert result == 0
    output = json.loads(capsys.readouterr().out)
    assert output["specification_lines"] == 5
    assert output["resource_count"] == 3


def test_cli_reports_missing_file(tmp_path, capsys):
    result = benchmark_module.main(
        [str(tmp_path / "missing.yaml")]
    )

    assert result == 1
    assert "FAIL" in capsys.readouterr().out
