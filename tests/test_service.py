import json
import os
import sys

os.environ["SKIP_MODEL_LOAD"] = "1"
os.environ["MODEL_VERSION"] = "vtest"
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "service"))
os.environ.setdefault("SCHEMA_PATH", os.path.join(os.path.dirname(__file__), "..", "data", "schema.json"))

from fastapi.testclient import TestClient  # noqa: E402

import app as service  # noqa: E402
import validation  # noqa: E402

GOOD = json.dumps({"intent": "weather_query", "date": None, "time": None, "place": "london"})


class FakeModel:
    def __init__(self, output):
        self.output = output

    def generate(self, text):
        return self.output


def client(model=None):
    service.state.model = model
    return TestClient(service.app)


def test_readyz_is_503_until_model_loaded_and_healthz_always_200():
    c = client(None)
    assert c.get("/healthz").status_code == 200
    assert c.get("/readyz").status_code == 503
    service.state.model = FakeModel(GOOD)
    assert c.get("/readyz").status_code == 200


def test_parse_returns_json_and_both_headers():
    c = client(FakeModel(" " + GOOD))
    r = c.post("/parse", json={"text": "weather in london"})
    assert r.status_code == 200
    assert r.json() == json.loads(GOOD)
    assert r.headers["X-Model-Version"] == "vtest"
    assert r.headers["X-Served-By"]


def test_invalid_model_output_gives_500_with_exact_body(monkeypatch):
    c = client(FakeModel("this is not json"))
    r = c.post("/parse", json={"text": "hi"})
    assert r.status_code == 500 and r.json() == {"error": "invalid_model_output"}


def test_fault_inject_replaces_output(monkeypatch):
    monkeypatch.setenv("FAULT_INJECT", "1")
    c = client(FakeModel(GOOD))
    r = c.post("/parse", json={"text": "hi"})
    assert r.status_code == 500 and r.json() == {"error": "invalid_model_output"}


def test_validator_rejects_bad_intent_extra_keys_and_non_string_slots():
    schema = validation.load_schema()
    ok = {"intent": "alarm_set", "date": None, "time": "six pm", "place": None}
    assert validation.validate_output(json.dumps(ok), schema) == ok
    assert validation.validate_output(json.dumps({**ok, "intent": "dance"}), schema) is None
    assert validation.validate_output(json.dumps({**ok, "extra": 1}), schema) is None
    assert validation.validate_output(json.dumps({**ok, "time": 6}), schema) is None
