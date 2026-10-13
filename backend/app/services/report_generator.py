"""
AuthentiScore — PDF Report Generator
=====================================

Implements:
  - S14: HTML/XML markup escaping for all user/dynamic strings
  - C4: Safe rendering of None scores ("Insufficient Data") without crashing
  - C5: Risk colors aligned with 34/67/90 thresholds
  - C24: Explanation method disclaimer
  - C36: Python hygiene (remove unused variables)
"""

from __future__ import annotations

import io
from datetime import datetime
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle


def _safe(val: object) -> str:
    """S14: Escape dynamic content before inserting into ReportLab Paragraph."""
    if val is None:
        return ""
    return escape(str(val))


def generate_pdf_report(scan_data: dict) -> bytes:
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        rightMargin=40,
        leftMargin=40,
        topMargin=40,
        bottomMargin=40,
    )

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "TitleStyle",
        parent=styles["Heading1"],
        fontSize=24,
        textColor=colors.HexColor("#4F46E5"),
        spaceAfter=20,
    )

    heading_style = ParagraphStyle(
        "HeadingStyle",
        parent=styles["Heading2"],
        fontSize=14,
        textColor=colors.HexColor("#1E293B"),
        spaceBefore=20,
        spaceAfter=10,
    )

    subheading_style = ParagraphStyle(
        "SubHeadingStyle",
        parent=styles["Italic"],
        fontSize=10,
        textColor=colors.HexColor("#64748B"),
        spaceAfter=10,
    )

    normal_style = styles["Normal"]

    elements = []

    # 1. Header
    elements.append(Paragraph("AuthentiScore Security Report", title_style))
    elements.append(
        Paragraph(f"<b>Scan ID:</b> {_safe(scan_data.get('scan_id', 'Unknown'))}", normal_style)
    )
    date_str = _safe(scan_data.get("timestamp", datetime.now().isoformat()))
    elements.append(Paragraph(f"<b>Date:</b> {date_str}", normal_style))
    elements.append(Spacer(1, 20))

    # 2. Profile Details
    elements.append(Paragraph("Profile Details", heading_style))
    profile_data = [
        ["Platform", _safe(str(scan_data.get("platform", "")).capitalize())],
        ["Username", _safe(scan_data.get("username", ""))],
        ["URL", _safe(scan_data.get("profile_url", ""))],
    ]

    t_profile = Table(profile_data, colWidths=[150, 350])
    t_profile.setStyle(
        TableStyle([
            ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#F1F5F9")),
            ("TEXTCOLOR", (0, 0), (-1, -1), colors.HexColor("#334155")),
            ("ALIGN", (0, 0), (-1, -1), "LEFT"),
            ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
            ("TOPPADDING", (0, 0), (-1, -1), 8),
            ("GRID", (0, 0), (-1, -1), 1, colors.HexColor("#E2E8F0")),
        ])
    )
    elements.append(t_profile)
    elements.append(Spacer(1, 20))

    # 3. Risk Score (C4, C5)
    elements.append(Paragraph("Risk Assessment", heading_style))
    score = scan_data.get("final_score")
    classification = scan_data.get("classification", "Unknown")

    if score is None or "insufficient" in str(classification).lower():
        score_text = f"Risk Score: Insufficient Data ({_safe(classification)})"
        score_color = "#64748B"
    else:
        score_val = float(score)
        # C5: Bands 34 / 67 / 90
        score_color = (
            "#10B981" if score_val < 34 else ("#F59E0B" if score_val < 67 else "#EF4444")
        )
        score_text = f"Risk Score: {score_val:.1f}/100 ({_safe(classification)})"

    score_style = ParagraphStyle(
        "ScoreStyle",
        fontSize=18,
        textColor=colors.HexColor(score_color),
        fontName="Helvetica-Bold",
        spaceAfter=10,
    )

    elements.append(Paragraph(score_text, score_style))
    elements.append(Spacer(1, 20))

    # 4. Explainable AI Factors (C24)
    elements.append(Paragraph("Key AI Risk Factors (SHAP)", heading_style))
    elements.append(
        Paragraph("Explanation method: RandomForest component (approximation)", subheading_style)
    )

    factors = scan_data.get("top_ml_factors") or []
    if factors:
        factor_data = [["Feature", "Value", "Impact", "SHAP Value"]]
        for f in factors:
            factor_data.append([
                _safe(f.get("feature", "")),
                _safe(f.get("value", "N/A")),
                _safe(f.get("label", f.get("impact", ""))),
                _safe(f.get("shap_value", "")),
            ])

        t_factors = Table(factor_data, colWidths=[140, 90, 150, 120])
        t_factors.setStyle(
            TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#334155")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
                ("ALIGN", (0, 0), (-1, -1), "LEFT"),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
                ("TOPPADDING", (0, 0), (-1, -1), 8),
                ("GRID", (0, 0), (-1, -1), 1, colors.HexColor("#E2E8F0")),
            ])
        )
        elements.append(t_factors)
    else:
        elements.append(Paragraph("No ML factors available (insufficient data).", normal_style))

    elements.append(Spacer(1, 20))

    # 5. NLP Signals
    elements.append(Paragraph("NLP Signals", heading_style))
    nlp_signals_obj = scan_data.get("nlp_signals") or {}
    matched_cats = nlp_signals_obj.get("matched_categories") or []
    matched_phrases = nlp_signals_obj.get("matched_phrases") or []

    if matched_cats or matched_phrases:
        nlp_data = [["Category / Signal", "Details"]]
        for cat in matched_cats:
            nlp_data.append(["Category Match", _safe(cat)])
        for phrase in matched_phrases:
            nlp_data.append(["Flagged Phrase", _safe(phrase)])

        t_nlp = Table(nlp_data, colWidths=[150, 350])
        t_nlp.setStyle(
            TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#334155")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
                ("ALIGN", (0, 0), (-1, -1), "LEFT"),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
                ("TOPPADDING", (0, 0), (-1, -1), 8),
                ("GRID", (0, 0), (-1, -1), 1, colors.HexColor("#E2E8F0")),
            ])
        )
        elements.append(t_nlp)
    else:
        elements.append(Paragraph("No suspicious text patterns found.", normal_style))

    doc.build(elements)

    pdf_bytes = buffer.getvalue()
    buffer.close()
    return pdf_bytes
