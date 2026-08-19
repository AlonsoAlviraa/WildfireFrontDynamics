"""VAL-only domain adaptation of frozen RCDA checkpoints on WFIGS TRAIN."""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import torch

from wildfire_front.open_if.regional.base import _atomic_write_json, utc_now
from wildfire_front.open_if.regional.wfigs_rights import wfigs_rights_summary

from .rcda_sealed import (
    EARLY_STOP_THRESHOLDS,
    SEALED_CHANNEL_NAMES,
    ProbabilityAveragingEnsemble,
    SealedTrainConfig,
    build_model,
    evaluate_threshold_grid,
    make_loader,
    objective_loss,
    prepare_inputs_for_device,
    prepare_model_for_device,
    select_threshold_on_val,
    set_seed,
)
from .wfigs_external_eval import WFIGSExternalDataset

ADAPTATION_SCHEMA = "wfd_rcda_wfigs_domain_adaptation_v1"


@dataclass(frozen=True)
class WFIGSAdaptConfig:
    epochs: int = 30
    batch_size: int = 4
    lr: float = 1e-4
    weight_decay: float = 1e-4
    patience: int = 7
    num_workers: int = 0


def adapt_frozen_rcda_on_wfigs(
    *,
    final_summary_path: Path,
    wfigs_dataset_root: Path,
    rcda_normalization_path: Path,
    output_root: Path,
    adaptation: WFIGSAdaptConfig = WFIGSAdaptConfig(),
) -> dict[str, Any]:
    """Fine-tune each preregistered seed; never load the WFIGS TEST manifest."""

    final = json.loads(Path(final_summary_path).read_text(encoding="utf-8"))
    if final.get("test_used_for_selection") is not False:
        raise ValueError("source RCDA summary does not prove selection isolation")
    dataset_root = Path(wfigs_dataset_root)
    train_manifest = json.loads((dataset_root / "train.json").read_text(encoding="utf-8"))
    val_manifest = json.loads((dataset_root / "validation.json").read_text(encoding="utf-8"))
    train_events = set(train_manifest.get("events") or [])
    val_events = set(val_manifest.get("events") or [])
    if train_events & val_events:
        raise ValueError("WFIGS TRAIN and VALIDATION events overlap")
    normalization = json.loads(Path(rcda_normalization_path).read_text(encoding="utf-8"))
    if normalization.get("fit_split") != "train":
        raise ValueError("RCDA normalization was not fitted on RCDA TRAIN")
    train_set = WFIGSExternalDataset(
        dataset_root=dataset_root,
        manifest=train_manifest,
        rcda_normalization=normalization,
        augment=True,
    )
    val_set = WFIGSExternalDataset(
        dataset_root=dataset_root,
        manifest=val_manifest,
        rcda_normalization=normalization,
        augment=False,
    )
    train_loader = make_loader(
        train_set,
        batch_size=adaptation.batch_size,
        shuffle=True,
        weighted=False,
        num_workers=adaptation.num_workers,
    )
    val_loader = make_loader(
        val_set,
        batch_size=adaptation.batch_size,
        shuffle=False,
        weighted=False,
        num_workers=adaptation.num_workers,
    )
    output_root = Path(output_root)
    output_root.mkdir(parents=True, exist_ok=True)
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    reports: list[dict[str, Any]] = []
    adapted_models: list[torch.nn.Module] = []
    adapted_target_mode: str | None = None
    for source in final.get("reports") or []:
        config = source["config"]
        seed = int(config["seed"])
        set_seed(seed)
        source_checkpoint = Path(source["local_checkpoint"])
        source_payload = torch.load(source_checkpoint, map_location=device, weights_only=False)
        if source_payload.get("selection_split") != "val":
            raise ValueError(f"source checkpoint was not selected on RCDA VAL: {source_checkpoint}")
        model = prepare_model_for_device(
            build_model(
                str(config["model_name"]),
                in_channels=len(SEALED_CHANNEL_NAMES),
                base=int(config["base_channels"]),
            ),
            device,
        )
        model.load_state_dict(source_payload["state_dict"])
        optimizer = torch.optim.AdamW(
            model.parameters(), lr=adaptation.lr, weight_decay=adaptation.weight_decay
        )
        scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(
            optimizer,
            T_max=max(adaptation.epochs, 1),
            eta_min=adaptation.lr * 0.02,
        )
        scaler = torch.amp.GradScaler("cuda", enabled=device.type == "cuda")
        loss_config = SealedTrainConfig(
            dataset_root=str(dataset_root),
            protocol_dir=str(dataset_root),
            output_dir=str(output_root),
            model_name=str(config["model_name"]),
            seed=seed,
            target_mode=str(config["target_mode"]),
            tversky_alpha=float(config.get("tversky_alpha", 0.3)),
            tversky_beta=float(config.get("tversky_beta", 0.7)),
            tversky_gamma=float(config.get("tversky_gamma", 0.75)),
            extent_loss_weight=float(config.get("extent_loss_weight", 0.35)),
            growth_loss_weight=float(config.get("growth_loss_weight", 0.65)),
            evaluate_test=False,
        )
        checkpoint_path = output_root / f"wfigs_adapt_seed{seed}_best.pt"
        best_score = -1.0
        best_epoch = -1
        stale = 0
        history: list[dict[str, Any]] = []
        for epoch in range(1, adaptation.epochs + 1):
            started = time.perf_counter()
            model.train()
            running_loss = 0.0
            for batch in train_loader:
                inputs = prepare_inputs_for_device(batch["input"], device)
                growth = batch["target"].to(device)
                extent = batch["extent_target"].to(device)
                optimizer.zero_grad(set_to_none=True)
                with torch.amp.autocast("cuda", enabled=device.type == "cuda"):
                    logits = model(inputs)
                    loss = objective_loss(logits, inputs, growth, extent, loss_config)
                scaler.scale(loss).backward()
                scaler.step(optimizer)
                scaler.update()
                running_loss += float(loss.item())
            scheduler.step()
            grid = evaluate_threshold_grid(
                model,
                val_loader,
                device,
                EARLY_STOP_THRESHOLDS,
                prediction_mode=str(config["target_mode"]),
            )
            selected = max(grid.values(), key=lambda row: float(row["event_macro_iou"]))
            score = float(selected["event_macro_iou"])
            history.append(
                {
                    "epoch": epoch,
                    "train_loss": running_loss / max(len(train_loader), 1),
                    "val_event_macro_iou": score,
                    "val_threshold": selected["threshold"],
                    "seconds": time.perf_counter() - started,
                }
            )
            if score >= best_score:
                best_score = score
                best_epoch = epoch
                stale = 0
                torch.save(
                    {
                        "state_dict": model.state_dict(),
                        "selection_split": "wfigs_validation",
                        "source_selection_split": "val",
                        "source_checkpoint": str(source_checkpoint),
                        "model_name": config["model_name"],
                        "target_mode": config["target_mode"],
                        "base_channels": config["base_channels"],
                        "seed": seed,
                        "epoch": epoch,
                        "wfigs_test_evaluated": False,
                    },
                    checkpoint_path,
                )
            else:
                stale += 1
                if stale > adaptation.patience:
                    break
        best = torch.load(checkpoint_path, map_location=device, weights_only=False)
        model.load_state_dict(best["state_dict"])
        threshold, val_search = select_threshold_on_val(
            model,
            val_loader,
            device,
            prediction_mode=str(config["target_mode"]),
            selection_metric="event_macro_iou",
        )
        reports.append(
            {
                "config": config,
                "source_checkpoint": str(source_checkpoint),
                "checkpoint": str(checkpoint_path),
                "best_epoch": best_epoch,
                "selected_threshold": threshold,
                "threshold_selected_on": "wfigs_validation",
                "validation": val_search,
                "history": history,
                "test_evaluated": False,
            }
        )
        adapted_models.append(model)
        current_target_mode = str(config["target_mode"])
        if adapted_target_mode is None:
            adapted_target_mode = current_target_mode
        elif adapted_target_mode != current_target_mode:
            raise ValueError("adapted seed target modes differ")
    ensemble = None
    if len(adapted_models) >= 2:
        ensemble_model = ProbabilityAveragingEnsemble(adapted_models)
        ensemble_threshold, ensemble_val_search = select_threshold_on_val(
            ensemble_model,
            val_loader,
            device,
            prediction_mode=str(adapted_target_mode),
            selection_metric="event_macro_iou",
        )
        ensemble = {
            "aggregation": "mean_seed_probability",
            "members": len(adapted_models),
            "selected_threshold": ensemble_threshold,
            "threshold_selected_on": "wfigs_validation",
            "validation": ensemble_val_search,
            "test_used_for_selection": False,
            "test_evaluated": False,
        }
    report = {
        "schema": ADAPTATION_SCHEMA,
        "generated_at": utc_now(),
        "device": str(device),
        "configuration": {
            **adaptation.__dict__,
            "source_architecture_and_seeds_frozen_on": "rcda_validation",
            "epoch_and_threshold_selected_on": "wfigs_validation",
        },
        "counts": {
            "train_events": len(train_events),
            "validation_events": len(val_events),
            "reports": len(reports),
        },
        "reports": reports,
        "ensemble": ensemble,
        "test_used_for_selection": False,
        "wfigs_test_loaded": False,
        "rights": wfigs_rights_summary(),
        "claims": {
            "domain_adaptation_trained": True,
            "wfigs_test_performance_known": False,
            "public_checkpoint_release_allowed": False,
        },
    }
    _atomic_write_json(output_root / "WFIGS_ADAPTATION_VAL_ONLY.json", report)
    return report


__all__ = ["ADAPTATION_SCHEMA", "WFIGSAdaptConfig", "adapt_frozen_rcda_on_wfigs"]
