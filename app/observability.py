import json
import logging
import sys
import time
import uuid

from prometheus_client import CONTENT_TYPE_LATEST, Counter, Gauge, Histogram, generate_latest
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

from app.config import settings
from app.version import APP_VERSION, GIT_SHA

RESERVED = set(logging.LogRecord("", 0, "", 0, "", (), None).__dict__.keys()) | {"message", "asctime"}

requests_total = Counter(
    "http_requests_total", "HTTP requests by method, route and status", ["method", "route", "status"]
)
request_duration = Histogram(
    "http_request_duration_seconds",
    "HTTP request latency in seconds by method and route",
    ["method", "route"],
    buckets=(0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5),
)
checks_total = Counter("primecheck_checks_total", "Primality checks by outcome", ["result"])
computation_duration = Histogram(
    "primecheck_computation_seconds",
    "Time spent deciding primality, excluding HTTP overhead",
    buckets=(0.0001, 0.0005, 0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25),
)
sieve_primes = Gauge("primecheck_sieve_primes", "Primes held in the warmed sieve")
app_ready = Gauge("primecheck_ready", "Readiness of the process, 1 ready and 0 warming")
feature_flag = Gauge("primecheck_feature_flag", "Feature flag state, 1 on and 0 off", ["flag"])
build_info = Gauge("build_info", "Build metadata", ["version", "git_sha"])

access_log = logging.getLogger("access")


def current_trace_id():
    try:
        from opentelemetry import trace
    except ImportError:
        return None
    ctx = trace.get_current_span().get_span_context()
    if ctx.is_valid:
        return format(ctx.trace_id, "032x")
    return None


class JsonFormatter(logging.Formatter):
    def format(self, record):
        payload = {
            "time": self.formatTime(record, "%Y-%m-%dT%H:%M:%S%z"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "service": settings.service_name,
            "version": APP_VERSION,
        }
        trace_id = current_trace_id()
        if trace_id:
            payload["trace_id"] = trace_id
        for key, value in record.__dict__.items():
            if key not in RESERVED:
                payload[key] = value
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str)


def configure_logging():
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(settings.log_level)
    for name in ("uvicorn", "uvicorn.error", "uvicorn.access"):
        logger = logging.getLogger(name)
        logger.handlers = [handler]
        logger.propagate = False
    build_info.labels(version=APP_VERSION, git_sha=GIT_SHA).set(1)


def route_of(request):
    route = request.scope.get("route")
    return getattr(route, "path_format", None) or getattr(route, "path", None) or "unmatched"


class ObservabilityMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        if request.url.path == "/metrics":
            return await call_next(request)
        request_id = request.headers.get("x-request-id") or uuid.uuid4().hex
        request.state.request_id = request_id
        started = time.perf_counter()
        status = 500
        try:
            response = await call_next(request)
            status = response.status_code
            response.headers["x-request-id"] = request_id
            return response
        finally:
            elapsed = time.perf_counter() - started
            route = route_of(request)
            requests_total.labels(request.method, route, str(status)).inc()
            request_duration.labels(request.method, route).observe(elapsed)
            access_log.info(
                "request completed",
                extra={
                    "request_id": request_id,
                    "method": request.method,
                    "route": route,
                    "path": request.url.path,
                    "status": status,
                    "duration_ms": round(elapsed * 1000, 3),
                },
            )


def metrics_response():
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)


def configure_tracing(app):
    if not settings.tracing_enabled or not settings.otlp_endpoint:
        return False
    from opentelemetry import trace
    from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
    from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
    from opentelemetry.sdk.resources import Resource
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor

    resource = Resource.create(
        {"service.name": settings.service_name, "service.version": APP_VERSION, "git.sha": GIT_SHA}
    )
    provider = TracerProvider(resource=resource)
    provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter()))
    trace.set_tracer_provider(provider)
    FastAPIInstrumentor.instrument_app(app, excluded_urls="healthz,readyz,metrics")
    return True
