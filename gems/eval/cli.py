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

    collect = commands.add_parser("backtest-collect", help="gather the backtest dataset from GitHub (needs GITHUB_TOKEN)")
    collect.add_argument("--registry", required=True, help="the published registry.json or .json.gz")
    collect.add_argument("--workdir", required=True)
    collect.add_argument("--output", required=True)
    collect.add_argument("--days", type=int, default=60)
    collect.add_argument("--size", type=int, default=200)
    collect.add_argument("--seed", type=int, default=7)

    rescore = commands.add_parser("backtest-score", help="score a collected backtest with the current ranking code")
    rescore.add_argument("--dataset", required=True)
    rescore.add_argument("--output", required=True)

    label = commands.add_parser("label", help="open a local page to mark picks as gem or not")
    label.add_argument("--picks", required=True)
    label.add_argument("--labels", default=str(labels_module.DEFAULT_PATH))
    label.add_argument("--port", type=int, default=0)


def dispatch(args) -> int:
    if args.command == "eval":
        picks = json.loads(Path(args.picks).read_text(encoding="utf-8"))
        backtest = json.loads(Path(args.backtest).read_text(encoding="utf-8")) if args.backtest else None
        row = scoreboard.score(picks, labels_module.load(args.labels), backtest)
        if args.note:
            scoreboard.append_history(row, args.note)
        print(json.dumps(row, sort_keys=True) if args.json else scoreboard.render(row))
        return 0
    if args.command == "backtest-collect":
        import datetime as dt

        from . import backtest
        from ..pipeline import write_json

        dataset = backtest.collect(
            args.registry, args.workdir, post=backtest.github_post(backtest.token_from_environment()),
            now=dt.datetime.now(dt.timezone.utc), days_back=args.days, size=args.size, seed=args.seed,
            report=lambda line: print(line, file=sys.stderr),
        )
        write_json(args.output, dataset)
        print(json.dumps({"sampled": dataset["sampled"], "rows": len(dataset["rows"]), "rewound_to": dataset["rewound_to"]}))
        return 0
    if args.command == "backtest-score":
        from . import backtest
        from ..pipeline import write_json

        scored = backtest.score_rows(json.loads(Path(args.dataset).read_text(encoding="utf-8")))
        write_json(args.output, scored)
        print(json.dumps({"rows": len(scored["rows"])}))
        return 0
    if args.command == "label":
        from .label_server import serve

        server = serve(args.picks, args.labels, port=args.port)
        print(f"Label picks at http://127.0.0.1:{server.server_address[1]}/  (Ctrl+C to stop)", flush=True)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass
        finally:
            server.server_close()
        return 0
    print(f"unknown command: {args.command}", file=sys.stderr)
    return 2
