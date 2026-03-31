# docx-jinja2-validator

Validate [Jinja2](https://jinja.palletsprojects.com/) template syntax inside `.docx` files — built for use with [docxtpl](https://docxtpl.readthedocs.io/).

## Install

```bash
pip install docx-jinja2-validator
```

## Usage

```bash
# single file
docx-validate template.docx

# entire folder
docx-validate ./templates/

# recursive (includes subfolders)
docx-validate ./templates/ --recursive

# verbose (show all block tags)
docx-validate ./templates/ --verbose
```

Or via Python module:

```bash
python -m docx_jinja2_validator template.docx
```

## What it checks

| # | Check | Example error caught |
|---|-------|----------------------|
| 1 | Valid ZIP / DOCX structure | Corrupt file |
| 2 | XML well-formedness | `word/document.xml` broken |
| 3 | `{{ }}` balance | Missing `}` in variable |
| 4 | `{% %}` balance | Missing `%}` in block tag |
| 5 | Split tags | Word splits `{{var}}` across XML runs |
| 6 | Common typos | `{{{`, `}}}`, `{ %`, `% }`, `end for` |
| 7 | Block pairing | `{% for %}` without `{% endfor %}` |
| 8 | Table row tags | `{%tr for %}` without `{%tr endfor %}` |
| 9 | Variable inventory | Lists all `{{ ... }}` found |

## Example output

```
Validating: template.docx  (42 KB)
────────────────────────────────────────────────────────────

1. DOCX structure
  ✓ Valid ZIP with 17 entries
  ✓ word/document.xml present

2. XML well-formedness
  ✓ word/document.xml

3. Jinja2 syntax
  ✓ word/document.xml: 6 variables, 4 block tags

4. Block tag pairing
  ✓ All for/if blocks properly closed

5. Table row tags {%tr %}
  ✓ word/document.xml: 1 table row loop(s) matched

6. Variable inventory
  → Found 6 unique variable expression(s):
    {{ objects.customer_id.name }}
    {{ objects.total_overdue_amount }}
    ...

Result
  ✓ PASSED
```

## Exit codes

| Code | Meaning |
|------|---------|
| `0`  | All files passed |
| `1`  | One or more files have issues |

Useful for CI/CD pipelines:

```bash
docx-validate ./templates/ && echo "Templates OK" || echo "Fix templates!"
```

## Use as a library

```python
from docx_jinja2_validator import validate_one
from pathlib import Path

result = validate_one(Path("template.docx"), verbose=False)
print(result.passed)   # True / False
print(result.issues)   # number of failed checks
```

## License

MIT
