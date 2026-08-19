#!/usr/bin/env python3
"""Compare standard U-Net vs CLM residual on every runnable fire.

CLM = lab_scratch_frozen residual + frozen 8-ring decode (official complete-proxy).
Standard = same-fire arch-sweep winner (abs U-Net + keep-t0).

Does not overwrite official LATAM complete-proxy JSON or product weights.

  python scripts/run_standard_vs_clm_all_fires.py
  python scripts/run_standard_vs_clm_all_fires.py --fire AU_EMSR500_PERTH
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.run_latam_au_complete_model_iou import (  # noqa: E402
    OOD_GROWTH_THRESHOLD,
    eval_pack,
)
from scripts.run_latam_au_more_data_iou import (  # noqa: E402
    OFFICIAL_JSON,
    OFFICIAL_LATAM_COMPLETE_PROXY_IDS,
    rel_to_root,
)
from scripts.run_same_fire_multi_geometry import (  # noqa: E402
    DEFAULT_FIRE_IDS,
    ISOLATION_FIRE_IDS,
    evaluate_fire,
)
from wildfire_front.ml.feature_schema import schema_channel_count  # noqa: E402
from wildfire_front.ml.unet_train import UNetTrainConfig, build_model  # noqa: E402
from wildfire_front.open_if.latam_au import EMSR_PACK_SPECS, pack_dir_for  # noqa: E402
from wildfire_front.open_if.same_fire_model import load_frozen_unet  # noqa: E402

N_CH = schema_channel_count("legacy17")
DEFAULT_OUT = ROOT / "outputs" / "ml_eval" / "mega_goal_model" / "standard_vs_clm"
CLM_WEIGHTS = (
    ROOT / "outputs" / "ml_eval" / "mega_goal_model" / "lab_scratch_frozen" / "weights_pretrained_best.pt"
)
PRODUCT_WEIGHTS = ROOT / "models" / "clm_ensemble" / "weights_multi_if.pt"
STANDARD_WEIGHTS = (
    ROOT / "outputs" / "ml_eval" / "mega_goal_model" / "same_fire_arch_sweep" / "standard_abs_lr1e4.pt"
)
LATAM_ROOT = ROOT / "data" / "open_if" / "latam_au"
CALDOR_ROOT = ROOT / "data" / "open_if" / "external_bridge" / "US_FIREBENCH_CALDOR_2021"
TOBARRA_ROOT = ROOT / "data" / "real_if" / "pablo_geacam_20260730_tobarra"

LATAM_IDS = tuple(OFFICIAL_LATAM_COMPLETE_PROXY_IDS)
MORE_PACK_IDS = ("ES_EMSR685_TENERIFE", "BO_EMSR765", "MX_EMSR717")
STANDARD_IN_SAMPLE = frozenset(
    {"EMSR578_AOI01", "EMSR632_AOI01", "US_FIREBENCH_CALDOR_2021"}
)

EXIT_OK = 0
EXIT_MISSING = 1
EXIT_USAGE = 3

NOT_CLAIMS = (
    "additional standard-vs-CLM eval — not official LATAM complete-proxy replacement",
    "standard U-Net is in-sample on EMSR578/632/Caldor tiles only",
    "CLM residual is in-sample on the official LATAM 4-pack tiles",
    "not sealed transfer IoU",
    "not GO_Q",
    "not clm_ensemble_v34",
    "not catalog 0.8963",
    "not U1 TEST CLM (0.857)",
    "lab_ok_conaf remains false",
)


def utc_now() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def all_fire_ids() -> list[str]:
    ids = list(LATAM_IDS)
    ids.extend(DEFAULT_FIRE_IDS)
    ids.extend(ISOLATION_FIRE_IDS)
    ids.extend(MORE_PACK_IDS)
    out: list[str] = []
    seen: set[str] = set()
    for fire_id in ids:
        if fire_id in seen:
            continue
        seen.add(fire_id)
        out.append(fire_id)
    return out


def sample_kind(fire_id: str) -> str:
    clm_is = fire_id in LATAM_IDS
    std_is = fire_id in STANDARD_IN_SAMPLE
    if clm_is and std_is:
        return "both_in_sample"
    if clm_is:
        return "clm_in_sample"
    if std_is:
        return "standard_in_sample"
    return "both_ood"


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--fire", action="append", dest="fire_ids", default=None)
    ap.add_argument("--out-root", type=Path, default=DEFAULT_OUT)
    ap.add_argument("--max-patches", type=int, default=32)
    ap.add_argument("--list-only", action="store_true")
    return ap


def load_standard(weights: Path, device):
    import torch

    cfg = UNetTrainConfig(architecture="standard", model="small", target_mode="absolute")
    model = build_model(cfg, in_channels=N_CH + 1)
    state = torch.load(weights, map_location=device, weights_only=True)
    model.load_state_dict(state, strict=True)
    model.to(device)
    model.eval()
    return model


def summarize_row(raw: dict[str, Any], *, family: str) -> dict[str, Any]:
    model_iou = raw.get("complete_proxy_model_iou")
    if model_iou is None:
        model_iou = raw.get("model_iou")
    if model_iou is None:
        model_iou = raw.get("scored_model_iou")
    copy_iou = raw.get("copy_baseline_iou")
    if copy_iou is None:
        copy_iou = raw.get("usable_copy_mean")
    delta = raw.get("delta_vs_copy")
    if delta is None and model_iou is not None and copy_iou is not None:
        delta = float(model_iou) - float(copy_iou)
    n_used = raw.get("n_pairs_used")
    if n_used is None:
        n_used = raw.get("n_usable_pairs")
    skip = raw.get("skip_class") or raw.get("error") or raw.get("eval_status")
    if model_iou is None and not skip and n_used == 0:
        skip = "no_usable_pairs"
    return {
        "family": family,
        "ok": bool(raw.get("ok", model_iou is not None)),
        "skip": skip,
        "n_pairs_used": n_used,
        "model_iou": None if model_iou is None else float(model_iou),
        "copy_iou": None if copy_iou is None else float(copy_iou),
        "delta_vs_copy": None if delta is None else float(delta),
    }


def eval_latam_like(
    event_id: str,
    model,
    device,
    *,
    architecture: str,
    keep_t0: bool,
    max_patches: int,
) -> dict[str, Any]:
    spec = EMSR_PACK_SPECS.get(event_id) or {}
    if not spec:
        return {"ok": False, "error": "unknown_pack", "complete_proxy_model_iou": None}
    pack = pack_dir_for(LATAM_ROOT, spec)
    return eval_pack(
        event_id,
        pack,
        model,
        device,
        architecture=architecture,
        target_mode="delta" if architecture == "residual" else "absolute",
        growth_threshold=OOD_GROWTH_THRESHOLD if architecture == "residual" else 0.5,
        require_growth_ring=architecture == "residual",
        keep_t0=keep_t0,
        max_patches=max_patches,
    )


def eval_one(
    fire_id: str,
    model,
    device,
    *,
    architecture: str,
    decode: str,
    keep_t0: bool,
    max_patches: int,
    meteo_cache: dict[str, Any],
) -> tuple[dict[str, Any], str]:
    if fire_id in LATAM_IDS or fire_id in MORE_PACK_IDS:
        raw = eval_latam_like(
            fire_id,
            model,
            device,
            architecture=architecture,
            keep_t0=keep_t0,
            max_patches=max_patches,
        )
        family = "latam_official" if fire_id in LATAM_IDS else "latam_more"
        return summarize_row(raw, family=family), family
    raw = evaluate_fire(
        fire_id,
        caldor_root=CALDOR_ROOT,
        tobarra_root=TOBARRA_ROOT,
        model=model,
        device=device,
        max_patches=max_patches,
        meteo_mode="constant",
        meteo_cache=meteo_cache,
        architecture=architecture,
        decode=decode,
    )
    family = str(raw.get("family") or "same_fire")
    return summarize_row(raw, family=family), family


def write_scorecard(doc: dict[str, Any], path: Path) -> None:
    lines = [
        "# SCORECARD — standard U-Net vs CLM residual (all runnable fires)",
        "",
        "Additional comparison. Not official LATAM MET. Not GO_Q / v34.",
        "",
        f"- as_of_utc: `{doc.get('as_of_utc')}`",
        f"- clm_weights: `{doc.get('clm_weights')}`",
        f"- standard_weights: `{doc.get('standard_weights')}`",
        f"- n_fires_standard_beats_clm: `{doc.get('n_fires_standard_beats_clm')}`",
        f"- n_fires_compared: `{doc.get('n_fires_compared')}`",
        "",
        "| fire | split | copy | CLM IoU | std IoU | Δ std−CLM | Δ std−copy | skip |",
        "|---|---|---:|---:|---:|---:|---:|---|",
    ]
    for row in doc.get("fires") or []:
        clm = row.get("clm") or {}
        std = row.get("standard") or {}
        delta = row.get("standard_minus_clm")
        lines.append(
            "| {id} | {split} | {copy} | {clm} | {std} | {d} | {ds} | {skip} |".format(
                id=row.get("fire_id"),
                split=row.get("sample_kind"),
                copy="" if (std.get("copy_iou") if std.get("copy_iou") is not None else clm.get("copy_iou")) is None
                else f"{(std.get('copy_iou') if std.get('copy_iou') is not None else clm.get('copy_iou')):.6f}",
                clm="" if clm.get("model_iou") is None else f"{clm['model_iou']:.6f}",
                std="" if std.get("model_iou") is None else f"{std['model_iou']:.6f}",
                d="" if delta is None else f"{delta:+.6f}",
                ds="" if std.get("delta_vs_copy") is None else f"{std['delta_vs_copy']:+.6f}",
                skip=row.get("skip") or "",
            )
        )
    lines.extend(["", "## not_claims", ""])
    for claim in doc.get("not_claims") or NOT_CLAIMS:
        lines.append(f"- {claim}")
    lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    requested = list(args.fire_ids) if args.fire_ids else all_fire_ids()
    known = set(all_fire_ids())
    if args.list_only:
        for fire_id in requested:
            print(f"{fire_id}\t{sample_kind(fire_id)}")
        return EXIT_OK
    unknown = [f for f in requested if f not in known]
    if unknown:
        print(f"error: unknown fire {unknown}", file=sys.stderr)
        return EXIT_USAGE

    out = Path(args.out_root)
    if out.resolve() == OFFICIAL_JSON.resolve() or out.resolve() == OFFICIAL_JSON.parent.resolve():
        print("error: refusing to write over official complete-proxy JSON", file=sys.stderr)
        return EXIT_USAGE

    clm_w = CLM_WEIGHTS if CLM_WEIGHTS.is_file() else PRODUCT_WEIGHTS
    if not clm_w.is_file():
        print(f"error: missing CLM weights {clm_w}", file=sys.stderr)
        return EXIT_MISSING
    if not STANDARD_WEIGHTS.is_file():
        print(f"error: missing standard weights {STANDARD_WEIGHTS}", file=sys.stderr)
        return EXIT_MISSING

    official_before = OFFICIAL_JSON.read_bytes() if OFFICIAL_JSON.is_file() else None
    print(f"loading CLM {rel_to_root(clm_w)}", flush=True)
    clm_model, device = load_frozen_unet(clm_w)
    print(f"loading standard {rel_to_root(STANDARD_WEIGHTS)}", flush=True)
    std_model = load_standard(STANDARD_WEIGHTS, device)

    meteo_cache: dict[str, Any] = {}
    fires: list[dict[str, Any]] = []
    n_std_better = 0
    n_compared = 0
    for fire_id in requested:
        print(f"evaluating {fire_id} ...", flush=True)
        clm, fam = eval_one(
            fire_id,
            clm_model,
            device,
            architecture="residual",
            decode="frozen_ring",
            keep_t0=False,
            max_patches=int(args.max_patches),
            meteo_cache=meteo_cache,
        )
        std, _fam = eval_one(
            fire_id,
            std_model,
            device,
            architecture="standard",
            decode="keep_t0_thr",
            keep_t0=True,
            max_patches=int(args.max_patches),
            meteo_cache=meteo_cache,
        )
        delta = None
        if clm.get("model_iou") is not None and std.get("model_iou") is not None:
            delta = float(std["model_iou"]) - float(clm["model_iou"])
            n_compared += 1
            if delta > 0:
                n_std_better += 1
        skip = None
        if clm.get("model_iou") is None and std.get("model_iou") is None:
            skip = std.get("skip") or clm.get("skip")
        row = {
            "fire_id": fire_id,
            "family": fam,
            "sample_kind": sample_kind(fire_id),
            "clm": clm,
            "standard": std,
            "standard_minus_clm": delta,
            "standard_beats_clm": None if delta is None else bool(delta > 0),
            "skip": skip,
        }
        fires.append(row)
        print(
            f"  {fire_id} clm={clm.get('model_iou')} std={std.get('model_iou')} "
            f"d={delta} skip={skip}",
            flush=True,
        )

    ood = [f for f in fires if f.get("sample_kind") == "both_ood" and f.get("standard_minus_clm") is not None]
    ood_wins = sum(1 for f in ood if f.get("standard_beats_clm"))
    doc = {
        "schema": "wfd_standard_vs_clm_all_fires_v1",
        "as_of_utc": utc_now(),
        "clm_weights": rel_to_root(clm_w),
        "standard_weights": rel_to_root(STANDARD_WEIGHTS),
        "clm_decode": "frozen_ring_8_k1_0.90",
        "standard_decode": "keep_t0_thr_0.50",
        "n_fires": len(fires),
        "n_fires_compared": n_compared,
        "n_fires_standard_beats_clm": n_std_better,
        "n_ood_compared": len(ood),
        "n_ood_standard_beats_clm": ood_wins,
        "fires": fires,
        "not_claims": list(NOT_CLAIMS),
        "go_q": "partial",
        "lab_ok_conaf": False,
        "sold_as_clm_ensemble_v34": False,
    }
    out.mkdir(parents=True, exist_ok=True)
    (out / "standard_vs_clm.json").write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")
    write_scorecard(doc, out / "SCORECARD.md")
    if official_before is not None and OFFICIAL_JSON.read_bytes() != official_before:
        print("error: official LATAM JSON changed", file=sys.stderr)
        return EXIT_USAGE
    print(
        f"wrote {rel_to_root(out / 'SCORECARD.md')} "
        f"std_beats_clm={n_std_better}/{n_compared} ood={ood_wins}/{len(ood)}"
    )
    return EXIT_OK


if __name__ == "__main__":
    raise SystemExit(main())
