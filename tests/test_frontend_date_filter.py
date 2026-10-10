import os
import subprocess
import threading
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path

import app


ROOT = Path(__file__).resolve().parents[1]
CHROME = Path("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome")


class FrontendDateFilterTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not CHROME.is_file():
            raise unittest.SkipTest("Google Chrome is required for the frontend regression test")
        try:
            subprocess.run(
                ["node", "-e", "require.resolve('playwright')"],
                cwd=ROOT,
                check=True,
                capture_output=True,
                text=True,
            )
        except (OSError, subprocess.CalledProcessError) as error:
            raise unittest.SkipTest("Playwright is required for the frontend regression test") from error

    def test_order_date_filter_activates_daily_data(self):
        server = ThreadingHTTPServer(("127.0.0.1", 0), app.Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            env = os.environ.copy()
            env["PLAYWRIGHT_CHROME_EXECUTABLE"] = str(CHROME)
            subprocess.run(
                [
                    "node",
                    "tests/frontend_date_filter.mjs",
                    f"http://127.0.0.1:{server.server_port}",
                ],
                cwd=ROOT,
                env=env,
                check=True,
                capture_output=True,
                text=True,
                timeout=30,
            )
        finally:
            server.shutdown()
            server.server_close()
            thread.join()


if __name__ == "__main__":
    unittest.main()
