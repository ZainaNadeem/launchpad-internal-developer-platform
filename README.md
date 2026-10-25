## Configuration benchmark

LaunchPad generates 67 lines of Kubernetes configuration from a
15-line service specification, producing three resources:

- Deployment
- Service
- HorizontalPodAutoscaler

Reproduce the measurement:

```bash
python platform/benchmark.py platform/examples/service.yaml
```

For JSON output:

```bash
python platform/benchmark.py platform/examples/service.yaml --json
```

Line counts exclude blank lines, full-line comments, and YAML document
markers. Generated manifests are measured in memory using the current
generator and PyYAML serializer.

These results measure configuration size, not developer time saved,
deployment speed, or runtime performance. Formatting, defaults, and
future generator changes can affect the counts.
