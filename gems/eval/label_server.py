"""A one-page local tool for judging picks: gem, or not a gem.

Runs on this computer only (loopback). Each click writes straight to
``labels.json``. Text from the picks file is untrusted, so the page inserts it as
text, never as HTML.
"""

from __future__ import annotations

import datetime as dt
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
from typing import Any

from . import labels as labels_module

MAX_BODY = 4096

PAGE = """<!doctype html>
<html lang="en"><head><meta charset="utf-8"><title>Label gem picks</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
<style>
  body { font: 16px/1.5 system-ui, sans-serif; max-width: 760px; margin: 2rem auto; padding: 0 1rem; color: #1a1a1a; background: #fafafa; }
  h1 { font-size: 1.4rem; margin-bottom: .2rem; }
  .lead { color: #555; margin-top: 0; }
  .pick { background: #fff; border: 1px solid #ddd; border-radius: 10px; padding: 1rem 1.1rem; margin: .9rem 0; }
  .pick.gem { border-color: #2e8b57; box-shadow: inset 4px 0 0 #2e8b57; }
  .pick.not { border-color: #b5651d; box-shadow: inset 4px 0 0 #b5651d; }
  .name { font-weight: 650; }
  .name a { color: #0b57d0; text-decoration: none; }
  .meta { color: #666; font-size: .88rem; }
  ul { margin: .4rem 0 .7rem 1.1rem; padding: 0; }
  button { font: inherit; padding: .4rem .9rem; border-radius: 8px; border: 1px solid #bbb; background: #fff; cursor: pointer; margin-right: .5rem; }
  button.on { background: #1a1a1a; color: #fff; border-color: #1a1a1a; }
  #count { position: sticky; top: 0; background: #fafafa; padding: .5rem 0; font-weight: 600; }
</style></head><body>
<h1>Is each of these a hidden gem?</h1>
<p class="lead">Open the project, look for a minute, and choose. Your answers are saved as you click and are used to score the gem system.</p>
<div id="count"></div><div id="list"></div>
<script>
const list = document.getElementById('list'), count = document.getElementById('count');
let state = {picks: [], labels: {}};
function el(tag, text, cls) { const n = document.createElement(tag); if (text !== undefined) n.textContent = text; if (cls) n.className = cls; return n; }
function draw() {
  list.replaceChildren();
  const done = state.picks.filter(p => p.full_name.toLowerCase() in state.labels).length;
  count.textContent = done + ' of ' + state.picks.length + ' labelled';
  for (const p of state.picks) {
    const key = p.full_name.toLowerCase(), label = state.labels[key];
    const card = el('div', undefined, 'pick' + (label === true ? ' gem' : label === false ? ' not' : ''));
    const name = el('div', undefined, 'name'), link = el('a', p.full_name);
    link.href = 'https://github.com/' + encodeURI(p.full_name); link.target = '_blank'; link.rel = 'noopener noreferrer';
    name.append(link); card.append(name);
    card.append(el('div', '#' + p.rank + ' · ' + p.stars + ' stars · ' + p.confidence, 'meta'));
    card.append(el('p', p.summary || ''));
    const reasons = el('ul'); for (const r of (p.reasons || [])) reasons.append(el('li', r)); card.append(reasons);
    for (const [text, value] of [['Gem', true], ['Not a gem', false]]) {
      const b = el('button', text, label === value ? 'on' : '');
      b.onclick = async () => {
        const r = await fetch('/label', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({name: p.full_name, gem: value})});
        if (r.ok) { state.labels[key] = value; draw(); }
      };
      card.append(b);
    }
    list.append(card);
  }
}
fetch('/state').then(r => r.json()).then(s => { state = s; draw(); });
</script></body></html>
"""


def make_handler(picks: list[dict[str, Any]], labels_path: Path, who: str):
    names = {str(pick.get("full_name")) for pick in picks}

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_args):  # quiet
            return

        def _send(self, status: int, body: bytes, content_type: str) -> None:
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Security-Policy", "default-src 'self' 'unsafe-inline'; frame-ancestors 'none'")
            self.end_headers()
            self.wfile.write(body)

        def _local(self) -> bool:
            host = (self.headers.get("Host") or "").rsplit(":", 1)[0]
            return host in {"127.0.0.1", "localhost"}

        def do_GET(self):  # noqa: N802
            if not self._local():
                return self._send(403, b"forbidden", "text/plain")
            if self.path == "/":
                return self._send(200, PAGE.encode("utf-8"), "text/html; charset=utf-8")
            if self.path == "/state":
                body = json.dumps({"picks": picks, "labels": labels_module.load(labels_path)}).encode("utf-8")
                return self._send(200, body, "application/json")
            return self._send(404, b"not found", "text/plain")

        def do_POST(self):  # noqa: N802
            # A JSON content type cannot be sent cross-site without a preflight, which
            # this server never answers, so another web page cannot write labels.
            if not self._local() or self.path != "/label" or self.headers.get("Content-Type") != "application/json":
                return self._send(403, b"forbidden", "text/plain")
            try:
                length = int(self.headers.get("Content-Length") or 0)
                if not 0 < length <= MAX_BODY:
                    raise ValueError("bad length")
                data = json.loads(self.rfile.read(length))
                name, gem = data["name"], data["gem"]
                if name not in names or not isinstance(gem, bool):
                    raise ValueError("unknown pick")
                at = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d")
                total = labels_module.save_one(name, gem, by=who, at=at, path=labels_path)
            except (ValueError, KeyError, TypeError):
                return self._send(400, b"bad request", "text/plain")
            return self._send(200, json.dumps({"labels": total}).encode("utf-8"), "application/json")

    return Handler


def serve(picks_path: str | Path, labels_path: str | Path, *, port: int = 0, who: str = "owner") -> ThreadingHTTPServer:
    """Build the server (not yet serving). Binds to loopback only."""
    document = json.loads(Path(picks_path).read_text(encoding="utf-8"))
    picks = [
        {key: pick.get(key) for key in ("full_name", "rank", "stars", "confidence", "summary", "reasons")}
        for pick in document.get("picks") or []
    ]
    return ThreadingHTTPServer(("127.0.0.1", port), make_handler(picks, Path(labels_path), who))
