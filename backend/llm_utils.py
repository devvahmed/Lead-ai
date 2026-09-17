"""
llm_utils.py -- Tri-Tier LLM Router with 50/50 Groq/Gemini Load Balancer
=========================================================================
Architecture:

  TIER 1 - Local Ollama (primary, lowest latency)
              URL: OLLAMA_URL / OLLAMA_BASE_URL  (default: http://localhost:11434)
              Connect timeout: 1.5 s (strict)
              - If reachable -> 100% of requests go here.
              - If unreachable or times out -> cascade to Tier 2.

  TIER 2 - Cloud Load Balanced (Groq / Gemini, 50/50)
              Even request index  -> tries Groq first, falls back to Gemini
              Odd  request index  -> tries Gemini first, falls back to Groq
              - Prevents any single API key from hitting rate limits.
              - As soon as Ollama recovers, all traffic instantly returns to Tier 1.

Environment Variables (backend/.env  or system env):
  OLLAMA_URL          http://localhost:11434
  OLLAMA_BASE_URL     same as OLLAMA_URL (legacy alias)
  OLLAMA_MODEL        llama3.2

  GROQ_API_KEY        gsk_...
  GROQ_MODEL          llama-3.3-70b-versatile

  GEMINI_API_KEY      AIza...
  GEMINI_MODEL        gemini-1.5-flash
"""

from __future__ import annotations

import json
import logging
import os
import time
import threading
import urllib.request
import urllib.error
from typing import Optional

logger = logging.getLogger("llm_utils")

# --- Environment helpers ------------------------------------------------------

def _ollama_base() -> str:
    # Prefer OLLAMA_BASE_URL if set to a non-localhost remote IP; otherwise OLLAMA_URL
    base_url = (os.getenv("OLLAMA_BASE_URL") or "").strip()
    url = (os.getenv("OLLAMA_URL") or "").strip()
    if base_url and not any(h in base_url for h in ("localhost", "127.0.0.1")):
        raw = base_url
    else:
        raw = url or base_url or "http://localhost:11434"
    base = raw.strip().rstrip("/")
    if base.endswith("/v1"):
        base = base[:-3]
    return base


def _ollama_model() -> str:
    return os.getenv("OLLAMA_MODEL", "llama3.2")


def _groq_key() -> str:
    return os.getenv("GROQ_API_KEY", "")


def _groq_model() -> str:
    return os.getenv("GROQ_MODEL", "groq/compound-mini")


def _gemini_key() -> str:
    return os.getenv("GEMINI_API_KEY", "")


def _gemini_model() -> str:
    return os.getenv("GEMINI_MODEL", "gemini-3.6-flash")


try:
    from dotenv import load_dotenv
    _env_file = os.path.join(os.path.dirname(__file__), ".env")
    if os.path.exists(_env_file):
        load_dotenv(_env_file, override=False)
    else:
        load_dotenv()
except Exception:
    pass

# --- Ollama probe cache -------------------------------------------------------

_ollama_lock = threading.Lock()
_ollama_last_check: float = 0.0
_ollama_available: bool = False
_ollama_active_model: str = ""
_ollama_installed_models: list = []
_OLLAMA_RECHECK_INTERVAL: float = 30.0   # seconds
_OLLAMA_CONNECT_TIMEOUT: float = 3.0     # connect probe timeout


# --- Load-balancer counter ----------------------------------------------------

_lb_lock = threading.Lock()
_lb_counter: int = 0


def _next_lb_index() -> int:
    global _lb_counter
    with _lb_lock:
        idx = _lb_counter
        _lb_counter += 1
    return idx


# --- Tier 1: Ollama probe -----------------------------------------------------

def _probe_ollama() -> bool:
    global _ollama_last_check, _ollama_available, _ollama_active_model, _ollama_installed_models
    now = time.monotonic()
    with _ollama_lock:
        if now - _ollama_last_check < _OLLAMA_RECHECK_INTERVAL:
            return _ollama_available
        base = _ollama_base()
        probe_url = f"{base}/api/tags"
        try:
            req = urllib.request.Request(
                probe_url,
                headers={"User-Agent": "ClientPlus-LLMRouter/1.0"},
                method="GET"
            )
            with urllib.request.urlopen(req, timeout=_OLLAMA_CONNECT_TIMEOUT) as r:
                ok = r.status == 200
                if ok:
                    try:
                        data = json.loads(r.read().decode("utf-8"))
                        raw_models = [m.get("name", "") for m in data.get("models", []) if m.get("name")]
                        _ollama_installed_models = raw_models
                        requested = _ollama_model().lower().strip()
                        best_match = None
                        for rm in raw_models:
                            rm_clean = rm.lower()
                            if rm_clean == requested or rm_clean.startswith(f"{requested}:"):
                                best_match = rm
                                break
                        if not best_match and raw_models:
                            llama_cands = [m for m in raw_models if "llama" in m.lower()]
                            best_match = llama_cands[0] if llama_cands else raw_models[0]
                            print(f"[Ollama Probe] ⚠️ Model '{requested}' not found. Automatically using installed model: '{best_match}'. Installed models: {raw_models}", flush=True)
                        _ollama_active_model = best_match or requested
                    except Exception:
                        pass
        except Exception:
            ok = False
        _ollama_available = ok
        _ollama_last_check = now
        status = "ONLINE" if ok else "OFFLINE"
        logger.debug(f"[LLM Router] Ollama probe -> {status} ({base})")
        return ok


# --- Tier 1: Ollama call ------------------------------------------------------

def _call_ollama(
    prompt: str,
    system_prompt: Optional[str],
    temperature: float,
    max_tokens: int,
    timeout: float,
    domain_tag: str,
) -> Optional[str]:
    global _ollama_last_check
    base = _ollama_base()
    endpoint = f"{base}/api/generate"
    model = _ollama_active_model or _ollama_model()
    tag = f"[{domain_tag}] " if domain_tag else ""

    payload: dict = {
        "model": model,
        "prompt": prompt,
        "stream": False,
    }
    if system_prompt:
        payload["system"] = system_prompt
    if temperature is not None or max_tokens is not None:
        payload["options"] = {}
        if temperature is not None:
            payload["options"]["temperature"] = temperature
        if max_tokens is not None:
            payload["options"]["num_predict"] = max_tokens

    t0 = time.time()
    try:
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            endpoint, data=data,
            headers={"Content-Type": "application/json", "User-Agent": "ClientPlus-AI/1.0"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=timeout) as r:
            body = json.loads(r.read().decode("utf-8"))
            content = body.get("response", "")
            if not content and "choices" in body:
                content = body["choices"][0]["message"]["content"]
            content = content.strip()
            elapsed = time.time() - t0
            print(f"[Ollama] {tag}<- OK ({len(content)} chars, {elapsed:.1f}s)", flush=True)
            return content
    except urllib.error.HTTPError as e:
        err_body = ""
        try:
            err_body = e.read().decode("utf-8")[:250]
        except Exception:
            pass
        elapsed = time.time() - t0
        print(f"[Ollama] {tag}FAILED (HTTP {e.code}: {e.reason}, {elapsed:.1f}s) | Details: {err_body}", flush=True)
        with _ollama_lock:
            _ollama_last_check = 0.0
        return None
    except Exception as e:
        elapsed = time.time() - t0
        print(f"[Ollama] {tag}FAILED ({type(e).__name__}: {e}, {elapsed:.1f}s)", flush=True)
        # Invalidate probe cache so next call re-probes immediately
        with _ollama_lock:
            _ollama_last_check = 0.0
        return None


# --- Tier 2A: Groq call -------------------------------------------------------

def _call_groq(
    prompt: str,
    system_prompt: Optional[str],
    temperature: float,
    max_tokens: int,
    domain_tag: str,
) -> Optional[str]:
    api_key = _groq_key()
    if not api_key:
        return None

    model = _groq_model()
    endpoint = "https://api.groq.com/openai/v1/chat/completions"
    tag = f"[{domain_tag}] " if domain_tag else ""

    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": prompt})

    payload = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    t0 = time.time()
    try:
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            endpoint, data=data,
            headers={
                "Content-Type": "application/json",
                "Accept": "application/json",
                "Authorization": f"Bearer {api_key}",
                "User-Agent": "Mozilla/5.0 (compatible; ClientPlus-AI/1.0)",
            },
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=20.0) as r:
            body = json.loads(r.read().decode("utf-8"))
            content = body["choices"][0]["message"]["content"].strip()
            elapsed = time.time() - t0
            print(f"[Groq] {tag}<- OK ({len(content)} chars, {elapsed:.1f}s)", flush=True)
            return content if content else None
    except urllib.error.HTTPError as e:
        err_body = ""
        try:
            err_body = e.read().decode("utf-8")[:200]
        except Exception:
            pass
        elapsed = time.time() - t0
        print(f"[Groq] {tag}HTTP {e.code} ({elapsed:.1f}s): {err_body}", flush=True)
        return None
    except Exception as e:
        elapsed = time.time() - t0
        print(f"[Groq] {tag}FAILED ({type(e).__name__}: {e}, {elapsed:.1f}s)", flush=True)
        return None


# --- Tier 2B: Gemini call -----------------------------------------------------

def _call_gemini(
    prompt: str,
    system_prompt: Optional[str],
    temperature: float,
    max_tokens: int,
    domain_tag: str,
) -> Optional[str]:
    api_key = _gemini_key()
    if not api_key:
        return None

    model = _gemini_model()
    endpoint = (
        f"https://generativelanguage.googleapis.com/v1beta/models/"
        f"{model}:generateContent?key={api_key}"
    )
    tag = f"[{domain_tag}] " if domain_tag else ""

    # Gemini supports systemInstruction separately since API v1beta
    payload: dict = {
        "contents": [{"role": "user", "parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": temperature,
            "maxOutputTokens": max_tokens,
        },
    }
    if system_prompt:
        payload["systemInstruction"] = {"parts": [{"text": system_prompt}]}
    t0 = time.time()
    try:
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            endpoint, data=data,
            headers={"Content-Type": "application/json", "User-Agent": "ClientPlus-AI/1.0"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=25.0) as r:
            body = json.loads(r.read().decode("utf-8"))
            candidate = body.get("candidates", [{}])[0]
            cand_content = candidate.get("content", {})
            parts = cand_content.get("parts", [])
            # Some Gemini thinking models include parts with only thoughtSignature (no text)
            text_parts = [p["text"] for p in parts if "text" in p]
            content = " ".join(text_parts).strip()
            elapsed = time.time() - t0
            if content:
                print(f"[Gemini] {tag}<- OK ({len(content)} chars, {elapsed:.1f}s)", flush=True)
                return content
            finish = candidate.get("finishReason", "UNKNOWN")
            print(f"[Gemini] {tag}Empty response (finishReason={finish}, {elapsed:.1f}s)", flush=True)
            return None
    except urllib.error.HTTPError as e:
        err_body = ""
        try:
            err_body = e.read().decode("utf-8")[:200]
        except Exception:
            pass
        elapsed = time.time() - t0
        print(f"[Gemini] {tag}HTTP {e.code} ({elapsed:.1f}s): {err_body}", flush=True)
        return None
    except Exception as e:
        elapsed = time.time() - t0
        print(f"[Gemini] {tag}FAILED ({type(e).__name__}: {e}, {elapsed:.1f}s)", flush=True)
        return None


# --- Public entry point -------------------------------------------------------

def call_llm(
    prompt: str,
    system_prompt: Optional[str] = None,
    temperature: float = 0.2,
    max_tokens: int = 1000,
    timeout: float = 15.0,
    domain_tag: str = "",
) -> Optional[str]:
    """
    3-Tier LLM Router.

    1. Probe Ollama (cached 30 s, 1.5 s connect timeout).
       ONLINE  -> call Ollama.  Return if successful.
       OFFLINE -> fall to Tier 2.
    2. 50/50 load-balance Groq / Gemini:
       Even request -> Groq first, Gemini fallback.
       Odd  request -> Gemini first, Groq fallback.
    3. Return None if all providers fail.
    """
    tag = f"[{domain_tag}] " if domain_tag else ""

    # Tier 1: Ollama
    if _probe_ollama():
        result = _call_ollama(prompt, system_prompt, temperature, max_tokens, timeout, domain_tag)
        if result:
            return result
        print(f"[LLM Router] {tag}Ollama failed despite probe -- falling back to cloud.", flush=True)
    else:
        print(f"[LLM Router] {tag}Ollama OFFLINE -- routing 50/50 Groq/Gemini.", flush=True)

    # Tier 2: Cloud 50/50
    lb_idx = _next_lb_index()
    if lb_idx % 2 == 0:
        result = _call_groq(prompt, system_prompt, temperature, max_tokens, domain_tag)
        if result:
            return result
        print(f"[LLM Router] {tag}Groq failed -- falling back to Gemini.", flush=True)
        return _call_gemini(prompt, system_prompt, temperature, max_tokens, domain_tag)
    else:
        result = _call_gemini(prompt, system_prompt, temperature, max_tokens, domain_tag)
        if result:
            return result
        print(f"[LLM Router] {tag}Gemini failed -- falling back to Groq.", flush=True)
        return _call_groq(prompt, system_prompt, temperature, max_tokens, domain_tag)
