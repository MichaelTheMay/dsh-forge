"""Command line for the hidden-gem system: ``python3 -m gems <command>``."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from . import pipeline
from .candidates import DEFAULT_LIMIT, CandidateError, load_queue, select
from .review import RUBRIC, review_filename, template

HERE = Path(__file__).resolve().parent
DEFAULT_REVIEWS = HERE / "reviews"


def _say(line: str) -> None:
    print(line, file=sys.stderr)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python3 -m gems", description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)

    build = commands.add_parser("build", help="run the whole pipeline and write gem-picks.json")
    build.add_argument("--queue", required=True, help="the published discovery queue (hidden-gems.json or .json.gz)")
    build.add_argument("--output", required=True, help="where to write gem-picks.json")
    build.add_argument("--workdir", required=True, help="scratch folder for repository checkouts")
    build.add_argument("--reviews", default=str(DEFAULT_REVIEWS))
    build.add_argument("--inspections", help="reuse and update this measurements file between runs")
    build.add_argument("--limit", type=int, default=DEFAULT_LIMIT, help="how many repositories to open")
    build.add_argument("--keep", action="store_true", help="keep checkouts in the workdir for a reviewer to read")

    listing = commands.add_parser("candidates", help="list the repositories the deep stage would open")
    listing.add_argument("--queue", required=True)
    listing.add_argument("--limit", type=int, default=DEFAULT_LIMIT)
    listing.add_argument("--unreviewed", action="store_true", help="only those with no review yet")
    listing.add_argument("--reviews", default=str(DEFAULT_REVIEWS))

    blank = commands.add_parser("review-template", help="print an empty review for one repository")
    blank.add_argument("full_name")
    blank.add_argument("commit")

    commands.add_parser("rubric", help="print the scoring rubric reviewers follow")

    from .eval import cli as eval_cli  # imported here so the core commands work without it

    eval_cli.register(commands)

    args = parser.parse_args(argv)
    try:
        if args.command == "build":
            result = pipeline.run(
                args.queue, args.workdir, args.reviews, args.output,
                inspections_path=args.inspections, candidate_limit=args.limit, keep=args.keep, report=_say,
            )
            print(json.dumps(result, separators=(",", ":")))
            return 0
        if args.command == "candidates":
            from .review import load_reviews

            chosen = select(load_queue(args.queue), limit=args.limit)
            reviewed, _ = load_reviews(args.reviews)
            for candidate in chosen:
                if args.unreviewed and candidate["full_name"].casefold() in reviewed:
                    continue
                print(f"{candidate['full_name']} {candidate['commit']}")
            return 0
        if args.command == "review-template":
            print(json.dumps(template(args.full_name, args.commit), indent=1))
            _say("save as " + review_filename(args.full_name, args.commit))
            return 0
        if args.command == "rubric":
            print(RUBRIC)
            return 0
        return eval_cli.dispatch(args)
    except (CandidateError, OSError, ValueError) as error:
        _say(f"error: {error}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
