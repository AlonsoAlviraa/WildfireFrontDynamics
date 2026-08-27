"""VAL-only domain adaptation of frozen RCDA checkpoints on WFIGS TRAIN."""

from __future__ import annotations

import json
import time
from collections.abc import Callable
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
    evaluate_growth_average_precision,
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
    max_grad_norm: float = 5.0
    trainable_scope: str = "all"
    front_ring_bce_weight: float = 0.0
    front_ring_radius_px: float = 16.0
    background_bce_weight: float = 0.0
    balanced_growth_bce_weight: float = 0.0
    far_background_bce_weight: float = 0.0
    far_background_min_distance_px: float = 12.0
    tversky_alpha: float | None = None
    tversky_beta: float | None = None
    tversky_gamma: float | None = None
    target_mode: str | None = None
    augment: bool = True
    include_valid_mask: bool = False
    include_geometry_features: bool = False
    include_tile_standardized_features: bool = False
    source_seeds: tuple[int, ...] | None = None
    focal_bce_weight: float = 0.0
    focal_gamma: float = 2.0
    epoch_selection_metric: str = "event_macro_iou"
    weighted_sampling: bool = False
    event_balance_power: float = 1.0
    sampling_strategy: str = "uniform_events"


def configure_trainable_scope(
    model: torch.nn.Module,
    scope: str,
) -> list[torch.nn.Parameter]:
    """Freeze the source encoder for low-data decoder-only adaptation."""

    if scope not in {"all", "decoder", "decoder_plus_input", "decoder_plus_enc1"}:
        raise ValueError(f"unknown WFIGS adaptation trainable scope: {scope!r}")
    frozen_prefixes = ("enc1.", "enc2.", "enc3.", "enc4.", "context.")
    trainable: list[torch.nn.Parameter] = []
    for name, parameter in model.named_parameters():
        parameter.requires_grad = (
            scope == "all"
            or not name.startswith(frozen_prefixes)
            or (
                scope == "decoder_plus_input"
                and name in {"enc1.body.0.weight", "enc1.skip.weight"}
            )
            or (scope == "decoder_plus_enc1" and name.startswith("enc1."))
        )
        if parameter.requires_grad:
            trainable.append(parameter)
    if not trainable:
        raise ValueError("WFIGS adaptation has no trainable parameters")
    return trainable


def set_adaptation_train_mode(model: torch.nn.Module, scope: str) -> None:
    """Enter train mode while keeping frozen encoder normalization immutable."""

    model.train()
    if scope in {"decoder", "decoder_plus_input", "decoder_plus_enc1"}:
        for name, module in model.named_children():
            frozen = {"enc2", "enc3", "enc4", "context"}
            if scope == "decoder":
                frozen.add("enc1")
            if name in frozen:
                module.eval()


def adapt_frozen_rcda_on_wfigs(
    *,
    final_summary_path: Path,
    wfigs_dataset_root: Path,
    rcda_normalization_path: Path,
    output_root: Path,
    adaptation: WFIGSAdaptConfig = WFIGSAdaptConfig(),
    progress_callback: Callable[[dict[str, Any]], None] | None = None,
) -> dict[str, Any]:
    """Fine-tune each preregistered seed; never load the WFIGS TEST manifest."""

    if adaptation.max_grad_norm <= 0.0:
        raise ValueError("WFIGS adaptation max_grad_norm must be positive")
    if not torch.isfinite(torch.tensor(adaptation.background_bce_weight)) or adaptation.background_bce_weight < 0.0:
        raise ValueError("WFIGS adaptation background_bce_weight must be finite and non-negative")
    if (
        not torch.isfinite(torch.tensor(adaptation.balanced_growth_bce_weight))
        or adaptation.balanced_growth_bce_weight < 0.0
    ):
        raise ValueError(
            "WFIGS adaptation balanced_growth_bce_weight must be finite and non-negative"
        )
    if (
        not torch.isfinite(torch.tensor(adaptation.far_background_bce_weight))
        or adaptation.far_background_bce_weight < 0.0
    ):
        raise ValueError(
            "WFIGS adaptation far_background_bce_weight must be finite and non-negative"
        )
    if not 0.0 < adaptation.far_background_min_distance_px <= 32.0:
        raise ValueError("WFIGS adaptation far-background distance must be within (0, 32]")
    if adaptation.epoch_selection_metric not in {"event_macro_iou", "growth_ap"}:
        raise ValueError(
            f"unknown WFIGS epoch selection metric: {adaptation.epoch_selection_metric!r}"
        )
    if not torch.isfinite(torch.tensor(adaptation.focal_bce_weight)) or adaptation.focal_bce_weight < 0.0:
        raise ValueError("WFIGS adaptation focal_bce_weight must be finite and non-negative")
    if not torch.isfinite(torch.tensor(adaptation.focal_gamma)) or adaptation.focal_gamma < 0.0:
        raise ValueError("WFIGS adaptation focal_gamma must be finite and non-negative")
    if not 0.0 <= adaptation.event_balance_power <= 1.0:
        raise ValueError("WFIGS adaptation event_balance_power must be within [0, 1]")
    if adaptation.sampling_strategy not in {"uniform_events", "size_event_power"}:
        raise ValueError(
            f"unknown WFIGS sampling strategy: {adaptation.sampling_strategy!r}"
        )
    for name, value in (
        ("tversky_alpha", adaptation.tversky_alpha),
        ("tversky_beta", adaptation.tversky_beta),
        ("tversky_gamma", adaptation.tversky_gamma),
    ):
        if value is not None and not 0.0 < value <= 1.0:
            raise ValueError(f"WFIGS adaptation {name} must be within (0, 1]")
    if adaptation.target_mode is not None and adaptation.target_mode not in {
        "growth",
        "extent",
        "hybrid",
        "multitask",
    }:
        raise ValueError(f"unknown WFIGS adaptation target mode: {adaptation.target_mode!r}")
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
        augment=adaptation.augment,
        include_valid_mask=adaptation.include_valid_mask,
        include_geometry_features=adaptation.include_geometry_features,
        include_tile_standardized_features=adaptation.include_tile_standardized_features,
    )
    val_set = WFIGSExternalDataset(
        dataset_root=dataset_root,
        manifest=val_manifest,
        rcda_normalization=normalization,
        augment=False,
        include_valid_mask=adaptation.include_valid_mask,
        include_geometry_features=adaptation.include_geometry_features,
        include_tile_standardized_features=adaptation.include_tile_standardized_features,
    )
    train_loader = make_loader(
        train_set,
        batch_size=adaptation.batch_size,
        shuffle=not adaptation.weighted_sampling,
        weighted=adaptation.weighted_sampling,
        num_workers=adaptation.num_workers,
        event_balance_power=adaptation.event_balance_power,
        sampling_strategy=adaptation.sampling_strategy,
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
    sources = list(final.get("reports") or [])
    if adaptation.source_seeds is not None:
        requested_seeds = set(adaptation.source_seeds)
        sources = [source for source in sources if int(source["config"]["seed"]) in requested_seeds]
        if {int(source["config"]["seed"]) for source in sources} != requested_seeds:
            raise ValueError("requested WFIGS adaptation seed is absent from RCDA final")
    if not sources:
        raise ValueError("WFIGS adaptation requires at least one RCDA source report")
    for source in sources:
        config = source["config"]
        seed = int(config["seed"])
        target_mode = str(adaptation.target_mode or config["target_mode"])
        set_seed(seed)
        source_checkpoint = Path(source["local_checkpoint"])
        source_payload = torch.load(source_checkpoint, map_location=device, weights_only=False)
        if source_payload.get("selection_split") != "val":
            raise ValueError(f"source checkpoint was not selected on RCDA VAL: {source_checkpoint}")
        input_channels = (
            len(SEALED_CHANNEL_NAMES)
            + int(adaptation.include_valid_mask)
            + 3 * int(adaptation.include_geometry_features)
            + 4 * int(adaptation.include_tile_standardized_features)
        )
        model = prepare_model_for_device(
            build_model(
                str(config["model_name"]),
                in_channels=input_channels,
                base=int(config["base_channels"]),
            ),
            device,
        )
        source_state = source_payload["state_dict"]
        if (
            adaptation.include_valid_mask
            or adaptation.include_geometry_features
            or adaptation.include_tile_standardized_features
        ):
            target_state = model.state_dict()
            for name, value in source_state.items():
                if name not in target_state:
                    raise ValueError(f"augmented source parameter missing from model: {name}")
                if target_state[name].shape == value.shape:
                    target_state[name] = value
                elif (
                    target_state[name].ndim == 4
                    and value.ndim == 4
                    and target_state[name].shape[0] == value.shape[0]
                    and target_state[name].shape[1] > value.shape[1]
                    and target_state[name].shape[2:] == value.shape[2:]
                ):
                    # The residual stem has both a 3x3 body projection and a
                    # 1x1 skip projection.  Preserve the source channels and
                    # start the learned valid-data channel at zero for either
                    # branch, so the adapted model initially matches RCDA.
                    target_state[name][:, : value.shape[1]] = value
                    target_state[name][:, value.shape[1] :] = 0.0
                else:
                    raise ValueError(f"augmented source parameter shape mismatch: {name}")
            model.load_state_dict(target_state)
        else:
            model.load_state_dict(source_state)
        trainable_parameters = configure_trainable_scope(
            model,
            adaptation.trainable_scope,
        )
        optimizer = torch.optim.AdamW(
            trainable_parameters,
            lr=adaptation.lr,
            weight_decay=adaptation.weight_decay,
        )
        scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(
            optimizer,
            T_max=max(adaptation.epochs, 1),
            eta_min=adaptation.lr * 0.02,
        )
        scaler = torch.amp.GradScaler(
            "cuda",
            enabled=device.type == "cuda",
            init_scale=1024.0,
        )
        loss_config = SealedTrainConfig(
            dataset_root=str(dataset_root),
            protocol_dir=str(dataset_root),
            output_dir=str(output_root),
            model_name=str(config["model_name"]),
            seed=seed,
            target_mode=target_mode,
            tversky_alpha=float(
                adaptation.tversky_alpha
                if adaptation.tversky_alpha is not None
                else config.get("tversky_alpha", 0.3)
            ),
            tversky_beta=float(
                adaptation.tversky_beta
                if adaptation.tversky_beta is not None
                else config.get("tversky_beta", 0.7)
            ),
            tversky_gamma=float(
                adaptation.tversky_gamma
                if adaptation.tversky_gamma is not None
                else config.get("tversky_gamma", 0.75)
            ),
            extent_loss_weight=float(config.get("extent_loss_weight", 0.35)),
            growth_loss_weight=float(config.get("growth_loss_weight", 0.65)),
            front_ring_bce_weight=adaptation.front_ring_bce_weight,
            front_ring_radius_px=adaptation.front_ring_radius_px,
            background_bce_weight=adaptation.background_bce_weight,
            balanced_growth_bce_weight=adaptation.balanced_growth_bce_weight,
            far_background_bce_weight=adaptation.far_background_bce_weight,
            far_background_min_distance_px=adaptation.far_background_min_distance_px,
            focal_bce_weight=adaptation.focal_bce_weight,
            focal_gamma=adaptation.focal_gamma,
            evaluate_test=False,
        )
        checkpoint_path = output_root / f"wfigs_adapt_seed{seed}_best.pt"
        best_score = -1.0
        best_epoch = -1
        stale = 0
        history: list[dict[str, Any]] = []
        for epoch in range(1, adaptation.epochs + 1):
            started = time.perf_counter()
            set_adaptation_train_mode(model, adaptation.trainable_scope)
            running_loss = 0.0
            for batch in train_loader:
                inputs = prepare_inputs_for_device(batch["input"], device)
                growth = batch["target"].to(device)
                extent = batch["extent_target"].to(device)
                optimizer.zero_grad(set_to_none=True)
                with torch.amp.autocast("cuda", enabled=device.type == "cuda"):
                    logits = model(inputs)
                loss = objective_loss(
                    logits.float(),
                    inputs,
                    growth.float(),
                    extent.float(),
                    loss_config,
                )
                if not bool(torch.isfinite(loss).item()):
                    print(
                        f"non-finite WFIGS loss skipped seed={seed} epoch={epoch}",
                        flush=True,
                    )
                    scaler.update()
                    continue
                scaler.scale(loss).backward()
                scaler.unscale_(optimizer)
                gradient_norm = torch.nn.utils.clip_grad_norm_(
                    trainable_parameters,
                    adaptation.max_grad_norm,
                    error_if_nonfinite=not scaler.is_enabled(),
                )
                if scaler.is_enabled() and not torch.isfinite(gradient_norm):
                    print(
                        f"AMP overflow skipped seed={seed} epoch={epoch}",
                        flush=True,
                    )
                    scaler.update()
                    continue
                if not torch.isfinite(gradient_norm):
                    raise FloatingPointError("non-finite WFIGS adaptation gradient norm")
                scaler.step(optimizer)
                scaler.update()
                running_loss += float(loss.item())
            scheduler.step()
            grid = evaluate_threshold_grid(
                model,
                val_loader,
                device,
                EARLY_STOP_THRESHOLDS,
                prediction_mode=target_mode,
            )
            selected = max(grid.values(), key=lambda row: float(row["event_macro_iou"]))
            growth_ap = evaluate_growth_average_precision(
                model,
                val_loader,
                device,
                prediction_mode=target_mode,
            )
            event_macro = float(selected["event_macro_iou"])
            score = (
                growth_ap
                if adaptation.epoch_selection_metric == "growth_ap"
                else event_macro
            )
            history.append(
                {
                    "epoch": epoch,
                    "train_loss": running_loss / max(len(train_loader), 1),
                    "val_event_macro_iou": event_macro,
                    "val_growth_ap": growth_ap,
                    "val_threshold": selected["threshold"],
                    "epoch_selection_metric": adaptation.epoch_selection_metric,
                    "seconds": time.perf_counter() - started,
                }
            )
            improved = score >= best_score
            should_stop = False
            if improved:
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
                        "target_mode": target_mode,
                        "base_channels": config["base_channels"],
                        "seed": seed,
                        "epoch": epoch,
                        "wfigs_test_evaluated": False,
                    },
                    checkpoint_path,
                )
            else:
                stale += 1
                should_stop = stale > adaptation.patience
            print(
                f"EPOCH seed={seed} epoch={epoch}/{adaptation.epochs} "
                f"loss={history[-1]['train_loss']:.4f} "
                f"val_iou={event_macro:.4f} val_ap={growth_ap:.4f} "
                f"thr={selected['threshold']} best={best_score:.4f} "
                f"improved={improved} stale={stale}",
                flush=True,
            )
            if progress_callback is not None:
                progress_callback(
                    {
                        "seed": seed,
                        "epoch": epoch,
                        "epochs_total": adaptation.epochs,
                        "train_loss": history[-1]["train_loss"],
                        "val_event_macro_iou": event_macro,
                        "val_growth_ap": growth_ap,
                        "val_threshold": selected["threshold"],
                        "best_epoch": best_epoch,
                        "best_val_event_macro_iou": best_score,
                        "improved": improved,
                        "early_stop_pending": should_stop,
                        "selection_split": "wfigs_validation",
                        "test_evaluated": False,
                    }
                )
            if should_stop:
                break
        best = torch.load(checkpoint_path, map_location=device, weights_only=False)
        model.load_state_dict(best["state_dict"])
        threshold, val_search = select_threshold_on_val(
            model,
            val_loader,
            device,
            prediction_mode=target_mode,
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
                "trainable_scope": adaptation.trainable_scope,
                "trainable_parameters": sum(
                    parameter.numel() for parameter in trainable_parameters
                ),
                "total_parameters": sum(parameter.numel() for parameter in model.parameters()),
                "test_evaluated": False,
            }
        )
        adapted_models.append(model)
        current_target_mode = target_mode
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


__all__ = [
    "ADAPTATION_SCHEMA",
    "WFIGSAdaptConfig",
    "adapt_frozen_rcda_on_wfigs",
    "configure_trainable_scope",
    "set_adaptation_train_mode",
]
