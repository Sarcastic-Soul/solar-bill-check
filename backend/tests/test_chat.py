"""Chat assistant: tools, request validation, history and the Strands loop with Bedrock stubbed."""

import json

import pytest
from conftest import DELHI_SOLAR, load_label

from api import aws
from api import chat as chat_mod
from api import chat_tools as T
from api.errors import ApiError
from api.fields import redact
from engine import build_plan

PID = "abcdefGHIJ_-1234"
SID = "session_ABCDEFGHIJKLMNOP"


@pytest.fixture(scope="module")
def stored():
    fields = load_label("delhi-brpl-hindi-clean-01")
    plan = build_plan({"bill": fields, "solar": DELHI_SOLAR, "location": {"pincode": "110075", "state": "Delhi"},
                       "answers": {"owns_roof": True, "name_matches_bank": True, "previous_solar_subsidy": False}})
    return {"plan": plan.model_dump(mode="json"),
            "inputs": {"fields": redact(fields), "pincode": "110075",
                       "answers": {"owns_roof": True, "name_matches_bank": True, "previous_subsidy": False},
                       "overrides": {}, "monthly_units": None}}


@pytest.fixture
def loader(stored):
    return lambda pid: stored if pid == PID else None


# ---------------------------------------------------------------- tools


def test_get_plan_summary(loader, stored):
    s = T.get_plan_data(PID, loader)
    rec = stored["plan"]["recommended"]
    assert s["plan_id"] == PID and s["verdict"] == stored["plan"]["verdict"]["code"]
    assert s["recommended"]["kw"] == rec["kw"]
    assert s["recommended"]["subsidy_total_rs"] == round(rec["subsidy"]["total"])
    assert s["recommended"]["your_cost_after_subsidy_rs"] == round(rec["net_cost"])
    assert s["recommended"]["loan"]["emi_rs"] == round(rec["loan"]["emi"])
    assert s["discom"].startswith("BSES Rajdhani")
    assert s["recommended"]["subsidy_calculation"].endswith("= Rs 69,000 central subsidy")
    assert {c["code"] for c in s["readiness"]} >= {"NAME_MATCHES_BANK", "OWNS_ROOF"}
    # No personal data: nothing from the bill's name or number reaches the tool output.
    dumped = json.dumps(s)
    assert "SUNITA" not in dumped and "152839471" not in dumped


def test_get_plan_missing(loader):
    assert T.get_plan_data("zzzzzzzzzzzzzzzz", loader)["error"] == "PLAN_NOT_FOUND"


def test_what_if_reruns_engine(loader, stored):
    r = T.what_if_data(PID, 3, loader)
    assert r["asked_kw"] == 3.0
    assert r["this_size"]["kw"] == 3.0 and r["this_size"]["label"] == "custom"
    assert r["this_size"]["subsidy_central_rs"] == 78_000
    assert r["original_recommended"]["kw"] == stored["plan"]["recommended"]["kw"]
    # Same inputs at the recommended size give the stored numbers back.
    same = T.what_if_data(PID, stored["plan"]["recommended"]["kw"], loader)
    assert same["this_size"]["first_year_savings_rs"] == round(stored["plan"]["recommended"]["year1_savings"])


def test_what_if_maps_previous_subsidy_answer(stored):
    s = json.loads(json.dumps(stored))
    s["inputs"]["answers"]["previous_subsidy"] = True
    r = T.what_if_data(PID, 2, lambda _pid: s)
    assert r["this_size"]["subsidy_total_rs"] == 0


@pytest.mark.parametrize("kw", [0, 0.4, 101, "lots", None])
def test_what_if_rejects_bad_size(loader, kw):
    assert T.what_if_data(PID, kw, loader)["error"] == "BAD_SIZE"


def test_what_if_without_inputs(stored):
    r = T.what_if_data(PID, 3, lambda _pid: {"plan": stored["plan"], "inputs": None})
    assert r["error"] == "INPUTS_NOT_SAVED"


def test_loan_emi():
    r = T.loan_emi_data(100_000, 6, 10)
    assert r["emi_rs"] == 1110 and r["months"] == 120
    assert r["total_interest_rs"] == r["total_paid_rs"] - 100_000
    assert T.loan_emi_data(120_000, 0, 10)["emi_rs"] == 1000
    assert T.loan_emi_data(100_000)["rate_pct"] == 6.0  # Jan Samarth default


@pytest.mark.parametrize("args", [(500, 6, 10), (100_000, 40, 10), (100_000, 6, 0), ("x", 6, 10)])
def test_loan_emi_rejects_bad_input(args):
    assert T.loan_emi_data(*args)["error"] == "BAD_INPUT"


@pytest.mark.parametrize("topic,key", [("subsidy", "subsidy"), ("Red flags", "red_flags"), ("jan_samarth", "loan"),
                                       ("DCR", "dcr"), ("how-to-apply", "steps"), ("RWA", "rwa"),
                                       ("deadline", "deadline"), ("net metering", "net_metering"),
                                       ("special category", "special_category")])
def test_scheme_facts(topic, key):
    r = T.scheme_facts_data(topic)
    assert r["topic"] == key and r["facts"]


def test_scheme_facts_content():
    text = " ".join(T.scheme_facts_data("subsidy")["facts"])
    assert "Rs 30,000" in text and "Rs 18,000" in text and "Rs 78,000" in text and "Rs 85,800" in text
    assert len([s for s in T.scheme_facts_data("steps")["facts"] if s[0].isdigit()]) == 7
    assert "31 March 2027" in T.scheme_facts_data("deadline")["facts"][0]
    assert "Sikkim" in " ".join(T.scheme_facts_data("special_category")["facts"])
    assert "6%" in " ".join(T.scheme_facts_data("loan")["facts"])
    assert T.scheme_facts_data("cricket")["error"] == "UNKNOWN_TOPIC"


def test_subsidy_calc():
    assert T.subsidy_calc(2.5, {"mode": "individual", "central": 69000}) == (
        "2 kW x Rs 30,000 + 0.5 kW x Rs 18,000 = Rs 69,000 central subsidy")
    assert T.subsidy_calc(5, {"mode": "individual", "central": 85800, "special_category": True}).endswith(
        "= Rs 85,800 central subsidy (nothing extra above 3 kW)")
    assert T.subsidy_calc(1, {"mode": "individual", "central": 30000}) == "1 kW x Rs 30,000 = Rs 30,000 central subsidy"
    assert T.subsidy_calc(3, {"mode": "rwa", "central": 54000}) is None


def test_inr_grouping():
    assert T._inr(78000) == "Rs 78,000" and T._inr(12345678) == "Rs 1,23,45,678" and T._inr(500) == "Rs 500"


def test_make_tools_default_plan_and_budget(loader):
    get_plan, what_if, loan_emi, scheme_facts = T.make_tools(PID, loader)
    assert get_plan.tool_name == "get_plan" and "plan_id" in json.dumps(get_plan.tool_spec)
    assert get_plan(plan_id="")["plan_id"] == PID  # empty id falls back to the session plan
    assert what_if(plan_id="made-up", kw=2)["plan_id"] == PID
    for _ in range(T.MAX_TOOL_CALLS - 2):
        scheme_facts(topic="subsidy")
    assert loan_emi(amount=100_000)["error"] == "TOOL_LIMIT"


# ---------------------------------------------------------------- endpoint


class FakeDynamo:
    def __init__(self):
        self.items: list[dict] = []
        self.plans: dict[str, dict] = {}

    def query(self, TableName, KeyConditionExpression, ExpressionAttributeValues, ScanIndexForward, Limit):
        sid = ExpressionAttributeValues[":s"]["S"]
        rows = sorted((i for i in self.items if i["sessionId"]["S"] == sid), key=lambda i: int(i["ts"]["N"]),
                      reverse=not ScanIndexForward)
        return {"Items": rows[:Limit]}

    def put_item(self, TableName, Item):
        self.items.append(Item)

    def get_item(self, TableName, Key):
        return {"Item": self.plans[Key["planId"]["S"]]} if Key["planId"]["S"] in self.plans else {}


@pytest.fixture
def db(monkeypatch):
    fake = FakeDynamo()
    monkeypatch.setattr(aws, "dynamodb", lambda: fake)
    return fake


class Runner:
    def __init__(self, reply="ok"):
        self.reply, self.calls = reply, []

    def __call__(self, history, message, plan_id, lang):
        self.calls.append({"history": history, "message": message, "plan_id": plan_id, "lang": lang})
        return self.reply, {"cycles": 1}


@pytest.mark.parametrize("body,code", [
    ({}, "EMPTY_MESSAGE"),
    ({"message": "   "}, "EMPTY_MESSAGE"),
    ({"message": "x" * 1001}, "MESSAGE_TOO_LONG"),
    ({"message": 5}, "BAD_REQUEST"),
    ({"message": "hi", "sessionId": "short"}, "BAD_SESSION"),
    ({"message": "hi", "sessionId": "bad id with spaces!!"}, "BAD_SESSION"),
    ({"message": "hi", "planId": "../../etc"}, "BAD_PLAN_ID"),
])
def test_chat_validation(db, body, code):
    runner = Runner()
    with pytest.raises(ApiError) as e:
        chat_mod.chat(body, runner)
    assert e.value.code == code and e.value.status == 400
    assert not runner.calls and not db.items


def test_chat_new_session_and_history(db):
    runner = Runner("Haan, worth it hai.")
    out = chat_mod.chat({"message": "Is it worth it?", "planId": PID, "lang": "hi"}, runner)
    sid = out["sessionId"]
    assert out["reply"] == "Haan, worth it hai." and chat_mod.SESSION_RE.match(sid)
    assert runner.calls[0] == {"history": [], "message": "Is it worth it?", "plan_id": PID, "lang": "hi"}
    assert db.items[0]["planId"]["S"] == PID and int(db.items[0]["expiresAt"]["N"]) > 0

    # Second turn: same session, no planId -> plan carried over, history sent oldest first.
    runner.reply = "3 kW: ..."
    out2 = chat_mod.chat({"message": "What if 3 kW?", "sessionId": sid, "lang": "bogus lang"}, runner)
    call = runner.calls[1]
    assert out2["sessionId"] == sid and call["plan_id"] == PID and call["lang"] is None
    assert call["history"] == [{"role": "user", "content": [{"text": "Is it worth it?"}]},
                               {"role": "assistant", "content": [{"text": "Haan, worth it hai."}]}]


def test_chat_keeps_last_10_turns(db):
    for i in range(14):
        db.put_item("t", {"sessionId": {"S": SID}, "ts": {"N": str(1000 + i)}, "user": {"S": f"q{i}"},
                          "assistant": {"S": f"a{i}"}, "expiresAt": {"N": "9999999999"}})
    runner = Runner()
    chat_mod.chat({"message": "next", "sessionId": SID}, runner)
    hist = runner.calls[0]["history"]
    assert len(hist) == 20 and hist[0]["content"][0]["text"] == "q4" and hist[-1]["content"][0]["text"] == "a13"


def test_chat_session_limit(db):
    for i in range(chat_mod.MAX_TURNS):
        db.put_item("t", {"sessionId": {"S": SID}, "ts": {"N": str(i)}, "user": {"S": "q"}, "assistant": {"S": "a"},
                          "expiresAt": {"N": "9999999999"}})
    runner = Runner()
    with pytest.raises(ApiError) as e:
        chat_mod.chat({"message": "one more", "sessionId": SID}, runner)
    assert e.value.code == "SESSION_LIMIT" and e.value.status == 429 and not runner.calls


def test_chat_scrubs_long_numbers(db):
    runner = Runner("Please don't share 1234 5678 9012 here.")
    out = chat_mod.chat({"message": "My Aadhaar is 1234 5678 9012, bank a/c 123456789012345"}, runner)
    assert "1234" not in runner.calls[0]["message"] and "[number removed]" in runner.calls[0]["message"]
    assert "5678" not in out["reply"]
    assert "9012" not in json.dumps(db.items)
    # Normal numbers stay.
    assert chat_mod.scrub("3 kW for ₹1,86,000 in 2026, 342 units") == "3 kW for ₹1,86,000 in 2026, 342 units"


def test_chat_model_error_is_503_and_not_saved(db):
    def boom(*_a):
        raise RuntimeError("model said something private")

    with pytest.raises(ApiError) as e:
        chat_mod.chat({"message": "hi"}, boom)
    assert e.value.code == "CHAT_UNAVAILABLE" and e.value.status == 503 and not db.items


def test_chat_empty_reply_gets_fallback(db):
    assert chat_mod.chat({"message": "hi"}, Runner("  "))["reply"] == chat_mod.FALLBACK_REPLY


def test_handler_route(db, monkeypatch):
    from api import handler

    monkeypatch.setattr(chat_mod, "run_agent", Runner("hello"))
    event = {"version": "2.0", "rawPath": "/chat", "headers": {"content-type": "application/json"},
             "requestContext": {"http": {"method": "POST", "path": "/chat"}, "stage": "$default"},
             "body": json.dumps({"message": "hi"}), "isBase64Encoded": False}
    resp = handler.app.resolve(event, None)
    assert resp["statusCode"] == 200
    assert json.loads(resp["body"])["reply"] == "hello"
    event["body"] = json.dumps({"message": ""})
    assert handler.app.resolve(event, None)["statusCode"] == 400


# ---------------------------------------------------------------- Strands loop, Bedrock stubbed


def _converse(content, stop):
    return {"output": {"message": {"role": "assistant", "content": content}}, "stopReason": stop,
            "usage": {"inputTokens": 10, "outputTokens": 5, "totalTokens": 15}, "metrics": {"latencyMs": 1}}


@pytest.fixture
def stub_model(monkeypatch, stored):
    from botocore.stub import Stubber
    from strands.models.bedrock import BedrockModel

    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "test")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "test")
    model = BedrockModel(model_id="moonshotai.kimi-k2.5", region_name="ap-south-1", streaming=False, max_tokens=100)
    stub = Stubber(model.client)
    stub.activate()
    seen: list[str] = []
    monkeypatch.setattr(chat_mod, "_model", lambda: model)
    monkeypatch.setattr(chat_mod, "load_stored_plan", lambda pid: seen.append(pid) or stored)
    yield stub, seen
    stub.assert_no_pending_responses()


TOOL_CALL = [{"toolUse": {"toolUseId": "t1", "name": "get_plan", "input": {"plan_id": PID}}}]


def test_run_agent_with_stubbed_bedrock(stub_model):
    stub, seen = stub_model
    stub.add_response("converse", _converse(TOOL_CALL, "tool_use"))
    stub.add_response("converse", _converse([{"text": "Haan, 5.7 saal mein paisa wapas."}], "end_turn"))
    reply, metrics = chat_mod.run_agent([], "Kya ye worth it hai?", PID, "hi")
    assert reply == "Haan, 5.7 saal mein paisa wapas."
    assert seen == [PID] and metrics["tools"] == {"get_plan": 1} and metrics["cycles"] == 2
    assert metrics["retried"] is False


def test_run_agent_retries_numbers_without_tools(stub_model):
    stub, seen = stub_model
    # First answer has a number but no tool call (taken from history): asked again, then uses the tool.
    stub.add_response("converse", _converse([{"text": "Subsidy ₹78,000 milegi."}], "end_turn"))
    stub.add_response("converse", _converse(TOOL_CALL, "tool_use"))
    stub.add_response("converse", _converse([{"text": "Subsidy ₹69,000 milegi."}], "end_turn"))
    reply, metrics = chat_mod.run_agent([], "Subsidy kitni?", PID, "hi")
    assert reply == "Subsidy ₹69,000 milegi."
    assert metrics["retried"] is True and metrics["tools"] == {"get_plan": 1} and seen == [PID]


def test_run_agent_no_retry_without_numbers(stub_model):
    stub, seen = stub_model
    stub.add_response("converse", _converse([{"text": "I can only help with solar and electricity."}], "end_turn"))
    reply, metrics = chat_mod.run_agent([], "Best biryani in Delhi?", PID, "en")
    assert reply.startswith("I can only help") and metrics["retried"] is False and not seen


# ---------------------------------------------------------------- prompt


def test_detect_script_and_prompt():
    from api.chat_prompt import detect_script, system_prompt

    assert detect_script("मुझे कितनी सब्सिडी मिलेगी?") == "Devanagari"
    assert detect_script("எவ்வளவு மானியம்?") == "Tamil"
    assert detect_script("Loan EMI kitna hoga?") is None
    p = system_prompt(PID, "hi", "मुझे कितनी सब्सिडी मिलेगी?")
    assert PID in p and "Devanagari script" in p and "App language: Hindi" in p
    assert "Aadhaar" in p and "check with your DISCOM" in p
    assert "no saved plan" in system_prompt(None, None, "hi")
