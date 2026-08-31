#!/usr/bin/env python3
"""Create a self-contained HTML preview from the editable DC export."""
import argparse
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    html = (ROOT / "web/index.html").read_text(encoding="utf-8")
    for name in ["vendor/react.production.min.js", "vendor/react-dom.production.min.js", "support.js"]:
        source = (ROOT / "web" / name).read_text(encoding="utf-8")
        if "</script" in source.lower():
            raise ValueError(f"Unsafe inline-script delimiter in {name}")
        html = html.replace(f'<script src="./{name}"></script>', '<script>\n' + source + '\n</script>')
    # The portable preview opens directly on the new page; Launch remains accessible.
    html = html.replace('<head>', '<head>\n<script>if (!location.hash) location.hash = "public-repos";</script>', 1)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(html, encoding="utf-8")
    print(f"Created self-contained preview: {args.output}")


if __name__ == "__main__":
    main()
