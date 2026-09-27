"""
magicpin AI Challenge — Local Verification Test Harness
Runs comprehensive verification against the local Vera bot server and submission artifacts.
"""

import sys
import json
import time
import subprocess
import urllib.request
import urllib.error

# Force UTF-8 on Windows stdout
sys.stdout.reconfigure(encoding='utf-8')

BASE_URL = "http://localhost:8080"

def log_test(name: str, passed: bool, details: str = ""):
    status = "PASS" if passed else "FAIL"
    print(f"[{status}] {name}" + (f" — {details}" if details else ""))
    if not passed:
        sys.exit(1)

def ensure_server():
    try:
        urllib.request.urlopen(f"{BASE_URL}/v1/healthz", timeout=1)
        return None
    except Exception:
        pass
    print("Bot server is not running on port 8080. Starting python bot.py automatically...")
    proc = subprocess.Popen([sys.executable, "bot.py"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    for _ in range(25):
        time.sleep(0.2)
        try:
            urllib.request.urlopen(f"{BASE_URL}/v1/healthz", timeout=1)
            print("Bot server started and ready on http://localhost:8080!\n")
            return proc
        except Exception:
            pass
    return proc

def main():
    server_proc = ensure_server()
    try:
        _run_tests()
    finally:
        if server_proc:
            server_proc.terminate()
            try:
                server_proc.wait(timeout=2)
            except Exception:
                server_proc.kill()

def _run_tests():
    print("=" * 60)
    print("Vera Bot Test Harness Verification")
    print("=" * 60)

    # 1. Healthz
    try:
        resp = urllib.request.urlopen(f"{BASE_URL}/v1/healthz")
        data = json.loads(resp.read().decode("utf-8"))
        log_test("GET /v1/healthz", resp.status == 200 and data.get("status") == "ok", f"Status {resp.status}, contexts: {data.get('contexts_loaded')}")
    except Exception as e:
        log_test("GET /v1/healthz", False, str(e))

    # 2. Metadata
    try:
        resp = urllib.request.urlopen(f"{BASE_URL}/v1/metadata")
        data = json.loads(resp.read().decode("utf-8"))
        log_test("GET /v1/metadata", resp.status == 200 and "team_name" in data, f"Team: {data.get('team_name')}, Model: {data.get('model')}")
    except Exception as e:
        log_test("GET /v1/metadata", False, str(e))

    # 3. Context Ingest & Idempotency
    try:
        # Push version 1
        cat_payload = {"slug": "dentists", "voice": {"tone": "peer_clinical"}}
        body = json.dumps({"scope": "category", "context_id": "test_dentists", "version": 1, "payload": cat_payload}).encode("utf-8")
        req = urllib.request.Request(f"{BASE_URL}/v1/context", data=body, headers={"Content-Type": "application/json"})
        resp = urllib.request.urlopen(req)
        data = json.loads(resp.read().decode("utf-8"))
        log_test("POST /v1/context (v1 fresh)", resp.status == 200 and data.get("accepted") is True, f"ack_id: {data.get('ack_id')}")

        # Push duplicate version 1 (must 409)
        duplicate_ok = False
        try:
            urllib.request.urlopen(req)
        except urllib.error.HTTPError as e:
            if e.code == 409:
                duplicate_ok = True
                data = json.loads(e.read().decode("utf-8"))
        log_test("POST /v1/context (idempotency 409)", duplicate_ok, f"Current version: {data.get('current_version')}")

        # Push version 2 (must replace)
        body2 = json.dumps({"scope": "category", "context_id": "test_dentists", "version": 2, "payload": cat_payload}).encode("utf-8")
        req2 = urllib.request.Request(f"{BASE_URL}/v1/context", data=body2, headers={"Content-Type": "application/json"})
        resp2 = urllib.request.urlopen(req2)
        data2 = json.loads(resp2.read().decode("utf-8"))
        log_test("POST /v1/context (v2 upgrade)", resp2.status == 200 and data2.get("accepted") is True, f"ack_id: {data2.get('ack_id')}")
    except Exception as e:
        log_test("POST /v1/context tests", False, str(e))

    # 4. Tick with Action Generation
    try:
        # Push a test merchant and trigger
        m_payload = {
            "merchant_id": "m_test_dentist",
            "category_slug": "dentists",
            "identity": {"name": "Dr. Smile", "locality": "South Ext", "city": "Delhi", "owner_first_name": "Smile", "languages": ["en"]},
            "performance": {"views": 1500, "calls": 20, "ctr": 0.03},
            "offers": [{"id": "o1", "title": "Dental Cleaning @ ₹299", "status": "active"}]
        }
        body_m = json.dumps({"scope": "merchant", "context_id": "m_test_dentist", "version": 1, "payload": m_payload}).encode("utf-8")
        urllib.request.urlopen(urllib.request.Request(f"{BASE_URL}/v1/context", data=body_m, headers={"Content-Type": "application/json"}))

        t_payload = {
            "id": "trg_test_1",
            "scope": "merchant",
            "kind": "perf_dip",
            "source": "internal",
            "merchant_id": "m_test_dentist",
            "payload": {"metric": "calls", "delta_pct": -0.40, "vs_baseline": 15},
            "suppression_key": "perf_dip:m_test_dentist:calls"
        }
        body_t = json.dumps({"scope": "trigger", "context_id": "trg_test_1", "version": 1, "payload": t_payload}).encode("utf-8")
        urllib.request.urlopen(urllib.request.Request(f"{BASE_URL}/v1/context", data=body_t, headers={"Content-Type": "application/json"}))

        # Call tick
        tick_body = json.dumps({"now": "2026-04-26T10:00:00Z", "available_triggers": ["trg_test_1"]}).encode("utf-8")
        resp_tick = urllib.request.urlopen(urllib.request.Request(f"{BASE_URL}/v1/tick", data=tick_body, headers={"Content-Type": "application/json"}))
        data_tick = json.loads(resp_tick.read().decode("utf-8"))
        actions = data_tick.get("actions", [])
        log_test("POST /v1/tick action generation", len(actions) == 1 and "40%" in actions[0]["body"], f"Action composed: '{actions[0]['body'][:60]}...'")
    except Exception as e:
        log_test("POST /v1/tick tests", False, str(e))

    # 5. Multi-Turn: Auto-Reply Detection & Exit
    try:
        conv_id = "test_conv_auto"
        auto_text = "Thank you for contacting us! Our team will respond shortly."
        actions_received = []
        for turn in range(1, 4):
            r_body = json.dumps({"conversation_id": conv_id, "merchant_id": "m_test_dentist", "from_role": "merchant", "message": auto_text, "received_at": "2026-04-26T10:00:00Z", "turn_number": turn + 1}).encode("utf-8")
            resp = urllib.request.urlopen(urllib.request.Request(f"{BASE_URL}/v1/reply", data=r_body, headers={"Content-Type": "application/json"}))
            r_data = json.loads(resp.read().decode("utf-8"))
            actions_received.append(r_data.get("action"))

        # Turn 1: send (gentle prompt), Turn 2: wait, Turn 3: end
        log_test("Auto-Reply Detection", actions_received == ["send", "wait", "end"], f"Sequence: {actions_received}")
    except Exception as e:
        log_test("Auto-Reply Detection", False, str(e))

    # 6. Multi-Turn: Intent Transition
    try:
        conv_id = "test_conv_intent"
        intent_text = "Ok lets do it. Whats next?"
        r_body = json.dumps({"conversation_id": conv_id, "merchant_id": "m_test_dentist", "from_role": "merchant", "message": intent_text, "received_at": "2026-04-26T10:00:00Z", "turn_number": 2}).encode("utf-8")
        resp = urllib.request.urlopen(urllib.request.Request(f"{BASE_URL}/v1/reply", data=r_body, headers={"Content-Type": "application/json"}))
        r_data = json.loads(resp.read().decode("utf-8"))
        body_text = r_data.get("body", "").lower()
        action_mode = any(w in body_text for w in ["done", "confirm", "sending", "here", "draft"]) and not any(w in body_text for w in ["would you", "can you tell", "what if"])
        log_test("Intent Transition (Immediate Action Mode)", r_data.get("action") == "send" and action_mode, f"Body: '{r_data.get('body')[:70]}...'")
    except Exception as e:
        log_test("Intent Transition", False, str(e))

    # 7. Multi-Turn: Hostility Opt-Out
    try:
        conv_id = "test_conv_hostile"
        hostile_text = "Stop messaging me. This is useless spam."
        r_body = json.dumps({"conversation_id": conv_id, "merchant_id": "m_test_dentist", "from_role": "merchant", "message": hostile_text, "received_at": "2026-04-26T10:00:00Z", "turn_number": 2}).encode("utf-8")
        resp = urllib.request.urlopen(urllib.request.Request(f"{BASE_URL}/v1/reply", data=r_body, headers={"Content-Type": "application/json"}))
        r_data = json.loads(resp.read().decode("utf-8"))
        log_test("Hostility Opt-out Handling", r_data.get("action") == "end", f"Action: {r_data.get('action')}, Rationale: {r_data.get('rationale')}")
    except Exception as e:
        log_test("Hostility Opt-out", False, str(e))

    # 8. Multi-Turn: Off-topic Redirection
    try:
        conv_id = "test_conv_offtopic"
        offtopic_text = "Can you also help me file my GST this month?"
        r_body = json.dumps({"conversation_id": conv_id, "merchant_id": "m_test_dentist", "from_role": "merchant", "message": offtopic_text, "received_at": "2026-04-26T10:00:00Z", "turn_number": 2}).encode("utf-8")
        resp = urllib.request.urlopen(urllib.request.Request(f"{BASE_URL}/v1/reply", data=r_body, headers={"Content-Type": "application/json"}))
        r_data = json.loads(resp.read().decode("utf-8"))
        body_text = r_data.get("body", "").lower()
        redirect_ok = "gst" in body_text and "ca" in body_text
        log_test("Off-Topic Redirection", r_data.get("action") == "send" and redirect_ok, f"Redirect: '{r_data.get('body')[:70]}...'")
    except Exception as e:
        log_test("Off-Topic Redirection", False, str(e))

    # 9. Submission Artifact Verification
    try:
        with open("submission.jsonl", encoding="utf-8") as f:
            lines = [json.loads(line) for line in f if line.strip()]
        valid_records = len(lines) == 30 and all(
            {"test_id", "body", "cta", "send_as", "suppression_key", "rationale"}.issubset(r.keys()) for r in lines
        )
        log_test("submission.jsonl (30 valid records)", valid_records, f"Count: {len(lines)}, Keys validated: YES")
    except Exception as e:
        log_test("submission.jsonl check", False, str(e))

    print("=" * 60)
    print("ALL TESTS PASSED WITH 100% SUCCESS!")
    print("=" * 60)

if __name__ == "__main__":
    main()
