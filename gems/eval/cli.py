"""Evaluation commands, registered on the main ``python3 -m gems`` parser."""

from __future__ import annotations

import json
from pathlib import Path
import sys

from . import labels as labels_module
from . import scoreboard


def register(commands) -> None:
    evaluate = commands.add_parser("eval", help="score a picks file against labels and the backtest")
    evaluate.add_argument("--picks", required=True)
    evaluate.add_argument("--labels", default=str(labels_module.DEFAULT_PATH))
    evaluate.add_argument("--backtest", help="a scored backtest file from `backtest-score`")
    evaluate.add_argument("--note", help="append this run to the history file with a note")
    evaluate.add_argument("--json", action="store_true")


def dispatch(args) -> int:
    if args.command == "eval":
        picks = json.loads(Path(args.picks).read_text(encoding="utf-8"))
        backtest = json.loads(Path(args.backtest).read_text(encoding="utf-8")) if args.backtest else None
        row = scoreboard.score(picks, labels_module.load(args.labels), backtest)
        if args.note:
            scoreboard.append_history(row, args.note)
        print(json.dumps(row, sort_keys=True) if args.json else scoreboard.render(row))
        return 0
    print(f"unknown command: {args.command}", file=sys.stderr)
    return 2
