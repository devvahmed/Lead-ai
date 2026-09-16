"""Smoke test for the tri-tier LLM router."""
import os, time, sys

# Keys should be loaded from .env or environment variables
os.environ.setdefault("OLLAMA_URL", "http://localhost:11434")

sys.path.insert(0, os.path.dirname(__file__))
from llm_utils import (
    _probe_ollama, _call_groq, _call_gemini, call_llm, _next_lb_index
)

print("=" * 60)
print("--- Tier 1: Ollama probe (expect OFFLINE on office PC) ---")
online = _probe_ollama()
print(f"Ollama online: {online}")

print()
print("--- Tier 2A: Direct Groq call ---")
t0 = time.time()
prompt = "Return the single word: OK"
res = _call_groq(prompt, system_prompt=None, temperature=0.0, max_tokens=10, domain_tag="smoke-groq")
print(f"Groq -> {res!r}  ({time.time()-t0:.1f}s)")

print()
print("--- Tier 2B: Direct Gemini call ---")
t0 = time.time()
res = _call_gemini(prompt, system_prompt=None, temperature=0.0, max_tokens=10, domain_tag="smoke-gemini")
print(f"Gemini -> {res!r}  ({time.time()-t0:.1f}s)")

print()
print("--- 50/50 router: 4 requests (2 Groq-first, 2 Gemini-first) ---")
# Reset counter for predictable even/odd pattern
import llm_utils
llm_utils._lb_counter = 0
for i in range(4):
    idx = llm_utils._next_lb_index()
    label = "Even->Groq-first" if idx % 2 == 0 else "Odd->Gemini-first"
    t0 = time.time()
    result = call_llm("Say only OK.", max_tokens=5, domain_tag=f"lb-{i}")
    print(f"  Request {i} [{label}]: {result!r}  ({time.time()-t0:.1f}s)")

print()
print("SMOKE TEST COMPLETE")

