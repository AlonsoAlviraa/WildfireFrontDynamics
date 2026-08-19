from __future__ import annotations

from scripts.build_rcda_sealed_splits import assign_event_splits


def _row(uid: str, year: int, original_split: str) -> dict[str, object]:
    return {"uid": uid, "year": year, "original_split": original_split}


def test_upstream_test_event_is_reserved_whole_even_if_it_leaks() -> None:
    records = [
        _row("UID_FIRE_1", 2018, "train"),
        _row("UID_FIRE_1", 2018, "test"),
        _row("UID_FIRE_2", 2018, "train"),
        _row("UID_FIRE_3", 2018, "train"),
        _row("UID_FIRE_4", 2019, "train"),
        _row("UID_FIRE_5", 2019, "test"),
    ]
    assignments = assign_event_splits(records, validation_fraction=0.34)
    assert assignments["UID_FIRE_1"] == "test"
    assert assignments["UID_FIRE_5"] == "test"
    assert {assignments[uid] for uid in ("UID_FIRE_2", "UID_FIRE_3")} >= {
        "train",
        "val",
    }


def test_event_split_is_deterministic() -> None:
    records = [
        _row(f"UID_FIRE_{index}", 2015 + index % 5, "train")
        for index in range(50)
    ] + [_row("UID_FIRE_99", 2019, "test")]
    first = assign_event_splits(records)
    second = assign_event_splits(list(reversed(records)))
    assert first == second
    assert first["UID_FIRE_99"] == "test"
