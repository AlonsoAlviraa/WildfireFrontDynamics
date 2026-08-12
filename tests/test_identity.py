from wildfire_front.identity import build_observation_id


class IdentityTests:
    def test_observation_id_is_stable_and_portable(self) -> None:
        first = build_observation_id("burn / 01", "thermal:1", "2026-06-10T12:00:00Z")
        second = build_observation_id("burn / 01", "thermal:1", "2026-06-10T12:00:00Z")
        assert first == second
        assert "/" not in first
        assert ":" not in first
