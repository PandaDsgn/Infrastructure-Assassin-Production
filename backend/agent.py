import asyncio
import os
import re

import httpx
from dotenv import load_dotenv
from google import genai

load_dotenv()

MODEL_NAME = "gemini-2.5-flash"
DEV_SANDBOX_MODE = False

_client = genai.Client(api_key=os.environ["GEMINI_API_KEY"]) if os.environ.get("GEMINI_API_KEY") else None

_LINE_RE = re.compile(r"(\d+)\s*[:\-]\s*(QUARANTINE|TERMINATE|UPDATE|KEEP)")


def compute_guaranteed_answer(resource):
    if resource.get("is_malicious"):
        return "QUARANTINE"
    if (resource.get("days_since_last_login") or 0) >= 30:
        return "TERMINATE"
    if resource.get("needs_update"):
        return "UPDATE"
    return "KEEP"


async def _call_gemini(prompt):
    if not os.environ.get("GEMINI_API_KEY"):
        raise RuntimeError("No Gemini key found")
    result = await asyncio.to_thread(_client.models.generate_content, model=MODEL_NAME, contents=prompt)
    return result.text.upper()


async def _call_openai_compatible(url, model, prompt, key_env):
    api_key = os.environ.get(key_env)
    if not api_key:
        raise RuntimeError(f"No {key_env} found")
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(
            url,
            headers={"Content-Type": "application/json", "Authorization": f"Bearer {api_key}"},
            json={"model": model, "messages": [{"role": "user", "content": prompt}]},
        )
        if resp.is_error:
            raise RuntimeError(f"HTTP Error: {resp.status_code}")
        data = resp.json()
        return data["choices"][0]["message"]["content"].upper()


# Waterfall order: Gemini -> Groq -> DeepSeek -> guaranteed local fallback.
_TIERS = [
    ("GEMINI", _call_gemini),
    (
        "GROQ",
        lambda prompt: _call_openai_compatible(
            "https://api.groq.com/openai/v1/chat/completions", "llama-3.1-8b-instant", prompt, "GROQ_API_KEY"
        ),
    ),
    (
        "DEEPSEEK",
        lambda prompt: _call_openai_compatible(
            "https://api.deepseek.com/chat/completions", "deepseek-chat", prompt, "DEEPSEEK_API_KEY"
        ),
    ),
]


async def _run_waterfall(prompt, extract, fallback, label):
    for name, call in _TIERS:
        try:
            raw = await call(prompt)
            return extract(raw, fallback)
        except Exception as err:
            print(f"[{name} API ERROR] {label} failed: {err}. Routing to next tier...")
    print(f"[WATERFALL] {label} exhausted all tiers. Dropping to safe defaults.")
    return fallback


def _extract_single_action(raw, fallback):
    for action in ("QUARANTINE", "TERMINATE", "UPDATE"):
        if action in raw:
            return action
    return fallback


def _extract_batch_actions(raw, guaranteed_answers):
    final = list(guaranteed_answers)
    for match in _LINE_RE.finditer(raw):
        idx = int(match.group(1))
        if 0 <= idx < len(final):
            final[idx] = match.group(2)
    return final


async def evaluate_resource(resource):
    guaranteed = compute_guaranteed_answer(resource)
    if DEV_SANDBOX_MODE:
        return guaranteed

    is_idle = "YES" if (resource.get("days_since_last_login") or 0) >= 30 else "NO"
    is_malicious = "YES" if resource.get("is_malicious") else "NO"
    needs_update = "YES" if resource.get("needs_update") else "NO"

    prompt = f"""
    You are a strict enterprise IT security agent. You must respond with EXACTLY ONE WORD.
    Malicious Threat: {is_malicious}
    Idle Over 30 Days: {is_idle}
    Needs Critical Update: {needs_update}

    RULES:
    1. If Malicious Threat is YES -> output QUARANTINE
    2. If Idle Over 30 Days is YES -> output TERMINATE
    3. If Needs Critical Update is YES -> output UPDATE
    4. Otherwise -> output KEEP
    """

    return await _run_waterfall(prompt, _extract_single_action, guaranteed, "Single audit")


async def evaluate_resources_batch(resources):
    guaranteed_answers = [compute_guaranteed_answer(r) for r in resources]
    if DEV_SANDBOX_MODE or not resources:
        return guaranteed_answers

    lines = []
    for i, r in enumerate(resources):
        is_idle = "YES" if (r.get("days_since_last_login") or 0) >= 30 else "NO"
        is_malicious = "YES" if r.get("is_malicious") else "NO"
        needs_update = "YES" if r.get("needs_update") else "NO"
        lines.append(
            f'{i}. "{r.get("resource_name")}" -> Malicious: {is_malicious}, '
            f"Idle Over 30 Days: {is_idle}, Needs Critical Update: {needs_update}"
        )
    summary = "\n".join(lines)

    prompt = f"""
    You are a strict enterprise IT security agent reviewing a batch of resources.
    For EACH numbered resource below, output exactly one line in the format
    "INDEX: ACTION" (e.g. "0: TERMINATE") and nothing else - no extra text.

    RULES (apply independently per resource, in priority order):
    1. If Malicious is YES -> QUARANTINE
    2. Else if Idle Over 30 Days is YES -> TERMINATE
    3. Else if Needs Critical Update is YES -> UPDATE
    4. Otherwise -> KEEP

    Resources:
    {summary}
    """

    return await _run_waterfall(prompt, _extract_batch_actions, guaranteed_answers, "Batch audit")
