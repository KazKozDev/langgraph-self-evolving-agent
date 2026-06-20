"""
Web Dashboard — FastAPI server for monitoring the self-evolving agent.

Endpoints:
  GET  /              — HTML dashboard
  GET  /api/skills    — list all skills
  GET  /api/metrics   — evolution metrics
  GET  /api/experiences — recent experiences
  POST /api/evolve    — trigger a manual evolution cycle
  GET  /api/health    — health check

Start: python dashboard.py  (default: http://localhost:8080)
"""
from __future__ import annotations

import json
import os
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

try:
    from fastapi import FastAPI, Request
    from fastapi.responses import HTMLResponse, JSONResponse
    import uvicorn
except ImportError:
    print("Install dependencies: pip install fastapi uvicorn")
    sys.exit(1)

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

app = FastAPI(title="Self-Evolving Agent Dashboard", version="0.2.0")

# ── Data helpers ───────────────────────────────────────────────

def _get_store():
    from src.memory.store import get_store
    return get_store()


def _get_graph():
    from src.graph import get_graph
    return get_graph()


# ── HTML Dashboard ─────────────────────────────────────────────

DASHBOARD_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Self-Evolving Agent</title>
<style>
  * { margin:0; padding:0; box-sizing:border-box; }
  body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
         background: #0d1117; color: #e6edf3; padding: 2rem; }
  h1 { font-size: 1.5rem; margin-bottom: 1.5rem; color: #58a6ff; }
  .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(320px, 1fr)); gap: 1rem; }
  .card { background: #161b22; border: 1px solid #30363d; border-radius: 8px; padding: 1.25rem; }
  .card h2 { font-size: 1rem; color: #8b949e; margin-bottom: .75rem; text-transform: uppercase; letter-spacing: .5px; }
  .metric { font-size: 2rem; font-weight: 700; color: #58a6ff; }
  .skill { padding: .5rem 0; border-bottom: 1px solid #21262d; }
  .skill:last-child { border-bottom: none; }
  .skill-name { font-weight: 600; }
  .skill-meta { font-size: .8rem; color: #8b949e; }
  .rate-good { color: #3fb950; }
  .rate-warn { color: #d29922; }
  .rate-bad { color: #f85149; }
  button { background: #238636; color: #fff; border: none; padding: .6rem 1.2rem;
           border-radius: 6px; cursor: pointer; font-size: .9rem; margin-top: 1rem; }
  button:hover { background: #2ea043; }
  button:disabled { opacity: 0.5; cursor: not-allowed; }
  .flash { padding: .5rem 1rem; border-radius: 6px; margin-bottom: 1rem; display: none; }
  .flash-ok { background: #033a16; color: #3fb950; }
  .flash-err { background: #3a0316; color: #f85149; }
</style>
</head>
<body>
  <h1>🧬 Self-Evolving Agent</h1>
  <div id="flash" class="flash"></div>
  <div class="grid">
    <div class="card">
      <h2>Skills</h2>
      <div id="skills-count" class="metric">…</div>
      <div id="skills-list"></div>
    </div>
    <div class="card">
      <h2>Metrics</h2>
      <div id="metrics"></div>
    </div>
    <div class="card">
      <h2>Recent Experiences</h2>
      <div id="experiences"></div>
    </div>
    <div class="card">
      <h2>Actions</h2>
      <button id="evolve-btn" onclick="triggerEvolve()">▶ Run Evolution Cycle</button>
      <p style="margin-top:.5rem;font-size:.8rem;color:#8b949e;" id="evolve-status"></p>
    </div>
  </div>

<script>
async function load() {
  try {
    const [sk, met, exp] = await Promise.all([
      fetch('/api/skills').then(r=>r.json()),
      fetch('/api/metrics').then(r=>r.json()),
      fetch('/api/experiences').then(r=>r.json()),
    ]);
    document.getElementById('skills-count').textContent = sk.length;
    document.getElementById('skills-list').innerHTML = sk.slice(0,10).map(s =>
      `<div class="skill">
        <div class="skill-name">${s.name}</div>
        <div class="skill-meta">
          rate: <span class="${s.success_rate>=0.8?'rate-good':s.success_rate>=0.5?'rate-warn':'rate-bad'}">${(s.success_rate*100).toFixed(0)}%</span>
          · used ${s.use_count||0}×
        </div>
      </div>`
    ).join('') || '<p style="color:#8b949e">No skills yet</p>';

    document.getElementById('metrics').innerHTML = `
      <div class="metric">${met.total_skills||0}</div> total skills<br>
      <div class="metric" style="font-size:1.2rem">${met.total_improvements||0}</div> improvements<br>
      <div style="margin-top:.5rem;font-size:.8rem;color:#8b949e">
        Last cycle: ${met.last_cycle||'never'}<br>
        Skills created: ${met.total_skills_created||0}
      </div>`;

    document.getElementById('experiences').innerHTML = (exp||[]).slice(0,8).map(e =>
      `<div class="skill">
        <div class="skill-name">${e.goal?.substring(0,60)||'…'}</div>
        <div class="skill-meta">${e.result} · ${e.domain} · ${e.tool_calls||0} tool calls</div>
      </div>`
    ).join('') || '<p style="color:#8b949e">No experiences</p>';
  } catch(e) { console.error(e); }
}

async function triggerEvolve() {
  const btn = document.getElementById('evolve-btn');
  const status = document.getElementById('evolve-status');
  btn.disabled = true; status.textContent = 'Running…';
  try {
    const r = await fetch('/api/evolve', {method:'POST'});
    const d = await r.json();
    showFlash(d.error ? 'err' : 'ok',
      d.error || `Cycle complete: ${d.skills_created||0} skills, ${d.policies_tested||0} variants`);
    load();
  } catch(e) { showFlash('err', 'Failed: '+e); }
  btn.disabled = false; status.textContent = '';
}

function showFlash(type, msg) {
  const f = document.getElementById('flash');
  f.className = 'flash flash-'+type; f.textContent = msg; f.style.display = 'block';
  setTimeout(()=>f.style.display='none', 5000);
}

load();
setInterval(load, 30000);
</script>
</body>
</html>"""


# ── API Endpoints ──────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
async def index():
    return DASHBOARD_HTML


@app.get("/api/health")
async def health():
    return {"status": "ok", "version": "0.2.0"}


@app.get("/api/skills")
async def list_skills():
    store = _get_store()
    skills = store.get_skills()
    # Sort by success_rate desc
    skills.sort(key=lambda s: s.get("success_rate", 0), reverse=True)
    return JSONResponse(skills)


@app.get("/api/metrics")
async def get_metrics():
    store = _get_store()
    return JSONResponse({
        "total_skills": len(store.get_skills()),
        "total_improvements": store.get_metric("total_improvements", 0),
        "total_skills_created": store.get_metric("total_skills_created", 0),
        "last_cycle": store.get_metric("last_cycle", 0),
    })


@app.get("/api/experiences")
async def list_experiences():
    store = _get_store()
    return JSONResponse(store.recent_experiences(20))


@app.post("/api/evolve")
async def trigger_evolution():
    """Run one evolution cycle manually."""
    try:
        graph = _get_graph()
        initial = {
            "messages": [],
            "experiences": [],
            "new_experiences_count": 0,
            "skills": [],
            "extracted_skills": [],
            "degraded_skills": [],
            "policy_variants": [],
            "variant_index": 0,
            "best_policy": None,
            "tournament_results": None,
            "cycle": 0,
            "phase": "collect",
            "human_approval_required": False,
            "human_decision": "",
            "total_skills_created": 0,
            "total_improvements": 0,
            "error": None,
        }
        config = {"configurable": {"thread_id": f"web-{int(time.time())}"}}
        final = graph.invoke(initial, config)

        return JSONResponse({
            "phase": final.get("phase"),
            "skills_created": len(final.get("extracted_skills", [])),
            "policies_tested": len(final.get("policy_variants", [])),
            "best_strategy": (final.get("best_policy") or {}).get("strategy_id"),
        })
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


def main():
    host = os.getenv("DASHBOARD_HOST", "0.0.0.0")
    port = int(os.getenv("DASHBOARD_PORT", "8080"))
    print(f"🧬 Self-Evolving Agent Dashboard")
    print(f"   http://{host}:{port}")
    uvicorn.run(app, host=host, port=port, log_level="info")


if __name__ == "__main__":
    main()
