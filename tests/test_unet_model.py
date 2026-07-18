"""Tests for the improved U-Net model architecture and loss functions.

These tests validate the loop-engineering improvements:
- 3-level U-Net bottleneck at 8×8 for 64×64 input
- SE attention module
- Composite loss (BCE + Dice + Tversky)
- Loss function factory
- Gradient flow
- No NaN/Inf in forward/backward

Run with: pytest tests/test_unet_model.py -v
"""

import numpy as np
import pytest

torch = pytest.importorskip("torch")


@pytest.fixture(scope="module")
def model_inputs():
    """Standard model input: batch=4, channels=18, 64×64."""
    torch.manual_seed(42)
    x = torch.randn(4, 18, 64, 64)
    targets = (torch.rand(4, 1, 64, 64) > 0.8).float()
    return x, targets


class TestResidualWildfireUNetSmall:
    """Test residual delta model over copy baseline."""

    def test_forward_with_prev_fire(self):
        from models.unet_model import ResidualWildfireUNetSmall

        model = ResidualWildfireUNetSmall(in_channels=18)
        x = torch.randn(2, 18, 64, 64)
        prev = (torch.rand(2, 64, 64) > 0.5).float()
        with torch.no_grad():
            out = model(x, prev)
        assert out.shape == (2, 1, 64, 64)
        assert torch.isfinite(out).all()

    def test_gradient_flow(self):
        from models.unet_model import ResidualWildfireUNetSmall

        model = ResidualWildfireUNetSmall(in_channels=18)
        x = torch.randn(2, 18, 64, 64, requires_grad=True)
        prev = torch.rand(2, 64, 64)
        target = (torch.rand(2, 1, 64, 64) > 0.8).float()
        logits = model(x, prev)
        loss = torch.nn.functional.binary_cross_entropy_with_logits(logits, target)
        loss.backward()
        assert x.grad is not None
        assert torch.isfinite(x.grad).all()


class TestWildfireUNet:
    """Test the full U-Net model."""

    def test_forward_output_shape(self):
        from models.unet_model import WildfireUNet

        model = WildfireUNet(in_channels=18, out_channels=1, bilinear=True)
        x = torch.randn(2, 18, 64, 64)
        with torch.no_grad():
            out = model(x)
        assert out.shape == (2, 1, 64, 64)

    def test_forward_output_shape_small(self):
        from models.unet_model import WildfireUNetSmall

        model = WildfireUNetSmall(in_channels=18, out_channels=1, bilinear=True)
        x = torch.randn(2, 18, 64, 64)
        with torch.no_grad():
            out = model(x)
        assert out.shape == (2, 1, 64, 64)

    def test_bottleneck_is_8x8(self):
        """Verify 64×64 → 8×8 bottleneck (3 down-levels, not 4)."""
        from models.unet_model import WildfireUNet

        model = WildfireUNet(in_channels=18, bilinear=True)
        x = torch.randn(1, 18, 64, 64)

        # Trace intermediate shapes
        x1 = model.inc(x)
        x2 = model.down1(x1)
        x3 = model.down2(x2)
        x4 = model.down3(x3)

        # Bottleneck should be 8×8 (64 / 2^3 = 8)
        assert x4.shape[2] == 8, f"Bottleneck H should be 8, got {x4.shape[2]}"
        assert x4.shape[3] == 8, f"Bottleneck W should be 8, got {x4.shape[3]}"

    def test_bottleneck_not_1x1(self):
        """Explicitly test that bottleneck is NOT 1×1 (the v13 bug)."""
        from models.unet_model import WildfireUNetSmall

        model = WildfireUNetSmall(in_channels=18, bilinear=True)
        x = torch.randn(1, 18, 64, 64)

        x1 = model.inc(x)
        x2 = model.down1(x1)
        x3 = model.down2(x2)
        x4 = model.down3(x3)

        assert x4.shape[2] > 1, "Bottleneck is 1×1 — spatial info destroyed!"
        assert x4.shape[3] > 1, "Bottleneck is 1×1 — spatial info destroyed!"

    def test_se_attention(self):
        """Test that SE attention can be enabled."""
        from models.unet_model import SqueezeExcitation, WildfireUNet

        model = WildfireUNet(in_channels=18, se_attention=True)
        x = torch.randn(2, 18, 64, 64)
        with torch.no_grad():
            out = model(x)
        assert out.shape == (2, 1, 64, 64)

        # Test SE module directly
        se = SqueezeExcitation(64)
        y = torch.randn(2, 64, 32, 32)
        out_se = se(y)
        assert out_se.shape == y.shape

    def test_predict_returns_probabilities(self):
        from models.unet_model import WildfireUNetSmall

        model = WildfireUNetSmall(in_channels=18)
        x = torch.randn(2, 18, 64, 64)
        probs = model.predict(x)
        assert probs.shape == (2, 1, 64, 64)
        assert (probs >= 0).all() and (probs <= 1).all()

    def test_parameter_count_reasonable(self):
        from models.unet_model import WildfireUNet, WildfireUNetSmall, count_parameters

        full = WildfireUNet(in_channels=18)
        small = WildfireUNetSmall(in_channels=18)

        full_params = count_parameters(full)
        small_params = count_parameters(small)

        # Small should have fewer params than full
        assert small_params < full_params
        # Should be in reasonable range (not 0, not billions)
        assert full_params > 100_000
        assert small_params > 10_000
        assert full_params < 100_000_000

    def test_batch_norm_option(self):
        from models.unet_model import WildfireUNet

        model = WildfireUNet(in_channels=18, norm="batch")
        x = torch.randn(2, 18, 64, 64)
        with torch.no_grad():
            out = model(x)
        assert out.shape == (2, 1, 64, 64)


class TestLossFunctions:
    """Test all loss functions."""

    @pytest.fixture
    def loss_inputs(self):
        torch.manual_seed(42)
        logits = torch.randn(4, 1, 64, 64, requires_grad=True)
        targets = (torch.rand(4, 1, 64, 64) > 0.8).float()
        return logits, targets

    def test_weighted_bce(self, loss_inputs):
        from models.unet_model import weighted_bce_loss

        logits, targets = loss_inputs
        loss = weighted_bce_loss(logits, targets, pos_weight=5.0)
        assert torch.isfinite(loss)
        loss.backward()
        assert logits.grad is not None

    def test_dice_loss(self, loss_inputs):
        from models.unet_model import dice_loss

        logits, targets = loss_inputs
        loss = dice_loss(logits, targets)
        assert torch.isfinite(loss)
        assert loss.item() >= 0  # Dice loss is non-negative
        loss.backward()
        assert logits.grad is not None

    def test_tversky_loss(self, loss_inputs):
        from models.unet_model import tversky_loss

        logits, targets = loss_inputs
        loss = tversky_loss(logits, targets, alpha=0.3, beta=0.7)
        assert torch.isfinite(loss)
        assert loss.item() >= 0
        loss.backward()
        assert logits.grad is not None

    def test_focal_loss(self, loss_inputs):
        from models.unet_model import focal_loss

        logits, targets = loss_inputs
        loss = focal_loss(logits, targets, gamma=2.0, pos_weight=5.0)
        assert torch.isfinite(loss)
        loss.backward()
        assert logits.grad is not None

    def test_combined_loss(self, loss_inputs):
        from models.unet_model import combined_loss

        logits, targets = loss_inputs
        loss = combined_loss(logits, targets, pos_weight=5.0, dice_weight=0.5)
        assert torch.isfinite(loss)
        loss.backward()
        assert logits.grad is not None

    def test_composite_loss(self, loss_inputs):
        from models.unet_model import composite_loss

        logits, targets = loss_inputs
        loss = composite_loss(logits, targets, pos_weight=5.0, dice_weight=0.3, tversky_weight=0.3)
        assert torch.isfinite(loss)
        loss.backward()
        assert logits.grad is not None

    def test_composite_loss_with_focal(self, loss_inputs):
        from models.unet_model import composite_loss

        logits, targets = loss_inputs
        loss = composite_loss(
            logits,
            targets,
            pos_weight=5.0,
            dice_weight=0.3,
            tversky_weight=0.3,
            focal_weight=0.2,
            focal_gamma=2.0,
        )
        assert torch.isfinite(loss)
        loss.backward()
        assert logits.grad is not None

    def test_dynamic_weighted_bce(self, loss_inputs):
        from models.unet_model import dynamic_weighted_bce

        logits, targets = loss_inputs
        loss = dynamic_weighted_bce(logits, targets, target_ratio=5.0)
        assert torch.isfinite(loss)
        loss.backward()
        assert logits.grad is not None

    def test_loss_zero_on_perfect_prediction(self):
        """Loss should be near zero when prediction matches target."""
        from models.unet_model import dice_loss

        # Perfect prediction: logits very high where target=1, very low where target=0
        targets = torch.zeros(1, 1, 8, 8)
        targets[0, 0, 2:6, 2:6] = 1.0
        logits = torch.where(targets > 0.5, torch.tensor(100.0), torch.tensor(-100.0))
        loss = dice_loss(logits, targets)
        assert loss.item() < 0.01, (
            f"Dice loss on perfect prediction should be ~0, got {loss.item()}"
        )


class TestLossFactory:
    """Test the make_loss_fn factory."""

    @pytest.fixture
    def loss_inputs(self):
        torch.manual_seed(42)
        logits = torch.randn(2, 1, 16, 16, requires_grad=True)
        targets = (torch.rand(2, 1, 16, 16) > 0.8).float()
        return logits, targets

    @pytest.mark.parametrize(
        "loss_name", ["bce", "dynamic_bce", "dice", "tversky", "focal", "combined", "composite"]
    )
    def test_factory_creates_valid_loss(self, loss_name, loss_inputs):
        from models.unet_model import make_loss_fn

        fn = make_loss_fn(loss_name, pos_weight=5.0)
        logits, targets = loss_inputs
        loss = fn(logits, targets)
        assert torch.isfinite(loss), f"{loss_name} produced non-finite loss"
        loss.backward()
        assert logits.grad is not None, f"{loss_name} produced no gradient"

    def test_factory_invalid_name_raises(self):
        from models.unet_model import make_loss_fn

        with pytest.raises(ValueError, match="Unknown loss"):
            make_loss_fn("nonexistent_loss")


class TestGradientFlow:
    """Test that gradients flow properly through the network."""

    def test_full_backward_pass(self):
        from models.unet_model import WildfireUNetSmall, composite_loss

        model = WildfireUNetSmall(in_channels=18)
        x = torch.randn(2, 18, 64, 64)
        targets = (torch.rand(2, 1, 64, 64) > 0.8).float()

        logits = model(x)
        loss = composite_loss(logits, targets, pos_weight=5.0)
        loss.backward()

        # Check all parameters have gradients
        no_grad_params = [name for name, p in model.named_parameters() if p.grad is None]
        assert not no_grad_params, f"Parameters without gradients: {no_grad_params}"

    def test_no_nan_gradients(self):
        from models.unet_model import WildfireUNetSmall, composite_loss

        model = WildfireUNetSmall(in_channels=18)
        x = torch.randn(2, 18, 64, 64)
        targets = (torch.rand(2, 1, 64, 64) > 0.8).float()

        logits = model(x)
        loss = composite_loss(logits, targets, pos_weight=5.0)
        loss.backward()

        for name, p in model.named_parameters():
            if p.grad is not None:
                assert not torch.isnan(p.grad).any(), f"NaN gradient in {name}"
                assert not torch.isinf(p.grad).any(), f"Inf gradient in {name}"

    def test_gradient_clipping_stability(self):
        """Test that training is stable even with high learning rate."""
        from models.unet_model import WildfireUNetSmall, composite_loss

        model = WildfireUNetSmall(in_channels=18)
        optimizer = torch.optim.Adam(model.parameters(), lr=1e-2)

        for _ in range(5):
            x = torch.randn(2, 18, 64, 64)
            targets = (torch.rand(2, 1, 64, 64) > 0.8).float()
            optimizer.zero_grad()
            logits = model(x)
            loss = composite_loss(logits, targets, pos_weight=5.0)
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            optimizer.step()
            assert torch.isfinite(loss), "Loss became non-finite during training"

    def test_apply_weighted_loss_uses_passed_pos_weight(self):
        """H2: apply_weighted_loss must honor pos_weight, not hard-coded 5.0."""
        from wildfire_front.ml.unet_train import apply_weighted_loss

        # All-positive targets with negative logits → FN-heavy; pos_weight scales loss up.
        logits = torch.full((1, 1, 4, 4), -2.0)
        targets = torch.ones(1, 1, 4, 4)
        weights = torch.ones_like(targets)

        def _unused_loss_fn(a: torch.Tensor, b: torch.Tensor) -> torch.Tensor:
            return a.sum() * 0.0

        loss_pw1 = apply_weighted_loss(_unused_loss_fn, logits, targets, weights, pos_weight=1.0)
        loss_pw10 = apply_weighted_loss(_unused_loss_fn, logits, targets, weights, pos_weight=10.0)
        assert torch.isfinite(loss_pw1) and torch.isfinite(loss_pw10)
        assert loss_pw10.item() > loss_pw1.item() * 5.0, (
            f"pos_weight=10 should greatly exceed pos_weight=1 "
            f"({loss_pw10.item():.4f} vs {loss_pw1.item():.4f})"
        )

        # Same call with default vs explicit 5.0 must match (default remains 5.0).
        loss_default = apply_weighted_loss(_unused_loss_fn, logits, targets, weights)
        loss_explicit5 = apply_weighted_loss(
            _unused_loss_fn, logits, targets, weights, pos_weight=5.0
        )
        assert abs(loss_default.item() - loss_explicit5.item()) < 1e-6

    def test_train_loop_passes_config_pos_weight_to_weighted_loss(self):
        """H2 call-site contract: train loop wires config.pos_weight into apply_weighted_loss."""
        import inspect

        import wildfire_front.ml.unet_train as unet_train

        src = inspect.getsource(unet_train)
        assert "apply_weighted_loss(" in src
        assert "pos_weight=config.pos_weight" in src
        # Guard against reintroducing a hard-coded tensor(5.0) in apply_weighted_loss body
        apply_src = inspect.getsource(unet_train.apply_weighted_loss)
        assert "torch.tensor(5.0" not in apply_src
        assert "pos_weight" in apply_src


class TestNpzDataset:
    """Test the NpzWildfireDataset with 64×64 patches."""

    @pytest.fixture
    def synthetic_data(self, tmp_path):
        """Create synthetic NPZ files."""

        for split, n in [("train", 8), ("val", 4), ("test", 4)]:
            d = tmp_path / split
            d.mkdir()
            for i in range(n):
                seq = np.random.randn(1, 17, 64, 64).astype(np.float32) * 0.5
                cf = np.zeros((64, 64), dtype=np.float32)
                tf_ = np.zeros((64, 64), dtype=np.float32)
                cf[20:40, 20:40] = 1.0
                tf_[18:42, 18:42] = 1.0
                np.savez_compressed(
                    d / f"patch_{i:06d}.npz", sequence=seq, current_fire=cf, target_fire=tf_
                )
        return tmp_path

    def test_dataset_loads_64x64(self, synthetic_data):
        from wildfire_front.ml.dataset import NpzWildfireDataset

        ds = NpzWildfireDataset(synthetic_data / "train")
        assert len(ds) == 8
        seq, cf, tf_ = ds[0]
        assert seq.shape == (1, 17, 64, 64)
        assert cf.shape == (64, 64)
        assert tf_.shape == (64, 64)

    def test_augmentation_flips(self, synthetic_data):
        from wildfire_front.ml.dataset import NpzWildfireDataset

        ds = NpzWildfireDataset(synthetic_data / "train", augment=True)
        seq, cf, tf_ = ds[0]
        # Just verify it doesn't crash and shapes are correct
        assert seq.shape == (1, 17, 64, 64)
        assert cf.shape == (64, 64)
        assert tf_.shape == (64, 64)

    def test_no_nan_in_dataset(self, synthetic_data):
        from wildfire_front.ml.dataset import NpzWildfireDataset

        ds = NpzWildfireDataset(synthetic_data / "train")
        for i in range(len(ds)):
            seq, cf, tf_ = ds[i]
            assert torch.isfinite(seq).all(), f"NaN in sample {i} sequence"
            assert torch.isfinite(cf).all(), f"NaN in sample {i} current_fire"
            assert torch.isfinite(tf_).all(), f"NaN in sample {i} target_fire"
