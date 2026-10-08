"""Fail-closed boundaries for unattended parser repairs (no GitHub/API access)."""
import ast
import hashlib
import json
import re
from pathlib import PurePosixPath

PARSERS = {name: "providers/{}.py".format(name) for name in (
    "deepinfra", "novita", "together", "fireworks", "groq", "openai",
    "anthropic", "gemini", "vertex", "bedrock", "azure")}
MAX_FILES = 6
MAX_FILE_BYTES = 128 * 1024
MAX_PROPOSAL_BYTES = 512 * 1024
PURE_IMPORTS = {"re", "json", "csv", "decimal", "datetime", "html", "unicodedata", "math"}
FORBIDDEN_NAMES = {
    "os", "sys", "subprocess", "socket", "requests", "urllib", "http", "builtins",
    "open", "eval", "exec", "compile", "__import__", "globals", "locals", "vars",
    "getattr", "setattr", "delattr", "input", "print", "breakpoint", "exit", "quit",
    "fetch_text", "fetch_bytes", "parse_or_archive", "vertex_catalog", "Collection",
    "collect", "Path", "pathlib", "importlib", "inspect", "encode_payload",
}
FORBIDDEN_ATTRIBUTES = {
    "open", "read", "write", "read_text", "write_text", "read_bytes", "write_bytes",
    "unlink", "remove", "rmdir", "mkdir", "chmod", "chown", "rename", "replace_file",
    "system", "popen", "request", "urlopen", "connect", "send", "environ", "getenv",
    "collect", "fetch_text", "fetch_bytes", "f_globals", "f_locals", "f_builtins", "f_back",
    "tb_frame", "gi_frame", "cr_frame", "mro",
}
SEMANTIC_KEYS = (
    "provider_model_id", "input_per_million", "output_per_million", "cache_read_per_million",
    "cache_write_per_million", "currency", "source_url", "context_window", "quantization", "region",
    "variant", "service_tier", "min_input_tokens", "max_input_tokens", "max_output_tokens", "pricing_notes",
)


def require(condition, message):
    if not condition:
        raise ValueError(message)


def identifier(value, label="run ID"):
    require(isinstance(value, str) and re.fullmatch(r"[1-9][0-9]{0,19}", value), "Invalid " + label)
    return value


def commit_sha(value):
    require(isinstance(value, str) and re.fullmatch(r"[0-9a-f]{40}", value), "Invalid commit SHA")
    return value


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()).hexdigest()


def shape(node):
    return ast.dump(node, include_attributes=False)


def validate_parser(before, after):
    """Only parse() and new pure helpers may change. Transport/registries stay fixed.

    This is defense in depth, not a Python security sandbox or proof of pricing
    correctness. Independent review, replay equivalence and secret-free CI are
    separate required gates.
    """
    old, new = ast.parse(before), ast.parse(after)
    old_fixed = [shape(n) for n in old.body if not isinstance(n, (ast.Import, ast.ImportFrom, ast.FunctionDef))]
    new_fixed = [shape(n) for n in new.body if not isinstance(n, (ast.Import, ast.ImportFrom, ast.FunctionDef))]
    require(old_fixed == new_fixed, "Parser constants, classes and module-level behavior must not change")
    old_imports = {shape(n) for n in old.body if isinstance(n, (ast.Import, ast.ImportFrom))}
    new_imports = {shape(n) for n in new.body if isinstance(n, (ast.Import, ast.ImportFrom))}
    require(old_imports <= new_imports, "Existing imports must not change")
    protected = {name.id for n in old.body if isinstance(n, ast.Assign) for target in n.targets for name in ast.walk(target) if isinstance(name, ast.Name)}
    bindings = set(protected)
    for n in old.body:
        if isinstance(n, (ast.Import, ast.ImportFrom)):
            bindings.update(a.asname or a.name.split('.')[0] for a in n.names)
        elif isinstance(n, (ast.FunctionDef, ast.ClassDef)):
            bindings.add(n.name)
    for n in new.body:
        if isinstance(n, (ast.Import, ast.ImportFrom)) and shape(n) not in old_imports:
            modules = [a.name.split('.')[0] for a in n.names] if isinstance(n, ast.Import) else [n.module.split('.')[0] if n.module else ""]
            require(all(m in PURE_IMPORTS for m in modules) and not getattr(n, 'level', 0), "Only pure standard-library imports may be added")
            require(all(a.name != '*' and (a.asname or a.name.split('.')[0]) not in bindings for a in n.names), "New imports must not shadow existing bindings")
    old_functions = {n.name: n for n in old.body if isinstance(n, ast.FunctionDef)}
    new_functions = {n.name: n for n in new.body if isinstance(n, ast.FunctionDef)}
    require(len(new_functions) == sum(isinstance(n, ast.FunctionDef) for n in new.body), "Duplicate function definitions are prohibited")
    require('parse' in old_functions and old_functions.keys() <= new_functions.keys(), "Existing parser functions must remain")
    for name, function in old_functions.items():
        if name != 'parse':
            require(shape(function) == shape(new_functions[name]), "Only parse() may change; protected function: " + name)
    require(shape(old_functions['parse'].args) == shape(new_functions['parse'].args)
            and [shape(n) for n in old_functions['parse'].decorator_list] == [shape(n) for n in new_functions['parse'].decorator_list]
            and (shape(old_functions['parse'].returns) if old_functions['parse'].returns else None)
                == (shape(new_functions['parse'].returns) if new_functions['parse'].returns else None), "Parser signature must remain")
    helpers = new_functions.keys() - old_functions.keys()
    require(all(name.startswith('_recovery_') for name in helpers), "New helpers must use the _recovery_ prefix")
    require(all(not new_functions[name].decorator_list and not new_functions[name].args.defaults
                and not any(new_functions[name].args.kw_defaults) and new_functions[name].returns is None
                and all(n.annotation is None for n in ast.walk(new_functions[name].args) if isinstance(n, ast.arg))
                for name in helpers), "New helpers must not execute decorators/defaults/annotations at import time")
    for name in {'parse'} | helpers:
        for node in ast.walk(new_functions[name]):
            require(not isinstance(node, (ast.Import, ast.ImportFrom, ast.Global, ast.Nonlocal, ast.AsyncFunctionDef, ast.ClassDef)), "Dynamic imports, global mutation and nested classes are prohibited")
            if isinstance(node, ast.Name):
                require(node.id not in FORBIDDEN_NAMES and not node.id.startswith('__'), "Unsafe parser reference: " + node.id)
                if isinstance(node.ctx, (ast.Store, ast.Del)):
                    require(node.id not in bindings, "Parser must not shadow module bindings: " + node.id)
            if isinstance(node, ast.Attribute):
                require(node.attr not in FORBIDDEN_ATTRIBUTES | FORBIDDEN_NAMES and not node.attr.startswith('_'), "Unsafe parser attribute: " + node.attr)
            if isinstance(node, ast.Subscript) and isinstance(node.ctx, (ast.Store, ast.Del)) and isinstance(node.value, ast.Name):
                require(node.value.id not in protected, "Parser must not mutate module registries")
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and isinstance(node.func.value, ast.Name):
                require(not (node.func.value.id in protected and node.func.attr in {'clear', 'update', 'pop', 'popitem', 'setdefault', 'append', 'extend', 'add', 'remove', 'discard'}), "Parser must not mutate module registries")
            if isinstance(node, ast.Constant) and isinstance(node.value, str):
                require(not re.search(r"__(?:class|dict|globals|builtins|subclasses|import)__", node.value), "Reflection strings are prohibited")
    # Existing fail-closed completeness/duplicate checks cannot simply disappear.
    protected_calls = {'require_models', 'unique_records', 'snapshot'}
    old_calls = {shape(n) for n in ast.walk(old_functions['parse']) if isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id in protected_calls}
    new_calls = {shape(n) for n in ast.walk(new_functions['parse']) if isinstance(n, ast.Call)}
    require(old_calls <= new_calls, "Existing completeness, duplicate and snapshot checks must remain unchanged")
    old_raises = [shape(n) for n in ast.walk(old_functions['parse']) if isinstance(n, ast.Raise)]
    new_raises = [shape(n) for n in ast.walk(new_functions['parse']) if isinstance(n, ast.Raise)]
    require(all(new_raises.count(n) >= old_raises.count(n) for n in set(old_raises)), "Existing parser validation errors must remain")


def validate_proposal(proposal, evidence):
    require(isinstance(proposal, dict) and set(proposal) == {'summary', 'files'}, "Invalid proposal fields")
    require(isinstance(proposal['summary'], str) and 1 <= len(proposal['summary']) <= 4000, "Invalid repair summary")
    files = proposal['files']
    require(isinstance(files, list) and 2 <= len(files) <= MAX_FILES, "Repair must include a parser and a new regression test")
    require(len(json.dumps(proposal).encode()) <= MAX_PROPOSAL_BYTES, "Proposal exceeds size limit")
    run_id = identifier(evidence['failed_run_id'])
    parser = PARSERS[evidence['provider']]
    test = 'tests/test_recovery_{}.py'.format(run_id)
    fixture = re.compile(r'tests/fixtures/recovery-' + run_id + r'-[a-z0-9-]+\.(?:html|json|md|txt)$')
    contents = {}
    for file in files:
        require(isinstance(file, dict) and set(file) == {'path', 'content'}, "Invalid file proposal")
        path, content = file['path'], file['content']
        require(isinstance(path, str) and str(PurePosixPath(path)) == path and '..' not in PurePosixPath(path).parts, "Unsafe path")
        require(path not in contents and (path in (parser, test) or fixture.fullmatch(path)), "Path is outside the repair allowlist: " + path)
        require(isinstance(content, str) and 0 < len(content.encode()) <= MAX_FILE_BYTES and '\x00' not in content, "Invalid/oversized file content")
        contents[path] = content
    require(parser in contents and test in contents, "Parser and regression test are required")
    require(contents[parser] != evidence['base_parser'], "No parser change proposed")
    validate_parser(evidence['base_parser'], contents[parser])
    test_tree = ast.parse(contents[test])
    require(any(isinstance(n, ast.FunctionDef) and n.name.startswith('test_') for n in ast.walk(test_tree)), "Regression test has no test cases")
    for node in ast.walk(test_tree):
        if isinstance(node, ast.Name):
            require((node.id not in FORBIDDEN_NAMES - {'print', 'Path', 'pathlib'} and not node.id.startswith('__'))
                    or node.id in ('__file__', '__name__'), "Unsafe regression reference")
        if isinstance(node, ast.Attribute):
            require(node.attr not in (FORBIDDEN_ATTRIBUTES | FORBIDDEN_NAMES) - {'read_text', 'read_bytes'} and not node.attr.startswith('_'), "Regression tests must not mutate files/environment or use reflection")
            if isinstance(node.ctx, (ast.Store, ast.Del)):
                require(isinstance(node.value, ast.Name) and node.value.id == 'self', "Regression must not monkeypatch modules/test machinery")
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            names = [a.name for a in node.names] if isinstance(node, ast.Import) else [node.module or '']
            allowed = {'unittest', 'json', 'datetime', 'decimal', 'hashlib', 'pathlib', 'providers', 'providers.' + evidence['provider'], 'scripts.normalize'}
            require(all(name in allowed for name in names) and not getattr(node, 'level', 0)
                    and all(a.name != '*' for a in node.names), "Unapproved regression import")
            if isinstance(node, ast.ImportFrom) and node.module == 'providers':
                require(all(a.name == evidence['provider'] for a in node.names), "Regression may import only the selected provider")
        require(not isinstance(node, (ast.Global, ast.Nonlocal)), "Regression tests cannot mutate global test state")
    return contents


def semantic_quotes(records):
    quotes = [{key: record.get(key) for key in SEMANTIC_KEYS} for record in records]
    return sorted(quotes, key=lambda row: json.dumps(row, sort_keys=True))


def last_good_quotes(provider, offerings, prices):
    by_id = {row['offering_id']: row for row in prices}
    records = []
    for offering in offerings:
        if offering['provider'] == provider and offering['active']:
            require(offering['id'] in by_id, "Missing last-good quote")
            records.append(dict(offering, **by_id[offering['id']]))
    require(records, "No reviewed baseline; human review required")
    return semantic_quotes(records)


def review_approved(review, candidate):
    require(isinstance(review, dict) and set(review) == {'approved', 'head_sha', 'ci_run_id', 'reason', 'risks'}, "Invalid review fields")
    require(review['head_sha'] == candidate['head_sha'] and review['ci_run_id'] == candidate['ci_run_id'], "Review is not bound to this tested commit")
    require(isinstance(review['reason'], str) and 1 <= len(review['reason']) <= 6000, "Invalid review explanation")
    require(isinstance(review['risks'], list) and all(isinstance(r, str) and len(r) <= 2000 for r in review['risks']), "Invalid review risks")
    require(type(review['approved']) is bool and review['approved'] is True and not review['risks'], "Independent reviewer did not approve without unresolved risks")
    return True
