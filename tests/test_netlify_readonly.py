import json
import subprocess
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class NetlifyReadonlyBuildTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        subprocess.run(
            ["python3", "scripts/build_netlify_readonly.py"],
            cwd=ROOT,
            check=True,
        )

    def test_dashboard_state_and_assets_are_published(self):
        public = ROOT / "netlify" / "public"
        state = json.loads((public / "api" / "state.json").read_text(encoding="utf-8"))

        self.assertTrue(state["summary"])
        self.assertTrue(state["latestSummary"])
        self.assertIn("latest", state["metrics"])
        self.assertIn("DASHBOARD_READ_ONLY", (public / "web" / "index.html").read_text())
        self.assertTrue((public / "downloads" / "tongji_summary_current.xlsx").is_file())

        for name in (
            "primary_daily_progress.png",
            "middle_daily_progress.png",
            "high_daily_progress.png",
            "lec1_share.png",
        ):
            self.assertTrue((public / "reports" / name).is_file())


if __name__ == "__main__":
    unittest.main()
