import json
import tempfile
import threading
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path
from urllib.request import Request, urlopen
from unittest.mock import patch

import app


class ServerRuntimeTest(unittest.TestCase):
    def setUp(self):
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), app.Handler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.base_url = f"http://127.0.0.1:{self.server.server_port}"

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()

    def request_json(self, path, method="GET"):
        request = Request(f"{self.base_url}{path}", method=method)
        with urlopen(request, timeout=5) as response:
            self.assertEqual(response.headers.get_content_type(), "application/json")
            return response.status, json.load(response)

    def test_health_reports_required_capabilities(self):
        status, payload = self.request_json("/api/health")

        self.assertEqual(status, 200)
        self.assertTrue(payload["ok"])
        self.assertTrue(
            {"health", "reload-demo", "reload-target", "online-sync"}.issubset(
                payload["capabilities"]
            )
        )

    def test_fixed_file_reload_endpoints_return_json(self):
        fake_state = {"summary": [], "latestSummary": [], "files": {}, "metrics": {}}

        with (
            patch("app.rebuild_outputs") as rebuild,
            patch("app.record_upload_time") as record_upload_time,
            patch("app.state_payload", return_value=fake_state),
            patch("app.sync_online_state", return_value={"ok": True}) as sync_online_state,
        ):
            for kind in ("demo", "target"):
                status, payload = self.request_json(f"/api/reload-{kind}", method="POST")
                self.assertEqual(status, 200)
                self.assertTrue(payload["ok"])
                self.assertEqual(payload["changed"], [kind])
                self.assertEqual(payload["state"], fake_state)
                self.assertEqual(payload["sync"], {"ok": True})

        self.assertEqual(rebuild.call_count, 2)
        self.assertEqual(sync_online_state.call_count, 2)
        self.assertEqual(
            record_upload_time.call_args_list,
            [unittest.mock.call(["demo"]), unittest.mock.call(["target"])],
        )

    def test_online_sync_can_be_skipped_when_token_is_missing(self):
        with patch("app.DASHBOARD_SYNC_TOKEN", ""):
            result = app.sync_online_state({"summary": [], "latestSummary": [], "metrics": {}})

        self.assertFalse(result["ok"])
        self.assertTrue(result["skipped"])

    def test_file_info_uses_recorded_upload_time_not_file_mtime(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            document_path = Path(temp_dir) / "tongji_demo.xlsx"
            metadata_path = Path(temp_dir) / "upload_metadata.json"
            document_path.write_bytes(b"first version")

            with patch("app.UPLOAD_METADATA_PATH", metadata_path):
                self.assertIsNone(app.file_info(document_path, "demo")["uploaded_at"])

                app.record_upload_time(["demo"])
                uploaded_at = app.file_info(document_path, "demo")["uploaded_at"]
                self.assertIsNotNone(uploaded_at)

                document_path.write_bytes(b"new version with a new file mtime")
                self.assertEqual(
                    app.file_info(document_path, "demo")["uploaded_at"],
                    uploaded_at,
                )


if __name__ == "__main__":
    unittest.main()
