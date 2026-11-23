"""Command line: ``python -m dirqa <command>``.

    run      do a cycle. Dry run unless --apply and the exact --authorize phrase are given.
    restore  put production back from a run's verified backup (undo a promotion). Dry run
             unless --apply and the exact restore phrase are given.
    rules    list the rule registry with severities.
    phrase   print the authorization phrase for this config (--restore: the restore phrase).
"""

from __future__ import annotations

import argparse
import sys

from .config import Config
from .pipeline import STAGE_NAMES, run
from .restore import NoRestorePoint, restore
from .rules.registry import load_rules


def cmd_run(args) -> int:
    only = args.stages.split(",") if args.stages else None
    if only:
        unknown = [s for s in only if s not in STAGE_NAMES]
        if unknown:
            print(f"unknown stages: {unknown}; choose from {STAGE_NAMES}", file=sys.stderr)
            return 2
    manifest = run(args.config, apply=args.apply, authorize=args.authorize, only=only)
    print(f"cycle {manifest.cycle}  mode {manifest.mode}  ->  {manifest.final_status}")
    print(f"run folder: {manifest.run_dir}")
    for stage in manifest.stages:
        summary = "; ".join(f"{k}={v}" for k, v in list(stage.summary.items())[:6]
                            if not isinstance(v, (list, dict)))
        print(f"  {stage.name:24s} {stage.status:10s} {summary}")
    if manifest.readiness:
        print(f"readiness: {manifest.readiness['verdict']}")
        for check in manifest.readiness["checks"]:
            if not check["ok"]:
                print(f"  - {check['check']}: {check['detail']}")
    return 0 if not manifest.final_status.startswith("failed") else 1


def cmd_rules(args) -> int:
    for rule in load_rules(Config.load(args.config).rules_file):
        promoted = f" (promoted {rule.promoted_on})" if rule.promoted_on else ""
        origin = f" [{rule.origin}]" if rule.origin != "spec" else ""
        print(f"{rule.severity:9s} {rule.expect or '-':17s} {rule.id}{origin}{promoted}")
        print(f"          {rule.description}")
    return 0


def cmd_restore(args) -> int:
    config = Config.load(args.config)
    try:
        result = restore(config, run=args.run, apply=args.apply, authorize=args.authorize,
                         discard_later_changes=args.discard_later_changes)
    except NoRestorePoint as exc:
        print(f"restore: {exc}", file=sys.stderr)
        return 1
    print(f"cycle {config.cycle}  restore from run {result.run}  ->  {result.status}")
    print(f"backup: {result.backup}")
    print(f"production {result.production_sha256_before[:12]} -> target {result.target_sha256[:12]}")
    for note in result.notes:
        print(f"  - {note}")
    if result.record:
        print(f"record: {result.record}")
    return 0 if result.status in ("dry-run", "restored", "nothing-to-do") else 1


def cmd_phrase(args) -> int:
    config = Config.load(args.config)
    print(config.restore_phrase if args.restore else config.authorization_phrase)
    return 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="dirqa", description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)

    p_run = sub.add_parser("run", help="run a cycle (dry run by default)")
    p_run.add_argument("--config", required=True)
    p_run.add_argument("--apply", action="store_true", help="allow promotion to production")
    p_run.add_argument("--authorize", metavar="PHRASE", help="the exact authorization phrase")
    p_run.add_argument("--stages", help="comma-separated subset of stages to run")
    p_run.set_defaults(func=cmd_run)

    p_restore = sub.add_parser("restore", help="put production back from a verified backup (dry run by default)")
    p_restore.add_argument("--config", required=True)
    p_restore.add_argument("--run", help="the run folder whose backup to restore (default: the latest promoted run)")
    p_restore.add_argument("--apply", action="store_true", help="actually replace production")
    p_restore.add_argument("--authorize", metavar="PHRASE", help="the exact restore phrase")
    p_restore.add_argument("--discard-later-changes", action="store_true",
                           help="restore even though production changed after that run")
    p_restore.set_defaults(func=cmd_restore)

    p_rules = sub.add_parser("rules", help="list the rule registry")
    p_rules.add_argument("--config", required=True)
    p_rules.set_defaults(func=cmd_rules)

    p_phrase = sub.add_parser("phrase", help="print the authorization phrase")
    p_phrase.add_argument("--config", required=True)
    p_phrase.add_argument("--restore", action="store_true", help="print the restore phrase instead")
    p_phrase.set_defaults(func=cmd_phrase)

    args = parser.parse_args(argv)
    return args.func(args)
