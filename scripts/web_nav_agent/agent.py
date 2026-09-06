"""The GOAL -> OBSERVE -> DECIDE -> EXECUTE -> VERIFY loop.

Deterministic guardrails live HERE, never in the LLM: auth-state checks,
budget limits, domain enforcement (via GoalContract), duplicate-click
detection, and LLM-failure circuit breaking.
"""

from __future__ import annotations

import json
import re
import sys
import time
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from .actions import execute_action  # noqa: E402
from .observer import observe, summarize_observation  # noqa: E402

MAX_TOKENS_FLOOR = 4000  # stealth/ox-alpha returns empty below ~4000


# --------------------------------------------------------------------- LLM

def llm_decide(prompt_messages: list[dict], temperature: float = 0.2) -> str:
    """Call the configured provider chain via the openai SDK.

    Reuses tailor_from_jd.llm_config() (openrouter first, nvidia fallback)
    rather than inventing a new provider resolution.
    """
    from openai import OpenAI
    try:
        from tailor_from_jd import llm_config
    except Exception:
        from ._llm_config_fallback import llm_config

    last_err: Exception | None = None
    for prov in llm_config():
        for i, model in enumerate(prov["models"]):
            timeout = 180 if i == 0 else 90
            try:
                client = OpenAI(base_url=prov["base_url"], api_key=prov["key"],
                                timeout=timeout, max_retries=0)
                resp = client.chat.completions.create(
                    model=model, messages=prompt_messages,
                    temperature=temperature,
                    max_tokens=max(MAX_TOKENS_FLOOR, 4000))
                content = (resp.choices[0].message.content or "").strip()
                if not content:
                    raise RuntimeError("empty completion")
                return content
            except Exception as exc:  # noqa: BLE001
                last_err = exc
    raise RuntimeError(f"no LLM provider responded: {last_err}")


def parse_decision(raw: str) -> dict:
    """Robustly extract a JSON decision object (strips code fences)."""
    text = raw.strip()
    fence = re.search(r"```(?:json)?\s*(.*?)```", text, re.DOTALL)
    if fence:
        text = fence.group(1).strip()
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end > start:
        text = text[start:end + 1]
    return json.loads(text)


def build_prompt(goal_contract, obs: dict, history: list[dict],
                 extracted: list, actions_used: int, task_hint: str) -> list[dict]:
    schema = {
        "thought": "short reasoning about the current page vs goal",
        "action": {"type": "<navigate|click|type|scroll|press_key|wait|extract|done>",
                   "...params": "e.g. url / role+name / text / key / seconds"},
        "extracted": ["entities on THIS page relevant to the goal"],
        "subgoal": "current sub-goal, one line",
    }
    hist = "\n".join(
        f"{i + 1}. {h.get('action', '?')} -> {h.get('result', '')[:200]}"
        for i, h in enumerate(history[-8:])
    )
    user = f"""{goal_contract.to_prompt_text()}
Task hint: {task_hint or '(none)'}

Current page url: {obs.get('url', '')}
Current page title: {obs.get('title', '')}
Auth state: {obs.get('auth_state', 'UNKNOWN')}

Accessibility outline (interactive elements + headings):
{json.dumps(obs.get('a11y_outline', [])[:120], ensure_ascii=False)}

Visible text (head):
{(obs.get('visible_text_head') or '')[:3000]}

Recent actions:
{hist or '(none yet)'}

Entities extracted so far: {json.dumps(extracted, ensure_ascii=False)}
Actions used: {actions_used}/{goal_contract.max_actions}

Respond with ONLY a JSON object matching this schema:
{json.dumps(schema)}"""
    return [
        {"role": "system", "content": (
            "You are a careful web-navigation agent. Choose ONE next action. "
            "Never perform prohibited actions. Prefer reading over clicking. "
            "When the goal is achieved, emit action type 'done' with summary "
            "in thought and all collected entities in extracted.")},
        {"role": "user", "content": user},
    ]


# ------------------------------------------------------------------- run

def run(session, goal_contract, task_hint: str = "",
        decide_fn=None, site: str = "linkedin") -> dict:
    """Run the navigation loop. Returns a RunResult dict."""
    decide_fn = decide_fn or llm_decide
    run_id = f"wna_{datetime_stamp()}_{uuid.uuid4().hex[:6]}"
    result: dict = {
        "run_id": run_id,
        "status": "ERROR",
        "extracted": [],
        "actions": [],
        "stop_reason": "",
    }
    session.log("run_start", run_id=run_id,
                goal=goal_contract.description[:120])
    t0 = time.time()
    consecutive_llm_failures = 0
    recent_click_targets: list[str] = []
    page = session.page

    while True:
        # ---- budget -------------------------------------------------
        if len(result["actions"]) >= goal_contract.max_actions:
            result.update(status="BUDGET_EXHAUSTED",
                          stop_reason="max_actions reached")
            break
        if time.time() - t0 > goal_contract.max_seconds:
            result.update(status="BUDGET_EXHAUSTED",
                          stop_reason="max_seconds reached")
            break

        # ---- OBSERVE + auth guard -----------------------------------
        try:
            obs = observe(page, session=session, site=site)
        except Exception as exc:  # noqa: BLE001
            result.update(status="ERROR",
                          stop_reason=f"observation failed: {exc}")
            break
        if obs.get("auth_state") in ("AUTH_REQUIRED", "CHALLENGE_OR_2FA"):
            result.update(status=obs["auth_state"],
                          stop_reason=f"auth gate detected at {obs.get('url')}")
            session.log("stop_auth", status=result["status"])
            break

        # ---- DECIDE --------------------------------------------------
        prompt = build_prompt(goal_contract, obs, result["actions"],
                              result["extracted"], len(result["actions"]),
                              task_hint)
        try:
            raw = decide_fn(prompt)
            decision = parse_decision(raw)
            consecutive_llm_failures = 0
        except Exception as exc:  # noqa: BLE001
            consecutive_llm_failures += 1
            session.log("llm_failure", n=consecutive_llm_failures,
                        err=str(exc)[:200])
            if consecutive_llm_failures >= 2:
                result.update(status="ERROR",
                              stop_reason=f"LLM failed twice: {exc}")
                break
            continue

        action = decision.get("action") or {}
        entities = decision.get("extracted") or []
        if isinstance(entities, list):
            result["extracted"].extend(
                e for e in entities if e not in result["extracted"])

        ok, reason = goal_contract.validate_action(action)
        if not ok:
            result["actions"].append({"action": action, "result": f"REFUSED: {reason}"})
            session.log("refused", reason=reason)
            continue

        atype = str(action.get("type", "")).lower()
        if atype == "done":
            result.update(status="SUCCESS",
                          stop_reason=str(decision.get("thought", ""))[:300])
            session.log("done", summary=result["stop_reason"])
            break

        # ---- duplicate-click detection -------------------------------
        if atype == "click":
            target = f"{action.get('role', '')}|{action.get('name') or action.get('ref', '')}|{action.get('selector', '')}"
            recent_click_targets.append(target)
            if len(recent_click_targets) > 3:
                recent_click_targets.pop(0)
            if (len(recent_click_targets) == 3
                    and len(set(recent_click_targets)) == 1):
                result.update(status="NO_PROGRESS",
                              stop_reason=f"identical click target 3x: {target}")
                session.log("stop_no_progress", target=target)
                break
        else:
            recent_click_targets.clear()

        # ---- EXECUTE --------------------------------------------------
        outcome = execute_action(page, action, goal=goal_contract,
                                 session=session)
        summary = outcome.get("status", "?")
        if outcome.get("error"):
            summary += f": {outcome['error'][:150]}"
        if atype == "extract":
            summary += f" value={str(outcome.get('value', ''))[:200]}"
        result["actions"].append({"action": action, "result": summary})

    session.log("run_end", run_id=run_id, status=result["status"],
                actions=len(result["actions"]),
                extracted=len(result["extracted"]))
    return result


def datetime_stamp() -> str:
    return time.strftime("%Y%m%d_%H%M%S")
