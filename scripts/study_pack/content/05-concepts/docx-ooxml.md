# DOCX and OOXML: visible text is structured evidence

A DOCX is a ZIP-based package of XML parts. python-docx provides useful paragraph,
run and table APIs. A run is a text segment with formatting; a visually continuous
sentence can contain many runs. Matching must therefore use reconstructed block
text while preserving each run's original offset and effective strike.

## Why inspect XML directly?

`paragraph.runs` omits hyperlink-contained runs. `_iter_paragraph_runs` uses
`iter_inner_content` and expands `Hyperlink.runs` in order. Formatting may be
inherited rather than written on the run: `_StyleResolver` follows character and
paragraph style `w:basedOn` chains and checks `docDefaults`. The default paragraph
style is identified by `w:default="1"`, not a hard-coded “Normal” name.

A bare `w:strike` means on; absent direct strike means consult inheritance.
An invalid value, missing referenced style or cycle must remain unknown with
a reason. Default-off is safe only after a known chain supplies no value.
Double strike without explicit ordinary strike remains unresolved by policy.

## Tables and excluded structures

A requirement inside a table cell becomes a TABLE_CELL_PARAGRAPH block with
coordinates. Merged masters are extracted once; nested cells keep their ancestor
path. Two separate cell paragraphs cannot jointly satisfy a span.

Tracked revisions, content controls, textboxes, fields and excluded
header/footer content can hide relevant text. Detecting them sets warnings and
Coverage.LIMITED. LIMITED is not MISSING and does not change the truth table;
it limits the scope of any absence claim. COMPLETE also remains relative to
the declared supported scope.

References: [[src/design_requirement_checker/docx_adapter.py::_iter_paragraph_runs]],
[[src/design_requirement_checker/docx_adapter.py::_StyleResolver.chain_strike]],
[[src/design_requirement_checker/docx_adapter.py::_collect_table]], [[tests/fixture_factory.py]].
Next: [adapter guide](../04-module-guides/docx-adapter.html).
