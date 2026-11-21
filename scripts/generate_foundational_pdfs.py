#!/usr/bin/env python3
"""
Publication-Grade PDF Generator for Foundational Documents
Software-Defined Vehicle (SDV) Cabin Environmental Monitoring & Automotive IoT Middleware
Technical Engineering Reference & Specification Compilation Suite

Transforms Markdown specifications into publication-grade A4 PDF documents using
Python-Markdown, LaTeX-to-MathML mathematical typesetting, and headless Google Chrome.
"""

import os
import re
import subprocess
import sys
import markdown
from latex2mathml.converter import convert

BASE_DIR = "/home/mosud/Documents/dev/HVAC-iot-monitoring"
FOUNDATIONAL_DIR = os.path.join(BASE_DIR, "foundational_document")
SCRATCH_DIR = "/home/mosud/.gemini/antigravity-ide/brain/7055d389-5e73-4385-aad0-2e13a4535482/scratch"

os.makedirs(SCRATCH_DIR, exist_ok=True)
os.makedirs(FOUNDATIONAL_DIR, exist_ok=True)


def convert_github_alerts(md_text: str) -> str:
    """Converts GitHub alert syntax (> [!NOTE], etc.) into styled HTML callout containers."""
    alert_types = {
        "NOTE": {"class": "callout-note", "title": "NOTE", "color": "#0284c7", "icon": "ℹ"},
        "IMPORTANT": {"class": "callout-important", "title": "IMPORTANT", "color": "#7c3aed", "icon": "★"},
        "WARNING": {"class": "callout-warning", "title": "WARNING", "color": "#d97706", "icon": "⚠"},
        "TIP": {"class": "callout-tip", "title": "TIP", "color": "#059669", "icon": "✔"},
        "CAUTION": {"class": "callout-caution", "title": "CAUTION", "color": "#dc2626", "icon": "⛔"},
    }

    lines = md_text.split("\n")
    output_lines = []
    in_alert = False
    current_alert = None
    alert_content = []

    for line in lines:
        match = re.match(r"^>\s*\[!(NOTE|IMPORTANT|WARNING|TIP|CAUTION)\]\s*$", line)
        if match:
            if in_alert:
                cfg = alert_types[current_alert]
                rendered = markdown.markdown("\n".join(alert_content), extensions=["tables", "fenced_code"])
                output_lines.append(f'<div class="callout {cfg["class"]}"><div class="callout-header"><span class="callout-icon">{cfg["icon"]}</span> <strong>{cfg["title"]}</strong></div>{rendered}</div>')
                alert_content = []
            in_alert = True
            current_alert = match.group(1)
            continue

        if in_alert:
            if line.startswith(">"):
                content_line = line[1:].lstrip()
                alert_content.append(content_line)
            else:
                cfg = alert_types[current_alert]
                rendered = markdown.markdown("\n".join(alert_content), extensions=["tables", "fenced_code"])
                output_lines.append(f'<div class="callout {cfg["class"]}"><div class="callout-header"><span class="callout-icon">{cfg["icon"]}</span> <strong>{cfg["title"]}</strong></div>{rendered}</div>')
                in_alert = False
                current_alert = None
                alert_content = []
                output_lines.append(line)
        else:
            output_lines.append(line)

    if in_alert and current_alert:
        cfg = alert_types[current_alert]
        rendered = markdown.markdown("\n".join(alert_content), extensions=["tables", "fenced_code"])
        output_lines.append(f'<div class="callout {cfg["class"]}"><div class="callout-header"><span class="callout-icon">{cfg["icon"]}</span> <strong>{cfg["title"]}</strong></div>{rendered}</div>')

    return "\n".join(output_lines)


def clean_fallback_math(latex: str) -> str:
    """Fallback text cleaner for basic mathematical notation."""
    replacements = [
        (r"\tau", "τ"),
        (r"\Delta", "Δ"),
        (r"\le", "≤"),
        (r"\ge", "≥"),
        (r"\approx", "≈"),
        (r"\implies", "⟹"),
        (r"\iff", "⟺"),
        (r"\lor", "∨"),
        (r"\land", "∧"),
        (r"\pm", "±"),
        (r"^\circ\text{C}", "°C"),
        (r"\text{C}", "C"),
        (r"\text{s}", "s"),
        (r"\text{ppm}", "ppm"),
        (r"\text{null}", "null"),
        (r"\text{FRESH}", "FRESH"),
        (r"\text{STALE}", "STALE"),
        (r"\text{DEGRADED}", "DEGRADED"),
        (r"\text{FAULT}", "FAULT"),
        (r"\,", " "),
    ]
    res = latex
    for pat, rep in replacements:
        res = res.replace(pat, rep)
    return res


def postprocess_mathml(mathml: str) -> str:
    """
    Enhances MathML output for publication-grade typographic spacing and correct semantic operators.
    """
    # 1. Format implication and equivalence arrows as relational operators with explicit spacing
    mathml = re.sub(r'<mi>(&#x027F9;|&#x027FA;)</mi>', r'<mo lspace="0.35em" rspace="0.35em">\1</mo>', mathml)
    # 2. Format single arrows (\to, \rightarrow, \Rightarrow) with proper spacing
    mathml = re.sub(r'<mo>(&#x02192;|&#x021D2;)</mo>', r'<mo lspace="0.3em" rspace="0.3em">\1</mo>', mathml)
    # 3. Format logical connectives (\lor, \land) with clean operator spacing
    mathml = re.sub(r'<mo>(&#x02228;|&#x02227;)</mo>', r'<mo lspace="0.28em" rspace="0.28em">\1</mo>', mathml)
    # 4. Remove unwanted extra space around negative unary minus when preceded by relational operator
    mathml = re.sub(r'(<mo>&#x0003C;|</mo>)\s*<mo>&#x02212;</mo>\s*<mn>', r'\1<mo form="prefix" rspace="0.05em">&#x02212;</mo><mn>', mathml)
    return mathml


def clean_latex_input(latex: str) -> str:
    """Pre-processes LaTeX to handle escaped characters, digit separators, and text blocks."""
    # Normalize escaped underscores inside text/subscript
    latex = latex.replace(r'\_', '_')
    return latex


def render_math_to_mathml(text: str) -> str:
    """
    Converts LaTeX mathematical equations ($...$ and $$...$$) into standard MathML Core tags.
    Protects fenced code blocks and inline code spans to prevent accidental conversion.
    """
    code_blocks = []
    def save_code(match):
        code_blocks.append(match.group(0))
        return f"___CODE_BLOCK_{len(code_blocks)-1}___"

    # Protect code blocks and inline code spans
    text = re.sub(r'```[\s\S]*?```', save_code, text)
    text = re.sub(r'`[^`\n]+`', save_code, text)

    # 1. Block equations: $$...$$
    def replace_block_math(match):
        latex = clean_latex_input(match.group(1).strip())
        try:
            mathml = convert(latex, display="block")
            mathml = postprocess_mathml(mathml)
            return f'\n\n<div class="math-block">{mathml}</div>\n\n'
        except Exception:
            fallback = clean_fallback_math(latex)
            return f'\n\n<div class="math-block"><code class="math-fallback">{fallback}</code></div>\n\n'

    text = re.sub(r'\$\$([\s\S]*?)\$\$', replace_block_math, text)

    # 2. Inline equations: $...$
    def replace_inline_math(match):
        latex = clean_latex_input(match.group(1).strip())
        try:
            mathml = convert(latex, display="inline")
            mathml = postprocess_mathml(mathml)
            return mathml
        except Exception:
            fallback = clean_fallback_math(latex)
            return f'<span class="math-inline">{fallback}</span>'

    text = re.sub(r'(?<!\$)\$(?!\$)([^\$\n]+?)(?<!\$)\$(?!\$)', replace_inline_math, text)

    # Restore code blocks
    for i, cb in enumerate(code_blocks):
        text = text.replace(f"___CODE_BLOCK_{i}___", cb)

    return text


def strip_institutional_sanctions(text: str) -> str:
    """
    Strips institutional affiliations, department sanctions, addresses, and university logos
    to ensure documents are presented purely as independent technical engineering specifications.
    """
    lines = text.split("\n")
    filtered_lines = []

    for line in lines:
        if "FH TECHNIKUM WIEN" in line or "TECHNIKUM WIEN" in line:
            continue
        if "DEPARTMENT OF ELECTRONIC ENGINEERING" in line or "Department of Electronic Engineering" in line:
            continue
        if "Research Cluster:" in line and ("Automotive IoT" in line or "Distributed Cyber-Physical" in line):
            continue
        if re.match(r"^\s*\*\*(?:Academic\s+)?Affiliation:\*\*\s+.*(?:Technikum|University).*", line, re.I):
            continue
        if re.match(r"^\s*\*\*Research Cluster:\*\*\s+.*", line, re.I):
            continue
        if "technikum-wien.at" in line:
            continue
        if "Höchstädtplatz" in line:
            continue
        if "Automotive IoT Research Cluster at the University" in line:
            continue
        if line.strip().startswith("**Academic Institution:**"):
            continue

        filtered_lines.append(line)

    sanitized = "\n".join(filtered_lines)

    # Replace document ID prefix FHTW-SDV with SDV
    sanitized = re.sub(r"\bFHTW-SDV-", "SDV-", sanitized)

    # Replace FHTW AIOT Root CA with SDV Automotive Root CA
    sanitized = sanitized.replace("FHTW AIOT Root CA", "SDV Automotive Edge Root CA")
    sanitized = sanitized.replace("FHTW-AIOT", "SDV-AIOT")

    return sanitized


def build_html_document(title: str, doc_id: str, doc_status: str, html_body: str) -> str:
    """Wraps body in clean, publication-grade technical engineering styling."""
    return f"""<!DOCTYPE html>
<html lang="en-GB">
<head>
<meta charset="UTF-8">
<title>{title}</title>
<style>
  @page {{
    size: A4 portrait;
    margin: 14mm 15mm 14mm 15mm;
    @top-right {{
      content: "{doc_id}";
      font-size: 7.2pt;
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
      color: #64748b;
    }}
    @bottom-center {{
      content: "Page " counter(page) " of " counter(pages);
      font-size: 7.5pt;
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
      color: #64748b;
    }}
  }}

  * {{
    box-sizing: border-box;
    margin: 0;
    padding: 0;
  }}

  body {{
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
    color: #1e293b;
    background-color: #ffffff;
    font-size: 8.5pt;
    line-height: 1.45;
    -webkit-print-color-adjust: exact;
    print-color-adjust: exact;
  }}

  /* Clean engineering project header (no university/department branding) */
  .project-header {{
    width: 100%;
    border-bottom: 2px solid #0284c7;
    padding-bottom: 5px;
    margin-bottom: 11px;
    display: flex;
    justify-content: space-between;
    align-items: center;
  }}

  .project-title-bar {{
    font-size: 7.5pt;
    font-weight: 700;
    color: #0369a1;
    text-transform: uppercase;
    letter-spacing: 0.04em;
  }}

  .spec-bar {{
    font-size: 7.2pt;
    color: #475569;
  }}

  .doc-hero {{
    background: linear-gradient(135deg, #0f172a 0%, #1e293b 100%);
    color: #ffffff;
    padding: 11px 15px;
    border-radius: 6px;
    margin-bottom: 13px;
    border-left: 4px solid #0284c7;
  }}

  .doc-hero h1 {{
    font-size: 13.5pt;
    font-weight: 800;
    color: #ffffff;
    line-height: 1.25;
    margin-bottom: 4px;
  }}

  .doc-hero .doc-meta-row {{
    display: flex;
    flex-wrap: wrap;
    gap: 14px;
    font-size: 7.2pt;
    color: #94a3b8;
    margin-top: 6px;
    border-top: 1px solid #334155;
    padding-top: 5px;
  }}

  .doc-meta-row span strong {{
    color: #e2e8f0;
  }}

  /* Headings */
  h1 {{
    font-size: 12.5pt;
    font-weight: 800;
    color: #0f172a;
    margin-top: 13px;
    margin-bottom: 6px;
    page-break-after: avoid;
  }}

  h2 {{
    font-size: 9.8pt;
    font-weight: 700;
    color: #0f172a;
    border-bottom: 1.2px solid #cbd5e1;
    padding-bottom: 2.5px;
    margin-top: 11px;
    margin-bottom: 5px;
    text-transform: uppercase;
    letter-spacing: 0.03em;
    page-break-after: avoid;
  }}

  h3 {{
    font-size: 8.8pt;
    font-weight: 700;
    color: #0284c7;
    margin-top: 8px;
    margin-bottom: 4px;
    page-break-after: avoid;
  }}

  h4 {{
    font-size: 8.2pt;
    font-weight: 700;
    color: #334155;
    margin-top: 6px;
    margin-bottom: 3px;
    page-break-after: avoid;
  }}

  p {{
    margin-bottom: 5px;
    text-align: justify;
  }}

  ul, ol {{
    margin-left: 16px;
    margin-bottom: 5px;
  }}

  li {{
    margin-bottom: 2px;
  }}

  /* Mathematical typesetting (MathML Core) */
  math {{
    font-family: "Latin Modern Math", "DejaVu Math TeX Gyre", "STIX Two Math", "Cambria Math", serif;
    font-size: 1.05em;
    vertical-align: middle;
  }}

  math[display="inline"] {{
    display: inline-math;
    padding: 0 1px;
  }}

  .math-block {{
    display: block;
    text-align: center;
    margin: 10px 0;
    padding: 9px 14px;
    background-color: #f8fafc;
    border-radius: 6px;
    border: 1px solid #e2e8f0;
    page-break-inside: avoid;
    overflow-x: auto;
  }}

  .math-block math[display="block"] {{
    display: inline-block;
    font-size: 1.18em;
  }}

  /* Tables: allow table to split across pages cleanly, but repeat header and avoid split inside row */
  table {{
    width: 100%;
    border-collapse: collapse;
    margin: 6px 0 9px 0;
    font-size: 7.3pt;
  }}

  thead {{
    display: table-header-group;
  }}

  tr {{
    page-break-inside: avoid;
  }}

  th, td {{
    border: 1px solid #cbd5e1;
    padding: 3.5px 5.5px;
    text-align: left;
    vertical-align: top;
  }}

  th {{
    background-color: #0f172a;
    color: #ffffff;
    font-weight: 700;
    font-size: 7pt;
    text-transform: uppercase;
    letter-spacing: 0.02em;
  }}

  tr:nth-child(even) td {{
    background-color: #f8fafc;
  }}

  /* Code blocks & preformatted */
  pre {{
    background-color: #0f172a;
    color: #f8fafc;
    border: 1px solid #1e293b;
    border-radius: 4px;
    padding: 6px 8px;
    font-family: "JetBrains Mono", "SFMono-Regular", Menlo, Monaco, Consolas, "Liberation Mono", monospace;
    font-size: 7pt;
    line-height: 1.35;
    margin: 5px 0 7px 0;
    overflow-x: hidden;
    white-space: pre-wrap;
    word-break: break-all;
    page-break-inside: avoid;
  }}

  code {{
    font-family: "JetBrains Mono", "SFMono-Regular", Menlo, Monaco, Consolas, "Liberation Mono", monospace;
    font-size: 7.4pt;
    background-color: #f1f5f9;
    color: #0f172a;
    padding: 1px 3px;
    border-radius: 3px;
    border: 1px solid #e2e8f0;
  }}

  pre code {{
    background-color: transparent;
    color: inherit;
    border: none;
    padding: 0;
    font-size: 7pt;
  }}

  /* Callouts */
  .callout {{
    border-left: 3.5px solid #0284c7;
    background-color: #f0f9ff;
    padding: 5px 8px;
    margin: 6px 0;
    font-size: 7.8pt;
    border-radius: 0 4px 4px 0;
    page-break-inside: avoid;
  }}

  .callout-header {{
    font-size: 7.6pt;
    font-weight: 700;
    margin-bottom: 2.5px;
    display: flex;
    align-items: center;
    gap: 4px;
  }}

  .callout-note {{
    border-left-color: #0284c7;
    background-color: #f0f9ff;
    color: #0369a1;
  }}

  .callout-important {{
    border-left-color: #7c3aed;
    background-color: #f5f3ff;
    color: #6d28d9;
  }}

  .callout-warning {{
    border-left-color: #d97706;
    background-color: #fffbeb;
    color: #b45309;
  }}

  .callout-tip {{
    border-left-color: #059669;
    background-color: #ecfdf5;
    color: #047857;
  }}

  .callout-caution {{
    border-left-color: #dc2626;
    background-color: #fef2f2;
    color: #b91c1c;
  }}

  .callout p {{
    color: #1e293b;
    margin-bottom: 2.5px;
  }}

  .callout ul {{
    color: #1e293b;
    margin-left: 14px;
    margin-bottom: 2.5px;
  }}

  /* Horizontal rule */
  hr {{
    border: none;
    border-top: 1px solid #e2e8f0;
    margin: 8px 0;
  }}

  /* Document Footer */
  .running-footer {{
    margin-top: 14px;
    border-top: 1.2px solid #cbd5e1;
    padding-top: 5px;
    display: flex;
    justify-content: space-between;
    font-size: 6.8pt;
    color: #64748b;
    page-break-inside: avoid;
  }}
</style>
</head>
<body>

<div class="project-header">
  <div class="project-title-bar">Software-Defined Vehicle (SDV) &bull; Edge Middleware Engineering</div>
  <div class="spec-bar">Standard Conformance: ETSI TS 118 101 Rel 4 / oneM2M Rel 4</div>
</div>

<div class="doc-hero">
  <h1>{title}</h1>
  <div class="doc-meta-row">
    <span><strong>Doc ID:</strong> {doc_id}</span>
    <span><strong>Status:</strong> {doc_status}</span>
    <span><strong>Standard:</strong> oneM2M TS-0001, TS-0004, TS-0010</span>
    <span><strong>Security:</strong> RFC 8446 (TLS 1.3 mTLS)</span>
  </div>
</div>

{html_body}

<div class="running-footer">
  <div>{doc_id} &bull; Technical Specification</div>
  <div>Software-Defined Vehicle (SDV) IoT HVAC &amp; Edge Middleware</div>
  <div>Open Technical Reference</div>
</div>

</body>
</html>
"""


def compile_md_to_pdf(input_md_path: str, output_pdf_path: str, doc_id: str, doc_status: str = "Approved Technical Specification") -> bool:
    """Renders a single Markdown file to publication-grade PDF via Chrome with MathML rendering."""
    if not os.path.exists(input_md_path):
        print(f"[ERROR] Input markdown file does not exist: {input_md_path}")
        return False

    with open(input_md_path, "r", encoding="utf-8") as f:
        md_content = f.read()

    # Extract title from first H1
    title_match = re.search(r"^#\s+(.+)$", md_content, re.MULTILINE)
    title = title_match.group(1).strip() if title_match else os.path.basename(input_md_path).replace(".md", "").replace("_", " ").title()

    # Remove the first H1 if present so it doesn't duplicate our hero block
    if title_match:
        md_content = md_content[:title_match.start()] + md_content[title_match.end():]

    # Pre-process pipeline:
    # 1. Strip institutional sanction claims
    processed_md = strip_institutional_sanctions(md_content)
    # 2. Render LaTeX mathematical equations ($ and $$) into native MathML
    processed_md = render_math_to_mathml(processed_md)
    # 3. Convert GitHub alerts into styled callout HTML blocks
    processed_md = convert_github_alerts(processed_md)

    # Convert markdown to HTML
    html_body = markdown.markdown(
        processed_md,
        extensions=[
            "tables",
            "fenced_code",
            "attr_list",
            "def_list",
            "sane_lists"
        ]
    )

    full_html = build_html_document(title, doc_id, doc_status, html_body)

    scratch_html_path = os.path.join(SCRATCH_DIR, os.path.basename(input_md_path).replace(".md", ".html"))
    with open(scratch_html_path, "w", encoding="utf-8") as f:
        f.write(full_html)

    # Compile with Headless Chrome
    chrome_cmd = [
        "google-chrome",
        "--headless",
        "--disable-gpu",
        "--no-sandbox",
        "--no-pdf-header-footer",
        f"--print-to-pdf={output_pdf_path}",
        scratch_html_path
    ]

    res = subprocess.run(chrome_cmd, capture_output=True, text=True)
    if res.returncode == 0 and os.path.exists(output_pdf_path):
        size_kb = os.path.getsize(output_pdf_path) / 1024
        print(f"[SUCCESS] Generated: {output_pdf_path} ({size_kb:.1f} KB)")
        return True
    else:
        print(f"[ERROR] Failed to generate {output_pdf_path}: {res.stderr}")
        return False


def main():
    print("=" * 80)
    print("  FOUNDATIONAL DOCUMENTS: PUBLICATION-GRADE PDF COMPILATION SUITE")
    print("  Software-Defined Vehicle (SDV) Automotive IoT Edge Middleware")
    print("=" * 80)

    documents = [
        {
            "md": os.path.join(FOUNDATIONAL_DIR, "acme_cse_cheat_sheet.md"),
            "pdf": os.path.join(FOUNDATIONAL_DIR, "acme_cse_cheat_sheet.pdf"),
            "doc_id": "REF-ACME-CSE-2026-01",
            "status": "Canonical Reference Guide"
        },
        {
            "md": os.path.join(FOUNDATIONAL_DIR, "system_architecture_and_pipeline_specification.md"),
            "pdf": os.path.join(FOUNDATIONAL_DIR, "system_architecture_and_pipeline_specification.pdf"),
            "doc_id": "SDV-ARCH-005",
            "status": "Approved Engineering Specification"
        },
        {
            "md": os.path.join(FOUNDATIONAL_DIR, "security_pki_and_data_health_specification.md"),
            "pdf": os.path.join(FOUNDATIONAL_DIR, "security_pki_and_data_health_specification.pdf"),
            "doc_id": "SDV-SEC-001",
            "status": "Approved Engineering Specification"
        },
        {
            "md": os.path.join(FOUNDATIONAL_DIR, "system_validation_and_benchmarking_report.md"),
            "pdf": os.path.join(FOUNDATIONAL_DIR, "system_validation_and_benchmarking_report.pdf"),
            "doc_id": "SDV-TEST-002",
            "status": "Approved Engineering Verification Report"
        },
        {
            "md": os.path.join(FOUNDATIONAL_DIR, "target_hardware_transition_deployment_guide.md"),
            "pdf": os.path.join(FOUNDATIONAL_DIR, "target_hardware_transition_deployment_guide.pdf"),
            "doc_id": "SDV-DEPL-003",
            "status": "Production Deployment Guide"
        },
        {
            "md": os.path.join(FOUNDATIONAL_DIR, "mvp_implementation_plan.md"),
            "pdf": os.path.join(FOUNDATIONAL_DIR, "mvp_implementation_plan.pdf"),
            "doc_id": "SDV-PLAN-001",
            "status": "Engineering Architecture Plan"
        },
        {
            "md": os.path.join(FOUNDATIONAL_DIR, "project_directory_and_file_structure.md"),
            "pdf": os.path.join(FOUNDATIONAL_DIR, "project_directory_and_file_structure.pdf"),
            "doc_id": "SDV-STRUCT-001",
            "status": "Repository Topology Specification"
        },
        {
            "md": os.path.join(FOUNDATIONAL_DIR, "acme_cse_gateway_capability_review.md"),
            "pdf": os.path.join(FOUNDATIONAL_DIR, "acme_cse_gateway_capability_review.pdf"),
            "doc_id": "SDV-REV-001",
            "status": "Architectural Gap Analysis & Capability Review"
        },
        {
            "md": os.path.join(FOUNDATIONAL_DIR, "onem2m_cabinnode_car01_registration_guide.md"),
            "pdf": os.path.join(FOUNDATIONAL_DIR, "onem2m_cabinnode_car01_registration_guide.pdf"),
            "doc_id": "SDV-REG-001",
            "status": "oneM2M AE Registration Guide: CabinNode"
        },
        {
            "md": os.path.join(FOUNDATIONAL_DIR, "onem2m_nodered_ingress_ipe_registration_guide.md"),
            "pdf": os.path.join(FOUNDATIONAL_DIR, "onem2m_nodered_ingress_ipe_registration_guide.pdf"),
            "doc_id": "SDV-REG-002",
            "status": "oneM2M IPE Registration Guide: Node-RED"
        },
        {
            "md": os.path.join(FOUNDATIONAL_DIR, "onem2m_python_bridge_ae_registration_guide.md"),
            "pdf": os.path.join(FOUNDATIONAL_DIR, "onem2m_python_bridge_ae_registration_guide.pdf"),
            "doc_id": "SDV-REG-003",
            "status": "oneM2M AE Registration Guide: Python Bridge"
        },
        {
            "md": os.path.join(FOUNDATIONAL_DIR, "onem2m_service_role_classification_and_topology.md"),
            "pdf": os.path.join(FOUNDATIONAL_DIR, "onem2m_service_role_classification_and_topology.pdf"),
            "doc_id": "SDV-TOPO-001",
            "status": "oneM2M Service Role & Topology Guide"
        }
    ]

    success_count = 0
    for doc in documents:
        print(f"\nCompiling: {os.path.basename(doc['md'])} -> {os.path.basename(doc['pdf'])}...")
        if compile_md_to_pdf(doc["md"], doc["pdf"], doc["doc_id"], doc["status"]):
            success_count += 1

    # Also generate a consolidated architectural dossier merging the 3 migrated specifications
    print("\nGenerating Consolidated Architecture, Security, & Validation Dossier...")
    consolidated_md_path = os.path.join(SCRATCH_DIR, "consolidated_dossier.md")
    consolidated_pdf_path = os.path.join(FOUNDATIONAL_DIR, "system_architecture_security_and_validation_dossier.pdf")

    specs = [
        os.path.join(FOUNDATIONAL_DIR, "system_architecture_and_pipeline_specification.md"),
        os.path.join(FOUNDATIONAL_DIR, "security_pki_and_data_health_specification.md"),
        os.path.join(FOUNDATIONAL_DIR, "system_validation_and_benchmarking_report.md")
    ]

    with open(consolidated_md_path, "w", encoding="utf-8") as out:
        out.write("# System Architecture, Security PKI, and Validation Benchmark Dossier\n\n")
        out.write("**Comprehensive Engineering Dossier for Software-Defined Vehicle (SDV) Cabin Environmental Monitoring**\n\n---\n\n")
        for spec in specs:
            if os.path.exists(spec):
                with open(spec, "r", encoding="utf-8") as s_in:
                    content = s_in.read()
                    out.write(content)
                    out.write("\n\n<div style='page-break-before: always;'></div>\n\n---\n\n")

    if compile_md_to_pdf(consolidated_md_path, consolidated_pdf_path, "SDV-DOSSIER-2026", "Consolidated Technical Dossier"):
        success_count += 1

    print("\n" + "=" * 80)
    print(f"  COMPILATION COMPLETE: {success_count}/{len(documents) + 1} PDFs Generated Successfully!")
    print("=" * 80)


if __name__ == "__main__":
    main()
