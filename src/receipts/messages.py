"""User-facing text. Codes, statuses and identifiers stay English; prose follows lang()."""
import os

MESSAGES = {
    'en': {
        'no_evidence': 'No sufficient preceding evidence.',
        'proof_runner': 'line {call}: runner {runner}; line {result}: exit={exit}{source}, status={status}',
        'proof_compound': 'line {call}: compound command; runner output could not be isolated.',
        'proof_git': 'line {call}: git {op}; line {result}: exit={exit}{source}. Historical result; current state not checked.',
        'proof_files': 'Recorded {n} distinct successfully changed paths; an incomplete inventory is not proof of falsehood.',
        'proof_created': 'line {line}: file created successfully.',
        'report_note': 'Offline review of preceding evidence; NO_EVIDENCE is not proof of falsehood.',
        'report_empty': 'No sessions found. No claims were checked.',
        'report_skipped': 'Skipped {n} files with an unknown format.',
        'report_header': '| Tool / session | Line | Claim | Status | Evidence |',
        'report_diagnostic': 'Diagnostic ({source}, line {line}): {code} - {message}',
        'report_no_claims': '{source}: no recognized claims in session {session}.',
        'report_saved': 'Report: {path}; sessions: {n}',
        'subagent_label': ' (subagent)',
        'cli_description': 'Local evidence audit: audit, check-diff, eval, hook.',
        'help_audit': 'Review local sessions',
        'help_diff': 'Test weakening signals',
        'help_eval': 'Metrics over manual labels',
        'help_hook': 'Optional warning-only hook',
        'help_lang': 'Output language: en (default) or bs',
        'check_incomplete': 'Check not completed: {error}',
        'bad_lang': 'Unknown language: {lang}. Use en or bs.',
        'bad_since': 'Use a duration such as 7d or 24h.',
        'unknown_profile': 'Unknown Claude profile: {name}.',
        'unknown_format': 'Unknown or incomplete session format; audit not confirmed.',
        'diag_file_limit': 'Session exceeds the allowed size.',
        'diag_line_limit': 'Session line is too large; audit incomplete.',
        'diag_invalid_json': 'Invalid or unfinished JSON line.',
        'diag_read_error': 'Session cannot be read.',
        'diag_orphan_result': 'Result without a matching call.',
        'diag_invalid_payload': 'Invalid event structure.',
        'diag_invalid_item': 'Invalid item structure.',
        'diag_invalid_changes': 'Invalid change structure.',
        'diag_invalid_action': 'Unknown file change type.',
        'diag_unsupported_call': 'Tool call could not be decoded reliably.',
        'diag_unsupported_result': 'Tool result could not be decoded reliably.',
        'hook_prefix': 'Agent Receipts (warning): ',
        'hook_no_runner': 'Test pass claim has no test runner call in this turn.',
        'hook_weakening': 'Test weakening signals: {n}; review and explanation needed.',
        'hook_git_unavailable': 'Git/testguard check unavailable; turn passed.',
        'hook_unknown': 'Hook check not finished (unknown format or identity); turn passed.',
        'hook_bad_input': 'Invalid hook input; turn passed.',
        'git_forbidden_cmd': 'Git command not allowed.',
        'git_forbidden_opt': 'Git option not allowed.',
        'git_missing': 'Git is not installed or not on PATH.',
        'git_unavailable': 'Git check unavailable or timed out.',
        'git_bad_base': 'Invalid base revision.',
        'git_no_base': 'Project has no available base Git revision.',
        'git_diff_unavailable': 'Git diff is unavailable.',
        'git_path_escape': 'Test path leaves the project.',
        'git_symlink': 'Symbolic test path is not allowed.',
        'git_too_large': 'Test file is too large.',
        'git_not_utf8': 'Test file is not readable as UTF-8 text.',
        'testguard_parse': 'Python test could not be parsed; result incomplete.',
        'eval_truth': 'Every label needs a manually checked truth=true/false.',
        'eval_source': 'Label source does not match the session.',
    },
    'bs': {
        'no_evidence': 'Nema dovoljnog prethodnog dokaza.',
        'proof_runner': 'red {call}: runner {runner}; red {result}: exit={exit}{source}, status={status}',
        'proof_compound': 'red {call}: složena komanda; izlaz runnera nije izdvojen.',
        'proof_git': 'red {call}: git {op}; red {result}: exit={exit}{source}. Istorijski rezultat; trenutno stanje nije provjereno.',
        'proof_files': 'Zabilježeno {n} različitih uspješno izmijenjenih putanja; nepotpun inventar nije dokaz neistine.',
        'proof_created': 'red {line}: uspješno kreiranje fajla.',
        'report_note': 'Offline pregled prethodnih dokaza; NO_EVIDENCE nije dokaz neistine.',
        'report_empty': 'Nema pronađenih sesija. Nije izvršena provjera tvrdnji.',
        'report_skipped': 'Preskočeno {n} fajlova nepoznatog formata.',
        'report_header': '| Alat / sesija | Red | Tvrdnja | Status | Dokaz |',
        'report_diagnostic': 'Dijagnostika ({source}, red {line}): {code} - {message}',
        'report_no_claims': '{source}: nema prepoznatih tvrdnji u sesiji {session}.',
        'report_saved': 'Izvještaj: {path}; sesija: {n}',
        'subagent_label': ' (subagent)',
        'cli_description': 'Lokalni audit dokaza: audit, check-diff, eval, hook.',
        'help_audit': 'Pregled lokalnih sesija',
        'help_diff': 'Signali slabljenja testova',
        'help_eval': 'Metrika nad ručnim labelama',
        'help_hook': 'Opcionalni warning-only hook',
        'help_lang': 'Jezik izlaza: en (podrazumijevano) ili bs',
        'check_incomplete': 'Provjera nije završena: {error}',
        'bad_lang': 'Nepoznat jezik: {lang}. Koristite en ili bs.',
        'bad_since': 'Koristite trajanje poput 7d ili 24h.',
        'unknown_profile': 'Nepoznat Claude profil: {name}.',
        'unknown_format': 'Nepoznat ili nepotpun format sesije; audit nije potvrđen.',
        'diag_file_limit': 'Sesija prelazi dozvoljenu veličinu.',
        'diag_line_limit': 'Red sesije je prevelik; audit nepotpun.',
        'diag_invalid_json': 'Neispravan ili nedovršen JSON red.',
        'diag_read_error': 'Sesija nije dostupna za čitanje.',
        'diag_orphan_result': 'Rezultat bez povezanog poziva.',
        'diag_invalid_payload': 'Neispravna struktura događaja.',
        'diag_invalid_item': 'Neispravna struktura stavke.',
        'diag_invalid_changes': 'Neispravna struktura promjena.',
        'diag_invalid_action': 'Nepoznat tip izmjene fajla.',
        'diag_unsupported_call': 'Poziv alata nije pouzdano dekodiran.',
        'diag_unsupported_result': 'Rezultat alata nije pouzdano dekodiran.',
        'hook_prefix': 'Agent Receipts (upozorenje): ',
        'hook_no_runner': 'Tvrdnja o prolasku testova nema poziv test runnera u ovom potezu.',
        'hook_weakening': 'Signali slabljenja testova: {n}; potreban je pregled i objašnjenje.',
        'hook_git_unavailable': 'Git/testguard provjera nije dostupna; potez je propušten.',
        'hook_unknown': 'Hook provjera nije završena (nepoznat format ili identitet); potez je propušten.',
        'hook_bad_input': 'Neispravan hook ulaz; potez je propušten.',
        'git_forbidden_cmd': 'Nedozvoljena Git komanda.',
        'git_forbidden_opt': 'Nedozvoljena Git opcija.',
        'git_missing': 'Git nije instaliran ili nije na PATH-u.',
        'git_unavailable': 'Git provjera nije dostupna ili je istekla.',
        'git_bad_base': 'Neispravna bazna revizija.',
        'git_no_base': 'Projekat nema dostupnu baznu Git reviziju.',
        'git_diff_unavailable': 'Git diff nije dostupan.',
        'git_path_escape': 'Test putanja izlazi iz projekta.',
        'git_symlink': 'Simbolička test putanja nije dozvoljena.',
        'git_too_large': 'Test fajl je prevelik.',
        'git_not_utf8': 'Test fajl nije dostupan kao UTF-8 tekst.',
        'testguard_parse': 'Python test nije moguće parsirati; rezultat je nepotpun.',
        'eval_truth': 'Svaka labela mora imati ručno provjeren truth=true/false.',
        'eval_source': 'Izvor labele ne odgovara sesiji.',
    },
}

_selected = None


def set_lang(value):
    """Select output language for this process; None follows RECEIPTS_LANG."""
    global _selected
    if value is not None and value not in MESSAGES:
        raise ValueError(MESSAGES['en']['bad_lang'].format(lang=value))
    _selected = value


def lang():
    if _selected:
        return _selected
    env = os.environ.get('RECEIPTS_LANG', '')
    return env if env in MESSAGES else 'en'


def t(key, **args):
    return MESSAGES[lang()][key].format(**args)
