"""Paradigme FastAPI routes, configuration, background jobs, and persistence."""
from __future__ import annotations
import asyncio
import json, os, re, uuid, logging
from datetime import datetime
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from llm_client import LLMClient
from analysis import run_analysis, CTX_LABELS, ANALYSIS_MODELS

ROOT = Path(__file__).parent.resolve()
CONFIG_PATH = Path(os.environ.get("PARADIGME_CONFIG", str(ROOT / "config.json")))
DATA_DIR = Path(os.environ.get("PARADIGME_DATA_DIR", str(ROOT / "data")))
REPORTS_DIR = DATA_DIR / "reports"
RESULTS_DIR = DATA_DIR / "results"
HISTORY_PATH = DATA_DIR / "history.json"
LOGS_DIR = Path(os.environ.get("PARADIGME_LOGS_DIR", str(ROOT / "logs")))
REPORTS_DIR.mkdir(parents=True, exist_ok=True)
RESULTS_DIR.mkdir(parents=True, exist_ok=True)
LOGS_DIR.mkdir(parents=True, exist_ok=True)

# Configure unified application logging
LOG_FILE = LOGS_DIR / "paradigme.log"
_root = logging.getLogger()
for _h in list(_root.handlers):
    _root.removeHandler(_h)
_file_handler = logging.FileHandler(str(LOG_FILE), encoding="utf-8", mode="a")
_file_handler.setFormatter(logging.Formatter(
    "%(asctime)s [%(levelname)s] %(name)s | %(message)s",
    datefmt="%H:%M:%S"))
_console_handler = logging.StreamHandler()
_console_handler.setFormatter(logging.Formatter(
    "%(asctime)s [%(levelname)s] %(name)s | %(message)s",
    datefmt="%H:%M:%S"))
_root.addHandler(_file_handler)
_root.addHandler(_console_handler)
_root.setLevel(logging.INFO)

# Reduce external-library log noise
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)
logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
logging.getLogger("uvicorn.error").setLevel(logging.INFO)
logging.getLogger("watchfiles").setLevel(logging.WARNING)
log = logging.getLogger("paradigme")
log.info("=" * 60)
log.info("Paradigme started")
log.info(f"Log file: {LOG_FILE}")
log.info("=" * 60)
_file_handler.flush()

# ANALYSIS_MODELS is imported from analysis.py (single source of truth)


# ============================================================================
# CONFIG / HISTORY
# ============================================================================

def load_config():
    if not CONFIG_PATH.exists():
        CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
        CONFIG_PATH.write_text((ROOT / "config.example.json").read_text(encoding="utf-8"), encoding="utf-8")
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return json.load(f)

def save_config(cfg):
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)

def load_history():
    try:
        return json.loads(HISTORY_PATH.read_text(encoding="utf-8")) if HISTORY_PATH.exists() else []
    except Exception:
        return []

def append_history(entry):
    h = load_history()
    h.insert(0, entry)
    HISTORY_PATH.write_text(json.dumps(h[:200], ensure_ascii=False, indent=2), encoding="utf-8")


def save_completed_job(job_id, job):
    """Persist the full result so history survives application restarts."""
    safe = re.sub(r'[^a-zA-Z0-9_-]', '', job_id)
    target = RESULTS_DIR / f"{safe}.json"
    temp = target.with_suffix(".json.tmp")
    temp.write_text(json.dumps(job, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    temp.replace(target)


def save_failed_job(job_id, job):
    """Persist a minimal failure record without request or provider payloads."""
    safe = re.sub(r'[^a-zA-Z0-9_-]', '', job_id)
    step = str(job.get("step") or "")
    if step.startswith("research"):
        safe_step = "research"
    elif step.startswith("sector analysis"):
        safe_step = "sector analysis"
    elif step.startswith("tree"):
        safe_step = "tree"
    elif step.startswith("projections"):
        safe_step = "projections"
    elif step.startswith("disruptions/recommendations"):
        safe_step = "recommendations"
    elif step in {"init", "queries", "synthesis", "PDF", "email"}:
        safe_step = step
    else:
        safe_step = "analysis"
    failed = {
        "id": safe,
        "status": "error",
        "step": safe_step,
        "error": job.get("error") or "Analysis failed. Check the configured services and application logs.",
        "started_at": job.get("started_at"),
        "finished_at": datetime.now().isoformat(),
        "progress": job.get("progress", 0),
        "result": None,
        "pdf_path": None,
        "email": None,
    }
    target = RESULTS_DIR / f"{safe}.json"
    temp = target.with_suffix(".json.tmp")
    temp.write_text(json.dumps(failed, ensure_ascii=False, indent=2), encoding="utf-8")
    temp.replace(target)


def load_completed_job(job_id):
    safe = re.sub(r'[^a-zA-Z0-9_-]', '', job_id)
    path = RESULTS_DIR / f"{safe}.json"
    if path.exists():
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(value, dict):
                return value
        except Exception:
            pass
    # Legacy reports without full JSON results remain accessible
    # through history and their PDF/text files.
    for item in load_history():
        if isinstance(item, dict) and item.get("id") == safe:
            return {
                **item,
                "status": "done",
                "result": None,
                "pdf_path": str(REPORTS_DIR / f"{safe}.pdf") if (REPORTS_DIR / f"{safe}.pdf").exists() else None,
                "txt_path": str(REPORTS_DIR / f"{safe}.txt") if (REPORTS_DIR / f"{safe}.txt").exists() else None,
            }
    return None

def _log(jid, msg):
    log.info(f"[{jid[:8]}] {msg}")


# ============================================================================
# APP
# ============================================================================

app = FastAPI(title="Paradigme", version="3.0.0")
JOBS = {}
ACTIVE_ANALYSES = set()


@app.get("/", response_class=HTMLResponse)
async def index():
    return HTMLResponse((ROOT / "static" / "index.html").read_text(encoding="utf-8"))

app.mount("/static", StaticFiles(directory=str(ROOT / "static")), name="static")


class AnalyzeRequest(BaseModel):
    subject: str = Field(..., min_length=1)
    context: str = ""
    send_email: bool = False
    generate_pdf: bool = True
    sources: dict = Field(default_factory=lambda: {
        "web": True, "wikipedia": True, "actualite": True, "youtube": True, "archive": True})
    deep_fetch: bool = True
    anticipation_contexts: list = Field(
        default_factory=lambda: ["social", "economique", "technologique", "mondial"])
    analysis_model: str = Field(default="classique")


# ── Health / Config / Models ──

@app.get("/api/health")
async def health():
    return {"app": "ok", "llm": await LLMClient(load_config()["llm"]).health()}

@app.get("/api/debug-llm")
async def debug_llm():
    """Return configuration flags only; never reveal a key or provider response."""
    cfg = load_config()["llm"]
    return {
        "config_provider": cfg.get("provider", ""),
        "groq_enabled": cfg.get("groq", {}).get("enabled", False),
        "groq_key_present": bool(cfg.get("groq", {}).get("api_key") or os.environ.get("GROQ_API_KEY")),
        "api_key_present": bool(cfg.get("api_key")),
    }

@app.get("/api/config")
async def get_config():
    c = json.loads(json.dumps(load_config()))
    if c.get("email", {}).get("smtp_password"):
        c["email"]["smtp_password"] = "***"
    if c.get("llm", {}).get("groq", {}).get("api_key"):
        c["llm"]["groq"]["api_key"] = "***"
    if c.get("llm", {}).get("api_key"):
        c["llm"]["api_key"] = "***"
    return c

@app.get("/api/models")
async def get_models():
    return ANALYSIS_MODELS

@app.post("/api/config")
async def update_config(payload: dict):
    cfg = load_config()
    def merge(a, b):
        for k, v in b.items():
            if isinstance(v, dict) and isinstance(a.get(k), dict):
                merge(a[k], v)
            elif k == "smtp_password" and v == "***":
                continue
            elif k == "api_key" and v == "***":
                continue
            else:
                a[k] = v
    merge(cfg, payload)
    save_config(cfg)
    return {"ok": True}


# ── First-run setup wizard ──

SETUP_PROVIDERS = {
    "groq": {"url": "https://api.groq.com/openai/v1", "model": "llama-3.3-70b-versatile"},
    "openai": {"url": "https://api.openai.com/v1", "model": "gpt-4o-mini"},
    "anthropic": {"url": "https://api.anthropic.com/v1", "model": "claude-sonnet-4-5"},
    "ollama": {"url": "http://127.0.0.1:11434", "model": "llama3"},
    "llamacpp": {"url": "http://127.0.0.1:8090", "model": "qwen2.5-3b-instruct"},
}

async def _probe_llm(provider: str, api_key: str, base_url: str) -> dict:
    """Probe the configured provider and return status plus a safe message."""
    import httpx as _hx
    base = (base_url or SETUP_PROVIDERS.get(provider, {}).get("url", "")).rstrip("/")
    if not base:
        return {"ok": False, "message": "Server URL missing"}
    hdr = {}
    if provider in ("groq", "openai", "anthropic", "custom") and api_key:
        hdr["Authorization"] = f"Bearer {api_key}"
    if provider == "anthropic":
        hdr.update({"x-api-key": api_key, "anthropic-version": "2023-06-01"})
    if provider in ("groq", "openai", "anthropic") and not api_key:
        return {"ok": False, "message": "API key missing"}
    paths = ["/api/tags"] if provider == "ollama" else ["/models", "/v1/models", "/health"]
    last = ""
    async with _hx.AsyncClient(timeout=8) as client:
        for pth in paths:
            try:
                r = await client.get(base + pth, headers=hdr)
            except Exception as e:
                last = f"Server unreachable ({type(e).__name__})"
                continue
            if r.status_code in (401, 403):
                return {"ok": False, "message": "API key rejected (401/403)"}
            if r.status_code < 400:
                return {"ok": True, "message": "Connection OK"}
            last = f"HTTP {r.status_code}"
    return {"ok": False, "message": last or "Failed"}

@app.get("/api/setup/status")
async def setup_status():
    cfg = load_config()
    llm = cfg.get("llm", {})
    has_key = bool(llm.get("groq", {}).get("api_key") or llm.get("api_key")
                   or os.environ.get("GROQ_API_KEY"))
    needs = not cfg.get("setup_done") and not has_key
    if needs and llm.get("provider") in ("llamacpp", "ollama", "custom", "bridge"):
        try:
            h = await asyncio.wait_for(LLMClient(llm).health(), timeout=6)
            needs = not (h or {}).get("ok", False) and not (h or {}).get("local_ok", False)
        except Exception:
            pass
    return {"needs_setup": needs, "provider": llm.get("provider", ""),
            "has_key": has_key, "email_enabled": cfg.get("email", {}).get("enabled", False)}

@app.post("/api/setup/test")
async def setup_test(p: dict):
    return await _probe_llm(p.get("provider", "groq"), (p.get("api_key") or "").strip(),
                            (p.get("base_url") or "").strip())

@app.post("/api/setup/save")
async def setup_save(p: dict):
    cfg = load_config()
    llm = cfg.setdefault("llm", {})
    prov = p.get("provider", "groq")
    d = SETUP_PROVIDERS.get(prov, {})
    key = (p.get("api_key") or "").strip()
    llm["provider"] = prov
    llm["base_url"] = (p.get("base_url") or d.get("url", "")).strip()
    llm["model"] = (p.get("model") or d.get("model", "")).strip()
    g = llm.setdefault("groq", {})
    g["enabled"] = prov == "groq"
    if prov == "groq":
        if key:
            g["api_key"] = key
        g["model"] = llm["model"]
    elif key:
        llm["api_key"] = key
    em = p.get("email") or {}
    if em.get("enabled"):
        e = cfg.setdefault("email", {})
        user = (em.get("smtp_user") or "").strip()
        e.update({"enabled": True, "smtp_host": em.get("smtp_host") or "smtp.gmail.com",
                  "smtp_port": int(em.get("smtp_port") or 465), "smtp_user": user,
                  "from_addr": user, "to_addr": (em.get("to_addr") or user).strip(),
                  "use_tls": False})
        if em.get("smtp_password"):
            e["smtp_password"] = em["smtp_password"]
    cfg["setup_done"] = True
    save_config(cfg)
    return {"ok": True}


# ── History / Reports / Jobs ──

@app.get("/api/history")
async def history():
    return load_history()

@app.get("/api/report/{job_id}")
async def get_report(job_id: str):
    p = REPORTS_DIR / f"{re.sub(r'[^a-zA-Z0-9_-]', '', job_id)}.pdf"
    if not p.exists():
        raise HTTPException(404)
    return FileResponse(str(p), media_type="application/pdf", filename=p.name)

@app.get("/api/report/{job_id}/txt")
async def get_report_txt(job_id: str):
    safe = re.sub(r'[^a-zA-Z0-9_-]', '', job_id)
    p = REPORTS_DIR / f"{safe}.txt"
    if not p.exists():
        # Generate text from an available saved or in-memory result
        j = JOBS.get(job_id) or load_completed_job(job_id)
        if j and j.get("result"):
            try:
                from txt_report import generate_txt
                generate_txt(j["result"], str(p))
            except Exception:
                pass
        if not p.exists():
            raise HTTPException(404)
    return FileResponse(str(p), media_type="text/plain; charset=utf-8", filename=p.name)

@app.get("/api/job/{job_id}")
async def get_job(job_id: str):
    j = JOBS.get(job_id) or load_completed_job(job_id)
    if not j:
        raise HTTPException(404)
    if j["status"] == "running":
        try:
            j["elapsed_total_s"] = int((datetime.now() - datetime.fromisoformat(j["started_at"])).total_seconds())
        except Exception:
            pass
    return j


@app.get("/api/logs")
async def get_logs():
    log_file = LOGS_DIR / "paradigme.log"
    if not log_file.exists():
        # Fallback ancien fichier
        log_file = LOGS_DIR / "errors.log"
    if not log_file.exists():
        return {"lines": [], "size": 0}
    text = log_file.read_text(encoding="utf-8", errors="replace")
    lines = text.strip().split("\n") if text.strip() else []
    return {"lines": lines[-500:], "size": len(lines)}

@app.post("/api/logs/clear")
async def clear_logs():
    for name in ("paradigme.log", "errors.log"):
        log_file = LOGS_DIR / name
        if log_file.exists():
            log_file.write_text("", encoding="utf-8")
    return {"ok": True}


# -- Analyze --

@app.post("/api/analyze")
async def analyze(req: AnalyzeRequest):
    jid = uuid.uuid4().hex[:12]
    JOBS[jid] = {
        "id": jid, "status": "queued", "step": "init", "step_detail": "",
        "progress": 0, "subject": req.subject, "context": req.context,
        "started_at": datetime.now().isoformat(),
        "step_started_at": datetime.now().isoformat(),
        "elapsed_step_s": 0, "elapsed_total_s": 0,
        "result": None, "error": None, "pdf_path": None, "email": None,
        "model_used": None, "sources_count": 0,
        "analysis_model": req.analysis_model
    }

    async def _run():
        cfg = load_config()
        llm = LLMClient(cfg["llm"])
        cfg["_reports_dir"] = str(REPORTS_DIR)
        result = await run_analysis(jid, req, JOBS, llm, cfg, _log)
        if result:
            save_completed_job(jid, JOBS[jid])
            append_history({
                "id": jid, "subject": req.subject, "context": req.context,
                "generated_at": result.get("generated_at", ""),
                "has_pdf": bool(JOBS[jid].get("pdf_path")),
                "email_sent": bool(JOBS[jid].get("email", {}).get("sent")) if JOBS[jid].get("email") else False,
                "model": JOBS[jid].get("model_used", {}).get("name"),
                "sources_count": JOBS[jid].get("sources_count", 0),
                "analysis_model": req.analysis_model,
                "quality": JOBS[jid].get("quality"),
                "status": "done",
            })
        elif JOBS[jid].get("status") == "error":
            save_failed_job(jid, JOBS[jid])

    # Retain an asyncio task so the HTTP response returns immediately.
    # A response-attached background task can delay clients until completion;
    # the retained task lets them receive the job ID and poll progress.
    # Keep a reference until the completion callback runs.
    task = asyncio.create_task(_run(), name=f"paradigme-analysis-{jid}")
    ACTIVE_ANALYSES.add(task)

    def _analysis_done(done_task):
        ACTIVE_ANALYSES.discard(done_task)
        if done_task.cancelled():
            JOBS[jid]["status"] = "error"
            JOBS[jid]["result"] = None
            JOBS[jid]["error"] = "Analysis interrupted by service shutdown."
            save_failed_job(jid, JOBS[jid])
            return
        error = done_task.exception()
        if error is not None:
            JOBS[jid]["status"] = "error"
            JOBS[jid]["result"] = None
            JOBS[jid].pop("quality", None)
            error_type = type(error).__name__
            if not error_type.isidentifier():
                error_type = "Exception"
            JOBS[jid]["error"] = (
                f"Analysis stopped unexpectedly ({error_type}). "
                "Check the configured services and application logs."
            )
            log.error("[%s] asynchronous analysis failed (%s)", jid[:8], error_type)
            save_failed_job(jid, JOBS[jid])

    task.add_done_callback(_analysis_done)
    return {"job_id": jid}


# ── Tests ──

@app.post("/api/test-email")
async def test_email():
    from mailer import send_report
    return send_report(load_config()["email"], "[Paradigme] Test", "Test.", [])

@app.post("/api/test-research")
async def test_research(p: dict):
    import research as R
    o = await R.gather_sources([p.get("query", "test")], deep=False)
    return {"total": len(o["sources"]), "by_source": o["counts_by_source"],
            "samples": o["sources"][:5]}


if __name__ == "__main__":
    import uvicorn
    c = load_config()
    s = c.get("server", {})
    uvicorn.run(app, host=s.get("host", "127.0.0.1"),
                port=int(s.get("port", 8765)), reload=False, log_level="info")
