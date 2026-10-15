import ast
from pathlib import PurePosixPath
import re
from .models import Finding


def is_test(path):
    p = PurePosixPath(path.replace('\\', '/'))
    name = p.name.lower()
    return bool(set(p.parts) & {'tests', '__tests__'} or
                (name.endswith('.py') and (name.startswith('test_') or name.endswith('_test.py'))) or
                name.endswith(('.test.ts', '.spec.ts', '.test.tsx', '.spec.tsx', '.test.js', '.spec.js')))


def _functions(text):
    try:
        tree = ast.parse(text)
    except (SyntaxError, RecursionError) as error:
        raise ValueError('Python test nije moguće parsirati; rezultat je nepotpun.') from error
    found = {}

    def visit(node, scope=''):
        for child in ast.iter_child_nodes(node):
            if isinstance(child, ast.ClassDef):
                visit(child, scope + child.name + '.')
            elif isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)) and child.name.startswith('test'):
                found[scope + child.name] = child
            else:
                visit(child, scope)
    visit(tree)
    return found


def _asserts(node):
    return sum(isinstance(x, ast.Assert) or
               (isinstance(x, ast.Call) and isinstance(x.func, ast.Attribute) and
                isinstance(x.func.value, ast.Name) and x.func.value.id == 'self' and
                x.func.attr.startswith('assert')) for x in ast.walk(node))


def compare_versions(path, old, new):
    if not is_test(path):
        return ()
    found = []
    if path.endswith('.py'):
        before, after = _functions(old), _functions(new)
        for name, node in before.items():
            if name not in after:
                found.append(Finding(path, name, 'removed_test', node.lineno, None))
            elif _asserts(after[name]) < _asserts(node):
                found.append(Finding(path, name, 'fewer_assertions', node.lineno, after[name].lineno))
        for name, node in after.items():
            previous = before.get(name)
            old_decorators = {ast.unparse(x) for x in previous.decorator_list} if previous else set()
            for decorator in node.decorator_list:
                text = ast.unparse(decorator)
                if text not in old_decorators and re.search(r'(?:pytest\.mark\.(?:skip|skipif|xfail)|unittest\.skip)', text):
                    found.append(Finding(path, name, 'added_skip', previous.lineno if previous else None, decorator.lineno))
            old_swallow = sum(isinstance(x, ast.ExceptHandler) and all(isinstance(b, ast.Pass) for b in x.body)
                              for x in ast.walk(previous)) if previous else 0
            handlers = [x for x in ast.walk(node) if isinstance(x, ast.ExceptHandler) and
                        all(isinstance(b, ast.Pass) for b in x.body)]
            if len(handlers) > old_swallow:
                found.append(Finding(path, name, 'swallowed_exception', previous.lineno if previous else None, handlers[0].lineno))
    elif path.endswith(('.js', '.jsx', '.ts', '.tsx')):
        # Heuristics intentionally produce review signals, not correctness verdicts.
        patterns = {
            'added_skip_or_only': r'\b(?:it|test|describe)\.(?:skip|only)\s*\(|\bxit\s*\(',
            'empty_catch': r'\bcatch\s*(?:\([^)]*\))?\s*\{\s*\}',
        }
        for signal, pattern in patterns.items():
            if len(re.findall(pattern, new)) > len(re.findall(pattern, old)):
                match = re.search(pattern, new)
                found.append(Finding(path, '(heuristic)', signal, None, new[:match.start()].count('\n') + 1))
        if len(re.findall(r'\bexpect\s*\(', new)) < len(re.findall(r'\bexpect\s*\(', old)):
            found.append(Finding(path, '(heuristic)', 'removed_expect', 1, 1))
        strong = r'\.(?:toEqual|toBe|toStrictEqual)\s*\('
        weak = r'\.(?:toBeDefined|toBeTruthy)\s*\('
        if len(re.findall(strong, new)) < len(re.findall(strong, old)) and len(re.findall(weak, new)) > len(re.findall(weak, old)):
            found.append(Finding(path, '(heuristic)', 'weaker_matcher', 1, 1))
    return tuple(found)
