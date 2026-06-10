import unittest

from wildfire_front.identity import build_observation_id


class IdentityTests(unittest.TestCase):
    def test_observation_id_is_stable_and_portable(self) -> None:
        first = build_observation_id("burn / 01", "thermal:1", "2026-06-10T12:00:00Z")
        second = build_observation_id("burn / 01", "thermal:1", "2026-06-10T12:00:00Z")
        self.assertEqual(first, second)
        self.assertNotIn("/", first)
        self.assertNotIn(":", first)


if __name__ == "__main__":
    unittest.main()

