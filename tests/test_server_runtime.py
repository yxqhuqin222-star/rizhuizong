import json
import threading
import unittest
from http.server import ThreadingHTTPServer
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
            {"health", "reload-demo", "reload-target"}.issubset(payload["capabilities"])
        )

    def test_fixed_file_reload_endpoints_return_json(self):
        fake_state = {"summary": [], "latestSummary": [], "files": {}, "metrics": {}}

        with (
            patch("app.rebuild_outputs") as rebuild,
            patch("app.state_payload", return_value=fake_state),
        ):
            for kind in ("demo", "target"):
                status, payload = self.request_json(f"/api/reload-{kind}", method="POST")
                self.assertEqual(status, 200)
                self.assertTrue(payload["ok"])
                self.assertEqual(payload["changed"], [kind])
                self.assertEqual(payload["state"], fake_state)

        self.assertEqual(rebuild.call_count, 2)


if __name__ == "__main__":
    unittest.main()
