import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "worker"))
import clean  # noqa: E402


def rec(i, text, raw):
    return {"id": i, "text": text, "teacher_raw": raw}


def j(intent="alarm_set", date=None, time=None, place=None):
    return json.dumps({"intent": intent, "date": date, "time": time, "place": place})


def test_each_rejection_reason_is_counted_once_and_totals_add_up():
    records = [
        rec("C1", "set alarm for seven am", j(time="seven am")),              # kept
        rec("C2", "hello", "not json"),                                        # a
        rec("C3", "hello", '{"intent": "alarm_set"}'),                         # b
        rec("C4", "hello", j(intent="make_coffee")),                           # c
        rec("C5", "set alarm", j(time="seven am")),                            # d: slot not in command
        rec("C6", "set alarm for seven am", j(time="seven am")),               # duplicate of C1
        rec("C7", "what is the weather in london", j("weather_query", place="london")),  # kept
    ]
    kept, counts = clean.clean(records)
    assert [r["id"] for r in kept] == ["C1", "C7"]
    assert counts == {"input": 7, "a_invalid_json": 1, "b_wrong_keys": 1, "c_bad_intent": 1,
                      "d_slot_not_in_command": 1, "duplicates": 1, "kept": 2}


def test_duplicate_keeps_smallest_id_regardless_of_input_order():
    text = "set alarm for seven am"
    kept, counts = clean.clean([rec("C9", text, j(time="seven am")), rec("C2", text, j(time="seven am"))])
    assert [r["id"] for r in kept] == ["C2"] and counts["duplicates"] == 1


def test_non_string_slot_and_non_object_are_rejected():
    assert clean.classify(rec("C1", "alarm at 7", '{"intent": "alarm_set", "date": null, "time": 7, "place": null}')) == "d"
    assert clean.classify(rec("C1", "x", "[1, 2]")) == "b"
