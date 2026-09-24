import json
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from hostpulse import check_endpoint, load_checks, main


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/missing":
            self.send_response(404)
            body = b"missing"
        else:
            self.send_response(200)
            body = b"service ready"
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *_args):
        pass


class HostPulseTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.base = f"http://127.0.0.1:{cls.server.server_port}"

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join()

    def test_status_and_content_pass(self):
        result = check_endpoint({"name": "site", "url": self.base, "expected_status": 200, "contains": "ready"}, 2)
        self.assertTrue(result["ok"])
        self.assertEqual(result["status"], 200)

    def test_mismatch_fails(self):
        result = check_endpoint({"name": "site", "url": self.base, "expected_status": 201, "contains": None}, 2)
        self.assertFalse(result["ok"])
        self.assertEqual(result["reason"], "expected HTTP 201")

    def test_expected_error_status_can_pass(self):
        result = check_endpoint({"name": "missing", "url": self.base + "/missing", "expected_status": 404, "contains": None}, 2)
        self.assertTrue(result["ok"])

    def test_rejects_duplicate_names_and_url_credentials(self):
        with tempfile.TemporaryDirectory() as directory:
            config = Path(directory) / "checks.json"
            config.write_text(json.dumps([{"name": "a", "url": self.base}, {"name": "a", "url": self.base}]))
            with self.assertRaisesRegex(ValueError, "unique"):
                load_checks(config)
            config.write_text(json.dumps([{"name": "a", "url": "https://user:pass@example.com"}]))
            with self.assertRaisesRegex(ValueError, "credentials"):
                load_checks(config)

    def test_exit_status(self):
        with tempfile.TemporaryDirectory() as directory:
            config = Path(directory) / "checks.json"
            config.write_text(json.dumps([{"name": "site", "url": self.base}]))
            self.assertEqual(main([str(config), "--json"]), 0)
            config.write_text(json.dumps([{"name": "site", "url": self.base, "expected_status": 500}]))
            self.assertEqual(main([str(config), "--json"]), 1)


if __name__ == "__main__":
    unittest.main()
