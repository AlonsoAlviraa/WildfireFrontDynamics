"""Unit tests for the Machine Learning dataset and fine-tuning pipelines."""

from __future__ import annotations

import unittest
import importlib.util
from pathlib import Path

try:
    import torch
except ModuleNotFoundError:
    torch = None  # type: ignore[assignment]

from wildfire_front.models import FrontObservation

HAS_SKLEARN = importlib.util.find_spec("sklearn") is not None


class MLPipelineTests(unittest.TestCase):
    def setUp(self) -> None:
        self.images_dir = Path("data/candidates/semireal_controlled_001/images")
        self.masks_dir = Path("data/candidates/semireal_controlled_001/masks")
        self.weights_path = Path("models/v3.pt")

    @unittest.skipIf(torch is None, "PyTorch is not installed")
    def test_wildfire_dataset_loading_and_shapes(self) -> None:
        from wildfire_front.ml.dataset import WildfireDataset

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

    @unittest.skipIf(torch is None, "PyTorch is not installed")
    def test_fine_tuning_execution_one_epoch(self) -> None:
        from wildfire_front.ml.train import fine_tune_model

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

    @unittest.skipIf(torch is None, "PyTorch is not installed")
    def test_cloud_train_build_parser(self) -> None:
        from wildfire_front.ml.cloud_train import build_parser
        parser = build_parser()
        args = parser.parse_args([
            "--images", "img_path",
            "--masks", "mask_path",
            "--weights", "weights_path",
            "--output-weights", "out_path",
        ])
        self.assertEqual(args.images, Path("img_path"))
        self.assertEqual(args.masks, Path("mask_path"))
        self.assertEqual(args.weights, Path("weights_path"))
        self.assertEqual(args.output_weights, Path("out_path"))

    @unittest.skipIf(torch is None, "PyTorch is not installed")
    def test_cloud_train_execution_one_epoch_without_upload(self) -> None:
        from wildfire_front.ml.cloud_train import main as cloud_main
        output_weights = Path("outputs/test-ml-weights/cloud_fine_tuned.pt")
        if output_weights.exists():
            output_weights.unlink()

        # Execute main with arguments
        cloud_main([
            "--images", str(self.images_dir),
            "--masks", str(self.masks_dir),
            "--weights", str(self.weights_path),
            "--output-weights", str(output_weights),
            "--epochs", "1",
            "--lr", "1e-4"
        ])

        self.assertTrue(output_weights.exists(), "Cloud weights checkpoint should be saved")

        if output_weights.exists():
            output_weights.unlink()
            output_weights.parent.rmdir()

    @unittest.skipIf(torch is None, "PyTorch is not installed")
    def test_npz_wildfire_dataset(self) -> None:
        import tempfile
        import numpy as np
        from wildfire_front.ml.dataset import NpzWildfireDataset

        with tempfile.TemporaryDirectory() as tmpdir:
            # Create a dummy NPZ file
            seq_dummy = np.random.randn(3, 16, 30, 30).astype(np.float32)
            curr_dummy = np.random.randint(0, 2, size=(30, 30)).astype(np.float32)
            target_dummy = np.random.randint(0, 2, size=(30, 30)).astype(np.float32)
            
            np.savez(
                Path(tmpdir) / "patch_000000.npz",
                sequence=seq_dummy,
                current_fire=curr_dummy,
                target_fire=target_dummy
            )
            
            # Load dataset
            dataset = NpzWildfireDataset(tmpdir)
            self.assertEqual(len(dataset), 1)
            
            seq, curr, target = dataset[0]
            self.assertEqual(seq.shape, (3, 16, 30, 30))
            self.assertEqual(curr.shape, (30, 30))
            self.assertEqual(target.shape, (30, 30))

    @unittest.skipIf(not HAS_SKLEARN, "scikit-learn is not installed")
    def test_wildfire_meta_labeler(self) -> None:
        import numpy as np
        from wildfire_front.ml.meta_labeler import WildfireMetaLabeler

        meta_labeler = WildfireMetaLabeler(n_estimators=5, max_depth=2, random_state=42)
        
        # Test feature building
        prob = np.array([0.1, 0.9, 0.5])
        slope = np.array([0.05, 0.1, 0.0])
        aspect = np.array([1.5, 3.1, 0.0])
        ws = 10.0
        hum = 45.0
        temp = 25.0
        
        features = meta_labeler.build_features(
            prob=prob,
            slope=slope,
            aspect=aspect,
            wind_speed=ws,
            humidity=hum,
            temp=temp
        )
        # 3 samples, 7 features
        self.assertEqual(features.shape, (3, 7))
        
        # Test training and prediction
        X = np.random.randn(10, 7)
        y = np.random.randint(0, 2, size=(10,))
        
        meta_labeler.train(X, y)
        self.assertTrue(meta_labeler.is_trained)
        
        preds = meta_labeler.predict_trustworthiness(X)
        probs = meta_labeler.predict_probability(X)
        
        self.assertEqual(preds.shape, (10,))
        self.assertEqual(probs.shape, (10,))
        self.assertTrue(np.all(probs >= 0.0) and np.all(probs <= 1.0))

    def test_preprocess_ndws_cli(self) -> None:
        import subprocess
        import sys
        
        # 1. Running without --split should fail with exit code 2 (argparse standard)
        res = subprocess.run([sys.executable, "kaggle_job/preprocess_ndws.py"], capture_output=True, text=True)
        self.assertEqual(res.returncode, 2)
        self.assertIn("required", res.stderr.lower() + res.stdout.lower())
        
        # 2. Running with --split train should fail because TF is missing or no records found
        res2 = subprocess.run([sys.executable, "kaggle_job/preprocess_ndws.py", "--split", "train"], capture_output=True, text=True)
        self.assertNotEqual(res2.returncode, 0)
        output = res2.stderr.lower() + res2.stdout.lower()
        self.assertTrue("no tfrecord" in output or "tensorflow" in output)


