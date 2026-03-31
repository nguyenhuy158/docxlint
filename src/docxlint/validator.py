#!/usr/bin/env python3
"""
validate_docx_jinja2.py
-----------------------
Validate a .docx file that contains Jinja2 template syntax.

Checks:
  1. File is a valid ZIP / DOCX structure
  2. word/document.xml is well-formed XML
  3. Jinja2 syntax is valid (no broken {{ }}, {% %}, {# #})
  4. Jinja2 tags are NOT split across XML runs (Word's favourite sin)
  5. All {% for %} have matching {% endfor %}
  6. All {% if %} have matching {% endif %}
  7. Table row tags {%tr ... %} are used correctly
  8. Detects common typos: {{{, }}}, {%, %}, etc.

Usage:
  python validate_docx_jinja2.py template.docx
  python validate_docx_jinja2.py template.docx --verbose
"""

import sys
import re
import zipfile
import argparse
from pathlib import Path
from xml.etree import ElementTree as ET
from typing import NamedTuple

# ── colours ──────────────────────────────────────────────────────────────────
RED    = "\033[91m"
YELLOW = "\033[93m"
GREEN  = "\033[92m"
CYAN   = "\033[96m"
BOLD   = "\033[1m"
RESET  = "\033[0m"

def ok(msg):    print(f"  {GREEN}✓{RESET} {msg}")
def warn(msg):  print(f"  {YELLOW}⚠{RESET}  {msg}")
def err(msg):   print(f"  {RED}✗{RESET} {msg}")
def info(msg):  print(f"  {CYAN}→{RESET} {msg}")
def header(msg):print(f"\n{BOLD}{msg}{RESET}")

# ── XML files to scan inside docx ────────────────────────────────────────────
TARGET_XML = [
    "word/document.xml",
    "word/header1.xml", "word/header2.xml", "word/header3.xml",
    "word/footer1.xml", "word/footer2.xml", "word/footer3.xml",
    "word/styles.xml",
]

# ── Jinja2 tag patterns ───────────────────────────────────────────────────────
RE_VAR      = re.compile(r'\{\{.*?\}\}', re.DOTALL)          # {{ ... }}
RE_BLOCK    = re.compile(r'\{%-?\s*(.*?)\s*-?%\}', re.DOTALL) # {% ... %}
RE_COMMENT  = re.compile(r'\{#.*?#\}', re.DOTALL)            # {# ... #}
RE_ANY_TAG  = re.compile(r'\{[{%#].*?[}%#]\}', re.DOTALL)

# common typos
RE_TYPOS = [
    (re.compile(r'\{\{\{'),        "Triple brace {{{ — extra '{' somewhere"),
    (re.compile(r'\}\}\}'),        "Triple brace }}} — extra '}' somewhere"),
    (re.compile(r'\{ %'),          "Space before % — should be {%"),
    (re.compile(r'% \}'),          "Space before } — should be %}"),
    (re.compile(r'\{ \{'),         "Space inside {{ — should be {{"),
    (re.compile(r'\} \}'),         "Space inside }} — should be }}"),
    (re.compile(r'\{%\s*end\s+'),  "Space in end-tag — e.g. 'end for' should be 'endfor'"),
]

# ── Step 1: DOCX structure ────────────────────────────────────────────────────
def check_zip_structure(path: Path) -> bool:
    header("1. DOCX structure")
    try:
        with zipfile.ZipFile(path) as z:
            names = z.namelist()
            if "word/document.xml" not in names:
                err("word/document.xml not found — not a valid docx")
                return False
            ok(f"Valid ZIP with {len(names)} entries")
            ok("word/document.xml present")
            # list which target xml files exist
            found = [x for x in TARGET_XML if x in names]
            info(f"XML files to scan: {', '.join(found)}")
            return True
    except zipfile.BadZipFile:
        err("File is not a valid ZIP/DOCX")
        return False

# ── Step 2: XML well-formedness ───────────────────────────────────────────────
def check_xml(path: Path) -> dict[str, str]:
    """Returns {xml_path: raw_text} for valid files."""
    header("2. XML well-formedness")
    results = {}
    with zipfile.ZipFile(path) as z:
        for xml_path in TARGET_XML:
            if xml_path not in z.namelist():
                continue
            raw = z.read(xml_path).decode("utf-8", errors="replace")
            try:
                ET.fromstring(raw)
                ok(xml_path)
                results[xml_path] = raw
            except ET.ParseError as e:
                err(f"{xml_path} — XML parse error: {e}")
                results[xml_path] = raw  # still include for further checks
    return results

# ── Step 3: Extract plain text (strip XML tags) ───────────────────────────────
def xml_to_text(raw_xml: str) -> str:
    """Strip all XML tags, return plain text (preserves Jinja2 syntax)."""
    return re.sub(r'<[^>]+>', ' ', raw_xml)

# ── Step 4: Jinja2 syntax check ───────────────────────────────────────────────
def check_jinja2_syntax(texts: dict[str, str], verbose: bool = False):
    header("3. Jinja2 syntax")
    all_ok = True

    for xml_path, raw in texts.items():
        plain = xml_to_text(raw)

        # --- detect split tags (Jinja2 tag broken across XML runs) -----------
        # A split tag would appear as partial sequences like "{{" without closing
        split_open_var  = len(re.findall(r'\{\{', plain))
        split_close_var = len(re.findall(r'\}\}', plain))
        split_open_blk  = len(re.findall(r'\{%', plain))
        split_close_blk = len(re.findall(r'%\}', plain))

        if split_open_var != split_close_var:
            err(f"{xml_path}: Mismatched {{ }} — {split_open_var} opening vs {split_close_var} closing")
            all_ok = False
        if split_open_blk != split_close_blk:
            err(f"{xml_path}: Mismatched {{%  %}} — {split_open_blk} opening vs {split_close_blk} closing")
            all_ok = False

        # --- check for split tags in the RAW XML (tag broken by XML nodes) ---
        # Pattern: "{{" or "{%" appearing inside XML with tags between chars
        # e.g. <w:t>{</w:t><w:t>{</w:t>variable}}
        split_pattern = re.compile(r'\{[^{%#<>}\s][^<>]*<[^>]+>[^<>]*[}%#]\}')
        for m in split_pattern.finditer(raw):
            warn(f"{xml_path}: Possible tag split by XML run near: ...{m.group()[:60]}...")
            all_ok = False

        # --- typo detection --------------------------------------------------
        for pattern, description in RE_TYPOS:
            matches = pattern.findall(plain)
            if matches:
                err(f"{xml_path}: {description} (found {len(matches)}x)")
                all_ok = False

        # --- valid jinja2 blocks ---------------------------------------------
        blocks = RE_BLOCK.findall(plain)
        for block in blocks:
            block = block.strip()
            if verbose:
                info(f"  block: {{% {block[:60]} %}}")

        # --- unclosed string literals in vars --------------------------------
        for m in RE_VAR.finditer(plain):
            content = m.group()
            if content.count('"') % 2 != 0 or content.count("'") % 2 != 0:
                warn(f"{xml_path}: Possibly unclosed string in: {content[:60]}")

        if split_open_var == split_close_var and split_open_blk == split_close_blk:
            count_var = len(RE_VAR.findall(plain))
            count_blk = len(blocks)
            ok(f"{xml_path}: {count_var} variables, {count_blk} block tags")

    return all_ok

# ── Step 5: Block pairing (for/endfor, if/endif) ──────────────────────────────
def check_block_pairs(texts: dict[str, str]):
    header("4. Block tag pairing")
    all_ok = True

    # Merge all plain text for a global check
    combined = " ".join(xml_to_text(raw) for raw in texts.values())
    blocks = RE_BLOCK.findall(combined)

    stack = []
    openers = {"for", "if", "macro", "call", "filter", "with", "block", "raw"}
    closers = {"endfor", "endif", "endmacro", "endcall", "endfilter", "endwith", "endblock", "endraw"}

    for block in blocks:
        token = block.strip().split()[0] if block.strip() else ""
        # Handle {%tr for ... %} style
        token = token.lstrip("tr").lstrip()
        token = token.split()[0] if token else ""

        if token in openers:
            stack.append(token)
        elif token in closers:
            expected_opener = token[3:]  # "endfor" -> "for"
            if stack and stack[-1] == expected_opener:
                stack.pop()
            else:
                top = stack[-1] if stack else "nothing"
                err(f"Unexpected {{% {token} %}} — expected to close '{top}'")
                all_ok = False

    if stack:
        for unclosed in stack:
            err(f"Unclosed {{% {unclosed} %}} — missing {{%end{unclosed}%}}")
        all_ok = False
    else:
        ok("All for/if blocks properly closed")

    return all_ok

# ── Step 6: Table row tag check ───────────────────────────────────────────────
def check_tr_tags(texts: dict[str, str]):
    header("5. Table row tags {%tr %}")
    all_ok = True

    for xml_path, raw in texts.items():
        plain = xml_to_text(raw)
        tr_for   = len(re.findall(r'\{%-?\s*tr\s+for\b', plain))
        tr_endfor= len(re.findall(r'\{%-?\s*tr\s+endfor', plain))

        if tr_for != tr_endfor:
            err(f"{xml_path}: {tr_for}x {{%tr for%}} but {tr_endfor}x {{%tr endfor%}}")
            all_ok = False
        elif tr_for > 0:
            ok(f"{xml_path}: {tr_for} table row loop(s) matched")

    return all_ok

# ── Step 7: Variable inventory ───────────────────────────────────────────────
def list_variables(texts: dict[str, str], verbose: bool):
    header("6. Variable inventory")
    all_vars = set()
    for raw in texts.values():
        plain = xml_to_text(raw)
        for m in RE_VAR.finditer(plain):
            inner = m.group()[2:-2].strip()
            # skip complex expressions, just get base name
            base = re.split(r'[\s|.(]', inner)[0]
            if base and not base.startswith('%'):
                all_vars.add(inner)

    if all_vars:
        info(f"Found {len(all_vars)} unique variable expression(s):")
        for v in sorted(all_vars):
            print(f"    {CYAN}{{{{ {v} }}}}{RESET}")
    else:
        warn("No {{ variables }} found — is this template empty?")

# ── Single file validator ─────────────────────────────────────────────────────
class FileResult(NamedTuple):
    path: Path
    passed: bool
    issues: int


def validate_one(path: Path, verbose: bool = False) -> FileResult:
    print(f"\n{BOLD}File:{RESET} {path}  ({path.stat().st_size // 1024} KB)")
    print("─" * 60)

    # 1. ZIP structure
    if not check_zip_structure(path):
        return FileResult(path, False, 1)

    # 2. XML
    xml_texts = check_xml(path)
    if not xml_texts:
        err("No XML content could be read")
        return FileResult(path, False, 1)

    results = []
    results.append(check_jinja2_syntax(xml_texts, verbose))
    results.append(check_block_pairs(xml_texts))
    results.append(check_tr_tags(xml_texts))
    list_variables(xml_texts, verbose)

    passed = all(results)
    issues = results.count(False)

    header("Result")
    if passed:
        print(f"  {GREEN}{BOLD}✓ PASSED{RESET}\n")
    else:
        print(f"  {RED}{BOLD}✗ FAILED  ({issues} check(s) failed){RESET}\n")

    return FileResult(path, passed, issues)


# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    from . import __version__

    parser = argparse.ArgumentParser(
        prog="docxlint",
        description="Validate Jinja2-templated .docx files (single file or entire folder)",
        epilog=(
            "Examples:\n"
            "  docxlint template.docx\n"
            "  docxlint templates/ --recursive\n"
            "  docxlint template.docx --verbose\n"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("path", help="Path to a .docx file OR a folder containing .docx files")
    parser.add_argument("--verbose", "-v", action="store_true", help="Show all block tags")
    parser.add_argument("--recursive", "-r", action="store_true", help="Scan subfolders too")
    parser.add_argument("--version", "-V", action="version", version=f"%(prog)s {__version__}")
    args = parser.parse_args()

    target = Path(args.path)
    if not target.exists():
        err(f"Path not found: {target}")
        sys.exit(1)

    # ── Collect files ─────────────────────────────────────────────────────────
    if target.is_file():
        if target.suffix.lower() != ".docx":
            warn(f"'{target.name}' is not a .docx file")
        files = [target]
    elif target.is_dir():
        glob = "**/*.docx" if args.recursive else "*.docx"
        files = sorted(target.glob(glob))
        if not files:
            warn(f"No .docx files found in: {target}")
            sys.exit(0)
        print(f"\n{BOLD}Scanning:{RESET} {target}  →  {len(files)} file(s) found")
    else:
        err(f"Not a file or directory: {target}")
        sys.exit(1)

    # ── Run validation ────────────────────────────────────────────────────────
    file_results: list[FileResult] = []
    for f in files:
        file_results.append(validate_one(f, args.verbose))

    # ── Final summary table (only when multiple files) ────────────────────────
    if len(files) > 1:
        print(f"\n{'═' * 60}")
        print(f"{BOLD}  FINAL SUMMARY  —  {len(files)} file(s){RESET}")
        print(f"{'═' * 60}")

        col_w = max(len(str(r.path.name)) for r in file_results) + 2
        for r in file_results:
            status = f"{GREEN}✓ PASS{RESET}" if r.passed else f"{RED}✗ FAIL{RESET}"
            name   = str(r.path.name).ljust(col_w)
            issues = "" if r.passed else f"  {YELLOW}({r.issues} check(s) failed){RESET}"
            print(f"  {status}  {name}{issues}")

        total   = len(file_results)
        passed  = sum(1 for r in file_results if r.passed)
        failed  = total - passed

        print(f"\n  Passed: {GREEN}{passed}{RESET}   Failed: {RED}{failed}{RESET}   Total: {total}")

        if failed:
            print(f"\n  {RED}{BOLD}✗ Some files have issues — fix before using with docxtpl{RESET}\n")
            sys.exit(1)
        else:
            print(f"\n  {GREEN}{BOLD}✓ All files passed!{RESET}\n")
            sys.exit(0)
    else:
        sys.exit(0 if file_results[0].passed else 1)


if __name__ == "__main__":
    main()
