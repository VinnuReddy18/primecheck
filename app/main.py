import logging
import secrets as secretslib
import threading
import time
from contextlib import asynccontextmanager, nullcontext

from fastapi import FastAPI, Header, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel

from app import observability
from app.config import settings
from app.prime import PrimeTester
from app.version import APP_VERSION, BUILD_TIME, GIT_SHA

log = logging.getLogger("primecheck")
tester = PrimeTester(settings.sieve_limit)


def warm_up():
    started = time.perf_counter()
    count = tester.warm_up()
    observability.sieve_primes.set(count)
    observability.app_ready.set(1)
    log.info(
        "sieve warmed",
        extra={
            "primes": count,
            "sieve_limit": settings.sieve_limit,
            "max_n": tester.max_n,
            "duration_ms": round((time.perf_counter() - started) * 1000, 1),
        },
    )


def computation_span(n):
    if not settings.tracing_enabled:
        return nullcontext()
    try:
        from opentelemetry import trace
    except ImportError:
        return nullcontext()
    return trace.get_tracer("primecheck").start_as_current_span(
        "primality", attributes={"primecheck.n": n}
    )


@asynccontextmanager
async def lifespan(app):
    observability.configure_logging()
    observability.app_ready.set(0)
    observability.feature_flag.labels("factor_hint").set(1 if settings.feature_factor_hint else 0)
    threading.Thread(target=warm_up, name="warmup", daemon=True).start()
    log.info("startup", extra={"version": APP_VERSION, "git_sha": GIT_SHA, "tracing": TRACING_ACTIVE})
    yield


app = FastAPI(title="primecheck", version=APP_VERSION, lifespan=lifespan)
app.add_middleware(observability.ObservabilityMiddleware)
TRACING_ACTIVE = observability.configure_tracing(app)


@app.get("/healthz", include_in_schema=False)
def healthz():
    return {"status": "alive"}


@app.get("/readyz", include_in_schema=False)
def readyz():
    if not tester.ready:
        return JSONResponse({"status": "warming", "sieve": "building"}, status_code=503)
    return {"status": "ready", "sieve": "warm", "primes": len(tester.primes)}


@app.get("/version", include_in_schema=False)
def version():
    return {"version": APP_VERSION, "git_sha": GIT_SHA, "build_time": BUILD_TIME}


@app.get("/metrics", include_in_schema=False)
def metrics():
    return observability.metrics_response()


@app.get("/", response_class=HTMLResponse, include_in_schema=False)
def index():
    return INDEX_HTML


class FlagUpdate(BaseModel):
    factor_hint: bool


def require_admin(token):
    if not settings.admin_token:
        raise HTTPException(status_code=503, detail="no admin token is configured")
    if not token or not secretslib.compare_digest(token, settings.admin_token):
        raise HTTPException(status_code=401, detail="invalid admin token")


@app.get("/admin/flags")
def read_flags(x_admin_token: str = Header(default="")):
    require_admin(x_admin_token)
    return {"factor_hint": settings.feature_factor_hint}


@app.post("/admin/flags")
def write_flags(update: FlagUpdate, request: Request, x_admin_token: str = Header(default="")):
    require_admin(x_admin_token)
    previous = settings.feature_factor_hint
    settings.feature_factor_hint = update.factor_hint
    observability.feature_flag.labels("factor_hint").set(1 if update.factor_hint else 0)
    log.warning(
        "feature flag changed",
        extra={
            "flag": "factor_hint",
            "previous": previous,
            "current": update.factor_hint,
            "request_id": getattr(request.state, "request_id", None),
        },
    )
    return {"factor_hint": settings.feature_factor_hint, "previous": previous}


@app.get("/check")
def check(request: Request, n: int = Query(..., description="the number to test")):
    if not tester.ready:
        raise HTTPException(status_code=503, detail="service is still warming up")
    if n < 0:
        raise HTTPException(status_code=400, detail="n must not be negative")
    if n > tester.max_n:
        raise HTTPException(status_code=400, detail=f"n must be {tester.max_n} or less")

    started = time.perf_counter()
    with computation_span(n):
        factor = tester.smallest_factor(n)
    elapsed = time.perf_counter() - started

    prime = n >= 2 and factor is None
    observability.computation_duration.observe(elapsed)
    observability.checks_total.labels("prime" if prime else "composite").inc()

    body = {"n": n, "prime": prime, "elapsed_ms": round(elapsed * 1000, 3)}
    if settings.feature_factor_hint and not prime and factor is not None:
        body["smallest_factor"] = factor

    log.info(
        "check completed",
        extra={
            "n": n,
            "prime": prime,
            "compute_ms": round(elapsed * 1000, 3),
            "request_id": getattr(request.state, "request_id", None),
        },
    )
    return body


INDEX_HTML = """<!doctype html>
<title>primecheck</title>
<style>
body { font-family: system-ui, sans-serif; max-width: 34rem; margin: 4rem auto; padding: 0 1rem; }
input { padding: .6rem; font-size: 1rem; width: 100%; box-sizing: border-box; }
button { padding: .6rem 1.2rem; margin-top: .6rem; font-size: 1rem; }
#out { font-size: 1.2rem; margin-top: 1.5rem; min-height: 1.5rem; }
.prime { color: #1a7f37; }
.composite { color: #a40e26; }
small { color: #666; }
</style>
<h1>primecheck</h1>
<form id="f">
  <input id="n" inputmode="numeric" placeholder="enter a number" required autofocus>
  <button>check</button>
</form>
<p id="out"></p>
<script>
document.getElementById('f').onsubmit = async (e) => {
  e.preventDefault();
  const out = document.getElementById('out');
  out.textContent = 'checking';
  out.className = '';
  const r = await fetch('/check?n=' + encodeURIComponent(document.getElementById('n').value));
  const j = await r.json();
  if (!r.ok) { out.textContent = j.detail; return; }
  out.className = j.prime ? 'prime' : 'composite';
  out.innerHTML = j.n + (j.prime ? ' is prime' : ' is not prime')
    + (j.smallest_factor ? ' (divisible by ' + j.smallest_factor + ')' : '')
    + ' <small>' + j.elapsed_ms + ' ms</small>';
};
</script>
"""
