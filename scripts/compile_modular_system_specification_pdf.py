#!/usr/bin/env python3
"""
Publication-Grade PDF Generator for Modular System Design Specification
Software-Defined Vehicle (SDV) Cabin Environmental Monitoring & Automotive IoT Middleware
Compiles: docs/architecture/modular_system_design_specification.md -> modular_system_design_specification.pdf
"""

import os
import re
import subprocess
import sys
import shutil
import markdown
from latex2mathml.converter import convert

BASE_DIR = "/home/mosud/Documents/dev/HVAC-iot-monitoring"
DOCS_ARCH_DIR = os.path.join(BASE_DIR, "docs", "architecture")
FOUNDATIONAL_DIR = os.path.join(BASE_DIR, "foundational_document")
ASSETS_DIR = os.path.join(BASE_DIR, "docs", "assets")
SCRATCH_DIR = "/home/mosud/.gemini/antigravity-ide/brain/7055d389-5e73-4385-aad0-2e13a4535482/scratch"

os.makedirs(SCRATCH_DIR, exist_ok=True)
os.makedirs(ASSETS_DIR, exist_ok=True)
os.makedirs(FOUNDATIONAL_DIR, exist_ok=True)

INPUT_MD = os.path.join(DOCS_ARCH_DIR, "modular_system_design_specification.md")
OUTPUT_PDF_ARCH = os.path.join(DOCS_ARCH_DIR, "modular_system_design_specification.pdf")
OUTPUT_PDF_FOUND = os.path.join(FOUNDATIONAL_DIR, "modular_system_design_specification.pdf")


def convert_mermaid_diagrams_to_svg(md_text: str) -> str:
    """Detects ```mermaid blocks, converts them to SVG using mmdc, and inlines the SVG."""
    mermaid_blocks = re.findall(r"```mermaid\s*([\s\S]*?)```", md_text)
    if not mermaid_blocks:
        return md_text

    mmdc_path = shutil.which("mmdc") or "/snap/bin/mmdc"
    if not os.path.exists(mmdc_path):
        print(f"[WARN] mmdc not found at {mmdc_path}. Preserving code blocks.")
        return md_text

    for i, diagram_code in enumerate(mermaid_blocks):
        tmp_mmd = os.path.join(ASSETS_DIR, f"temp_diag_{i}.mmd")
        tmp_svg = os.path.join(ASSETS_DIR, f"temp_diag_{i}.svg")
        
        with open(tmp_mmd, "w", encoding="utf-8") as f:
            f.write(diagram_code.strip())
            
        cfg_path = os.path.join(ASSETS_DIR, f"temp_cfg_{i}.json")
        with open(cfg_path, "w", encoding="utf-8") as f:
            f.write(
                '{"theme": "neutral", "themeVariables": {"fontSize": "11px", "fontFamily": "Liberation Sans, Arial, sans-serif"}, '
                '"flowchart": {"htmlLabels": false, "useMaxWidth": true, "nodeSpacing": 35, "rankSpacing": 35}}'
            )

        cmd = [
            mmdc_path,
            "-i", tmp_mmd,
            "-o", tmp_svg,
            "-c", cfg_path,
            "-w", "1200",
            "-b", "transparent"
        ]
        res = subprocess.run(cmd, capture_output=True, text=True)
        if os.path.exists(cfg_path):
            os.remove(cfg_path)
        if res.returncode == 0 and os.path.exists(tmp_svg):
            with open(tmp_svg, "r", encoding="utf-8") as f:
                svg_content = f.read()
            
            # Clean up svg headers if any
            svg_content = re.sub(r'<\?xml[^>]*\?>', '', svg_content)
            # Wrap in responsive container
            wrapped_svg = f'<div class="mermaid-diagram-container" style="text-align: center; margin: 12px 0;">{svg_content}</div>'
            md_text = md_text.replace(f"```mermaid\n{diagram_code}```", wrapped_svg)
            md_text = md_text.replace(f"```mermaid\r\n{diagram_code}```", wrapped_svg)
            md_text = md_text.replace(f"```mermaid{diagram_code}```", wrapped_svg)
            
            # Remove temp files
            os.remove(tmp_mmd)
            os.remove(tmp_svg)
            print(f"[INFO] Rendered Mermaid diagram {i+1} to SVG.")
        else:
            print(f"[WARN] Failed to render Mermaid diagram {i+1}: {res.stderr}")
            if os.path.exists(tmp_mmd):
                os.remove(tmp_mmd)

    return md_text


def convert_github_alerts(md_text: str) -> str:
    """Converts GitHub alert syntax (> [!NOTE], etc.) into styled HTML callouts."""
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


def postprocess_mathml(mathml: str) -> str:
    """Enhances MathML spacing and operators."""
    mathml = re.sub(r'<mi>(&#x027F9;|&#x027FA;)</mi>', r'<mo lspace="0.35em" rspace="0.35em">\1</mo>', mathml)
    mathml = re.sub(r'<mo>(&#x02192;|&#x021D2;)</mo>', r'<mo lspace="0.3em" rspace="0.3em">\1</mo>', mathml)
    mathml = re.sub(r'<mo>(&#x02228;|&#x02227;)</mo>', r'<mo lspace="0.28em" rspace="0.28em">\1</mo>', mathml)
    mathml = re.sub(r'(<mo>&#x0003C;|</mo>)\s*<mo>&#x02212;</mo>\s*<mn>', r'\1<mo form="prefix" rspace="0.05em">&#x02212;</mo><mn>', mathml)
    return mathml


def clean_latex_input(latex: str) -> str:
    """Pre-processes LaTeX syntax."""
    latex = latex.replace(r'\_', '_')
    return latex


def render_math_to_mathml(text: str) -> str:
    """Converts LaTeX mathematical equations into native MathML tags."""
    code_blocks = []
    def save_code(match):
        code_blocks.append(match.group(0))
        return f"___CODE_BLOCK_{len(code_blocks)-1}___"

    text = re.sub(r'```[\s\S]*?```', save_code, text)
    text = re.sub(r'`[^`\n]+`', save_code, text)

    # 1. Block math: $$...$$
    def replace_block_math(match):
        latex = clean_latex_input(match.group(1).strip())
        try:
            mathml = convert(latex, display="block")
            mathml = postprocess_mathml(mathml)
            return f'\n\n<div class="math-block">{mathml}</div>\n\n'
        except Exception as e:
            return f'\n\n<div class="math-block"><code class="math-fallback">{latex}</code></div>\n\n'

    text = re.sub(r'\$\$([\s\S]*?)\$\$', replace_block_math, text)

    # 2. Inline math: $...$
    def replace_inline_math(match):
        latex = clean_latex_input(match.group(1).strip())
        try:
            mathml = convert(latex, display="inline")
            mathml = postprocess_mathml(mathml)
            return mathml
        except Exception as e:
            return f'<span class="math-inline">{latex}</span>'

    text = re.sub(r'(?<!\$)\$(?!\$)([^\$\n]+?)(?<!\$)\$(?!\$)', replace_inline_math, text)

    # Restore code blocks
    for i, cb in enumerate(code_blocks):
        text = text.replace(f"___CODE_BLOCK_{i}___", cb)

    return text


def strip_institutional_sanctions(text: str) -> str:
    """Strips institutional affiliation headers to ensure an independent technical reference."""
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
        if "technikum-wien.at" in line or "Höchstädtplatz" in line:
            continue
        if line.strip().startswith("**Academic Institution:**"):
            continue

        filtered_lines.append(line)

    sanitized = "\n".join(filtered_lines)
    sanitized = re.sub(r"\bFHTW-SDV-", "SDV-", sanitized)
    sanitized = sanitized.replace("FHTW AIOT Root CA", "SDV Automotive Edge Root CA")
    sanitized = sanitized.replace("FHTW-AIOT", "SDV-AIOT")
    return sanitized


def build_html_document(title: str, doc_id: str, doc_status: str, html_body: str) -> str:
    """Wraps body in publication-grade technical styling."""
    return f"""<!DOCTYPE html>
<html lang="en-GB">
<head>
<meta charset="UTF-8">
<title>{title}</title>
<style>
  @page {{
    size: A4 portrait;
    margin: 13mm 14mm 13mm 14mm;
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
    margin-bottom: 6px;
    text-align: justify;
  }}

  ul, ol {{
    margin-left: 18px;
    margin-bottom: 7px;
  }}

  li {{
    margin-bottom: 2.5px;
  }}

  code {{
    font-family: "JetBrains Mono", "Fira Code", "Courier New", monospace;
    font-size: 7.6pt;
    background-color: #f1f5f9;
    color: #0f172a;
    padding: 1px 3.5px;
    border-radius: 3px;
    border: 1px solid #e2e8f0;
  }}

  pre {{
    background-color: #0f172a;
    color: #f8fafc;
    padding: 8px 10px;
    border-radius: 5px;
    margin: 7px 0;
    font-family: "JetBrains Mono", "Fira Code", monospace;
    font-size: 7.2pt;
    line-height: 1.35;
    overflow-x: hidden;
    white-space: pre-wrap;
    word-break: break-all;
    border-left: 3px solid #38bdf8;
    page-break-inside: avoid;
  }}

  pre code {{
    background-color: transparent;
    color: #f8fafc;
    padding: 0;
    border: none;
    font-size: 7.2pt;
  }}

  /* MathML Typesetting */
  math {{
    font-family: "STIX Two Math", "Cambria Math", "Latin Modern Math", serif;
    font-size: 1.05em;
  }}

  .math-block {{
    display: flex;
    justify-content: center;
    align-items: center;
    background-color: #f8fafc;
    border: 1px solid #e2e8f0;
    border-left: 3.5px solid #0284c7;
    border-radius: 5px;
    padding: 7px 12px;
    margin: 8px 0;
    overflow-x: auto;
    page-break-inside: avoid;
  }}

  .math-block math {{
    font-size: 1.15em;
  }}

  /* Tables */
  table {{
    width: 100%;
    border-collapse: collapse;
    margin: 8px 0;
    font-size: 7.6pt;
    page-break-inside: avoid;
  }}

  th, td {{
    border: 1px solid #cbd5e1;
    padding: 4px 6px;
    text-align: left;
    vertical-align: top;
  }}

  th {{
    background-color: #f1f5f9;
    font-weight: 700;
    color: #0f172a;
  }}

  tr:nth-child(even) {{
    background-color: #f8fafc;
  }}

  /* Callouts */
  .callout {{
    border-left: 3.5px solid #0284c7;
    background-color: #f0f9ff;
    padding: 7px 10px;
    margin: 7px 0;
    border-radius: 4px;
    page-break-inside: avoid;
  }}

  .callout-header {{
    font-size: 8pt;
    font-weight: 700;
    margin-bottom: 3px;
    display: flex;
    align-items: center;
    gap: 5px;
  }}

  .mermaid-diagram-container svg {{
    max-width: 100%;
    height: auto;
  }}

  hr {{
    border: none;
    border-top: 1px solid #e2e8f0;
    margin: 9px 0;
  }}

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


def main():
    print("=" * 80)
    print("  MODULAR SYSTEM DESIGN SPECIFICATION: PDF GENERATOR")
    print(f"  Source: {INPUT_MD}")
    print("=" * 80)

    if not os.path.exists(INPUT_MD):
        print(f"[ERROR] Source Markdown file not found: {INPUT_MD}")
        sys.exit(1)

    with open(INPUT_MD, "r", encoding="utf-8") as f:
        md_content = f.read()

    # Extract title from first H1
    title_match = re.search(r"^#\s+(.+)$", md_content, re.MULTILINE)
    title = title_match.group(1).strip() if title_match else "Modular Base CSE and Multi-Instance Vehicle AE Architecture"

    if title_match:
        md_content = md_content[:title_match.start()] + md_content[title_match.end():]

    # Pre-process pipeline
    print("\n[STEP 1] Stripping institutional headers...")
    processed_md = strip_institutional_sanctions(md_content)

    print("[STEP 2] Rendering Mermaid diagrams to SVG...")
    processed_md = convert_mermaid_diagrams_to_svg(processed_md)

    print("[STEP 3] Converting LaTeX equations to MathML Core...")
    processed_md = render_math_to_mathml(processed_md)

    print("[STEP 4] Formatting GitHub alerts...")
    processed_md = convert_github_alerts(processed_md)

    print("[STEP 5] Converting Markdown to HTML...")
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

    full_html = build_html_document(
        title=title,
        doc_id="SDS-SDV-MODULAR-001",
        doc_status="Approved Technical Architecture",
        html_body=html_body
    )

    scratch_html_path = os.path.join(SCRATCH_DIR, "modular_system_design_specification.html")
    with open(scratch_html_path, "w", encoding="utf-8") as f:
        f.write(full_html)
    print(f"[INFO] Intermediate HTML written to {scratch_html_path}")

    print("\n[STEP 6] Compiling PDF via Headless Chrome...")
    chrome_cmd = [
        "google-chrome",
        "--headless",
        "--disable-gpu",
        "--no-sandbox",
        "--no-pdf-header-footer",
        f"--print-to-pdf={OUTPUT_PDF_ARCH}",
        scratch_html_path
    ]

    res = subprocess.run(chrome_cmd, capture_output=True, text=True)
    if res.returncode == 0 and os.path.exists(OUTPUT_PDF_ARCH):
        size_kb = os.path.getsize(OUTPUT_PDF_ARCH) / 1024
        print(f"[SUCCESS] Compiled architecture PDF: {OUTPUT_PDF_ARCH} ({size_kb:.1f} KB)")
        
        # Also copy to foundational_document directory for repository completeness
        shutil.copyfile(OUTPUT_PDF_ARCH, OUTPUT_PDF_FOUND)
        print(f"[SUCCESS] Replicated to foundational documents: {OUTPUT_PDF_FOUND}")
    else:
        print(f"[ERROR] Chrome PDF compilation failed: {res.stderr}")
        sys.exit(1)


if __name__ == "__main__":
    main()
