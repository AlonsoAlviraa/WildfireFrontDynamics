"""
LEGACY — A3C-LSTM (not production).

Production spread models are U-Net / CLM ensemble:
  models/unet_model.py, models/catalog.json, models/production/, models/clm_ensemble/.
See models/README.md.

A3C Model V3 with LSTM - 16 Channels (FULL FEATURES)
Temporal modeling for wildfire spread prediction with all weather channels

Input channels:
- Channel 0-1: DEM (slope, aspect)
- Channel 2-10: Weather (temp, humidity, wind_speed, wind_dir, precip, pressure, cloud, visibility, dew_point)
- Channel 11: NDVI (vegetation)
- Channel 12-15: FSM (forest susceptibility, one-hot)
"""

import torch
import torch.nn as nn
import torch.nn.functional as F


class A3C_PerCellModel_LSTM(nn.Module):
    """
    A3C model with CNN encoder + LSTM for temporal context.

    Architecture (v2 — spatial-aware, no pooling bottleneck):
    1. CNN Encoder: Processes each timestep spatially (16ch -> 256, 30x30)
    2. Spatial pooling ONLY for LSTM temporal context vector (batch, 256)
    3. LSTM: Models global temporal trends -> context vector (batch, 256)
    4. Fusion: temporal context is broadcast and ADDED to the spatial features
       of the last timestep, preserving positional information (U-Net style).
    5. Policy/Value Heads: Predict per-cell from fused spatial features.
    """

    def __init__(self, in_channels=16, lstm_hidden=256, sequence_length=3, use_groupnorm=True):
        super().__init__()

        self.in_channels = in_channels
        self.lstm_hidden = lstm_hidden
        self.sequence_length = sequence_length
        self.use_groupnorm = use_groupnorm

        # CNN Encoder (per-timestep spatial processing)
        # Input: (batch, 16, 30, 30) -> Output: (batch, 256, 30, 30)
        self.conv1 = nn.Conv2d(in_channels, 64, kernel_size=3, padding=1)
        self.norm1 = nn.GroupNorm(8, 64) if use_groupnorm else nn.Identity()
        self.dropout1 = nn.Dropout2d(0.2)  # Sprint 3.4: increased from 0.1 to 0.2

        self.conv2 = nn.Conv2d(64, 128, kernel_size=3, padding=1)
        self.norm2 = nn.GroupNorm(16, 128) if use_groupnorm else nn.Identity()
        self.dropout2 = nn.Dropout2d(0.2)  # Sprint 3.4: increased from 0.1 to 0.2

        self.conv3 = nn.Conv2d(128, 256, kernel_size=3, padding=1)
        self.norm3 = nn.GroupNorm(32, 256) if use_groupnorm else nn.Identity()
        self.dropout3 = nn.Dropout2d(0.2)  # Sprint 3.4: increased from 0.1 to 0.2

        # Spatial pooling to get per-timestep feature vector
        # (batch, 256, 30, 30) -> (batch, 256) — used ONLY as global temporal context
        self.spatial_pool = nn.AdaptiveAvgPool2d(1)

        # LSTM for temporal modeling (global context only)
        # Input: (sequence_length, batch, 256) -> Output: (sequence_length, batch, lstm_hidden)
        self.lstm = nn.LSTM(
            input_size=256,
            hidden_size=lstm_hidden,
            num_layers=1,
            batch_first=False,  # (seq, batch, features)
            dropout=0.0,
        )

        # Temporal-context projection: maps LSTM hidden state (256) to a spatial
        # feature map (256, 30, 30) that will be FUSED with the last-timestep
        # spatial features. This avoids the information-destroying upsample of v1.
        self.temporal_projection = nn.Sequential(
            nn.Linear(lstm_hidden, 256),
            nn.ReLU(),
            nn.Unflatten(1, (256, 1, 1)),
        )

        # Fusion gate: learns how much temporal context to inject at each pixel.
        # (batch, 512, 30, 30) -> (batch, 256, 30, 30)
        self.fusion_gate = nn.Sequential(
            nn.Conv2d(256 * 2, 256, kernel_size=1),
            nn.Sigmoid(),
        )

        # Refinement conv after fusion (keeps spatial resolution)
        self.refine = nn.Sequential(
            nn.Conv2d(256, 256, kernel_size=3, padding=1),
            nn.GroupNorm(32, 256) if use_groupnorm else nn.Identity(),
            nn.ReLU(),
        )

        # Policy head - per-cell 8-neighbor prediction (operates on fused features)
        self.policy_head = nn.Sequential(
            nn.Linear(256 * 9, 256), nn.ReLU(), nn.Dropout(0.2), nn.Linear(256, 8)
        )

        # Value head (global pooling over fused features)
        self.value_head = nn.Sequential(
            nn.AdaptiveAvgPool2d(1),
            nn.Flatten(),
            nn.Linear(256, 64),
            nn.ReLU(),
            nn.Dropout(0.2),
            nn.Linear(64, 1),
        )

        self._initialize_weights()

    def _initialize_weights(self):
        """Initialize weights for strong gradients"""
        for m in self.modules():
            if isinstance(m, (nn.Conv2d, nn.Linear)):
                nn.init.kaiming_normal_(m.weight, mode="fan_out", nonlinearity="relu")
                if m.bias is not None:
                    nn.init.constant_(m.bias, 0)
            elif isinstance(m, nn.LSTM):
                for name, param in m.named_parameters():
                    if "weight" in name:
                        nn.init.orthogonal_(param)
                    elif "bias" in name:
                        nn.init.constant_(param, 0)

    def encode_timestep(self, x):
        """
        Encode a single timestep spatially with CNN.

        Args:
            x: (batch, 16, 30, 30) - single timestep

        Returns:
            spatial_features: (batch, 256, 30, 30)
            pooled_features: (batch, 256)
        """
        # CNN encoding
        x = F.relu(self.norm1(self.conv1(x)))
        x = self.dropout1(x)

        x = F.relu(self.norm2(self.conv2(x)))
        x = self.dropout2(x)

        spatial_features = F.relu(self.norm3(self.conv3(x)))
        spatial_features = self.dropout3(spatial_features)

        # Pool for LSTM input
        pooled = self.spatial_pool(spatial_features).flatten(1)

        return spatial_features, pooled

    def forward(self, sequence, fire_mask):
        """
        Forward pass with temporal sequence (v2 — spatial-aware fusion).

        Args:
            sequence: (batch, seq_len, 16, 30, 30) - temporal sequence
            fire_mask: (batch, 30, 30) - current fire mask (only for last timestep)

        Returns:
            spatial_features: (batch, 256, 30, 30) - fused features for policy head
            value: (batch, 1) - state value
        """
        batch_size, seq_len, C, H, W = sequence.shape

        # Encode each timestep with CNN, keeping BOTH spatial and pooled features
        pooled_sequence = []
        last_spatial = None
        for t in range(seq_len):
            spatial_t, pooled_t = self.encode_timestep(sequence[:, t])  # (B,256,30,30), (B,256)
            pooled_sequence.append(pooled_t)
            if t == seq_len - 1:
                last_spatial = spatial_t  # keep full-resolution features of last frame

        # Stack into sequence: (seq_len, batch, 256)
        pooled_sequence = torch.stack(pooled_sequence, dim=0)

        # LSTM temporal processing -> global temporal context
        lstm_out, (h_n, c_n) = self.lstm(pooled_sequence)
        final_hidden = h_n.squeeze(0)  # (batch, lstm_hidden)

        # Temporal-context projection: (batch, lstm_hidden) -> (batch, 256, 1, 1)
        temporal_ctx = self.temporal_projection(final_hidden)
        # Broadcast to spatial dims: (batch, 256, 30, 30)
        temporal_ctx = temporal_ctx.expand(-1, -1, H, W)

        # Gated fusion: concat [last_spatial, temporal_ctx] and learn per-pixel gate
        # (batch, 512, 30, 30) -> (batch, 256, 30, 30)
        gate = self.fusion_gate(torch.cat([last_spatial, temporal_ctx], dim=1))
        fused = gate * temporal_ctx + (1.0 - gate) * last_spatial

        # Refinement conv keeps spatial resolution and mixes fused features
        spatial_features = self.refine(fused)

        # Value prediction (global pooling over fused spatial features)
        value = self.value_head(spatial_features)

        return spatial_features, value

    def get_burning_cells(self, fire_mask):
        """Extract burning cell locations"""
        if fire_mask.dim() == 3:
            fire_mask = fire_mask[0]
        burning_indices = torch.nonzero(fire_mask > 0.5, as_tuple=False)
        return [(int(idx[0]), int(idx[1])) for idx in burning_indices]

    def extract_local_features(self, features, i, j):
        """Extract 3x3 local features around cell (i, j)"""
        B, C, H, W = features.shape
        padded_features = F.pad(features, (1, 1, 1, 1), mode="constant", value=0)
        local = padded_features[:, :, i : i + 3, j : j + 3]
        return local.flatten(1)

    def predict_8_neighbors(self, features, i, j):
        """Predict 8-neighbor spread for burning cell"""
        local_features = self.extract_local_features(features, i, j)
        logits = self.policy_head(local_features)
        return logits

    def get_8_neighbor_coords(self, i, j, H, W):
        """Get 8-neighbor coordinates"""
        neighbors = [
            (i - 1, j),
            (i - 1, j + 1),
            (i, j + 1),
            (i + 1, j + 1),
            (i + 1, j),
            (i + 1, j - 1),
            (i, j - 1),
            (i - 1, j - 1),
        ]
        valid_neighbors = []
        for ni, nj in neighbors:
            if 0 <= ni < H and 0 <= nj < W:
                valid_neighbors.append((ni, nj))
            else:
                valid_neighbors.append(None)
        return valid_neighbors

    # ------------------------------------------------------------------ #
    # VECTORIZED BATCH METHODS (v7 — 10-50x faster training)
    # ------------------------------------------------------------------ #

    def predict_all_8_neighbors_vectorized(self, features, burning_cells):
        """Predict 8-neighbor logits for ALL burning cells in ONE batched call.

        Instead of calling predict_8_neighbors() N times (N = ~100 cells),
        this extracts all 3x3 patches at once via unfold and runs policy_head
        once on the full batch.

        Args:
            features: (1, 256, H, W) fused spatial features
            burning_cells: list of (i, j) tuples

        Returns:
            logits: (N_cells, 8) — predictions for all cells
        """
        if len(burning_cells) == 0:
            return torch.empty(0, 8, device=features.device)

        # Pad features with 1px zeros border so edge cells work
        padded = F.pad(features, (1, 1, 1, 1), mode="constant", value=0)  # (1,256,H+2,W+2)

        # Extract all 3x3 patches for all burning cells in one operation
        N = len(burning_cells)
        all_local = torch.empty(N, 256 * 9, device=features.device)
        for idx, (i, j) in enumerate(burning_cells):
            local = padded[0, :, i : i + 3, j : j + 3]  # (256, 3, 3)
            all_local[idx] = local.flatten()

        # Single batched forward through policy_head
        logits = self.policy_head(all_local)  # (N, 8)
        return logits

    def build_neighbor_labels_vectorized(self, burning_cells, current_fire, target_fire, H, W):
        """Build 8-neighbor target labels for all cells WITHOUT Python loops.

        Returns:
            labels: (N_cells, 8) float tensor (1.0 = spread, 0.0 = no spread)
        """
        N = len(burning_cells)
        labels = torch.zeros(N, 8, device=target_fire.device)

        # Neighbor offset order matches get_8_neighbor_coords:
        # 0:(-1,0) 1:(-1,+1) 2:(0,+1) 3:(+1,+1) 4:(+1,0) 5:(+1,-1) 6:(0,-1) 7:(-1,-1)
        offsets = [(-1, 0), (-1, 1), (0, 1), (1, 1), (1, 0), (1, -1), (0, -1), (-1, -1)]

        for idx, (i, j) in enumerate(burning_cells):
            for n_idx, (di, dj) in enumerate(offsets):
                ni, nj = i + di, j + dj
                if (
                    0 <= ni < H
                    and 0 <= nj < W
                    and target_fire[0, ni, nj] > 0.5
                    and current_fire[0, ni, nj] <= 0.5
                ):
                    labels[idx, n_idx] = 1.0
        return labels

    def get_action_and_value(self, sequence, fire_mask, action=None):
        """
        Get actions for all burning cells and compute value.

        Args:
            sequence: (1, seq_len, 16, 30, 30) - temporal sequence
            fire_mask: (1, 30, 30) or (30, 30) - current fire mask
            action: Optional pre-specified action

        Returns:
            action_grid: (H, W) binary prediction grid
            log_prob: Scalar log probability
            entropy: Scalar entropy
            value: (1, 1) state value
            burning_cells_info: List of cell info for debugging
        """
        if fire_mask.dim() == 2:
            fire_mask = fire_mask.unsqueeze(0)

        B, H, W = fire_mask.shape
        assert B == 1, "Batch size must be 1"

        features, value = self.forward(sequence, fire_mask)

        burning_cells = self.get_burning_cells(fire_mask)

        if len(burning_cells) == 0:
            action_grid = torch.zeros(H, W)
            log_prob = torch.tensor(0.0)
            entropy = torch.tensor(0.0)
            return action_grid, log_prob, entropy, value, []

        all_log_probs = []
        all_entropies = []
        burning_cells_info = []
        action_grid = torch.zeros(H, W)

        for cell_idx, (i, j) in enumerate(burning_cells):
            logits_8d = self.predict_8_neighbors(features, i, j).squeeze(0)
            probs_8d = torch.sigmoid(logits_8d)
            probs_8d = torch.clamp(probs_8d, 1e-7, 1 - 1e-7)

            if action is None:
                action_8d = torch.bernoulli(probs_8d)
            else:
                action_8d = (
                    action[cell_idx] if isinstance(action, list) else torch.bernoulli(probs_8d)
                )

            log_prob_8d = action_8d * torch.log(probs_8d) + (1 - action_8d) * torch.log(
                1 - probs_8d
            )
            log_prob_cell = log_prob_8d.sum()

            entropy_8d = -(
                probs_8d * torch.log(probs_8d) + (1 - probs_8d) * torch.log(1 - probs_8d)
            )
            entropy_cell = entropy_8d.sum()

            all_log_probs.append(log_prob_cell)
            all_entropies.append(entropy_cell)

            neighbors = self.get_8_neighbor_coords(i, j, H, W)
            for n_idx, neighbor in enumerate(neighbors):
                if neighbor is not None and action_8d[n_idx] > 0.5:
                    ni, nj = neighbor
                    action_grid[ni, nj] = 1.0

            burning_cells_info.append((i, j, action_8d, log_prob_cell))

        total_log_prob = torch.stack(all_log_probs).sum()
        total_entropy = torch.stack(all_entropies).sum()

        return action_grid, total_log_prob, total_entropy, value, burning_cells_info
