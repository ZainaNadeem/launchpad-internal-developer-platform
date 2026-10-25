from fastapi import FastAPI, Request
from fastapi.responses import Response
from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST
import time


app = FastAPI(
    title="LaunchPad Demo Service",
    version="0.1.0"
)


REQUEST_COUNT = Counter(
    "launchpad_http_requests_total",
    "Total number of HTTP requests",
    ["method", "endpoint", "status_code"]
)

REQUEST_LATENCY = Histogram(
    "launchpad_http_request_duration_seconds",
    "HTTP request latency in seconds",
    ["method", "endpoint"]
)


@app.middleware("http")
async def collect_metrics(request: Request, call_next):
    start_time = time.perf_counter()

    response = await call_next(request)

    duration = time.perf_counter() - start_time
    # Route templates bound label cardinality; arbitrary 404 paths share a label.
    route = request.scope.get("route")
    endpoint = getattr(route, "path", "unmatched")
    method = request.method if request.method in {
        "GET", "HEAD", "POST", "PUT", "PATCH", "DELETE", "OPTIONS", "TRACE", "CONNECT"
    } else "OTHER"

    REQUEST_COUNT.labels(
        method=method,
        endpoint=endpoint,
        status_code=response.status_code
    ).inc()

    REQUEST_LATENCY.labels(
        method=method,
        endpoint=endpoint
    ).observe(duration)

    return response


@app.get("/")
def root():
    return {
        "service": "launchpad-demo",
        "message": "Deployed through LaunchPad"
    }


@app.get("/health")
def health():
    return {
        "status": "healthy"
    }


@app.get("/metrics")
def metrics():
    return Response(
        content=generate_latest(),
        media_type=CONTENT_TYPE_LATEST
    )
