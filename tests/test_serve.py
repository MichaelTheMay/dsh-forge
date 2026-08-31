import importlib.util
from functools import partial
from http.server import ThreadingHTTPServer
from pathlib import Path
import threading
import unittest
import urllib.error
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("serve", ROOT / "scripts/serve.py")
serve = importlib.util.module_from_spec(spec)
spec.loader.exec_module(serve)


class StaticServer(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        class QuietHandler(serve.StaticUIHandler):
            def log_message(self, *_args):
                pass
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), partial(QuietHandler, directory=str(serve.WEB_ROOT)))
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.url = "http://127.0.0.1:" + str(cls.server.server_address[1])

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join(timeout=3)

    def test_index_and_local_dependencies(self):
        for path in ["/", "/support.js", "/vendor/react.production.min.js", "/vendor/react-dom.production.min.js"]:
            with urllib.request.urlopen(self.url + path, timeout=3) as response:
                self.assertEqual(response.status, 200)
                self.assertEqual(response.headers["X-Content-Type-Options"], "nosniff")
                self.assertGreater(len(response.read()), 1000)

    def test_source_git_and_directory_listings_are_not_served(self):
        for path in ["/.git/config", "/../.git/config", "/scripts/seed_catalog.py", "/vendor/"]:
            with self.assertRaises(urllib.error.HTTPError) as context:
                urllib.request.urlopen(self.url + path, timeout=3)
            self.assertEqual(context.exception.code, 404)

    def test_no_mutation_endpoints(self):
        for path in ["/api/launch", "/api/install", "/api/merge"]:
            request = urllib.request.Request(self.url + path, data=b"{}", method="POST")
            with self.assertRaises(urllib.error.HTTPError) as context:
                urllib.request.urlopen(request, timeout=3)
            self.assertEqual(context.exception.code, 501)


if __name__ == "__main__":
    unittest.main()
