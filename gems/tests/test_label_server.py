import json
from pathlib import Path
import tempfile
import threading
import unittest
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from gems.eval import labels
from gems.eval.label_server import serve


class LabelServerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        root = Path(self.temp.name)
        self.labels = root / "labels.json"
        picks = root / "picks.json"
        picks.write_text(json.dumps({"picks": [
            {"full_name": "a/gem", "rank": 1, "stars": 2, "confidence": "reviewed",
             "summary": "<img src=x onerror=alert(1)>", "reasons": ["r"], "score": 90, "parts": {"secret": 1}},
        ]}), encoding="utf-8")
        self.server = serve(picks, self.labels)
        self.base = f"http://127.0.0.1:{self.server.server_address[1]}"
        thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        thread.start()
        self.addCleanup(self.server.server_close)
        self.addCleanup(self.server.shutdown)

    def post(self, body, content_type="application/json", host=None):
        headers = {"Content-Type": content_type}
        if host:
            headers["Host"] = host
        request = Request(self.base + "/label", data=json.dumps(body).encode(), headers=headers, method="POST")
        with urlopen(request, timeout=5) as response:
            return response.status, json.loads(response.read())

    def test_serves_the_page_and_only_the_fields_it_needs(self):
        with urlopen(self.base + "/", timeout=5) as response:
            page = response.read().decode()
            self.assertIn("frame-ancestors 'none'", response.headers["Content-Security-Policy"])
        self.assertIn("Is each of these a hidden gem?", page)
        # Pick text reaches the page as data and is inserted with textContent, not markup.
        self.assertNotIn("onerror", page)
        self.assertNotIn("innerHTML", page)
        with urlopen(self.base + "/state", timeout=5) as response:
            state = json.loads(response.read())
        self.assertEqual(set(state["picks"][0]), {"full_name", "rank", "stars", "confidence", "summary", "reasons"})

    def test_a_click_saves_a_label(self):
        self.assertEqual(self.post({"name": "a/gem", "gem": True}), (200, {"labels": 1}))
        self.assertEqual(labels.load(self.labels), {"a/gem": True})
        self.post({"name": "a/gem", "gem": False})
        self.assertEqual(labels.load(self.labels), {"a/gem": False})

    def test_rejects_unknown_picks_bad_bodies_and_cross_site_posts(self):
        for body, kwargs in [
            ({"name": "not/listed", "gem": True}, {}),
            ({"name": "a/gem", "gem": "yes"}, {}),
            ({"name": "a/gem", "gem": True}, {"content_type": "text/plain"}),
            ({"name": "a/gem", "gem": True}, {"host": "evil.example"}),
        ]:
            with self.subTest(body=body, kwargs=kwargs), self.assertRaises(HTTPError) as caught:
                self.post(body, **kwargs)
            self.assertIn(caught.exception.code, (400, 403))
        self.assertEqual(labels.load(self.labels), {})


if __name__ == "__main__":
    unittest.main()
