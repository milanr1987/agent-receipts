"""Strict local-only Git reads. Commands from transcripts never reach here."""
from dataclasses import dataclass
import os
from pathlib import Path
import re
import shutil
import subprocess
from .messages import t


@dataclass(frozen=True)
class FileVersion:
    path: str
    old: str
    new: str


def run_git(root, args, timeout=5.0):
    if not args or args[0] not in ('diff', 'show', 'rev-parse', 'ls-files', 'log'):
        raise ValueError(t('git_forbidden_cmd'))
    if any(a.startswith(('--output', '--exec', '--ext-diff', '--textconv')) for a in args):
        raise ValueError(t('git_forbidden_opt'))
    executable = os.environ.get('RECEIPTS_GIT') or shutil.which('git')
    if not executable:
        raise ValueError(t('git_missing'))
    env = {k: v for k, v in os.environ.items() if not k.upper().startswith('GIT_')}
    env.update(GIT_TERMINAL_PROMPT='0', GIT_OPTIONAL_LOCKS='0', GIT_CONFIG_NOSYSTEM='1')
    try:
        return subprocess.run([executable, '-C', str(root), '--no-optional-locks',
                               '-c', 'core.fsmonitor=false', '-c', 'core.hooksPath=',
                               *args], env=env, shell=False, stdin=subprocess.DEVNULL,
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                              text=True, encoding='utf-8', errors='replace', timeout=timeout,
                              creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
    except (OSError, subprocess.TimeoutExpired) as error:
        raise ValueError(t('git_unavailable')) from error


def repo_root(root):
    """Repository top level for a directory (Git reports paths relative to it); the directory itself otherwise."""
    root = Path(root).resolve()
    top = run_git(root, ['rev-parse', '--show-toplevel'])
    if top.returncode == 0 and top.stdout.strip():
        return Path(top.stdout.strip()).resolve()
    return root


def changed_versions(root, base='HEAD', include=None, paths=None, resolved=False):
    """paths: repo-relative files to list (literal pathspecs); resolved: root is already the repo top level."""
    root = Path(root) if resolved else repo_root(root)
    spec = ['--'] + [':(literal)' + p for p in paths] if paths else ['--']
    if not re.fullmatch(r'(?:HEAD(?:[~^]\d*)?|[A-Za-z0-9][A-Za-z0-9_./-]*)', base) or '..' in base:
        raise ValueError(t('git_bad_base'))
    check = run_git(root, ['rev-parse', '--verify', base + '^{commit}'])
    if check.returncode:
        raise ValueError(t('git_no_base'))
    # Pin the validated commit so a ref cannot move between subsequent reads.
    revision = check.stdout.strip()
    listed = run_git(root, ['diff', '--no-ext-diff', '--no-textconv', '--no-renames', '--cached', '--name-only', '-z', revision, *spec])
    unstaged = run_git(root, ['diff', '--no-ext-diff', '--no-textconv', '--no-renames', '--name-only', '-z', *spec])
    untracked = run_git(root, ['ls-files', '--others', '--exclude-standard', '-z', *spec])
    if listed.returncode or untracked.returncode or unstaged.returncode:
        raise ValueError(t('git_diff_unavailable'))
    paths = sorted(set((listed.stdout + unstaged.stdout + untracked.stdout).split('\0')) - {''})
    versions = []
    for rel in paths:
        from .testguard import is_test
        if not is_test(rel) or (include is not None and not include(rel)):
            continue
        path = root / rel
        try:
            path.resolve().relative_to(root)
        except ValueError:
            raise ValueError(t('git_path_escape'))
        if path.is_symlink():
            raise ValueError(t('git_symlink'))
        old = run_git(root, ['show', '--no-ext-diff', '--no-textconv', revision + ':' + rel])
        staged = run_git(root, ['show', '--no-ext-diff', '--no-textconv', ':' + rel])
        try:
            if path.exists() and path.stat().st_size > 8 * 1024 * 1024:
                raise ValueError(t('git_too_large'))
            new = path.read_text(encoding='utf-8-sig') if path.exists() else ''
        except (OSError, UnicodeError) as error:
            raise ValueError(t('git_not_utf8')) from error
        original = old.stdout if old.returncode == 0 else ''
        index = staged.stdout if staged.returncode == 0 else ''
        if original != index:
            versions.append(FileVersion(rel, original, index))
        if index != new:
            versions.append(FileVersion(rel, index, new))
    return tuple(versions)
