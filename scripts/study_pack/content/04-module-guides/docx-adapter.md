# docx_adapter.py — convert Word complexity into evidence

## Purpose and libraries

This is the only production module allowed to understand python-docx, lxml,
OOXML and Word package internals. python-docx opens the package and exposes
paragraph/table/run objects; focused XML traversal handles details that high-level
accessors omit. `hashlib` identifies the exact bytes read and `io.BytesIO`
ensures the parser sees those same bytes. No source file is written.

## Important types and functions

`read_document` is the entry point and `DocxReadError` carries stable failure
categories. `_StyleResolver.chain_strike` follows style inheritance with cycle
and broken-reference detection. `_collect_body`, `_collect_table` and
`_collect_paragraph` traverse structure. `_iter_paragraph_runs` preserves
hyperlink-contained runs. `_resolve_strike` produces value, origin and reason.

## Inputs, outputs and data flow

Input: a local `Path`. Output: immutable `Document` or `DocxReadError`.
Bytes → package → body/table paragraphs → ordered runs → frozen blocks with
locations and warnings → Document. Unknown strike remains `None` in `TextRun`.
Warnings make overall coverage LIMITED; they do not invent a check status.

## Important invariants and design reasons

Resolve direct strike, character style, paragraph style/default style,
docDefaults, then default off only when the chain is known. Broken style chains
must not become active text accidentally. Double strike remains a policy
uncertainty when ordinary strike is not explicitly true.

Tables are traversed through XML cell elements so merged masters appear once.
Nested tables retain ancestor coordinates. Each cell paragraph remains a
separate block; no concatenation borrows a value from its neighbour.

## Failure modes

Unreadable files, malformed packages and unexpected parser errors are distinct
failures. Tracked changes, textboxes, content controls, field codes, excluded
headers/footers and other detected unsupported structures produce explicit
coverage warnings. COMPLETE means complete within declared supported scope,
not universal support for Word features.

References: [[src/design_requirement_checker/docx_adapter.py::read_document]],
[[src/design_requirement_checker/docx_adapter.py::_resolve_strike]], [[tests/test_docx_adapter.py]].
Next: [OOXML tutorial](../05-concepts/docx-ooxml.html).
