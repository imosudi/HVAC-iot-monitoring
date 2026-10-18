#!/usr/bin/env python3
"""
Publication-Grade PDF Generator for Foundational Documents
Software-Defined Vehicle (SDV) Cabin Environmental Monitoring & Automotive IoT Middleware
FH Technikum Wien | Department of Electronic Engineering & Automotive Computing
Research Cluster: Distributed Cyber-Physical Systems and Automotive IoT (FHTW-AIOT)

Transforms Markdown specifications into publication-grade A4 PDF documents using
Python-Markdown and headless Google Chrome.
"""

import base64
import os
import re
import subprocess
import sys
import markdown

BASE_DIR = "/home/mosud/Documents/dev/HVAC-iot-monitoring"
FOUNDATIONAL_DIR = os.path.join(BASE_DIR, "foundational_document")
SCRATCH_DIR = "/home/mosud/.gemini/antigravity-ide/brain/7055d389-5e73-4385-aad0-2e13a4535482/scratch"
LOGO_PATH = os.path.join(BASE_DIR, "docs/assets/fhtw_logo.jpg")

os.makedirs(SCRATCH_DIR, exist_ok=True)
os.makedirs(FOUNDATIONAL_DIR, exist_ok=True)

# Read logo as base64
logo_b64 = ""
if os.path.exists(LOGO_PATH):
    with open(LOGO_PATH, "rb") as f:
        logo_b64 = base64.b64encode(f.read()).decode("utf-8")


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


def clean_latex_math(text: str) -> str:
    """Substitutes inline LaTeX symbols into clean unicode typography using exact string matching."""
    replacements = [
        (r"$\tau \le 2.5\,\text{s}$", "τ ≤ 2.5 s"),
        (r"$\tau \le 2.5\text{s}$", "τ ≤ 2.5 s"),
        (r"$\pm(30\,\text{ppm} + 3\%)$", "±(30 ppm + 3%)"),
        (r"$\pm 0.4^\circ\text{C}$", "±0.4 °C"),
        (r"$\pm 3\%)$", "±3%)"),
        (r"$\pm 3\%$", "±3%"),
        (r"$\pm 0.5^\circ\text{C}$", "±0.5 °C"),
        (r"$CO_2$", "CO₂"),
        (r"$t_{latency} \le 5.0\,\text{s}$", "t_latency ≤ 5.0 s"),
        (r"$t_{latency} > 30.0\,\text{s}$", "t_latency > 30.0 s"),
        (r"$|T_{SCD30} - T_{DHT22}| > 3.0^\circ\text{C}$", "|T_SCD30 - T_DHT22| > 3.0 °C"),
        (r"$|RH_{SCD30} - RH_{DHT22}| > 15\%$", "|RH_SCD30 - RH_DHT22| > 15%"),
        (r"$\frac{dT}{dt} > 0.5^\circ\text{C}/\text{s}$", "dT/dt > 0.5 °C/s"),
        (r"$RPM < 300$", "RPM < 300"),
        (r"$> 800\,\text{ppm}$", "> 800 ppm"),
        (r"$> 1200\,\text{ppm}$", "> 1200 ppm"),
        (r"$> 1800\,\text{ppm}$", "> 1800 ppm"),
        (r"$25\,\text{kHz}$", "25 kHz"),
    ]
    for target, repl in replacements:
        text = text.replace(target, repl)
    return text


def build_html_document(title: str, doc_id: str, doc_status: str, html_body: str) -> str:
    """Wraps body in publication-grade institutional styling with repeating table headers."""
    logo_img = f'<img src="data:image/jpeg;base64,{logo_b64}" class="logo" alt="FHTW Logo">' if logo_b64 else ''

    return f"""<!DOCTYPE html>
<html lang="en-GB">
<head>
<meta charset="UTF-8">
<title>{title}</title>
<style>
  @page {{
    size: A4 portrait;
    margin: 12mm 14mm 12mm 14mm;
    @top-right {{
      content: "{doc_id}";
      font-size: 7pt;
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
    line-height: 1.42;
    -webkit-print-color-adjust: exact;
    print-color-adjust: exact;
  }}

  /* Top institutional banner */
  .inst-header {{
    width: 100%;
    border-bottom: 2px solid #004080;
    padding-bottom: 6px;
    margin-bottom: 10px;
    display: flex;
    justify-content: space-between;
    align-items: center;
  }}

  .inst-left {{
    flex: 1;
  }}

  .inst-right {{
    width: 140px;
    text-align: right;
  }}

  .logo {{
    max-height: 38px;
    width: auto;
  }}

  .inst-cluster {{
    font-size: 7.2pt;
    font-weight: 700;
    color: #0284c7;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    margin-bottom: 2px;
  }}

  .inst-dept {{
    font-size: 7.2pt;
    color: #475569;
    line-height: 1.3;
  }}

  .doc-hero {{
    background: linear-gradient(135deg, #0f172a 0%, #1e293b 100%);
    color: #ffffff;
    padding: 10px 14px;
    border-radius: 6px;
    margin-bottom: 12px;
    border-left: 4px solid #0284c7;
  }}

  .doc-hero h1 {{
    font-size: 13.5pt;
    font-weight: 800;
    color: #ffffff;
    line-height: 1.25;
    margin-bottom: 3px;
  }}

  .doc-hero .doc-meta-row {{
    display: flex;
    flex-wrap: wrap;
    gap: 12px;
    font-size: 7.2pt;
    color: #94a3b8;
    margin-top: 5px;
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
    color: #004080;
    margin-top: 12px;
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

<div class="inst-header">
  <div class="inst-left">
    <div class="inst-cluster">FH Technikum Wien &bull; Research Cluster Distributed Cyber-Physical Systems &amp; Automotive IoT</div>
    <div class="inst-dept">Department of Electronic Engineering &amp; Automotive Computing &bull; Standard Conformance: ETSI TS 118 101 Rel 4</div>
  </div>
  <div class="inst-right">
    {logo_img}
  </div>
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
  <div>{doc_id} &bull; Canonical Technical Reference</div>
  <div>Software-Defined Vehicle (SDV) IoT HVAC Monitoring &bull; FH Technikum Wien</div>
  <div>Classification: Technical Specification &bull; Open Academic Standard</div>
</div>

</body>
</html>
"""


def compile_md_to_pdf(input_md_path: str, output_pdf_path: str, doc_id: str, doc_status: str = "Approved Technical Specification") -> bool:
    """Renders a single Markdown file to publication-grade PDF via Chrome."""
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

    # Pre-process alerts and LaTeX math
    processed_md = clean_latex_math(md_content)
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
    print("  FH Technikum Wien | Automotive IoT & Software-Defined Vehicles")
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
            "doc_id": "FHTW-SDV-ARCH-005",
            "status": "Approved Engineering Specification"
        },
        {
            "md": os.path.join(FOUNDATIONAL_DIR, "security_pki_and_data_health_specification.md"),
            "pdf": os.path.join(FOUNDATIONAL_DIR, "security_pki_and_data_health_specification.pdf"),
            "doc_id": "FHTW-SDV-SEC-001",
            "status": "Approved Engineering Specification"
        },
        {
            "md": os.path.join(FOUNDATIONAL_DIR, "system_validation_and_benchmarking_report.md"),
            "pdf": os.path.join(FOUNDATIONAL_DIR, "system_validation_and_benchmarking_report.pdf"),
            "doc_id": "FHTW-SDV-TEST-002",
            "status": "Approved Engineering Verification Report"
        },
        {
            "md": os.path.join(FOUNDATIONAL_DIR, "target_hardware_transition_deployment_guide.md"),
            "pdf": os.path.join(FOUNDATIONAL_DIR, "target_hardware_transition_deployment_guide.pdf"),
            "doc_id": "FHTW-SDV-DEPL-003",
            "status": "Production Deployment Guide"
        },
        {
            "md": os.path.join(FOUNDATIONAL_DIR, "mvp_implementation_plan.md"),
            "pdf": os.path.join(FOUNDATIONAL_DIR, "mvp_implementation_plan.pdf"),
            "doc_id": "FHTW-SDV-PLAN-001",
            "status": "Engineering Architecture Plan"
        },
        {
            "md": os.path.join(FOUNDATIONAL_DIR, "project_directory_and_file_structure.md"),
            "pdf": os.path.join(FOUNDATIONAL_DIR, "project_directory_and_file_structure.pdf"),
            "doc_id": "FHTW-SDV-STRUCT-001",
            "status": "Repository Topology Specification"
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

    if compile_md_to_pdf(consolidated_md_path, consolidated_pdf_path, "FHTW-SDV-DOSSIER-2026", "Consolidated Technical Dossier"):
        success_count += 1

    print("\n" + "=" * 80)
    print(f"  COMPILATION COMPLETE: {success_count}/{len(documents) + 1} PDFs Generated Successfully!")
    print("=" * 80)


if __name__ == "__main__":
    main()
