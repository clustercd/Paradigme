"""Configured LLM providers, JSON parsing, and adaptive request budgets."""
from __future__ import annotations
import json, os, re, socket, time, logging
from typing import Any
import httpx

log = logging.getLogger("paradigme.llm")

# ============================================================================
# GROQ CLOUD CONFIG
# ============================================================================

GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"
GROQ_MODELS = [
    "llama-3.3-70b-versatile",
    "llama-3.1-8b-instant",
    "meta-llama/llama-4-scout-17b-16e-instruct",
]

# Adaptive engine budgets
ENGINE_PARAMS = {
    "groq": {
        "max_sources": 25,
        "synthesis_sources": 15,
        "default_max_tokens": 1500,
        "queries_tokens": 400,
        "synthesis_tokens": 1500,
        "sectors_tokens": 2500,
        "tree_tokens": 2000,
        "projections_tokens": 1000,
    },
    "local": {
        "max_sources": 8,
        "synthesis_sources": 5,
        "default_max_tokens": 800,
        "queries_tokens": 300,
        "synthesis_tokens": 800,
        "sectors_tokens": 800,
        "tree_tokens": 800,
        "projections_tokens": 500,
    },
}


def _has_internet(timeout=2.0) -> bool:
    """Check outbound connectivity with a short timeout."""
    try:
        socket.create_connection(("8.8.8.8", 53), timeout=timeout).close()
        return True
    except OSError:
        return False


class LLMClient:
    def __init__(self, cfg: dict):
        self.cfg = cfg
        self.base_url = cfg.get("base_url", "http://127.0.0.1:8090").rstrip("/")
        self.system_prompt = cfg.get("system_prompt", "")
        self.temperature = float(cfg.get("temperature", 0.6))
        self.max_tokens = int(cfg.get("max_tokens", 1200))
        self.timeout = float(cfg.get("timeout", 600))
        self.model_hint = cfg.get("model", "") or None

        # Groq config
        groq_cfg = cfg.get("groq", {})
        self.groq_api_key = groq_cfg.get("api_key", "") or os.environ.get("GROQ_API_KEY", "")
        self.groq_model = groq_cfg.get("model", GROQ_MODELS[0])
        # Respect the selected provider. An environment credential must not
        # silently enable Groq for a request intended for another provider.
        # Cloud use remains an explicit configuration choice.
        self.groq_enabled = (
            cfg.get("provider", "groq") == "groq"
            and groq_cfg.get("enabled", True)
            and bool(self.groq_api_key)
        )
        self.groq_timeout = float(groq_cfg.get("timeout", 120))

        # Etat
        self._active_engine = None  # 'groq' or 'local', selected on first use
        self._engine_name = None    # Display name

    @property
    def engine_params(self) -> dict:
        """Return budgets for the active inference engine."""
        return ENGINE_PARAMS.get(self._active_engine or "local", ENGINE_PARAMS["local"])

    async def _try_groq(self, messages, max_tokens=None):
        """Request Groq completion text or raise an exception."""
        effective_tokens = max_tokens or self.max_tokens
        headers = {
            "Authorization": f"Bearer {self.groq_api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self.groq_model,
            "messages": messages,
            "temperature": self.temperature,
            "max_tokens": effective_tokens,
            "stream": False,
        }
        # Log requete : model, tokens, taille prompt
        user_preview = next((m["content"][:80] for m in messages if m["role"] == "user"), "")
        t0 = time.time()
        log.info(f"GROQ -> {self.groq_model} | max_tokens={effective_tokens} | prompt: {user_preview!r}...")
        async with httpx.AsyncClient(timeout=self.groq_timeout) as client:
            r = await client.post(GROQ_API_URL, json=payload, headers=headers)
            elapsed = time.time() - t0
            if r.status_code == 429:
                log.warning(f"GROQ <- rate limit ({elapsed:.1f}s)")
                raise RuntimeError("Groq rate limit")
            if r.status_code >= 400:
                log.error(f"GROQ <- {r.status_code} ({elapsed:.1f}s)")
                r.raise_for_status()
            data = r.json()
            content = data["choices"][0]["message"]["content"]
            usage = data.get("usage", {})
            log.info(f"GROQ <- {len(content)} chars en {elapsed:.1f}s | tokens: prompt={usage.get('prompt_tokens','?')} completion={usage.get('completion_tokens','?')}")
            log.debug(f"GROQ response (start): {content[:200]}")
            return content

    async def _try_local(self, messages, max_tokens=None):
        """Request the explicitly configured provider or compatible server."""
        effective_tokens = max_tokens or self.max_tokens
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            # A shared bridge exposes status and chat endpoints.
            # Use the configured bridge URL directly rather than assuming
            # an OpenAI-compatible route. This preserves shared inference
            # without loading a separate model instance in this application.
            # The model server is managed independently.
            if self.cfg.get("provider") == "bridge":
                try:
                    r = await client.post(self.base_url + "/chat", json={
                        "messages": messages,
                        "temperature": self.temperature,
                        "max_tokens": effective_tokens,
                        "priority": 5,
                    })
                    if r.status_code < 400:
                        data = r.json()
                        content = data.get("response")
                        if isinstance(content, str) and content.strip():
                            return content
                    raise RuntimeError(
                        f"Bridge LLM HTTP {r.status_code}"
                    )
                except Exception as exc:
                    raise RuntimeError(f"Bridge LLM unreachable: {exc}") from exc

            if self.cfg.get("provider") == "anthropic":
                payload = {
                    "model": self.model_hint,
                    "messages": [m for m in messages if m["role"] != "system"],
                    "system": "\n".join(m["content"] for m in messages if m["role"] == "system"),
                    "temperature": self.temperature,
                    "max_tokens": effective_tokens,
                }
                r = await client.post(self.base_url + "/messages", json=payload, headers={
                    "x-api-key": self.cfg.get("api_key", ""),
                    "anthropic-version": "2023-06-01",
                })
                r.raise_for_status()
                return "\n".join(block["text"] for block in r.json().get("content", [])
                                 if block.get("type") == "text")

            # OpenAI-compat endpoints
            for ep in ("/v1/chat/completions", "/chat/completions"):
                try:
                    payload = {"messages": messages, "temperature": self.temperature,
                               "max_tokens": effective_tokens, "stream": False}
                    if self.model_hint:
                        payload["model"] = self.model_hint
                    hdr = {}
                    if self.cfg.get("api_key"):
                        hdr["Authorization"] = f"Bearer {self.cfg['api_key']}"
                    r = await client.post(self.base_url + ep, json=payload, headers=hdr)
                    if r.status_code == 404:
                        continue
                    if r.status_code >= 400:
                        continue
                    return r.json()["choices"][0]["message"]["content"]
                except Exception:
                    continue

            # Ollama chat
            try:
                r = await client.post(self.base_url + "/api/chat", json={
                    "model": self.model_hint or "llama3", "messages": messages,
                    "stream": False, "options": {"temperature": self.temperature, "num_predict": effective_tokens}
                })
                if r.status_code < 400 and "message" in r.json():
                    return r.json()["message"]["content"]
            except Exception:
                pass

            # Completion fallback
            sys_p = next((m["content"] for m in messages if m["role"] == "system"), "")
            user_p = next((m["content"] for m in messages if m["role"] == "user"), "")
            prompt = f"<|im_start|>system\n{sys_p}<|im_end|>\n<|im_start|>user\n{user_p}<|im_end|>\n<|im_start|>assistant\n"
            try:
                r = await client.post(self.base_url + "/completion", json={
                    "prompt": prompt, "temperature": self.temperature,
                    "n_predict": effective_tokens, "stream": False})
                if r.status_code < 400:
                    return r.json().get("content", "")
            except Exception:
                pass

        raise RuntimeError(f"Configured LLM unreachable at {self.base_url}")

    async def chat(self, user_prompt, *, json_mode=False, system=None, max_tokens=None):
        """Request a completion using the configured provider."""
        sys_p = system if system is not None else self.system_prompt
        sys_p += "\nWrite all natural-language output in English. Preserve the requested JSON keys and enum IDs."
        if json_mode:
            sys_p = (sys_p + "\nReponds STRICTEMENT en JSON valide, sans texte hors JSON, sans markdown.").strip()
        messages = [{"role": "system", "content": sys_p}, {"role": "user", "content": user_prompt}]

        # Try Groq only when enabled
        if self.groq_enabled and _has_internet():
            for model in dict.fromkeys([self.groq_model, *GROQ_MODELS]):
                try:
                    self.groq_model = model
                    result = await self._try_groq(messages, max_tokens)
                    self._active_engine = "groq"
                    self._engine_name = f"Groq ({model})"
                    return result
                except Exception:
                    continue

        # Fallback local
        try:
            result = await self._try_local(messages, max_tokens)
            self._active_engine = "local"
            self._engine_name = self.model_hint or "local"
            return result
        except Exception as e:
            raise RuntimeError(
                f"LLM unreachable. Groq: {'disabled' if not self.groq_enabled else 'failed'}. "
                f"Local ({self.base_url}): {e}")

    async def chat_json(self, user_prompt, *, system=None, retries=1, max_tokens=None):
        """Request JSON with bounded parsing retries."""
        last_raw = ""
        for attempt in range(retries + 1):
            raw = await self.chat(user_prompt, json_mode=True, system=system, max_tokens=max_tokens)
            last_raw = raw
            parsed = _extract_json(raw)
            if parsed is not None:
                return parsed
            if attempt < retries:
                user_prompt += "\n\nTa derniere reponse n'etait pas du JSON valide. Renvoie UNIQUEMENT le JSON."
        raise ValueError(f"Invalid LLM JSON after {retries + 1} attempts")

    async def health(self):
        """Check provider availability and select adaptive request budgets."""
        info = {"ok": False, "url": self.base_url, "model": None,
                "server_type": None, "groq_available": False}

        # Test Groq
        if self.groq_enabled:
            try:
                async with httpx.AsyncClient(timeout=5) as client:
                    r = await client.get("https://api.groq.com/openai/v1/models",
                                         headers={"Authorization": f"Bearer {self.groq_api_key}"})
                    if r.status_code < 400:
                        info["groq_available"] = True
                        models = [m["id"] for m in r.json().get("data", []) if isinstance(m, dict)]
                        info["groq_models"] = models[:5]
            except Exception:
                pass

        # Test local / Bridge
        async with httpx.AsyncClient(timeout=5) as client:
            if self.cfg.get("provider") == "bridge":
                try:
                    r = await client.get(self.base_url + "/status")
                    if r.status_code < 400:
                        data = r.json()
                        info["ok"] = bool(data.get("model_loaded"))
                        info["server_type"] = "bridge"
                        info["model"] = data.get("current_model") or self.model_hint
                except Exception as exc:
                    info["error"] = f"Bridge LLM unreachable: {exc}"
            headers = {}
            if self.cfg.get("api_key"):
                headers["Authorization"] = "Bearer " + self.cfg["api_key"]
            if self.cfg.get("provider") == "anthropic":
                headers = {"x-api-key": self.cfg.get("api_key", ""), "anthropic-version": "2023-06-01"}
                probes = [("/models", "anthropic")]
            elif self.cfg.get("provider") == "ollama":
                probes = [("/api/tags", "ollama")]
            elif self.cfg.get("provider") == "bridge":
                probes = []
            else:
                probes = [("/models", "openai_compatible"), ("/v1/models", "openai_compatible"),
                          ("/props", "llama_cpp"), ("/health", "generic")]
            for path, label in probes:
                if info["ok"]:
                    break
                try:
                    r = await client.get(self.base_url + path, headers=headers)
                    if r.status_code < 400:
                        info["ok"] = True
                        info["server_type"] = label
                        if label in ("openai_compatible", "anthropic", "ollama"):
                            data = r.json()
                            items = data.get("data") or data.get("models") or []
                            models = [m.get("id") or m.get("name") for m in items if isinstance(m, dict)]
                            info["model"] = models[0] if models else self.model_hint
                        elif label == "llama_cpp":
                            data = r.json()
                            info["model"] = (data.get("default_generation_settings", {}).get("model")
                                             or data.get("model_alias") or self.model_hint)
                        break
                except Exception:
                    continue

        # Select the active engine
        if info["groq_available"] and _has_internet():
            info["active_engine"] = "groq"
            info["model"] = self.groq_model
            info["ok"] = True
        elif info["ok"]:
            info["active_engine"] = "local"
        else:
            info["active_engine"] = "none"
            if not info.get("error"):
                info["error"] = f"No LLM available (Groq: {'no key' if not self.groq_api_key else 'failed'}, local: {self.base_url} unreachable)"

        self._active_engine = info["active_engine"]
        return info


# ============================================================================
# JSON EXTRACTION (including truncated responses)
# ============================================================================

def _extract_json(text):
    if not text:
        return None
    t = text.strip()
    if t.startswith("```"):
        t = re.sub(r"^```(?:json)?\s*", "", t)
        t = re.sub(r"\s*```\s*$", "", t)
    try:
        return json.loads(t)
    except Exception:
        pass
    start_brace = t.find("{")
    start_bracket = t.find("[")
    cs = [x for x in (start_brace, start_bracket) if x != -1]
    if not cs:
        return None
    start = min(cs)
    end = max(t.rfind("}"), t.rfind("]"))
    if end <= start:
        return _try_close_json(t[start:])
    candidate = t[start:end + 1]
    try:
        return json.loads(candidate)
    except Exception:
        cleaned = re.sub(r",(\s*[}\]])", r"\1", candidate)
        try:
            return json.loads(cleaned)
        except Exception:
            return _try_close_json(candidate)


def _try_close_json(text):
    if not text:
        return None
    t = text
    t = re.sub(r',\s*"[^"]*\Z', '', t)
    t = re.sub(r':\s*"[^"]*\Z', ': ""', t)
    t = re.sub(r',\s*\Z', '', t)
    stack = []
    in_str = False
    escape = False
    for ch in t:
        if escape:
            escape = False
            continue
        if ch == '\\':
            escape = True
            continue
        if ch == '"':
            in_str = not in_str
            continue
        if in_str:
            continue
        if ch in ('{', '['):
            stack.append('}' if ch == '{' else ']')
        elif ch in ('}', ']') and stack:
            stack.pop()
    t = t + ''.join(reversed(stack))
    t = re.sub(r',(\s*[}\]])', r'\1', t)
    try:
        return json.loads(t)
    except Exception:
        return None
