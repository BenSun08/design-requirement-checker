"""Deterministic synthetic DOCX fixtures for the S1/S2 technical spike.

Each builder writes a fixed-content fixture to ``path``. Expected outcomes for
these fixtures are hand-written as independent labels inside the spike test
files; do not derive expectations from probe output.

Cases that python-docx cannot generate through its public API are created by
small, documented raw-OOXML patches (double strike, invalid strike value,
orphan style reference, docDefaults strike, tracked revisions, content
controls, text boxes, hidden vertically-merged-cell content).
"""

from pathlib import Path

from docx import Document
from docx.enum.style import WD_STYLE_TYPE
from docx.oxml import parse_xml
from docx.oxml.ns import qn

NSDECL = 'xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"'


def _raw(xml: str):  # type: ignore[no-untyped-def]
    return parse_xml(xml)


def build_normal(path: Path) -> Path:
    """Body paragraphs, split runs, adjacent same-format runs, whitespace, empty paragraph."""
    doc = Document()
    doc.add_paragraph("plain body paragraph one")
    p1 = doc.add_paragraph()
    p1.add_run("Hello ")
    bold = p1.add_run("bold")
    bold.bold = True
    p1.add_run(" world")
    p2 = doc.add_paragraph()
    p2.add_run("Alpha")
    p2.add_run("Beta")
    doc.add_paragraph("A  B\tC")
    doc.add_paragraph("")
    doc.save(path)
    return path


def build_table(path: Path) -> Path:
    """One body paragraph, a 2x2 table (one cell with two paragraphs), one trailing paragraph."""
    doc = Document()
    doc.add_paragraph("intro")
    table = doc.add_table(rows=2, cols=2)
    table.cell(0, 0).text = "r0c0"
    table.cell(0, 1).text = "r0c1"
    table.cell(1, 0).text = "r1c0"
    cell = table.cell(1, 1)
    cell.text = "cell para A"
    cell.add_paragraph("cell para B")
    doc.add_paragraph("outro")
    doc.save(path)
    return path


def build_nested_merged(path: Path) -> Path:
    """3x3 grid with a gridSpan master, a vMerge master, patched hidden continuation
    content, and a nested table inside a cell."""
    doc = Document()
    table = doc.add_table(rows=3, cols=3)
    table.cell(0, 0).merge(table.cell(0, 1))
    table.cell(0, 0).text = "H-MERGE"
    table.cell(0, 2).text = "r0c2"
    table.cell(1, 0).text = "r1c0"
    table.cell(1, 1).text = "r1c1"
    table.cell(1, 2).merge(table.cell(2, 2))
    table.cell(1, 2).text = "V-MERGE"
    table.cell(2, 0).text = "r2c0"
    outer = table.cell(2, 1)
    outer.text = "outer-para"
    nested = outer.add_table(rows=1, cols=1)
    nested.cell(0, 0).text = "NESTED-CELL"
    # Raw patch: the vertically merged continuation cell at (row 2, grid col 2)
    # contains text that Word does not display. Word requires each tc to end
    # with a paragraph; the continuation tc keeps an empty w:p which we fill.
    continuation_tc = table.rows[2]._tr.tc_lst[2]
    continuation_p = continuation_tc.find(qn("w:p"))
    continuation_p.append(_raw(f"<w:r {NSDECL}><w:t>HIDDEN-CONT</w:t></w:r>"))
    doc.save(path)
    return path


def build_strike_matrix(path: Path) -> Path:
    """S1 formatting matrix in one document."""
    doc = Document()
    doc.add_paragraph().add_run("direct strike").font.strike = True
    doc.add_paragraph().add_run("explicit false").font.strike = False
    p2 = doc.add_paragraph()
    p2.add_run("keep ")
    p2.add_run("gone ").font.strike = True
    p2.add_run("tail")
    struck = doc.styles.add_style("StruckStyle", WD_STYLE_TYPE.PARAGRAPH)
    struck.base_style = doc.styles["Normal"]
    struck.font.strike = True
    doc.add_paragraph("inherited", style=struck)
    p4 = doc.add_paragraph(style=struck)
    p4.add_run("override").font.strike = False
    # Raw patch: double strikethrough (python-docx cannot set dstrike via font).
    p5 = doc.add_paragraph()
    r5 = p5.add_run("dbl")
    r5._r.get_or_add_rPr().append(_raw(f"<w:dstrike {NSDECL}/>"))
    # Raw patch: invalid strike value, outside the ST_OnOff vocabulary.
    p6 = doc.add_paragraph()
    r6 = p6.add_run("maybe")
    r6._r.get_or_add_rPr().append(_raw(f'<w:strike {NSDECL} w:val="maybe"/>'))
    # Raw patch: character style reference to a style that does not exist.
    p7 = doc.add_paragraph()
    r7 = p7.add_run("orphan")
    r7._r.get_or_add_rPr().append(_raw(f'<w:rStyle {NSDECL} w:val="MissingStyle"/>'))
    doc.save(path)
    return path


def build_docdefaults_strike(path: Path) -> Path:
    """docDefaults-level strike; one plain paragraph, one explicit-false override."""
    doc = Document()
    doc_defaults_rpr = (
        doc.styles.element.find(qn("w:docDefaults")).find(qn("w:rPrDefault")).find(qn("w:rPr"))
    )  # type: ignore[union-attr]
    doc_defaults_rpr.append(_raw(f"<w:strike {NSDECL}/>"))
    doc.add_paragraph("plain")
    p1 = doc.add_paragraph()
    p1.add_run("off").font.strike = False
    doc.save(path)
    return path


def build_tracked_revisions(path: Path) -> Path:
    """One paragraph with tracked insert/delete plus one clean paragraph."""
    doc = Document()
    p0 = doc.add_paragraph()
    p0.add_run("kept ")
    # Raw patch: tracked insertion and deletion (python-docx has no revision API).
    p0._p.append(
        _raw(
            f'<w:ins {NSDECL} w:id="1" w:author="spike" w:date="2026-01-01T00:00:00Z">'
            "<w:r><w:t>INSERTED</w:t></w:r></w:ins>"
        )
    )
    p0._p.append(
        _raw(
            f'<w:del {NSDECL} w:id="2" w:author="spike" w:date="2026-01-01T00:00:00Z">'
            "<w:r><w:delText>REMOVED</w:delText></w:r></w:del>"
        )
    )
    doc.add_paragraph("clean paragraph")
    doc.save(path)
    return path


def build_excluded_parts(path: Path) -> Path:
    """Header/footer text, a body-level content-control paragraph, and a text box."""
    doc = Document()
    doc.add_paragraph("visible body")
    section = doc.sections[0]
    section.header.paragraphs[0].text = "HEADER TEXT"
    section.footer.paragraphs[0].text = "FOOTER TEXT"
    # Raw patch: body-level content control (w:sdt) holding a paragraph.
    # Inserted before sectPr to keep the required body element order.
    sect_pr = doc.element.body.find(qn("w:sectPr"))
    sect_pr.addprevious(
        _raw(
            f'<w:sdt {NSDECL}><w:sdtPr><w:id w:val="1"/></w:sdtPr>'
            "<w:sdtContent><w:p><w:r><w:t>SDT PARA</w:t></w:r></w:p></w:sdtContent></w:sdt>"
        )
    )
    # Raw patch: minimal text box (drawing/txbxContent) inside a body paragraph run.
    p1 = doc.add_paragraph()
    p1.add_run("host ")
    textbox_run = p1.add_run()
    textbox_run._r.append(
        _raw(
            "<mc:AlternateContent "
            'xmlns:mc="http://schemas.openxmlformats.org/markup-compatibility/2006">'
            '<mc:Choice Requires="wps">'
            "<w:drawing "
            'xmlns:wps="http://schemas.microsoft.com/office/word/2010/wordprocessingShape" '
            'xmlns:wp="http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing" '
            f'xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" {NSDECL}>'
            '<wp:inline><a:graphic><a:graphicData uri="wordprocessingShape">'
            "<wps:wsp><wps:txbx><w:txbxContent>"
            "<w:p><w:r><w:t>TEXTBOX TEXT</w:t></w:r></w:p>"
            "</w:txbxContent></wps:txbx></wps:wsp>"
            "</a:graphicData></a:graphic></wp:inline></w:drawing>"
            "</mc:Choice></mc:AlternateContent>"
        )
    )
    doc.save(path)
    return path


def build_empty(path: Path) -> Path:
    """A valid document with no paragraphs and no tables."""
    doc = Document()
    doc.save(path)
    return path


def build_malformed(path: Path) -> Path:
    """Bytes that are not an OOXML package at all."""
    path.write_bytes(b"this is not a zip package")
    return path
