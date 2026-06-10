import json
import tempfile
import unittest
from pathlib import Path

from wildfire_front.cli import run_demo
from wildfire_front.models import ScenarioConfig
from wildfire_front.reconstruction import estimate_local_speeds, reconstruct_arrival_grid, summarize
from wildfire_front.synthetic import generate_observations


class PipelineTests(unittest.TestCase):
    def test_reconstruction_is_monotonic_and_measurable(self) -> None:
        config = ScenarioConfig(position_error_m=0.2)
        observations = generate_observations(config)
        estimates = estimate_local_speeds(observations, config)
        _, _, arrival = reconstruct_arrival_grid(observations, config)
        metrics = summarize(estimates, arrival)
        self.assertGreater(metrics["observable_ratio"], 0.75)
        self.assertLess(metrics["speed_mae_m_min"], 0.35)
        self.assertGreater(metrics["arrival_cells_observed"], 100)

    def test_demo_writes_complete_artifact_set(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp)
            metrics = run_demo(output, seed=11, position_error_m=0.4)
            expected = {
                "fronts.geojson",
                "observations_manifest.csv",
                "arrival_time.csv",
                "local_speeds.csv",
                "fronts.svg",
                "report.html",
                "summary.json",
            }
            self.assertEqual(expected, {item.name for item in output.iterdir()})
            geojson = json.loads((output / "fronts.geojson").read_text(encoding="utf-8"))
            self.assertEqual(geojson["type"], "FeatureCollection")
            self.assertEqual(len(geojson["features"]), metrics["num_observations"] * 2)

    def test_high_error_causes_abstention(self) -> None:
        low_error = ScenarioConfig(position_error_m=0.2)
        high_error = ScenarioConfig(position_error_m=3.0)
        low = estimate_local_speeds(generate_observations(low_error), low_error)
        high = estimate_local_speeds(generate_observations(high_error), high_error)
        self.assertGreater(sum(item.observable for item in low), sum(item.observable for item in high))

    def test_invalid_config_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            generate_observations(ScenarioConfig(position_error_m=-1.0))


if __name__ == "__main__":
    unittest.main()
