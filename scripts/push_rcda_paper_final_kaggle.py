#!/usr/bin/env python3
"""Push the preregistered multi-seed RCDA final evaluation to Kaggle."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.push_rcda_paper_kaggle import _helpers_source  # noqa: E402
from scripts.push_rcda_sealed_kaggle import _protocol_blobs  # noqa: E402

STAGE = ROOT / "kaggle_job/_push_rcda_paper_final"
KERNEL_ID = "alonsoalvira/wfd-rcda-paper-final-v1"


def _validated_frozen(path: Path) -> dict[str, Any]:
    document = json.loads(path.read_text(encoding="utf-8"))
    if document.get("schema") != "wfd_rcda_paper_frozen_recipe_v1":
        raise ValueError("unexpected frozen recipe schema")
    if document.get("test_observed_during_tuning") is not False:
        raise ValueError("frozen recipe did not preserve TEST isolation")
    data_contract = document.get("data_contract") or {}
    if (
        data_contract.get("rcda_archive_md5") != "d7856d77dcb823d0bdb5e10c6bac4f87"
        or data_contract.get("event_split_seed") != "wfd_rcda_event_split_v1"
        or data_contract.get("normalization_fit_split") != "train"
        or len(data_contract.get("protocol_sha256") or {}) != 4
        or len(str(data_contract.get("pretest_decision_log_sha256") or "")) != 64
    ):
        raise ValueError("frozen recipe does not identify the sealed RCDA data contract")
    final = document.get("final_evaluation") or {}
    if final.get("recipe_changes_after_test_forbidden") is not True:
        raise ValueError("frozen recipe does not forbid post-TEST changes")
    seeds = final.get("seeds") or []
    if len(seeds) < 3 or len(set(seeds)) != len(seeds):
        raise ValueError("final evaluation requires at least three unique seeds")
    ensemble = final.get("secondary_probability_ensemble") or {}
    if (
        ensemble.get("aggregation") != "mean_seed_probability"
        or ensemble.get("threshold_selected_on") != "val"
        or ensemble.get("changes_primary_endpoint_or_gate") is not False
    ):
        raise ValueError("frozen recipe does not preregister the probability ensemble")
    decoder = final.get("secondary_spatial_decoder")
    if decoder is not None and (
        decoder.get("role") != "preregistered_secondary_spatial_decoder"
        or decoder.get("applied_to") != "mean_seed_probability"
        or decoder.get("threshold_and_geometry_selected_on") != "val"
        or decoder.get("changes_primary_endpoint_or_gate") is not False
        or int(decoder.get("dilation_radius_px", -1)) < 0
        or len(str(decoder.get("source_artifact_sha256") or "")) != 64
    ):
        raise ValueError("frozen recipe contains an invalid spatial decoder")
    return document


def self_contained_final_kernel(frozen: dict[str, Any]) -> str:
    library = (ROOT / "wildfire_front/ml/rcda_sealed.py").read_text(encoding="utf-8")
    blobs = json.dumps(_protocol_blobs(), indent=2)
    embedded = repr(json.dumps(frozen, sort_keys=True))
    return f'''{library.rstrip()}

import hashlib
import os
import shutil
import subprocess
import sys
import zipfile

{_helpers_source()}
PROTOCOL_BLOBS = {blobs}
FROZEN_RECIPE = json.loads({embedded})

def main() -> int:
    output = Path("/kaggle/working/rcda_paper_final")
    output.mkdir(parents=True, exist_ok=True)
    dataset = locate_dataset()
    protocol = locate_protocol(Path("/kaggle/input/wfd-rcda-sealed"))
    recipe = FROZEN_RECIPE["winner"]["config"]
    reports = []
    for seed in FROZEN_RECIPE["final_evaluation"]["seeds"]:
        report_path = output / (str(recipe["run_name"]) + f"_final_seed{{seed}}_report.json")
        if report_path.is_file():
            completed = json.loads(report_path.read_text(encoding="utf-8"))
            if (
                int(completed["config"]["seed"]) != int(seed)
                or completed.get("threshold_selected_on") != "val"
                or completed.get("test_used_for_selection") is not False
                or completed.get("test_evaluated") is not True
                or "test_once" not in completed
            ):
                raise ValueError(f"invalid resumable final report: {{report_path}}")
            reports.append(completed)
            continue
        config = SealedTrainConfig(
            dataset_root=str(dataset),
            protocol_dir=str(protocol),
            output_dir=str(output),
            run_name=str(recipe["run_name"]) + "_final",
            model_name=str(recipe["model_name"]),
            target_mode=str(recipe["target_mode"]),
            seed=int(seed),
            epochs=int(recipe["epochs"]),
            batch_size=int(recipe["batch_size"]),
            lr=float(recipe["lr"]),
            weight_decay=float(recipe["weight_decay"]),
            patience=int(recipe["patience"]),
            num_workers=2,
            loss_name=str(recipe["loss_name"]),
            tversky_alpha=float(recipe["tversky_alpha"]),
            tversky_beta=float(recipe["tversky_beta"]),
            tversky_gamma=float(recipe["tversky_gamma"]),
            extent_loss_weight=float(recipe["extent_loss_weight"]),
            growth_loss_weight=float(recipe["growth_loss_weight"]),
            base_channels=int(recipe["base_channels"]),
            scheduler_name=str(recipe["scheduler_name"]),
            selection_metric=str(recipe["selection_metric"]),
            weighted_sampling=bool(recipe["weighted_sampling"]),
            sampling_strategy=str(recipe.get("sampling_strategy", "size_event_power")),
            event_balance_power=float(recipe.get("event_balance_power", 0.5)),
            evaluate_test=True,
            compute_paper_metrics=False,
            amp=True,
        )
        reports.append(train_sealed(config))
    for report in reports:
        checkpoint_bytes = Path(report["checkpoint"]).read_bytes()
        report["checkpoint_sha256"] = hashlib.sha256(checkpoint_bytes).hexdigest()
    protocol_document = load_protocol(protocol)
    val_dataset = SealedRCDADataset(
        dataset,
        protocol_document["manifests"]["val"],
        protocol_document["normalization"],
        augment=False,
    )
    test_dataset = SealedRCDADataset(
        dataset,
        protocol_document["manifests"]["test"],
        protocol_document["normalization"],
        augment=False,
    )
    val_loader = make_loader(
        val_dataset, batch_size=8, shuffle=False, weighted=False, num_workers=2
    )
    test_loader = make_loader(
        test_dataset, batch_size=8, shuffle=False, weighted=False, num_workers=2
    )
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    seed_models = []
    for report in reports:
        payload = torch.load(report["checkpoint"], map_location=device, weights_only=False)
        model = prepare_model_for_device(
            build_model(
                str(recipe["model_name"]),
                in_channels=len(SEALED_CHANNEL_NAMES),
                base=int(recipe["base_channels"]),
            ),
            device,
        )
        model.load_state_dict(payload["state_dict"])
        model.eval()
        seed_models.append(model)
    ensemble_model = ProbabilityAveragingEnsemble(seed_models).to(device)
    ensemble_threshold, ensemble_val = select_threshold_on_val(
        ensemble_model,
        val_loader,
        device,
        prediction_mode=str(recipe["target_mode"]),
        selection_metric=str(recipe["selection_metric"]),
    )
    ensemble_test = evaluate_split(
        ensemble_model,
        test_loader,
        device,
        ensemble_threshold,
        prediction_mode=str(recipe["target_mode"]),
        paper_metrics=False,
    )
    decoder_recipe = FROZEN_RECIPE["final_evaluation"].get("secondary_spatial_decoder")
    decoder_report = None
    if decoder_recipe is not None:
        decoder_test = evaluate_split_postprocessed(
            ensemble_model,
            test_loader,
            device,
            float(decoder_recipe["threshold"]),
            prediction_mode=str(recipe["target_mode"]),
            dilation_radius=int(decoder_recipe["dilation_radius_px"]),
            require_t0_connection=bool(decoder_recipe["require_t0_connection"]),
        )
        decoder_report = {{
            "role": decoder_recipe["role"],
            "applied_to": decoder_recipe["applied_to"],
            "source_artifact_sha256": decoder_recipe["source_artifact_sha256"],
            "threshold_and_geometry_selected_on": "val",
            "threshold": float(decoder_recipe["threshold"]),
            "dilation_radius_px": int(decoder_recipe["dilation_radius_px"]),
            "require_t0_connection": bool(decoder_recipe["require_t0_connection"]),
            "test_used_for_selection": False,
            "test_evaluated": True,
            "test_once": decoder_test,
        }}
    test_event_macro = np.asarray(
        [row["test_once"]["event_macro_iou"] for row in reports], dtype=np.float64
    )
    test_pooled = np.asarray(
        [row["test_once"]["iou"] for row in reports], dtype=np.float64
    )
    summary = {{
        "schema": "wfd_rcda_paper_final_v1",
        "frozen_recipe": FROZEN_RECIPE,
        "selection_split": "val",
        "test_used_for_selection": False,
        "test_evaluated_after_recipe_frozen": True,
        "n_preregistered_seeds": len(reports),
        "primary": {{
            "metric": "test_event_macro_iou_mean_across_seeds",
            "mean": float(test_event_macro.mean()),
            "sample_std": float(test_event_macro.std(ddof=1)),
            "values": test_event_macro.tolist(),
        }},
        "pooled_iou": {{
            "mean": float(test_pooled.mean()),
            "sample_std": float(test_pooled.std(ddof=1)),
            "values": test_pooled.tolist(),
        }},
        "ensemble": {{
            "aggregation": "mean_seed_probability",
            "threshold_selected_on": "val",
            "selected_threshold": ensemble_threshold,
            "val": ensemble_val,
            "test_used_for_selection": False,
            "test_evaluated": True,
            "test_once": ensemble_test,
        }},
        "decoder": decoder_report,
        "reports": reports,
    }}
    (output / "FINAL_SUMMARY.json").write_text(
        json.dumps(summary, indent=2) + "\\n", encoding="utf-8"
    )
    print(json.dumps({{
        "primary": summary["primary"],
        "pooled": summary["pooled_iou"],
        "ensemble_event_macro_iou": summary["ensemble"]["test_once"]["event_macro_iou"],
        "decoder_event_macro_iou": (
            summary["decoder"]["test_once"]["event_macro_iou"]
            if summary["decoder"] is not None
            else None
        ),
    }}, indent=2))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
'''


def stage_kernel(frozen_path: Path) -> Path:
    frozen = _validated_frozen(frozen_path)
    if STAGE.exists():
        shutil.rmtree(STAGE)
    STAGE.mkdir(parents=True)
    source = self_contained_final_kernel(frozen)
    compile(source, "run_rcda_paper_final.py", "exec")
    (STAGE / "run_rcda_paper_final.py").write_text(source, encoding="utf-8")
    frozen_sha = hashlib.sha256(frozen_path.read_bytes()).hexdigest()
    metadata = {
        "id": KERNEL_ID,
        "title": "wfd-rcda-paper-final-v1",
        "code_file": "run_rcda_paper_final.py",
        "language": "python",
        "kernel_type": "script",
        "is_private": True,
        "enable_gpu": True,
        "enable_internet": False,
        "machine_shape": "NvidiaTeslaT4",
        "dataset_sources": [
            "alonsoalvira/wfd-rcda-sealed",
            "alonsoalvira/wfd-rcda-archive",
        ],
        "competition_sources": [],
        "kernel_sources": [],
        "_frozen_recipe_sha256": frozen_sha,
    }
    kaggle_metadata = {key: value for key, value in metadata.items() if not key.startswith("_")}
    (STAGE / "kernel-metadata.json").write_text(
        json.dumps(kaggle_metadata, indent=2) + "\n", encoding="utf-8"
    )
    (STAGE / "FROZEN_RECIPE_SHA256.txt").write_text(frozen_sha + "\n", encoding="utf-8")
    return STAGE


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("frozen_recipe", type=Path)
    parser.add_argument("--stage-only", action="store_true")
    args = parser.parse_args()
    stage = stage_kernel(args.frozen_recipe)
    if not args.stage_only:
        subprocess.run(["kaggle", "kernels", "push", "-p", str(stage)], check=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
