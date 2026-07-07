"""Unit tests for the Machine Learning dataset and fine-tuning pipelines."""

from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path

try:
    import torch
except ModuleNotFoundError:
    torch = None  # type: ignore[assignment]


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
        args = parser.parse_args(
            [
                "--images",
                "img_path",
                "--masks",
                "mask_path",
                "--weights",
                "weights_path",
                "--output-weights",
                "out_path",
            ]
        )
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
        cloud_main(
            [
                "--images",
                str(self.images_dir),
                "--masks",
                str(self.masks_dir),
                "--weights",
                str(self.weights_path),
                "--output-weights",
                str(output_weights),
                "--epochs",
                "1",
                "--lr",
                "1e-4",
            ]
        )

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
                target_fire=target_dummy,
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
            prob=prob, slope=slope, aspect=aspect, wind_speed=ws, humidity=hum, temp=temp
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

    @unittest.skipIf(not HAS_SKLEARN, "scikit-learn is not installed")
    def test_meta_labeler_single_class_guard(self) -> None:
        """Regression test: predict_proba()[:, 1] must not crash when the
        validation set yields a single-class label (all-correct or all-wrong)."""
        import numpy as np

        from wildfire_front.ml.meta_labeler import WildfireMetaLabeler

        meta_labeler = WildfireMetaLabeler(n_estimators=5, max_depth=2, random_state=42)
        X = np.random.randn(10, 7)

        # Degenerate case: all labels = 1
        y_single = np.ones(10, dtype=np.int64)
        meta_labeler.train(X, y_single)
        self.assertTrue(meta_labeler.is_trained)
        self.assertEqual(meta_labeler._single_class_label, 1)

        preds = meta_labeler.predict_trustworthiness(X)
        probs = meta_labeler.predict_probability(X)
        self.assertEqual(preds.shape, (10,))
        self.assertEqual(probs.shape, (10,))
        self.assertTrue(np.all(preds == 1))
        self.assertTrue(np.allclose(probs, 1.0))

        # Degenerate case: all labels = 0
        y_zero = np.zeros(10, dtype=np.int64)
        meta_labeler.train(X, y_zero)
        self.assertEqual(meta_labeler._single_class_label, 0)
        probs0 = meta_labeler.predict_probability(X)
        self.assertTrue(np.allclose(probs0, 0.0))

    @unittest.skipIf(not HAS_SKLEARN, "scikit-learn is not installed")
    def test_meta_labeler_entropy_boundaries(self) -> None:
        """Entropy of p=0.5 is maximal (1.0 bit); p near 0/1 is near-zero."""
        import numpy as np

        from wildfire_front.ml.meta_labeler import WildfireMetaLabeler

        meta_labeler = WildfireMetaLabeler(n_estimators=5, max_depth=2, random_state=42)
        prob = np.array([0.5, 1e-8, 1.0 - 1e-8])
        ent = meta_labeler.compute_entropy(prob)
        self.assertAlmostEqual(ent[0], 1.0, places=5)  # max entropy at p=0.5
        self.assertLess(ent[1], 1e-5)  # near-zero at extremes
        self.assertLess(ent[2], 1e-5)

    @unittest.skipIf(not HAS_SKLEARN, "scikit-learn is not installed")
    def test_meta_labeler_entropy_symmetry_and_shape(self) -> None:
        """H(p) == H(1-p) (binary entropy symmetry) and shape is preserved."""
        import numpy as np

        from wildfire_front.ml.meta_labeler import WildfireMetaLabeler

        ml = WildfireMetaLabeler(n_estimators=5, max_depth=2)
        rng = np.random.default_rng(0)
        p = rng.random(50)
        h_p = ml.compute_entropy(p)
        h_inv = ml.compute_entropy(1.0 - p)
        np.testing.assert_allclose(h_p, h_inv, atol=1e-10)
        self.assertEqual(h_p.shape, p.shape)

    @unittest.skipIf(not HAS_SKLEARN, "scikit-learn is not installed")
    def test_meta_labeler_predict_without_training_raises(self) -> None:
        """predict_* must raise ValueError if called before train()."""
        import numpy as np

        from wildfire_front.ml.meta_labeler import WildfireMetaLabeler

        ml = WildfireMetaLabeler(n_estimators=5, max_depth=2)
        X = np.random.randn(5, 7)
        with self.assertRaises(ValueError):
            ml.predict_trustworthiness(X)
        with self.assertRaises(ValueError):
            ml.predict_probability(X)

    @unittest.skipIf(not HAS_SKLEARN, "scikit-learn is not installed")
    def test_meta_labeler_build_features_columns_and_2d(self) -> None:
        """Column 1 must be entropy of column 0; 2D grid inputs flatten correctly."""
        import numpy as np

        from wildfire_front.ml.meta_labeler import WildfireMetaLabeler

        ml = WildfireMetaLabeler(n_estimators=5, max_depth=2)
        # 1D path
        prob = np.array([0.1, 0.9, 0.5])
        slope = np.array([0.0, 0.1, 0.2])
        aspect = np.array([1.0, 2.0, 3.0])
        feats = ml.build_features(prob, slope, aspect, 10.0, 50.0, 20.0)
        self.assertEqual(feats.shape, (3, 7))
        np.testing.assert_allclose(feats[:, 0], prob)
        np.testing.assert_allclose(feats[:, 1], ml.compute_entropy(prob))
        np.testing.assert_allclose(feats[:, 2], slope)
        np.testing.assert_allclose(feats[:, 4], 10.0)  # wind_speed broadcast

        # 2D grid path (real use case)
        prob2d = np.full((4, 4), 0.3)
        slope2d = np.full((4, 4), 0.05)
        aspect2d = np.full((4, 4), 1.5)
        ws2d = np.full((4, 4), 12.0)
        feats2d = ml.build_features(prob2d, slope2d, aspect2d, ws2d, 40.0, 22.0)
        self.assertEqual(feats2d.shape, (16, 7))

    @unittest.skipIf(not HAS_SKLEARN, "scikit-learn is not installed")
    def test_meta_labeler_save_load_roundtrip(self) -> None:
        """save/load must preserve trained state and predictions (incl. single-class)."""
        import os
        import tempfile

        import numpy as np

        from wildfire_front.ml.meta_labeler import WildfireMetaLabeler

        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "meta.pkl")

            # Two-class model
            ml = WildfireMetaLabeler(n_estimators=5, max_depth=3, random_state=7)
            rng = np.random.default_rng(1)
            X = rng.normal(size=(40, 7))
            y = (X[:, 0] > 0).astype(np.int64)
            ml.train(X, y)
            ml.save(path)

            loaded = WildfireMetaLabeler.load(path)
            self.assertTrue(loaded.is_trained)
            np.testing.assert_array_equal(
                ml.predict_trustworthiness(X), loaded.predict_trustworthiness(X)
            )
            np.testing.assert_allclose(ml.predict_probability(X), loaded.predict_probability(X))

            # Single-class roundtrip
            path2 = os.path.join(tmp, "single.pkl")
            ml_single = WildfireMetaLabeler(n_estimators=3, random_state=0)
            ml_single.train(X, np.ones(len(X), dtype=np.int64))
            ml_single.save(path2)
            loaded2 = WildfireMetaLabeler.load(path2)
            self.assertEqual(loaded2._single_class_label, 1)
            np.testing.assert_allclose(loaded2.predict_probability(X), 1.0)

    @unittest.skipIf(not HAS_SKLEARN, "scikit-learn is not installed")
    def test_meta_labeler_determinism_via_random_state(self) -> None:
        """Same random_state → identical predictions (reproducible training)."""
        import numpy as np

        from wildfire_front.ml.meta_labeler import WildfireMetaLabeler

        rng = np.random.default_rng(99)
        X = rng.normal(size=(60, 7))
        y = (X[:, 0] * X[:, 1] > 0).astype(np.int64)

        a = WildfireMetaLabeler(n_estimators=8, max_depth=4, random_state=123)
        b = WildfireMetaLabeler(n_estimators=8, max_depth=4, random_state=123)
        a.train(X, y)
        b.train(X, y)
        np.testing.assert_array_equal(a.predict_trustworthiness(X), b.predict_trustworthiness(X))

    def test_preprocess_ndws_cli(self) -> None:
        import subprocess
        import sys

        # 1. Running without --split should fail with exit code 2 (argparse standard)
        res = subprocess.run(
            [sys.executable, "kaggle_job/preprocess_ndws.py"], capture_output=True, text=True
        )
        self.assertEqual(res.returncode, 2)
        self.assertIn("required", res.stderr.lower() + res.stdout.lower())

        # 2. Running with --split train should fail because TF is missing or no records found
        res2 = subprocess.run(
            [sys.executable, "kaggle_job/preprocess_ndws.py", "--split", "train"],
            capture_output=True,
            text=True,
        )
        self.assertNotEqual(res2.returncode, 0)
        output = res2.stderr.lower() + res2.stdout.lower()
        self.assertTrue("no tfrecord" in output or "tensorflow" in output)
