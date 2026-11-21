#!/usr/bin/env python3
"""
scripts/generate_google_doc.py

Generates a Google Docs-optimised Microsoft Word (.docx) document and matching PDF
from docs/system_overview_and_component_specification.md, ensuring professional typography,
table styling, code block callouts, equation rendering, and image embedding.
"""

import os
import re
import sys
import docx
from docx.shared import Inches, Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.oxml import parse_xml
from docx.oxml.ns import nsdecls

# Curated Professional Color Palette (Navy / Slate / Blue)
NAVY_PRIMARY = RGBColor(15, 41, 74)       # #0F294A - Primary Headings
BLUE_ACCENT  = RGBColor(29, 78, 216)     # #1D4ED8 - Secondary Headings & Accents
SLATE_DARK   = RGBColor(51, 65, 85)       # #334155 - Tertiary Headings
BODY_TEXT    = RGBColor(30, 41, 59)       # #1E293B - Body Text
MUTED_SLATE  = RGBColor(100, 116, 139)   # #64748B - Captions & Subtitles
CODE_TEXT    = RGBColor(15, 23, 42)       # #0F172A - Monospace Code
WHITE        = RGBColor(255, 255, 255)

def set_cell_background(cell, fill_hex):
    """Sets background shading of a table cell."""
    tcPr = cell._tc.get_or_add_tcPr()
    for child in list(tcPr):
        if child.tag.endswith('shd'):
            tcPr.remove(child)
    tcPr.append(parse_xml(f'<w:shd {nsdecls("w")} w:fill="{fill_hex}"/>'))

def set_cell_margins(cell, top=120, bottom=120, left=160, right=160):
    """Sets internal padding (in twips/dxa) for a table cell."""
    tcPr = cell._tc.get_or_add_tcPr()
    for child in list(tcPr):
        if child.tag.endswith('tcMar'):
            tcPr.remove(child)
    tcMar = parse_xml(f'''
        <w:tcMar {nsdecls("w")}>
            <w:top w:w="{top}" w:type="dxa"/>
            <w:bottom w:w="{bottom}" w:type="dxa"/>
            <w:left w:w="{left}" w:type="dxa"/>
            <w:right w:w="{right}" w:type="dxa"/>
        </w:tcMar>
    ''')
    tcPr.append(tcMar)

def set_table_borders(table, color="CBD5E1", sz="4"):
    """Sets clean horizontal borders and removes heavy vertical borders."""
    tblPr = table._tbl.tblPr
    borders = parse_xml(f'''
        <w:tblBorders {nsdecls("w")}>
            <w:top w:val="single" w:sz="{sz}" w:space="0" w:color="{color}"/>
            <w:bottom w:val="single" w:sz="{sz}" w:space="0" w:color="{color}"/>
            <w:insideH w:val="single" w:sz="{sz}" w:space="0" w:color="{color}"/>
            <w:insideV w:val="single" w:sz="{sz}" w:space="0" w:color="{color}"/>
            <w:left w:val="none"/>
            <w:right w:val="none"/>
        </w:tblBorders>
    ''')
    tblPr.append(borders)

def clean_math_string(s):
    """Cleans LaTeX syntax into readable mathematical notation."""
    # Protect set braces
    s = s.replace(r'\{', '«LBRACE»').replace(r'\}', '«RBRACE»')

    # Handle cases environment
    if r'\begin{cases}' in s:
        s = s.replace(r'\begin{cases}', '{ ').replace(r'\end{cases}', ' }')
        s = s.replace(r'\\', ' ;  ')
        s = s.replace('&', ' ')

    # Normalize subscripts, superscripts, and formatting wrappers before fraction parsing
    for _ in range(3):
        s = re.sub(r'_\{([^}]+)\}', r'_\1', s)
        s = re.sub(r'\^\{([^}]+)\}', r'^\1', s)
        s = re.sub(r'\\(?:text|mathrm|mathbf|mathit|mathcal)\{([^}]+)\}', r'\1', s)
        s = re.sub(r'\\frac\{([^}]+)\}\{([^}]+)\}', r'(\1 / \2)', s)

    s = s.replace(r'\left(', '(').replace(r'\right)', ')')
    s = s.replace(r'\left[', '[').replace(r'\right]', ']')
    s = s.replace(r'\max', 'max').replace(r'\min', 'min').replace(r'\sin', 'sin').replace(r'\cos', 'cos')
    s = s.replace(r'\round', 'round')
    s = s.replace(r'\quad', '    ').replace(r'\qquad', '        ')
    s = s.replace(r'\longrightarrow', ' ──> ').replace(r'\to', ' → ').replace(r'\implies', ' ⇒ ')
    s = s.replace(r'\ge', '≥').replace(r'\le', '≤').replace(r'\approx', '≈').replace(r'\pm', '±')
    s = s.replace(r'\cdot', '·').replace(r'\times', '×')
    s = s.replace(r'\notin', '∉').replace(r'\in', '∈')
    s = s.replace(r'\lor', ' OR ').replace(r'\land', ' AND ')
    s = s.replace(r'^{\circ}C', '°C').replace(r'^{\circ}\text{C}', '°C').replace(r'^\circ\text{C}', '°C').replace(r'^\circ C', '°C').replace(r'^\circ', '°')
    s = s.replace(r'\,', ' ')
    s = s.replace(r'\Delta', 'Δ').replace(r'\alpha', 'α').replace(r'\beta', 'β').replace(r'\gamma', 'γ').replace(r'\tau', 'τ').replace(r'\theta', 'θ')

    # Restore set braces
    s = s.replace('«LBRACE»', '{').replace('«RBRACE»', '}')
    return s

def format_inline_math(p, math_str, base_font_size=10, is_bold=False):
    """Formats mathematical expressions with proper subscripts, superscripts, and Greek letters."""
    s = clean_math_string(math_str)

    # Tokenize subscripts/superscripts: e.g. T_{scd30}, T_scd30, CO_2, \tau_{age}
    sub_pattern = re.compile(r'([A-Za-z0-9ΔπτθαβγT̂]+(?:_\{[^}]+\}|_[A-Za-z0-9]+|\^\{[^}]+\}|\^[A-Za-z0-9]+))')
    tokens = sub_pattern.split(s)

    for tok in tokens:
        if not tok:
            continue
        if '_' in tok:
            parts = tok.split('_', 1)
            base = parts[0]
            sub = parts[1].strip('{}')
            r1 = p.add_run(base)
            r1.font.name = 'Arial'
            r1.font.size = Pt(base_font_size)
            r1.font.italic = True
            r1.font.bold = is_bold
            r1.font.color.rgb = BODY_TEXT

            r2 = p.add_run(sub)
            r2.font.name = 'Arial'
            r2.font.size = Pt(base_font_size * 0.8)
            r2.font.subscript = True
            r2.font.bold = is_bold
            r2.font.color.rgb = BODY_TEXT
        elif '^' in tok:
            parts = tok.split('^', 1)
            base = parts[0]
            sup = parts[1].strip('{}')
            r1 = p.add_run(base)
            r1.font.name = 'Arial'
            r1.font.size = Pt(base_font_size)
            r1.font.italic = True
            r1.font.bold = is_bold
            r1.font.color.rgb = BODY_TEXT

            r2 = p.add_run(sup)
            r2.font.name = 'Arial'
            r2.font.size = Pt(base_font_size * 0.8)
            r2.font.superscript = True
            r2.font.bold = is_bold
            r2.font.color.rgb = BODY_TEXT
        else:
            # Strip any remaining rogue braces
            clean_tok = tok.replace('{', '').replace('}', '')
            r = p.add_run(clean_tok)
            r.font.name = 'Arial'
            r.font.size = Pt(base_font_size)
            r.font.bold = is_bold
            r.font.color.rgb = BODY_TEXT

def parse_and_add_text(p, text, base_font_size=10, is_italic=False, is_bold=False, base_color=BODY_TEXT):
    """Parses markdown bold, italic, code, links, and inline math in a line, handling nested formatting."""
    token_pattern = re.compile(r'(\[.*?\]\(.*?\)|\*\*.*?\*\*|`.*?`|\$.*?\$|\*.*?\*)')
    tokens = token_pattern.split(text)

    for tok in tokens:
        if not tok:
            continue
        
        # Link [text](url)
        link_match = re.match(r'^\[(.*?)\]\((.*?)\)$', tok)
        if link_match:
            link_text = link_match.group(1)
            r = p.add_run(link_text)
            r.font.name = 'Arial'
            r.font.size = Pt(base_font_size)
            r.font.underline = True
            r.font.color.rgb = BLUE_ACCENT
            continue

        # Bold **text** (handles nested math or code inside bold)
        if tok.startswith('**') and tok.endswith('**') and len(tok) >= 4:
            content = tok[2:-2]
            inner_tokens = re.split(r'(\$.*?\$|`.*?`)', content)
            for itok in inner_tokens:
                if not itok:
                    continue
                if itok.startswith('$') and itok.endswith('$') and len(itok) >= 2:
                    format_inline_math(p, itok[1:-1], base_font_size=base_font_size, is_bold=True)
                elif itok.startswith('`') and itok.endswith('`') and len(itok) >= 2:
                    r = p.add_run(itok[1:-1])
                    r.font.name = 'Consolas'
                    r.font.size = Pt(base_font_size * 0.9)
                    r.font.bold = True
                    r.font.color.rgb = CODE_TEXT
                else:
                    r = p.add_run(itok)
                    r.font.name = 'Arial'
                    r.font.size = Pt(base_font_size)
                    r.font.bold = True
                    r.font.italic = is_italic
                    r.font.color.rgb = base_color
            continue

        # Inline Code `text`
        if tok.startswith('`') and tok.endswith('`') and len(tok) >= 2:
            r = p.add_run(tok[1:-1])
            r.font.name = 'Courier New'
            rPr = r._r.get_or_add_rPr()
            rPr.append(parse_xml(f'<w:rFonts {nsdecls("w")} w:ascii="Courier New" w:hAnsi="Courier New" w:cs="Courier New"/>'))
            r.font.size = Pt(base_font_size * 0.9)
            r.font.bold = is_bold
            r.font.color.rgb = CODE_TEXT
            continue

        # Inline Math $math$
        if tok.startswith('$') and tok.endswith('$') and len(tok) >= 2:
            format_inline_math(p, tok[1:-1], base_font_size=base_font_size, is_bold=is_bold)
            continue

        # Italic *text*
        if tok.startswith('*') and tok.endswith('*') and len(tok) >= 2:
            r = p.add_run(tok[1:-1])
            r.font.name = 'Arial'
            r.font.size = Pt(base_font_size)
            r.font.italic = True
            r.font.bold = is_bold
            r.font.color.rgb = base_color
            continue

        # Regular text
        r = p.add_run(tok)
        r.font.name = 'Arial'
        r.font.size = Pt(base_font_size)
        r.font.italic = is_italic
        r.font.bold = is_bold
        r.font.color.rgb = base_color

def convert_markdown_to_google_doc(md_path, docx_path):
    """Converts a Markdown file into a Google Docs-optimised .docx file."""
    doc = docx.Document()

    # Set Document Metadata
    doc.core_properties.title = "Software-Defined Vehicle (SDV) Cyber-Physical Cabin Environmental Monitoring and Closed-Loop HVAC Regulation System"
    doc.core_properties.author = "Isiaka Mosudi, Ashok Ramalingam, Pooja Janwalkar, AnnaMaria Moçi, Julia Philip"
    doc.core_properties.subject = "System Overview, Component Architecture, and Functional Specification"
    doc.core_properties.category = "Technical Specification"

    # Set Margins (0.75 in all around for wide readable tables)
    for section in doc.sections:
        section.top_margin = Inches(0.75)
        section.bottom_margin = Inches(0.75)
        section.left_margin = Inches(0.75)
        section.right_margin = Inches(0.75)
        # Clear headers and footers to ensure clean layout
        for p in section.header.paragraphs:
            p.text = ""
        for p in section.footer.paragraphs:
            p.text = ""

    with open(md_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    idx = 0
    total_lines = len(lines)

    in_code_block = False
    code_lang = ""
    code_lines = []

    in_table = False
    table_lines = []

    in_blockquote = False
    quote_lines = []

    def flush_code_block():
        nonlocal in_code_block, code_lang, code_lines
        if not code_lines:
            in_code_block = False
            return
        
        # Create a single-cell callout box for the code snippet
        tbl = doc.add_table(rows=1, cols=1)
        tbl.alignment = WD_TABLE_ALIGNMENT.CENTER
        cell = tbl.cell(0, 0)
        set_cell_background(cell, "F1F5F9")  # soft light slate background
        set_cell_margins(cell, top=100, bottom=100, left=140, right=140)
        
        tcPr = cell._tc.get_or_add_tcPr()
        borders = parse_xml(f'''
            <w:tcBorders {nsdecls("w")}>
                <w:top w:val="single" w:sz="4" w:space="0" w:color="CBD5E1"/>
                <w:left w:val="single" w:sz="18" w:space="0" w:color="2563EB"/>
                <w:bottom w:val="single" w:sz="4" w:space="0" w:color="CBD5E1"/>
                <w:right w:val="single" w:sz="4" w:space="0" w:color="CBD5E1"/>
            </w:tcBorders>
        ''')
        tcPr.append(borders)

        cp = cell.paragraphs[0]
        cp.paragraph_format.space_before = Pt(2)
        cp.paragraph_format.space_after = Pt(2)
        cp.paragraph_format.line_spacing = 1.05

        full_code = ''.join(code_lines).rstrip()
        r = cp.add_run(full_code)
        r.font.name = 'Courier New'
        rPr = r._r.get_or_add_rPr()
        rPr.append(parse_xml(f'<w:rFonts {nsdecls("w")} w:ascii="Courier New" w:hAnsi="Courier New" w:cs="Courier New"/>'))
        r.font.size = Pt(7.5)
        r.font.color.rgb = CODE_TEXT

        sp = doc.add_paragraph()
        sp.paragraph_format.space_before = Pt(0)
        sp.paragraph_format.space_after = Pt(4)

        code_lines = []
        in_code_block = False
        code_lang = ""

    def flush_table():
        nonlocal in_table, table_lines
        if not table_lines:
            in_table = False
            return

        rows_data = []
        for line in table_lines:
            s_line = line.strip()
            if not s_line.startswith('|') or not s_line.endswith('|'):
                continue
            cells = [c.strip() for c in s_line[1:-1].split('|')]
            # Check if separator row (e.g. |:---|:---|)
            if all(re.match(r'^:?-+:?$', c) for c in cells if c):
                continue
            rows_data.append(cells)

        if not rows_data:
            table_lines = []
            in_table = False
            return

        num_rows = len(rows_data)
        num_cols = max(len(r) for r in rows_data)

        for r in rows_data:
            while len(r) < num_cols:
                r.append("")

        tbl = doc.add_table(rows=num_rows, cols=num_cols)
        tbl.alignment = WD_TABLE_ALIGNMENT.CENTER
        set_table_borders(tbl, color="CBD5E1", sz="4")

        # Format header row
        hdr_row = tbl.rows[0]
        trPr = hdr_row._tr.get_or_add_trPr()
        trPr.append(parse_xml(f'<w:tblHeader {nsdecls("w")}/>'))
        trPr.append(parse_xml(f'<w:cantSplit {nsdecls("w")}/>'))

        for c_idx, cell in enumerate(hdr_row.cells):
            set_cell_background(cell, "0F294A")  # Dark Navy
            set_cell_margins(cell, top=120, bottom=120, left=140, right=140)
            p = cell.paragraphs[0]
            p.alignment = WD_ALIGN_PARAGRAPH.LEFT
            p.paragraph_format.space_before = Pt(2)
            p.paragraph_format.space_after = Pt(2)
            cell_text = rows_data[0][c_idx]
            parse_and_add_text(p, cell_text, base_font_size=9.5, is_bold=True, base_color=WHITE)

        # Format body rows
        for r_idx in range(1, num_rows):
            row = tbl.rows[r_idx]
            r_trPr = row._tr.get_or_add_trPr()
            r_trPr.append(parse_xml(f'<w:cantSplit {nsdecls("w")}/>'))
            bg_color = "F8FAFC" if (r_idx % 2 == 1) else "FFFFFF"

            for c_idx, cell in enumerate(row.cells):
                set_cell_background(cell, bg_color)
                set_cell_margins(cell, top=100, bottom=100, left=140, right=140)
                p = cell.paragraphs[0]
                p.alignment = WD_ALIGN_PARAGRAPH.LEFT
                p.paragraph_format.space_before = Pt(2)
                p.paragraph_format.space_after = Pt(2)
                cell_text = rows_data[r_idx][c_idx]
                parse_and_add_text(p, cell_text, base_font_size=9, base_color=BODY_TEXT)

        sp = doc.add_paragraph()
        sp.paragraph_format.space_before = Pt(0)
        sp.paragraph_format.space_after = Pt(6)

        table_lines = []
        in_table = False

    def flush_blockquote():
        nonlocal in_blockquote, quote_lines
        if not quote_lines:
            in_blockquote = False
            return

        tbl = doc.add_table(rows=1, cols=1)
        tbl.alignment = WD_TABLE_ALIGNMENT.CENTER
        cell = tbl.cell(0, 0)
        set_cell_background(cell, "F8FAFC")
        set_cell_margins(cell, top=80, bottom=80, left=160, right=160)
        
        tcPr = cell._tc.get_or_add_tcPr()
        borders = parse_xml(f'''
            <w:tcBorders {nsdecls("w")}>
                <w:top w:val="none"/>
                <w:left w:val="single" w:sz="18" w:space="0" w:color="3B82F6"/>
                <w:bottom w:val="none"/>
                <w:right w:val="none"/>
            </w:tcBorders>
        ''')
        tcPr.append(borders)

        cp = cell.paragraphs[0]
        cp.paragraph_format.space_before = Pt(2)
        cp.paragraph_format.space_after = Pt(2)
        quote_text = ' '.join(quote_lines)
        parse_and_add_text(cp, quote_text, base_font_size=9.5, is_italic=True, base_color=SLATE_DARK)

        sp = doc.add_paragraph()
        sp.paragraph_format.space_before = Pt(0)
        sp.paragraph_format.space_after = Pt(4)

        quote_lines = []
        in_blockquote = False

    while idx < total_lines:
        line = lines[idx]
        stripped = line.strip()

        # Handle Code Fences
        if stripped.startswith('```'):
            if not in_code_block:
                if in_table:
                    flush_table()
                if in_blockquote:
                    flush_blockquote()
                in_code_block = True
                code_lang = stripped[3:].strip()
                code_lines = []
            else:
                flush_code_block()
            idx += 1
            continue

        if in_code_block:
            code_lines.append(line)
            idx += 1
            continue

        # Handle Tables
        if stripped.startswith('|') and stripped.endswith('|'):
            if not in_table:
                if in_blockquote:
                    flush_blockquote()
                in_table = True
                table_lines = []
            table_lines.append(line)
            idx += 1
            continue
        elif in_table:
            flush_table()

        # Handle Blockquotes
        if stripped.startswith('>'):
            if not in_blockquote:
                in_blockquote = True
                quote_lines = []
            quote_lines.append(stripped.lstrip('>').strip())
            idx += 1
            continue
        elif in_blockquote:
            flush_blockquote()

        # Blank line
        if not stripped:
            idx += 1
            continue

        # Horizontal rule
        if stripped in ['---', '***', '___']:
            p = doc.add_paragraph()
            p.paragraph_format.space_before = Pt(6)
            p.paragraph_format.space_after = Pt(6)
            pBdr = parse_xml(f'''
                <w:pBdr {nsdecls("w")}>
                    <w:bottom w:val="single" w:sz="6" w:space="1" w:color="E2E8F0"/>
                </w:pBdr>
            ''')
            p._p.get_or_add_pPr().append(pBdr)
            idx += 1
            continue

        # Handle Images (![caption](url))
        img_match = re.match(r'^!\[(.*?)\]\((.*?)\)$', stripped)
        if img_match:
            caption = img_match.group(1)
            rel_path = img_match.group(2)
            full_img_path = rel_path if os.path.isabs(rel_path) else os.path.normpath(os.path.join(os.path.dirname(md_path), rel_path))
            
            if not os.path.exists(full_img_path):
                candidate_paths = [
                    os.path.join(os.path.dirname(md_path), 'assets', os.path.basename(rel_path)),
                    os.path.join(os.path.dirname(md_path), '..', 'docs', 'assets', os.path.basename(rel_path)),
                    os.path.join('/home/mosud/Documents/dev/HVAC-iot-monitoring/docs/assets', os.path.basename(rel_path)),
                    os.path.join('/home/mosud/Documents/dev/HVAC-iot-monitoring/foundational_document/assets', os.path.basename(rel_path))
                ]
                for c in candidate_paths:
                    if os.path.exists(c):
                        full_img_path = c
                        break

            if os.path.exists(full_img_path):
                try:
                    from PIL import Image
                    with Image.open(full_img_path) as im:
                        img_w, img_h = im.size
                        aspect = img_h / img_w
                    max_w_in = min(6.2, 5.5 / aspect if aspect > 0.8 else 6.2)
                    target_width = Inches(max_w_in)
                except Exception:
                    target_width = Inches(6.2)

                p = doc.add_paragraph()
                p.alignment = WD_ALIGN_PARAGRAPH.CENTER
                p.paragraph_format.space_before = Pt(8)
                p.paragraph_format.space_after = Pt(2)
                p.paragraph_format.keep_with_next = True
                r = p.add_run()
                r.add_picture(full_img_path, width=target_width)
                
                if caption:
                    cp = doc.add_paragraph()
                    cp.alignment = WD_ALIGN_PARAGRAPH.CENTER
                    cp.paragraph_format.space_before = Pt(2)
                    cp.paragraph_format.space_after = Pt(8)
                    cr = cp.add_run(caption)
                    cr.font.name = 'Arial'
                    cr.font.size = Pt(8.5)
                    cr.font.italic = True
                    cr.font.color.rgb = MUTED_SLATE
            idx += 1
            continue

        # Handle Display Math Equations ($$ ... $$) - supports single or multi-line
        if stripped.startswith('$$'):
            math_lines = []
            if stripped.endswith('$$') and len(stripped) > 4:
                math_lines.append(stripped[2:-2].strip())
                idx += 1
            else:
                # Multi-line math block
                first_line = stripped[2:].strip()
                if first_line:
                    math_lines.append(first_line)
                idx += 1
                while idx < total_lines:
                    m_line = lines[idx].strip()
                    if m_line.endswith('$$'):
                        last_part = m_line[:-2].strip()
                        if last_part:
                            math_lines.append(last_part)
                        idx += 1
                        break
                    elif m_line == '$$':
                        idx += 1
                        break
                    else:
                        math_lines.append(m_line)
                        idx += 1

            math_content = ' '.join(math_lines)
            tbl = doc.add_table(rows=1, cols=1)
            tbl.alignment = WD_TABLE_ALIGNMENT.CENTER
            cell = tbl.cell(0, 0)
            set_cell_background(cell, "F8FAFC")
            set_cell_margins(cell, top=100, bottom=100, left=160, right=160)
            set_table_borders(tbl, color="CBD5E1", sz="4")
            
            p = cell.paragraphs[0]
            p.alignment = WD_ALIGN_PARAGRAPH.CENTER
            p.paragraph_format.space_before = Pt(3)
            p.paragraph_format.space_after = Pt(3)
            format_inline_math(p, math_content, base_font_size=10.5, is_bold=True)
            sp = doc.add_paragraph()
            sp.paragraph_format.space_before = Pt(0)
            sp.paragraph_format.space_after = Pt(4)
            continue

        # Document Title (# Title)
        if stripped.startswith('# ') and not stripped.startswith('## '):
            title_text = stripped[2:].strip()
            p = doc.add_paragraph()
            p.paragraph_format.space_before = Pt(0)
            p.paragraph_format.space_after = Pt(4)
            p.paragraph_format.keep_with_next = True
            parse_and_add_text(p, title_text, base_font_size=18, is_bold=True, base_color=NAVY_PRIMARY)
            idx += 1
            continue

        # Heading 1 (## Heading)
        if stripped.startswith('## ') and not stripped.startswith('### '):
            h1_text = stripped[3:].strip()
            p = doc.add_paragraph()
            p.paragraph_format.space_before = Pt(14)
            p.paragraph_format.space_after = Pt(4)
            p.paragraph_format.keep_with_next = True
            parse_and_add_text(p, h1_text, base_font_size=14, is_bold=True, base_color=NAVY_PRIMARY)
            idx += 1
            continue

        # Heading 2 (### Heading)
        if stripped.startswith('### ') and not stripped.startswith('#### '):
            h2_text = stripped[4:].strip()
            p = doc.add_paragraph()
            p.paragraph_format.space_before = Pt(10)
            p.paragraph_format.space_after = Pt(3)
            p.paragraph_format.keep_with_next = True
            parse_and_add_text(p, h2_text, base_font_size=12, is_bold=True, base_color=BLUE_ACCENT)
            idx += 1
            continue

        # Heading 3 (#### Heading)
        if stripped.startswith('#### '):
            h3_text = stripped[5:].strip()
            p = doc.add_paragraph()
            p.paragraph_format.space_before = Pt(8)
            p.paragraph_format.space_after = Pt(2)
            p.paragraph_format.keep_with_next = True
            parse_and_add_text(p, h3_text, base_font_size=10.5, is_bold=True, base_color=SLATE_DARK)
            idx += 1
            continue

        # Bullet List Items (- or * item)
        if stripped.startswith('- ') or stripped.startswith('* '):
            bullet_text = stripped[2:].strip()
            p = doc.add_paragraph(style='List Bullet')
            p.paragraph_format.space_before = Pt(1)
            p.paragraph_format.space_after = Pt(2)
            p.paragraph_format.line_spacing = 1.15
            parse_and_add_text(p, bullet_text, base_font_size=10, base_color=BODY_TEXT)
            idx += 1
            continue

        # Numbered List Items (1. item) - Handled with explicit hanging indent to prevent continuous global accumulation
        num_match = re.match(r'^(\d+)\.\s+(.*)$', stripped)
        if num_match:
            num_str = num_match.group(1)
            item_text = num_match.group(2)
            p = doc.add_paragraph()
            p.paragraph_format.left_indent = Inches(0.28)
            p.paragraph_format.first_line_indent = Inches(-0.28)
            p.paragraph_format.space_before = Pt(1.5)
            p.paragraph_format.space_after = Pt(2.5)
            p.paragraph_format.line_spacing = 1.15

            r_num = p.add_run(f"{num_str}. ")
            r_num.font.name = 'Arial'
            r_num.font.size = Pt(10)
            r_num.font.bold = True
            r_num.font.color.rgb = NAVY_PRIMARY

            parse_and_add_text(p, item_text, base_font_size=10, base_color=BODY_TEXT)
            idx += 1
            continue

        # Regular Paragraph
        p = doc.add_paragraph()
        p.paragraph_format.space_before = Pt(2)
        p.paragraph_format.space_after = Pt(4)
        p.paragraph_format.line_spacing = 1.15
        parse_and_add_text(p, stripped, base_font_size=10, base_color=BODY_TEXT)
        idx += 1

    # Cleanup remaining open blocks
    if in_code_block:
        flush_code_block()
    if in_table:
        flush_table()
    if in_blockquote:
        flush_blockquote()

    doc.save(docx_path)
    print(f"Successfully generated Google Docs (.docx): {docx_path}")

if __name__ == '__main__':
    project_root = '/home/mosud/Documents/dev/HVAC-iot-monitoring'
    md_file = os.path.join(project_root, 'docs', 'system_overview_and_component_specification.md')
    docx_file = os.path.join(project_root, 'docs', 'system_overview_and_component_specification.docx')
    foundational_docx = os.path.join(project_root, 'foundational_document', 'system_overview_and_component_specification.docx')

    convert_markdown_to_google_doc(md_file, docx_file)
    
    # Also copy to foundational_document
    import shutil
    shutil.copy2(docx_file, foundational_docx)
    print(f"Successfully mirrored to: {foundational_docx}")
