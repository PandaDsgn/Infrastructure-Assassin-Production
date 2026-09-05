import asyncio
import json
import os
import re
import time
from collections import defaultdict
from contextlib import asynccontextmanager

import certifi
import httpx
import redis.asyncio as redis
from dotenv import load_dotenv
from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from google import genai
from pydantic import BaseModel

import db as pgdb
from agent import evaluate_resources_batch
from firebase import auth as fb_auth
from firebase import db as fb_db

load_dotenv()

# --- REDIS (Stateless Memory) ---
_redis_url = os.environ.get("REDIS_URL", "redis://127.0.0.1:6379")
_redis_kwargs = {"decode_responses": True}
if _redis_url.startswith("rediss://"):
    _redis_kwargs["ssl_ca_certs"] = certifi.where()
redis_client = redis.from_url(_redis_url, **_redis_kwargs)

if not os.environ.get("GEMINI_API_KEY"):
    print(
        "[STARTUP WARNING] GEMINI_API_KEY is not set in this environment - "
        "every /api/chat request will fail and fall back to the local NLP engine."
    )
_ai = genai.Client(api_key=os.environ["GEMINI_API_KEY"]) if os.environ.get("GEMINI_API_KEY") else None
CHAT_MODEL_NAME = "gemini-2.5-flash"

MAX_CHAT_HISTORY = 6


# --- SSE fanout (Postgres LISTEN/NOTIFY -> local clients) ---
_sse_clients: list[dict] = []


def push_to_local_clients(payload):
    message = json.dumps(payload)
    for client in list(_sse_clients):
        client["queue"].put_nowait(message)


async def broadcast_event(event_type, data=None):
    try:
        await pgdb.publish_realtime_event(event_type, data or {})
    except Exception as err:
        print(f'[REALTIME BUS] Failed to publish "{event_type}":', err)
        push_to_local_clients({"type": event_type, "data": data or {}, "timestamp": int(time.time() * 1000)})


@asynccontextmanager
async def lifespan(app: FastAPI):
    await pgdb.init_db()
    try:
        await pgdb.init_realtime_bus(push_to_local_clients)
    except Exception as err:
        print("[REALTIME BUS] Failed to initialize:", err)
    try:
        await redis_client.ping()
        print("🟢 Redis external state store connected.")
    except Exception as err:
        print("[REDIS ERROR]", err)
    yield
    await redis_client.aclose()


app = FastAPI(lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    return JSONResponse(status_code=exc.status_code, content={"error": exc.detail})


# --- 1. RATE LIMITING (DDoS & Quota Protection) ---
RATE_WINDOW_S = 60
RATE_MAX = 100
_rate_state = defaultdict(lambda: {"count": 0, "reset_at": 0.0})


@app.middleware("http")
async def rate_limiter(request: Request, call_next):
    if request.url.path.startswith("/api/"):
        ip = request.client.host if request.client else "unknown"
        now = time.time()
        state = _rate_state[ip]
        if now > state["reset_at"]:
            state["count"] = 0
            state["reset_at"] = now + RATE_WINDOW_S
        state["count"] += 1
        if state["count"] > RATE_MAX:
            return JSONResponse(
                status_code=429,
                content={"error": "Neural link saturated. Too many requests. Please hold."},
            )
    return await call_next(request)


@app.get("/api/config")
async def get_config():
    return {
        "apiKey": os.environ.get("FIREBASE_API_KEY"),
        "authDomain": os.environ.get("FIREBASE_AUTH_DOMAIN"),
        "projectId": os.environ.get("FIREBASE_PROJECT_ID"),
        "storageBucket": os.environ.get("FIREBASE_STORAGE_BUCKET"),
        "messagingSenderId": os.environ.get("FIREBASE_MESSAGING_SENDER_ID"),
        "appId": os.environ.get("FIREBASE_APP_ID"),
    }


async def authenticate_user(request: Request) -> dict:
    auth_header = request.headers.get("authorization")
    token = None

    if auth_header and auth_header.startswith("Bearer "):
        token = auth_header.split(" ")[1]
    elif request.query_params.get("token"):
        token = request.query_params.get("token")

    if not token:
        raise HTTPException(status_code=401, detail="No authorization token provided.")

    try:
        decoded = await asyncio.to_thread(fb_auth.verify_id_token, token)
        user_doc = await asyncio.to_thread(lambda: fb_db.collection("users").document(decoded["uid"]).get())

        role = "Junior-Developer"
        name = decoded["email"].split("@")[0]

        if user_doc.exists:
            data = user_doc.to_dict()
            role = data.get("role", role)
            name = data.get("name", name)

        return {"uid": decoded["uid"], "email": decoded["email"], "name": name, "role": role}
    except HTTPException:
        raise
    except Exception as err:
        print("[AUTH ERROR] Token verification failed:", err)
        raise HTTPException(status_code=401, detail="Session expired or invalid.")


async def require_admin(user: dict = Depends(authenticate_user)) -> dict:
    if user["role"] != "IT-Director":
        raise HTTPException(status_code=403, detail="Admin clearance required.")
    return user


@app.get("/api/events")
async def sse_events(request: Request, user: dict = Depends(authenticate_user)):
    queue: asyncio.Queue = asyncio.Queue()
    client = {"uid": user["uid"], "role": user["role"], "queue": queue}
    _sse_clients.append(client)

    async def event_stream():
        yield ": connected\n\n"
        try:
            while True:
                if await request.is_disconnected():
                    break
                try:
                    message = await asyncio.wait_for(queue.get(), timeout=20)
                    yield f"data: {message}\n\n"
                except asyncio.TimeoutError:
                    yield ": heartbeat\n\n"
        finally:
            _sse_clients.remove(client)

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@app.get("/api/auth/me")
async def auth_me(user: dict = Depends(authenticate_user)):
    return {"name": user["name"], "role": user["role"], "email": user["email"]}


class RegisterBody(BaseModel):
    name: str | None = None
    inviteCode: str | None = None


@app.post("/api/auth/register")
async def auth_register(body: RegisterBody, user: dict = Depends(authenticate_user)):
    secret_code = os.environ.get("ADMIN_INVITE_CODE", "aegis-admin")
    assigned_role = "IT-Director" if body.inviteCode == secret_code else "Junior-Developer"

    try:
        await asyncio.to_thread(
            lambda: fb_db.collection("users")
            .document(user["uid"])
            .set(
                {
                    "name": body.name or user["email"].split("@")[0],
                    "role": assigned_role,
                    "email": user["email"],
                }
            )
        )
        await broadcast_event("user_registered", {"uid": user["uid"], "role": assigned_role})
        return {"success": True, "role": assigned_role}
    except Exception:
        raise HTTPException(status_code=500, detail="Failed to create user profile.")


_cached_audit_results = None
_last_audit_time = 0.0


@app.get("/api/audit")
async def get_audit(user: dict = Depends(authenticate_user)):
    global _cached_audit_results, _last_audit_time
    if _cached_audit_results is not None and time.time() - _last_audit_time < 300:
        return _cached_audit_results

    try:
        rows = await pgdb.query("SELECT * FROM resources WHERE status = 'Active' OR status = 'Pending Approval'")
        actions = await evaluate_resources_batch(rows)
        audited = [{**row, "recommended_action": actions[i]} for i, row in enumerate(rows)]

        _cached_audit_results = audited
        _last_audit_time = time.time()
        return audited
    except Exception as err:
        raise HTTPException(status_code=500, detail=str(err))


def resolve_target_status(action_type):
    return {
        "TERMINATE": "Terminated",
        "QUARANTINE": "Quarantined",
        "UPDATE": "Updated",
        "KEEP": "Kept Active",
    }.get(action_type, "Active")


def _invalidate_audit_cache():
    global _cached_audit_results, _last_audit_time
    _cached_audit_results = None
    _last_audit_time = 0.0


class ActionBody(BaseModel):
    actionType: str
    resource_id: int


@app.post("/api/action")
async def post_action(body: ActionBody, user: dict = Depends(authenticate_user)):
    rows = await pgdb.query("SELECT status, resource_name FROM resources WHERE id = $1", [body.resource_id])

    if not rows:
        raise HTTPException(status_code=404, detail="Resource not found.")

    resource_name = rows[0]["resource_name"]

    if rows[0]["status"] == "Pending Approval":
        raise HTTPException(status_code=409, detail="Request already in progress.")

    try:
        if user["role"] == "Junior-Developer":
            log_rows = await pgdb.query(
                """INSERT INTO request_log (resource_name, requester_uid, requester_name, action_type, status)
                   VALUES ($1, $2, $3, $4, 'Pending') RETURNING id""",
                [resource_name, user["uid"], user["name"], body.actionType],
            )
            log_id = log_rows[0]["id"]

            await pgdb.query(
                "UPDATE resources SET status = 'Pending Approval', pending_action_by = $1, "
                "pending_action_type = $2, pending_log_id = $3 WHERE id = $4",
                [user["name"], body.actionType, log_id, body.resource_id],
            )

            _invalidate_audit_cache()
            await broadcast_event(
                "resource_pending",
                {"resource_name": resource_name, "requester": user["name"], "actionType": body.actionType},
            )

            return {
                "success": True,
                "pending": True,
                "message": f"{body.actionType} request routed to Admin control queue.",
            }

        target_status = resolve_target_status(body.actionType)

        await pgdb.query(
            "UPDATE resources SET status = $1, pending_action_by = NULL, pending_action_type = NULL WHERE id = $2",
            [target_status, body.resource_id],
        )

        _invalidate_audit_cache()
        await broadcast_event(
            "resource_updated", {"resource_name": resource_name, "status": target_status, "actor": user["name"]}
        )

        return {
            "success": True,
            "pending": False,
            "message": f"{body.actionType} protocol successfully committed to cloud ledger.",
        }
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=500, detail="Failed to apply resource state update.")


class CancelBody(BaseModel):
    resource_id: int


@app.post("/api/action/cancel-request")
async def cancel_request(body: CancelBody, user: dict = Depends(authenticate_user)):
    try:
        rows = await pgdb.query(
            "SELECT pending_log_id, resource_name FROM resources WHERE id = $1", [body.resource_id]
        )

        if not rows:
            raise HTTPException(status_code=404, detail="Resource not found.")

        log_id = rows[0]["pending_log_id"]
        resource_name = rows[0]["resource_name"]

        await pgdb.query(
            "UPDATE resources SET status = 'Active', pending_action_by = NULL, "
            "pending_action_type = NULL, pending_log_id = NULL WHERE id = $1",
            [body.resource_id],
        )

        if log_id:
            await pgdb.query(
                "UPDATE request_log SET status = 'Cancelled', resolved_at = NOW(), resolved_by = $1 WHERE id = $2",
                [user["name"], log_id],
            )

        _invalidate_audit_cache()
        await broadcast_event("resource_cancelled", {"resource_name": resource_name, "actor": user["name"]})
        return {"success": True, "message": "Request discarded cleanly."}
    except HTTPException:
        raise
    except Exception as err:
        raise HTTPException(status_code=500, detail=str(err))


@app.get("/api/approvals")
async def get_approvals(user: dict = Depends(authenticate_user)):
    if user["role"] != "IT-Director":
        return []

    try:
        rows = await pgdb.query("""
            SELECT r.*, rl.requested_at
            FROM resources r
            LEFT JOIN request_log rl ON rl.id = r.pending_log_id
            WHERE r.status = 'Pending Approval'
        """)
        return [
            {
                "id": row["id"],
                "requester": row["pending_action_by"],
                "action": row["pending_action_type"] or "UNKNOWN",
                "resource": row["resource_name"],
                "requested_at": row["requested_at"],
            }
            for row in rows
        ]
    except Exception:
        raise HTTPException(status_code=500, detail="Failed to fetch approvals.")


class ApprovalResolveBody(BaseModel):
    id: int
    decision: str


@app.post("/api/approvals/resolve")
async def resolve_approval(body: ApprovalResolveBody, user: dict = Depends(require_admin)):
    try:
        rows = await pgdb.query(
            "SELECT pending_action_type, resource_name, pending_log_id FROM resources WHERE id = $1", [body.id]
        )
        if not rows:
            raise HTTPException(status_code=404, detail="Request not found.")

        requested_action = rows[0]["pending_action_type"]
        log_id = rows[0]["pending_log_id"]

        if body.decision == "Approve":
            final_status = resolve_target_status(requested_action)
            message = f"Approved. {requested_action or 'Requested action'} applied to {rows[0]['resource_name']}."
        else:
            final_status = "Active"
            message = "Rejected user request."

        await pgdb.query(
            "UPDATE resources SET status = $1, pending_action_by = NULL, "
            "pending_action_type = NULL, pending_log_id = NULL WHERE id = $2",
            [final_status, body.id],
        )

        if log_id:
            await pgdb.query(
                "UPDATE request_log SET status = $1, resolved_at = NOW(), resolved_by = $2 WHERE id = $3",
                ["Approved" if body.decision == "Approve" else "Rejected", user["name"], log_id],
            )

        _invalidate_audit_cache()
        await broadcast_event(
            "approval_resolved",
            {"id": body.id, "decision": body.decision, "requestedAction": requested_action, "finalStatus": final_status},
        )

        return {"success": True, "message": message}
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=500, detail="Approval pipeline database synchronization error.")


@app.get("/api/requests/outgoing")
async def outgoing_requests(user: dict = Depends(authenticate_user)):
    try:
        rows = await pgdb.query(
            """SELECT id, resource_name, action_type, status, requested_at, resolved_at, resolved_by
               FROM request_log
               WHERE requester_uid = $1
               ORDER BY requested_at DESC
               LIMIT 100""",
            [user["uid"]],
        )
        return rows
    except Exception:
        raise HTTPException(status_code=500, detail="Failed to fetch outgoing requests.")


@app.get("/api/users")
async def list_users(user: dict = Depends(require_admin)):
    try:
        snapshot = await asyncio.to_thread(lambda: list(fb_db.collection("users").stream()))
        return [{"uid": doc.id, **doc.to_dict()} for doc in snapshot if doc.id != user["uid"]]
    except Exception:
        raise HTTPException(status_code=500, detail="Failed to fetch users.")


@app.delete("/api/users/{target_uid}")
async def delete_user(target_uid: str, user: dict = Depends(require_admin)):
    try:
        user_ref = fb_db.collection("users").document(target_uid)
        doc = await asyncio.to_thread(user_ref.get)

        if doc.exists and doc.to_dict().get("role") == "IT-Director":
            raise HTTPException(
                status_code=403, detail="ACCESS DENIED: IT Directors cannot terminate other IT Directors."
            )

        await asyncio.to_thread(fb_auth.delete_user, target_uid)
        await asyncio.to_thread(user_ref.delete)

        await broadcast_event("user_removed", {"targetUid": target_uid, "actor": user["name"]})

        return {"success": True, "message": "Personnel permanently erased from all systems."}
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=500, detail="Failed to completely delete user.")


class ChatBody(BaseModel):
    message: str


@app.post("/api/chat")
async def chat(body: ChatBody, user: dict = Depends(authenticate_user)):
    user_message = body.message.strip()
    user_id = user["uid"]

    chat_key = f"chat:{user_id}"
    tier_key = f"tier:{user_id}"

    user_preference = await redis_client.get(tier_key) or "auto"

    command_msg = user_message.lower()
    if command_msg.startswith("/use "):
        target = command_msg.replace("/use ", "").strip()

        if target in ("gemini", "groq", "deepseek", "auto"):
            await redis_client.set(tier_key, target)
            target_display = "Default Waterfall Cascade" if target == "auto" else target.upper()

            await redis_client.rpush(chat_key, f"System: Locked to {target}")
            await redis_client.ltrim(chat_key, -MAX_CHAT_HISTORY, -1)

            return {
                "reply": f"Routing preference updated. System is now locked to: **{target_display}**.",
                "source": "System Override",
            }
        else:
            return {
                "reply": "Unknown target. Please use: `/use gemini`, `/use groq`, `/use deepseek`, or `/use auto`.",
                "source": "System Error",
            }

    await redis_client.rpush(chat_key, f"User: {user_message}")
    await redis_client.ltrim(chat_key, -MAX_CHAT_HISTORY, -1)
    current_history = await redis_client.lrange(chat_key, 0, -1)

    try:
        rows = await pgdb.query("SELECT * FROM resources")
    except Exception:
        raise HTTPException(status_code=500, detail="Failed to read database for context.")

    system_prompt = f"""You are "Infrastructure Assassin", an enterprise IT security AI.
        Talking to {user["name"]} (Role: {user["role"]}).
        Infrastructure Data: {json.dumps(rows, default=str)}
        Recent Context: {chr(10).join(current_history)}

        RULES:
        1. Never execute actions.
        2. Tell the user to use dashboard buttons.
        3. If Junior-Developer, remind them it requires approval."""

    final_reply = ""
    source = ""

    if user_preference in ("auto", "gemini"):
        try:
            if not os.environ.get("GEMINI_API_KEY"):
                raise RuntimeError("No Gemini key found")
            result = await asyncio.to_thread(
                _ai.models.generate_content,
                model=CHAT_MODEL_NAME,
                contents=f'{system_prompt}\n\nRespond to: "{user_message}"',
            )
            final_reply = result.text.strip()
            source = "Gemini (Tier 1)"
        except Exception as err:
            print(f"[GEMINI FAILED] {err}.")
            if user_preference == "gemini":
                return {"reply": "[Gemini Error] Quota exhausted or API unavailable.", "source": "System Error"}

    if (user_preference == "auto" and not final_reply) or user_preference == "groq":
        try:
            api_key = os.environ.get("GROQ_API_KEY")
            if not api_key:
                raise RuntimeError("No Groq key found")
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.post(
                    "https://api.groq.com/openai/v1/chat/completions",
                    headers={"Content-Type": "application/json", "Authorization": f"Bearer {api_key}"},
                    json={
                        "model": "llama-3.1-8b-instant",
                        "messages": [
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": user_message},
                        ],
                    },
                )
                if resp.is_error:
                    raise RuntimeError(f"Groq rejected payload: {resp.text}")
                data = resp.json()
                final_reply = data["choices"][0]["message"]["content"].strip()
                source = "Groq (Tier 2)"
        except Exception as err:
            print(f"[GROQ FAILED] {err}.")
            if user_preference == "groq":
                return {"reply": "[Groq Error] API unavailable.", "source": "System Error"}

    if (user_preference == "auto" and not final_reply) or user_preference == "deepseek":
        try:
            api_key = os.environ.get("DEEPSEEK_API_KEY")
            if not api_key:
                raise RuntimeError("No DeepSeek key found")
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.post(
                    "https://api.deepseek.com/chat/completions",
                    headers={"Content-Type": "application/json", "Authorization": f"Bearer {api_key}"},
                    json={
                        "model": "deepseek-chat",
                        "messages": [
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": user_message},
                        ],
                    },
                )
                if resp.is_error:
                    raise RuntimeError(f"DeepSeek rejected payload: {resp.text}")
                data = resp.json()
                final_reply = data["choices"][0]["message"]["content"].strip()
                source = "DeepSeek (Tier 3)"
        except Exception as err:
            print(f"[DEEPSEEK FAILED] {err}.")
            if user_preference == "deepseek":
                return {"reply": "[DeepSeek Error] API unavailable.", "source": "System Error"}

    if final_reply:
        await redis_client.rpush(chat_key, f"Assassin AI: {final_reply}")
        await redis_client.ltrim(chat_key, -MAX_CHAT_HISTORY, -1)
        return {"reply": final_reply, "source": source}

    # --- Local Heuristics Fallback (Tier 4) ---
    msg = user_message.lower()
    dynamic_savings = 0

    for r in rows:
        if r["status"] in ("Active", "Pending Approval") and (
            (r["days_since_last_login"] or 0) >= 30 or r["is_malicious"]
        ):
            dynamic_savings += r["monthly_cost"] or 0

    words = [w for w in msg.split() if len(w) > 2]
    mentioned_resource = next(
        (r for r in rows if any(w in r["resource_name"].lower() for w in words)), None
    )

    is_asking_cost = bool(re.search(r"(cost|spend|sav|money|budget|summary)", msg))
    is_asking_terminate = bool(re.search(r"(terminat|delete|remove|kill|idle|unused)", msg))
    is_asking_quarantine = bool(re.search(r"(quarantin|quanrantin|malicious|virus|malware|threat|hack)", msg))
    is_asking_update = bool(re.search(r"(updat|patch|upgrad|outdated)", msg))

    if mentioned_resource:
        name = mentioned_resource["resource_name"]
        cost = mentioned_resource["monthly_cost"]
        idle = mentioned_resource["days_since_last_login"] or 0

        if mentioned_resource["is_malicious"]:
            local_reply = f"CRITICAL ALERT: {name} is flagged as malicious. Immediate QUARANTINE recommended. (Cost: ₹{cost}/mo)"
        elif idle >= 30:
            local_reply = f"{name} should be TERMINATED. It costs ₹{cost}/mo and has been idle for {idle} days."
        elif mentioned_resource["needs_update"]:
            local_reply = f"{name} requires a critical security patch. Recommendation: UPDATE."
        else:
            local_reply = f"{name} is secure and active (Idle: {idle} days). Recommendation: KEEP."
    elif is_asking_quarantine:
        targets = [r["resource_name"] for r in rows if r["is_malicious"]]
        local_reply = (
            f"URGENT: The following resources are malicious and must be QUARANTINED: {', '.join(targets)}."
            if targets
            else "No active malicious threats detected."
        )
    elif is_asking_terminate:
        targets = [r["resource_name"] for r in rows if not r["is_malicious"] and (r["days_since_last_login"] or 0) >= 30]
        local_reply = (
            f"Based on telemetry, these idle resources should be TERMINATED: {', '.join(targets)}."
            if targets
            else "No resources are currently flagged for termination based on idle time."
        )
    elif is_asking_update:
        targets = [r["resource_name"] for r in rows if r["needs_update"] and not r["is_malicious"]]
        local_reply = (
            f"These resources require critical patches (UPDATE): {', '.join(targets)}."
            if targets
            else "All active applications are up to date."
        )
    elif is_asking_cost:
        local_reply = (
            f"Local metrics report: You have ₹{dynamic_savings:,} in potential savings identified. "
            "Focus on Quarantining malicious apps and Terminating idle resources to realize this."
        )
    else:
        local_reply = (
            "Neural Link offline. I am operating on local heuristics. You can ask me about costs, threats "
            "(quarantine), idle resources (terminate), or type the name of a specific application in the ledger."
        )

    await redis_client.rpush(chat_key, f"Assassin AI: {local_reply}")
    await redis_client.ltrim(chat_key, -MAX_CHAT_HISTORY, -1)
    return {"reply": local_reply, "source": "Heuristics (Tier 4)"}


@app.get("/api/chat/history")
async def chat_history(user: dict = Depends(authenticate_user)):
    return await redis_client.lrange(f"chat:{user['uid']}", 0, -1)


@app.post("/api/chat/clear")
async def chat_clear(user: dict = Depends(authenticate_user)):
    await redis_client.delete(f"chat:{user['uid']}")
    return {"success": True}
