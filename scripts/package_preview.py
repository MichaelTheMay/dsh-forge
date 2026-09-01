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
    for name in ["vendor/react.production.min.js", "vendor/react-dom.production.min.js", "launcher.js", "support.js"]:
        source = (ROOT / "web" / name).read_text(encoding="utf-8")
        if "</script" in source.lower():
            raise ValueError(f"Unsafe inline-script delimiter in {name}")
        html = html.replace(f'<script src="./{name}"></script>', '<script>\n' + source + '\n</script>')
    # Launch remains the default. This export is an honest disconnected preview.
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(html, encoding="utf-8")
    print(f"Created self-contained preview: {args.output}")


if __name__ == "__main__":
    main()
