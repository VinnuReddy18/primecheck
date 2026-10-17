import time

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import HTMLResponse

from app.prime import PrimeTester

SIEVE_LIMIT = 1000000

tester = PrimeTester(SIEVE_LIMIT)
tester.warm_up()

app = FastAPI(title="primecheck", version="0.1.0")


@app.get("/healthz", include_in_schema=False)
def healthz():
    return {"status": "alive"}


@app.get("/check")
def check(n: int = Query(..., description="the number to test")):
    if n < 0:
        raise HTTPException(status_code=400, detail="n must not be negative")
    if n > tester.max_n:
        raise HTTPException(status_code=400, detail=f"n must be {tester.max_n} or less")

    started = time.perf_counter()
    factor = tester.smallest_factor(n)
    elapsed = time.perf_counter() - started

    return {
        "n": n,
        "prime": n >= 2 and factor is None,
        "elapsed_ms": round(elapsed * 1000, 3),
    }


@app.get("/", response_class=HTMLResponse, include_in_schema=False)
def index():
    return INDEX_HTML


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
    + ' <small>' + j.elapsed_ms + ' ms</small>';
};
</script>
"""
