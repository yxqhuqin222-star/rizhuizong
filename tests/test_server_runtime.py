import json
import tempfile
import threading
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path
from urllib.error import URLError
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
        self.assertIn("sync", payload)

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
        with (
            tempfile.TemporaryDirectory() as temp_dir,
            patch("app.STATE_DIR", Path(temp_dir)),
            patch("app.SYNC_QUEUE_PATH", Path(temp_dir) / "sync_queue.json"),
            patch("app.DASHBOARD_SYNC_TOKEN", ""),
        ):
            result = app.sync_online_state({"summary": [], "latestSummary": [], "metrics": {}})

        self.assertFalse(result["ok"])
        self.assertTrue(result["queued"])
        self.assertTrue(result["queue"]["pending"])
        self.assertIn("缺少 DASHBOARD_SYNC_TOKEN", result["queue"]["lastError"])

    def test_failed_online_sync_is_saved_and_later_retried(self):
        with (
            tempfile.TemporaryDirectory() as temp_dir,
            patch("app.STATE_DIR", Path(temp_dir)),
            patch("app.SYNC_QUEUE_PATH", Path(temp_dir) / "sync_queue.json"),
            patch("app.perform_online_sync", side_effect=RuntimeError("temporary refusal")),
        ):
            failed = app.sync_online_state({"summary": [], "latestSummary": [], "metrics": {}})

            self.assertFalse(failed["ok"])
            self.assertTrue(failed["queue"]["pending"])
            self.assertEqual(failed["queue"]["attempts"], 1)
            self.assertIn("temporary refusal", failed["queue"]["lastError"])

            with (
                patch("app.perform_online_sync", return_value={"ok": True, "syncedAt": "2026-07-19T10:00:00+08:00"}),
                patch("app.state_payload", return_value={"summary": [], "latestSummary": [], "metrics": {}}),
            ):
                retried = app.retry_pending_sync_once()

            self.assertTrue(retried["ok"])
            self.assertFalse(app.sync_queue_status()["pending"])
            self.assertEqual(app.sync_queue_status()["syncedAt"], "2026-07-19T10:00:00+08:00")

    def test_successful_online_sync_uploads_synced_queue_status(self):
        stale_sync = {"pending": True, "status": "failed", "lastError": "old refusal"}
        uploaded_payloads = []

        def fake_post(url, data, content_type):
            uploaded_payloads.append((url, data, content_type))
            return {"ok": True}

        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir)
            (output_dir / "tongji_summary_current.xlsx").write_bytes(b"workbook")
            with (
                patch("app.OUTPUT_DIR", output_dir),
                patch("app.REPORT_FILES", {}),
                patch("app.DASHBOARD_SYNC_TOKEN", "token"),
                patch("app.DASHBOARD_WORKBOOK_UPLOAD_URL", "https://example.com/workbook"),
                patch("app.DASHBOARD_STATE_UPLOAD_URL", "https://example.com/state"),
                patch("app.post_online_bytes", side_effect=fake_post),
            ):
                app.perform_online_sync({"summary": [], "sync": stale_sync})

        state_payload = json.loads(uploaded_payloads[1][1].decode("utf-8"))
        self.assertFalse(state_payload["sync"]["pending"])
        self.assertEqual(state_payload["sync"]["status"], "synced")
        self.assertIsNone(state_payload["sync"]["lastError"])
        self.assertEqual(state_payload["sync"]["syncedAt"], state_payload["syncedAt"])

    def test_retry_sync_endpoint_returns_json(self):
        with patch("app.retry_pending_sync_once", return_value={"ok": True, "skipped": True}):
            status, payload = self.request_json("/api/retry-sync", method="POST")

        self.assertEqual(status, 200)
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["sync"], {"ok": True, "skipped": True})

    def test_online_request_retries_transient_connection_refusal(self):
        response = unittest.mock.MagicMock()
        response.__enter__.return_value.read.return_value = b'{"ok": true}'
        response.__enter__.return_value.headers = {}

        with (
            patch(
                "app.urlopen",
                side_effect=[URLError(ConnectionRefusedError(61, "Connection refused")), response],
            ) as mocked_urlopen,
            patch("app.time.sleep") as mocked_sleep,
        ):
            result = app.post_online_bytes(
                "https://example.test/api/state",
                b'{"summary":[],"latestSummary":[],"metrics":{}}',
                "application/json; charset=utf-8",
            )

        self.assertEqual(result, {"ok": True})
        self.assertEqual(mocked_urlopen.call_count, 2)
        mocked_sleep.assert_called_once_with(2)

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
