"""Strict local-only Git reads. Commands from transcripts never reach here."""
from dataclasses import dataclass
import os
from pathlib import Path
import re
import shutil
import subprocess


@dataclass(frozen=True)
class FileVersion:
    path: str
    old: str
    new: str


def run_git(root, args, timeout=5.0):
    if not args or args[0] not in ('diff', 'show', 'rev-parse', 'ls-files', 'log'):
        raise ValueError('Nedozvoljena Git komanda.')
    if any(a.startswith(('--output', '--exec', '--ext-diff', '--textconv')) for a in args):
        raise ValueError('Nedozvoljena Git opcija.')
    executable = os.environ.get('RECEIPTS_GIT') or shutil.which('git')
    if not executable:
        raise ValueError('Git nije instaliran ili nije na PATH-u.')
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
        raise ValueError('Git provjera nije dostupna ili je istekla.') from error


def changed_versions(root, base='HEAD'):
    root = Path(root).resolve()
    if not re.fullmatch(r'(?:HEAD(?:[~^]\d*)?|[A-Za-z0-9][A-Za-z0-9_./-]*)', base) or '..' in base:
        raise ValueError('Neispravna bazna revizija.')
    check = run_git(root, ['rev-parse', '--verify', base + '^{commit}'])
    if check.returncode:
        raise ValueError('Projekat nema dostupnu baznu Git reviziju.')
    # Pin the validated commit so a ref cannot move between subsequent reads.
    revision = check.stdout.strip()
    listed = run_git(root, ['diff', '--no-ext-diff', '--no-textconv', '--no-renames', '--cached', '--name-only', '-z', revision, '--'])
    unstaged = run_git(root, ['diff', '--no-ext-diff', '--no-textconv', '--no-renames', '--name-only', '-z', '--'])
    untracked = run_git(root, ['ls-files', '--others', '--exclude-standard', '-z'])
    if listed.returncode or untracked.returncode or unstaged.returncode:
        raise ValueError('Git diff nije dostupan.')
    paths = sorted(set((listed.stdout + unstaged.stdout + untracked.stdout).split('\0')) - {''})
    versions = []
    for rel in paths:
        from .testguard import is_test
        if not is_test(rel):
            continue
        path = root / rel
        try:
            path.resolve().relative_to(root)
        except ValueError:
            raise ValueError('Test putanja izlazi iz projekta.')
        if path.is_symlink():
            raise ValueError('Simbolička test putanja nije dozvoljena.')
        old = run_git(root, ['show', '--no-ext-diff', '--no-textconv', revision + ':' + rel])
        staged = run_git(root, ['show', '--no-ext-diff', '--no-textconv', ':' + rel])
        try:
            if path.exists() and path.stat().st_size > 8 * 1024 * 1024:
                raise ValueError('Test fajl je prevelik.')
            new = path.read_text(encoding='utf-8-sig') if path.exists() else ''
        except (OSError, UnicodeError) as error:
            raise ValueError('Test fajl nije dostupan kao UTF-8 tekst.') from error
        original = old.stdout if old.returncode == 0 else ''
        index = staged.stdout if staged.returncode == 0 else ''
        if original != index:
            versions.append(FileVersion(rel, original, index))
        if index != new:
            versions.append(FileVersion(rel, index, new))
    return tuple(versions)
