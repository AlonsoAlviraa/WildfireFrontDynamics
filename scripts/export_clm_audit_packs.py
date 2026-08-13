#!/usr/bin/env python3
"""Export auditable CLM pack manifests (JSON+MD) without copying rasters.

Reuses score_if_weakness_board rows when a board JSON is present; otherwise
scores from --root. Retuerta/Polán stay NO_USE and are excluded from usable
packs. Never invents Vp/ha or writes infocam_anchors.json.

python scripts/export_clm_audit_packs.py
python scripts/export_clm_audit_packs.py --root <tmp> --out <tmp/packs>
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
_SCRIPTS = Path(__file__).resolve().parent
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

import score_if_weakness_board as board  # noqa: E402

USABLE_FIRE_IDS = (
    "hellin_2024",
    "cardoso_2025",
    "la_estrella_acom1_2024",
    "la_estrella_acom2_2024",
)
NO_USE_FIRE_IDS = ("retuerta_2025", "polan_2025")
R_KEYS = board.R_KEYS
H_KEYS = board.H_KEYS
DEFAULT_OUT = ROOT / "docs" / "data_campaigns" / "clm_audit_packs"


def _row_from_board(board_doc: dict[str, Any], fire_id: str) -> dict[str, Any] | None:
    for row in board_doc.get("fires") or []:
        if isinstance(row, dict) and row.get("fire_id") == fire_id:
            return row
    return None


def _score_row(root: Path, fire_id: str, anchors_path: Path) -> dict[str, Any]:
    doc = board.load_anchors(anchors_path)
    stable = set(board.process_one_fire_ids()) | set(doc["anchors"].keys()) | set(
        board.OPEN_PROXY_IDS
    )
    return board.score_fire(
        root, fire_id, anchors=doc["anchors"], stable_ids=stable
    )


def pack_from_row(row: dict[str, Any], *, usable: bool) -> dict[str, Any]:
    fire_id = str(row.get("fire_id") or "")
    named_no_use = fire_id in board.NO_USE_REASONS or fire_id in NO_USE_FIRE_IDS
    honesty = row.get("honesty_class")
    use_flag = "NO_USE" if named_no_use or honesty == "discard" else (
        row.get("use_flag") or "review"
    )
    if named_no_use:
        usable = False
        honesty = "discard"
        use_flag = "NO_USE"
    status = row.get("status")
    if named_no_use:
        status = "NO_USE"
    if status == "confirmed" and fire_id != "tobarra_20240802":
        # Packs never promote. Hellín/Cardoso/Estrella stay non-confirmed here.
        status = "pending_external"
    if honesty == "ml_strong" and fire_id != "tobarra_20240802":
        honesty = "ml_weak"
    return {
        "schema": "wfd_clm_audit_pack_v1",
        "fire_id": fire_id,
        "trees_present": list(row.get("trees_present") or []),
        "on_disk_tif_count": int(row.get("on_disk_tif_count") or 0),
        "on_disk_kmz_count": int(row.get("on_disk_kmz_count") or 0),
        "aligned_tif_count": int(row.get("aligned_tif_count") or 0),
        "mask_tif_count": int(row.get("mask_tif_count") or 0),
        "tree_fingerprint": row.get("tree_fingerprint") or "",
        "manifest_sha256": dict(row.get("manifest_sha256") or {}),
        "honesty_class": honesty,
        "use_flag": use_flag,
        "blocking_gap": row.get("blocking_gap"),
        "status": status,
        **{k: int(row.get(k) or 0) for k in (*R_KEYS, *H_KEYS)},
        "invented_vp_ha": False,
        "usable_pack": bool(usable) and use_flag != "NO_USE" and honesty != "discard",
        "no_rasters_copied": True,
        "confirmed": False if fire_id != "tobarra_20240802" else status == "confirmed",
        "ml_strong": honesty == "ml_strong",
    }


def render_pack_md(pack: dict[str, Any]) -> str:
    trees = pack.get("trees_present") or []
    tree_lines = "\n".join(f"- `{t}`" for t in trees) or "- *(none on this checkout)*"
    rh = " ".join(f"{k}={pack.get(k)}" for k in (*R_KEYS, *H_KEYS))
    return (
        f"# CLM audit pack — `{pack['fire_id']}`\n\n"
        f"> Inventory only. **Does not** copy GeoTIFFs/KMZ into git. "
        f"`invented_vp_ha=false`. Not a promote.\n\n"
        f"| Field | Value |\n"
        f"|-------|--------|\n"
        f"| honesty_class | `{pack.get('honesty_class')}` |\n"
        f"| use_flag | `{pack.get('use_flag')}` |\n"
        f"| status | `{pack.get('status')}` |\n"
        f"| blocking_gap | {pack.get('blocking_gap')} |\n"
        f"| tif / kmz / aligned / mask | "
        f"{pack.get('on_disk_tif_count')} / {pack.get('on_disk_kmz_count')} / "
        f"{pack.get('aligned_tif_count')} / {pack.get('mask_tif_count')} |\n"
        f"| tree_fingerprint | `{pack.get('tree_fingerprint') or '—'}` |\n"
        f"| usable_pack | `{pack.get('usable_pack')}` |\n"
        f"| invented_vp_ha | `false` |\n\n"
        f"R/H bits: `{rh}`\n\n"
        f"## Trees present\n\n{tree_lines}\n"
    )


def write_pack(pack: dict[str, Any], out_dir: Path) -> tuple[Path, Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / f"{pack['fire_id']}.json"
    md_path = out_dir / f"{pack['fire_id']}.md"
    json_path.write_text(json.dumps(pack, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    md_path.write_text(render_pack_md(pack), encoding="utf-8")
    return json_path, md_path


def load_optional_board(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(doc, dict) or doc.get("schema") != board.SCHEMA:
        return None
    return doc


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Export CLM audit pack manifests (no rasters copied)."
    )
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--anchors", type=Path, default=None)
    parser.add_argument("--board", type=Path, default=None)
    parser.add_argument("--out", type=Path, default=None)
    parser.add_argument("--fire-id", action="append", dest="fire_ids", default=None)
    args = parser.parse_args(argv)

    root = args.root.resolve()
    anchors_path = (args.anchors or (root / "data" / "infocam_anchors.json")).resolve()
    out_dir = (args.out or DEFAULT_OUT).resolve()
    board_path = args.board or (root / "docs" / "WEAKNESS_BOARD.json")
    board_doc = load_optional_board(board_path)

    if not anchors_path.is_file() and board_doc is None:
        print(f"error: missing anchors file: {anchors_path}", file=sys.stderr)
        return 1

    requested = list(args.fire_ids or (*USABLE_FIRE_IDS, *NO_USE_FIRE_IDS))
    known = set(board.TREE_MAP) | set(board.OPEN_PROXY_IDS) | set(board.NO_USE_REASONS)
    if anchors_path.is_file():
        try:
            known |= set(board.load_anchors(anchors_path)["anchors"].keys())
        except (OSError, ValueError) as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 1
    unknown = [fid for fid in requested if fid not in known]
    if unknown:
        print(f"error: unknown fire_id {unknown!r}", file=sys.stderr)
        return 1

    usable_written: list[str] = []
    excluded: list[dict[str, Any]] = []
    written: list[str] = []
    for fid in requested:
        row = _row_from_board(board_doc, fid) if board_doc else None
        if row is None:
            if not anchors_path.is_file():
                print(f"error: cannot score {fid}: missing anchors", file=sys.stderr)
                return 1
            try:
                row = _score_row(root, fid, anchors_path)
            except (OSError, ValueError) as exc:
                print(f"error: {exc}", file=sys.stderr)
                return 1
        named_no_use = fid in NO_USE_FIRE_IDS or fid in board.NO_USE_REASONS
        pack = pack_from_row(row, usable=not named_no_use)
        if named_no_use or not pack["usable_pack"]:
            excluded.append(
                {
                    "fire_id": fid,
                    "use_flag": pack["use_flag"],
                    "honesty_class": pack["honesty_class"],
                    "blocking_gap": pack["blocking_gap"],
                    "reason": board.NO_USE_REASONS.get(fid) or pack["blocking_gap"],
                }
            )
            if named_no_use:
                # Document why, but do not list as a usable pack file.
                note_path = out_dir / "NO_USE.md"
                out_dir.mkdir(parents=True, exist_ok=True)
                continue
        json_path, _md = write_pack(pack, out_dir)
        written.append(str(json_path))
        if pack["usable_pack"]:
            usable_written.append(fid)

    no_use_md = (
        "# CLM packs excluded as NO_USE\n\n"
        "These fires are **not** auditable usable packs.\n\n"
        "| fire_id | reason | honesty | use_flag |\n"
        "|---------|--------|---------|----------|\n"
        "| `retuerta_2025` | historical FOV (QA flag) | `discard` | `NO_USE` |\n"
        "| `polan_2025` | usable aligned/reproj stack < 3 frames | `discard` | `NO_USE` |\n\n"
        "Do not promote. Do not invent Vp/ha. See `docs/WEAKNESS_BOARD.md`.\n"
    )
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "NO_USE.md").write_text(no_use_md, encoding="utf-8")
    index = {
        "schema": "wfd_clm_audit_packs_index_v1",
        "as_of_utc": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        "usable_fire_ids": usable_written,
        "excluded_no_use": [
            {"fire_id": "retuerta_2025", "reason": "FOV"},
            {"fire_id": "polan_2025", "reason": ">=3 frames"},
        ],
        "invented_vp_ha": False,
        "rasters_copied": False,
        "note": "Manifests only. Retuerta/Polán excluded from usable packs.",
    }
    (out_dir / "index.json").write_text(
        json.dumps(index, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print(
        json.dumps(
            {
                "ok": True,
                "usable_fire_ids": usable_written,
                "excluded_no_use": [e["fire_id"] for e in index["excluded_no_use"]],
                "written": written,
                "invented_vp_ha": False,
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
