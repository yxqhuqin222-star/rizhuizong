import importlib.util
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "scripts" / "publish_netlify.py"
SPEC = importlib.util.spec_from_file_location("publish_netlify", MODULE_PATH)
publish_netlify = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(publish_netlify)


class PublishNetlifyTests(unittest.TestCase):
    def test_current_outputs_are_consistent(self):
        payload, snapshot = publish_netlify.validate_outputs()

        self.assertTrue(payload["latest_summary"]["rows"])
        self.assertEqual(set(snapshot), {"小学", "初中", "高中"})
        for department in snapshot.values():
            self.assertGreater(department["target"], 0)
            self.assertGreaterEqual(department["current"], 0)
            self.assertGreaterEqual(department["progress"], 0)
            self.assertLessEqual(department["progress"], 1)

    def test_porcelain_parser_preserves_unicode_names(self):
        paths = publish_netlify.parse_porcelain_paths(
            " M outputs/tongji_summary/distribution_学部.csv\0"
            "?? reports/daily_progress/小学.png\0"
        )

        self.assertEqual(
            paths,
            [
                "outputs/tongji_summary/distribution_学部.csv",
                "reports/daily_progress/小学.png",
            ],
        )


if __name__ == "__main__":
    unittest.main()
