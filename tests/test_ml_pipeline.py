"""Unit tests for the Machine Learning dataset and fine-tuning pipelines."""

from __future__ import annotations

import unittest
from pathlib import Path

import torch

from wildfire_front.ml.dataset import WildfireDataset
from wildfire_front.ml.train import fine_tune_model
from wildfire_front.models import FrontObservation


class MLPipelineTests(unittest.TestCase):
    def setUp(self) -> None:
        self.images_dir = Path("data/candidates/semireal_controlled_001/images")
        self.masks_dir = Path("data/candidates/semireal_controlled_001/masks")
        self.weights_path = Path("models/v3.pt")

    def test_wildfire_dataset_loading_and_shapes(self) -> None:
        # Check that the dataset loads and extracts patches of size 30x30
        dataset = WildfireDataset(
            images_dir=self.images_dir,
            masks_dir=self.masks_dir,
            sequence_length=3,
            patch_size=30,
        )
        self.assertGreater(len(dataset), 0, "Dataset should have at least one valid sequence patch")

        # Get first patch
        sequence, current_fire, target_fire = dataset[0]

        # Assert shapes:
        # sequence: (3, 16, 30, 30)
        self.assertEqual(sequence.shape, (3, 16, 30, 30))
        # current_fire: (30, 30)
        self.assertEqual(current_fire.shape, (30, 30))
        # target_fire: (30, 30)
        self.assertEqual(target_fire.shape, (30, 30))

        # Check values
        self.assertTrue(torch.is_tensor(sequence))
        self.assertTrue(torch.is_tensor(current_fire))
        self.assertTrue(torch.is_tensor(target_fire))

    def test_fine_tuning_execution_one_epoch(self) -> None:
        # Run fine-tuning for exactly one epoch on the semireal candidate
        output_weights = Path("outputs/test-ml-weights/fine_tuned.pt")
        if output_weights.exists():
            output_weights.unlink()

        result = fine_tune_model(
            images_dir=self.images_dir,
            masks_dir=self.masks_dir,
            weights_path=self.weights_path,
            output_weights_path=output_weights,
            epochs=1,
            lr=1e-4,
        )

        self.assertEqual(result["status"], "success")
        self.assertEqual(len(result["loss_history"]), 1)
        self.assertTrue(output_weights.exists(), "Fine-tuned model checkpoint should be saved")

        # Clean up output weights
        if output_weights.exists():
            output_weights.unlink()
            output_weights.parent.rmdir()
