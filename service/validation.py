"""Validate and extract the model output against data/schema.json (stdlib only)."""
import json
import os

SCHEMA_PATH = os.environ.get(
    "SCHEMA_PATH",
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "schema.json"),
)


def load_schema(path=SCHEMA_PATH):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def validate_output(text, schema):
    """Return the parsed object if `text` is a valid four-key object per the schema, else None."""
    try:
        obj = json.loads(text)
    except (json.JSONDecodeError, TypeError):
        return None
    if not isinstance(obj, dict) or set(obj) != set(schema["keys"]):
        return None
    if obj["intent"] not in schema["intents"]:
        return None
    for k in ("date", "time", "place"):
        if obj[k] is not None and not isinstance(obj[k], str):
            return None
    return obj


def first_json_candidate(generated):
    """The model is trained to emit one JSON object then stop; keep only the first line."""
    return generated.strip().partition("\n")[0].strip()
