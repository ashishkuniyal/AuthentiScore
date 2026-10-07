import io
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from datetime import datetime

def generate_pdf_report(scan_data: dict) -> bytes:
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer, 
        pagesize=letter,
        rightMargin=40, leftMargin=40,
        topMargin=40, bottomMargin=40
    )
    
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "TitleStyle", 
        parent=styles["Heading1"],
        fontSize=24,
        textColor=colors.HexColor("#4F46E5"),
        spaceAfter=20
    )
    
    heading_style = ParagraphStyle(
        "HeadingStyle",
        parent=styles["Heading2"],
        fontSize=14,
        textColor=colors.HexColor("#1E293B"),
        spaceBefore=20,
        spaceAfter=10
    )
    
    normal_style = styles["Normal"]
    
    elements = []
    
    # 1. Header
    elements.append(Paragraph("AuthentiScore Security Report", title_style))
    elements.append(Paragraph(f"<b>Scan ID:</b> {scan_data.get('scan_id', 'Unknown')}", normal_style))
    date_str = scan_data.get("timestamp", datetime.now().isoformat())
    elements.append(Paragraph(f"<b>Date:</b> {date_str}", normal_style))
    elements.append(Spacer(1, 20))
    
    # 2. Profile Details
    elements.append(Paragraph("Profile Details", heading_style))
    profile_data = [
        ["Platform", str(scan_data.get("platform", "")).capitalize()],
        ["Username", scan_data.get("username", "")],
        ["URL", scan_data.get("profile_url", "")],
    ]
    
    t_profile = Table(profile_data, colWidths=[150, 350])
    t_profile.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (0,-1), colors.HexColor("#F1F5F9")),
        ('TEXTCOLOR', (0,0), (-1,-1), colors.HexColor("#334155")),
        ('ALIGN', (0,0), (-1,-1), 'LEFT'),
        ('FONTNAME', (0,0), (0,-1), 'Helvetica-Bold'),
        ('BOTTOMPADDING', (0,0), (-1,-1), 8),
        ('TOPPADDING', (0,0), (-1,-1), 8),
        ('GRID', (0,0), (-1,-1), 1, colors.HexColor("#E2E8F0")),
    ]))
    elements.append(t_profile)
    elements.append(Spacer(1, 20))
    
    # 3. Risk Score
    elements.append(Paragraph("Risk Assessment", heading_style))
    score = scan_data.get("final_score", 0)
    classification = scan_data.get("classification", "Unknown")
    
    score_color = "#10B981" if score < 40 else ("#F59E0B" if score < 70 else "#EF4444")
    score_style = ParagraphStyle(
        "ScoreStyle",
        fontSize=18,
        textColor=colors.HexColor(score_color),
        fontName="Helvetica-Bold",
        spaceAfter=10
    )
    
    elements.append(Paragraph(f"Risk Score: {score}/100 ({classification})", score_style))
    elements.append(Spacer(1, 20))
    
    # 4. Explainable AI Factors
    elements.append(Paragraph("Key AI Risk Factors (SHAP)", heading_style))
    
    factors = scan_data.get("top_ml_factors", [])
    if factors:
        factor_data = [["Feature", "Value", "Impact", "SHAP Value"]]
        for f in factors:
            impact_str = f.get("impact", "")
            impact_color = colors.red if "increases" in impact_str else colors.green
            
            factor_data.append([
                f.get("feature", ""),
                str(f.get("value", "")),
                impact_str,
                str(f.get("shap_value", ""))
            ])
            
        t_factors = Table(factor_data, colWidths=[150, 100, 120, 130])
        t_factors.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#334155")),
            ('TEXTCOLOR', (0,0), (-1,0), colors.whitesmoke),
            ('ALIGN', (0,0), (-1,-1), 'LEFT'),
            ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
            ('BOTTOMPADDING', (0,0), (-1,-1), 8),
            ('TOPPADDING', (0,0), (-1,-1), 8),
            ('GRID', (0,0), (-1,-1), 1, colors.HexColor("#E2E8F0")),
        ]))
        elements.append(t_factors)
    else:
        elements.append(Paragraph("No ML factors available.", normal_style))
        
    elements.append(Spacer(1, 20))
    
    # 5. NLP Signals
    elements.append(Paragraph("NLP Signals", heading_style))
    nlp_signals = scan_data.get("nlp_signals", {}).get("matches", [])
    if nlp_signals:
        nlp_data = [["Category", "Matched Text"]]
        for signal in nlp_signals:
            nlp_data.append([signal.get("category", ""), signal.get("matched_text", "")])
            
        t_nlp = Table(nlp_data, colWidths=[150, 350])
        t_nlp.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#334155")),
            ('TEXTCOLOR', (0,0), (-1,0), colors.whitesmoke),
            ('ALIGN', (0,0), (-1,-1), 'LEFT'),
            ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
            ('BOTTOMPADDING', (0,0), (-1,-1), 8),
            ('TOPPADDING', (0,0), (-1,-1), 8),
            ('GRID', (0,0), (-1,-1), 1, colors.HexColor("#E2E8F0")),
        ]))
        elements.append(t_nlp)
    else:
        elements.append(Paragraph("No suspicious text patterns found.", normal_style))

    doc.build(elements)
    
    pdf_bytes = buffer.getvalue()
    buffer.close()
    return pdf_bytes
