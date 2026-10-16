import argparse
from dataclasses import asdict, replace
import json
from pathlib import Path
import sys
from . import __version__
from .claims import extract_claims
from .discovery import discover, parse_since
from .evidence import evaluate
from .ingest.detect import detect
from .ingest import claude, codex
from . import report
from .redaction import redact
from .messages import MESSAGES, set_lang, t

FATAL_DIAGNOSTICS = {'file_limit', 'line_limit', 'read_error'}


def _language(argv):
    pre = argparse.ArgumentParser(add_help=False)
    pre.add_argument('--lang')
    known, _ = pre.parse_known_args(argv)
    return known.lang


def main(argv=None):
    try:
        set_lang(_language(argv))
    except ValueError as error:
        print(str(error), file=sys.stderr)
        return 2
    try:
        return _run(argv)
    finally:
        set_lang(None)


def _run(argv):
    lang_opt = argparse.ArgumentParser(add_help=False)
    lang_opt.add_argument('--lang', choices=sorted(MESSAGES), default=argparse.SUPPRESS, help=t('help_lang'))
    parser = argparse.ArgumentParser(prog='receipts', description=t('cli_description'), parents=[lang_opt])
    parser.add_argument('--version', action='version', version=__version__)
    commands = parser.add_subparsers(dest='action')
    audit = commands.add_parser('audit', help=t('help_audit'), parents=[lang_opt])
    audit.add_argument('session', nargs='?')
    audit.add_argument('--since', default='7d')
    audit.add_argument('--source', choices=['all','claude','codex'], default='all')
    audit.add_argument('--profile')
    audit.add_argument('--project', type=Path)
    audit.add_argument('--include-subagents', action='store_true')
    diff = commands.add_parser('check-diff', help=t('help_diff'), parents=[lang_opt])
    diff.add_argument('--project', type=Path, default=Path.cwd())
    diff.add_argument('--base', default='HEAD')
    evaluation = commands.add_parser('eval', help=t('help_eval'), parents=[lang_opt])
    evaluation.add_argument('labels', type=Path)
    hook = commands.add_parser('hook', help=t('help_hook'), parents=[lang_opt])
    hook.add_argument('--source', required=True, choices=['codex','claude'])
    args = parser.parse_args(argv)
    try:
        if args.action == 'audit':
            explicit = bool(args.session)
            paths = (Path(args.session).expanduser(),) if explicit else discover(Path.home(),args.source,
                parse_since(args.since),args.profile,args.project,include_subagents=args.include_subagents)
            results, incomplete, skipped = [], False, 0
            for path in paths:
                try:
                    source = detect(path)
                except ValueError:
                    if explicit:
                        raise
                    skipped += 1
                    continue
                if args.source != 'all' and source != args.source:
                    continue
                session = (codex if source == 'codex' else claude).parse(path)
                if 'subagents' in path.parts:
                    session = replace(session, subagent=True)
                incomplete |= any(d.code in FATAL_DIAGNOSTICS for d in session.diagnostics)
                results.append((session,evaluate(session,extract_claims(session.events))))
            output = report.save_report(report.render_report(results, skipped))
            print(redact(t('report_saved', path=output, n=len(results))))
            if incomplete or not results:
                return 2
            return int(any(v.status != 'CONFIRMED' for _, verdicts in results for v in verdicts))
        if args.action == 'check-diff':
            from .git_read import changed_versions
            from .testguard import compare_versions
            findings = [asdict(f) for version in changed_versions(args.project,args.base)
                        for f in compare_versions(version.path,version.old,version.new)]
            text = redact(json.dumps(findings,ensure_ascii=False,indent=2))
            report.save_report(text,'testguard.json')
            print(text)
            return int(bool(findings))
        if args.action == 'eval':
            from .evaluation import evaluate_labels
            text = redact(json.dumps(evaluate_labels(args.labels),ensure_ascii=False,indent=2))
            report.save_report(text,'eval.json')
            print(text)
            return 0
        if args.action == 'hook':
            from .hook import run_hook
            return run_hook(args.source)
        parser.print_help()
        return 0
    except (ValueError,OSError,TypeError,KeyError) as error:
        print(redact(t('check_incomplete', error=error)),file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
