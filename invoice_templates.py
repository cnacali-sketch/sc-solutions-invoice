import os
from datetime import date
from decimal import Decimal, ROUND_HALF_UP
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.colors import HexColor
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT, TA_JUSTIFY
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable
)

CENT = Decimal("0.01")
ZERO = Decimal("0.00")


def dec(value, default="0"):
    try:
        return Decimal(str(value).strip() or default)
    except Exception:
        return Decimal(default)


def money_amount(value):
    return dec(value, "0").quantize(CENT, rounding=ROUND_HALF_UP)


def fmt_decimal(value):
    d = money_amount(value)
    if d == d.to_integral():
        return str(int(d))
    return f"{d.normalize():f}"


def get_fonts():
    candidates = [
        ("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"),
    ]
    for regular_path, bold_path in candidates:
        if os.path.exists(regular_path):
            try:
                pdfmetrics.registerFont(TTFont("InvoiceFont", regular_path))
                font_name = "InvoiceFont"
            except Exception:
                continue
            bold_font_name = font_name
            if os.path.exists(bold_path):
                try:
                    pdfmetrics.registerFont(TTFont("InvoiceFont-Bold", bold_path))
                    bold_font_name = "InvoiceFont-Bold"
                except Exception:
                    bold_font_name = font_name
            return font_name, bold_font_name
    return "Helvetica", "Helvetica-Bold"


def money(value):
    amount = money_amount(value)
    sign = "-" if amount < 0 else ""
    amount = abs(amount)
    text = f"{amount:.2f}"
    whole, frac = text.split(".")
    last3 = whole[-3:]
    rest = whole[:-3]
    while rest:
        last3 = rest[-2:] + "," + last3
        rest = rest[:-2]
    symbol = "₹" if get_fonts()[0] != "Helvetica" else "Rs. "
    return f"{sign}{symbol}{last3}.{frac}"


def safe_filename(text):
    text = re.sub(r"[^A-Za-z0-9_-]+", "-", str(text or "item").lower()).strip("-")
    return text[:60] or "item"


def br_html(lines):
    cleaned = []
    for line in lines:
        line = str(line).strip()
        if line:
            cleaned.append(line)
    return "<br/>".join(cleaned)


def money_in_words(amount):
    from num2words import num2words
    amount = money_amount(amount)
    sign = ""
    if amount < 0:
        sign = "Negative "
        amount = abs(amount)
    whole = int(amount)
    paise = int((amount - Decimal(whole)) * 100)
    try:
        words = num2words(whole, lang="en_IN")
    except Exception:
        words = num2words(whole, lang="en")
    words = words.replace("-", " ").title()
    if paise:
        try:
            paise_words = num2words(paise, lang="en_IN")
        except Exception:
            paise_words = num2words(paise, lang="en")
        paise_words = paise_words.replace("-", " ").title()
        return f"{sign}{words} Rupees And {paise_words} Paise Only"
    return f"{sign}{words} Rupees Only"


def add_page_number(canvas, doc):
    canvas.saveState()
    font, _ = get_fonts()
    canvas.setFont(font, 7)
    canvas.drawRightString(doc.pagesize[0] - doc.rightMargin, 8 * mm, f"Page {doc.page}")
    canvas.restoreState()


def _prepare_styles(font, bold):
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name="InvTitle", fontName=bold, fontSize=18, leading=22, alignment=TA_CENTER, spaceAfter=4))
    styles.add(ParagraphStyle(name="InvCo", fontName=bold, fontSize=15, leading=18, alignment=TA_CENTER, spaceAfter=6))
    styles.add(ParagraphStyle(name="InvBlock", fontName=font, fontSize=8.2, leading=10.5, alignment=TA_LEFT))
    styles.add(ParagraphStyle(name="InvCell", fontName=font, fontSize=6.7, leading=8.2, alignment=TA_LEFT))
    styles.add(ParagraphStyle(name="InvCellRight", parent=styles["InvCell"], alignment=TA_RIGHT))
    styles.add(ParagraphStyle(name="InvHeaderCell", fontName=bold, fontSize=6.8, leading=8.2, alignment=TA_CENTER, textColor=colors.white))
    styles.add(ParagraphStyle(name="InvSection", fontName=bold, fontSize=10, leading=12, spaceBefore=6, spaceAfter=4))
    styles.add(ParagraphStyle(name="InvTerm", fontName=font, fontSize=8, leading=10, leftIndent=4*mm))
    styles.add(ParagraphStyle(name="InvWords", fontName=font, fontSize=9, leading=12, spaceAfter=4))
    styles.add(ParagraphStyle(name="InvSmall", fontName=font, fontSize=6, leading=7, alignment=TA_CENTER))
    return styles


def _prepare_header(data, font):
    company_lines = [escape(data["company_name"])]
    for line in data["company_address"].splitlines():
        line = line.strip()
        if line:
            company_lines.append(escape(line))
    if len(company_lines) == 1:
        company_lines.append("-")
    if data.get("gst"):
        company_lines.append(escape(f"GSTIN: {data['gst']}"))
    else:
        company_lines.append("GSTIN:")
    if data.get("pan"):
        company_lines.append(escape(f"PAN: {data['pan']}"))
    else:
        company_lines.append("PAN:")
    if data.get("phone"):
        company_lines.append(escape(f"Phone: {data['phone']}"))
    else:
        company_lines.append("Phone:")

    customer_lines = ["<b>FOR</b>", escape(data["customer_name"] or "-")]
    for line in data["customer_address"].splitlines():
        line = line.strip()
        if line:
            customer_lines.append(escape(line))
    if len(customer_lines) == 2:
        customer_lines.append("-")
    if data.get("customer_phone"):
        customer_lines.append(escape(f"Phone: {data['customer_phone']}"))
    return company_lines, customer_lines


def _prepare_item_data(data, font, bold, styles):
    item_headers = ["Item", "Area / Unit Type", "GST Rate", "Qty", "Rate", "Amount", "CGST", "SGST", "Total"]
    item_data = [[Paragraph(escape(h), styles["InvHeaderCell"]) for h in item_headers]]
    for index, item in enumerate(data["items"], 1):
        item_data.append([
            Paragraph(f"{index}.", styles["InvCell"]),
            Paragraph(item["area"], styles["InvCell"]),
            Paragraph(item["gst"], styles["InvCell"]),
            Paragraph(fmt_decimal(item["qty"]), styles["InvCellRight"]),
            Paragraph(money(item["rate"]), styles["InvCellRight"]),
            Paragraph(money(item["amount"]), styles["InvCellRight"]),
            Paragraph(money(item["cgst"]), styles["InvCellRight"]),
            Paragraph(money(item["sgst"]), styles["InvCellRight"]),
            Paragraph(money(item["total"]), styles["InvCellRight"]),
        ])
        item_data.append([
            Paragraph(item["description"], styles["InvCell"]),
            "", "", "", "", "", "", "", "",
        ])
    return item_data


# ==================== TEMPLATE A: PROFESSIONAL BLUE ====================
def build_template_a(data, path):
    """Professional Blue Proforma Invoice - Corporate polished look"""
    font, bold = get_fonts()
    styles = _prepare_styles(font, bold)
    PRIMARY = HexColor("#1f4e79")
    ACCENT = HexColor("#d9eaf7")

    doc = SimpleDocTemplate(path, pagesize=A4, rightMargin=9*mm, leftMargin=9*mm, topMargin=10*mm, bottomMargin=12*mm)
    story = []

    story.append(Paragraph("Proforma Invoice", styles["InvTitle"]))
    story.append(Paragraph(escape(data["company_name"]), styles["InvCo"]))
    story.append(Spacer(1, 2*mm))

    company_lines, customer_lines = _prepare_header(data, font)
    company_para = Paragraph(br_html(company_lines), styles["InvBlock"])
    customer_para = Paragraph(br_html(customer_lines), styles["InvBlock"])
    header_table = Table([[company_para, customer_para]], colWidths=[96*mm, 96*mm])
    header_table.setStyle(TableStyle([
        ("VALIGN", (0,0), (-1,-1), "TOP"),
        ("BOX", (0,0), (-1,-1), 0.35, colors.black),
        ("INNERGRID", (0,0), (-1,-1), 0.25, colors.black),
        ("BACKGROUND", (0,0), (0,0), colors.whitesmoke),
        ("BACKGROUND", (1,0), (1,0), colors.whitesmoke),
        ("LEFTPADDING", (0,0), (-1,-1), 5),
        ("RIGHTPADDING", (0,0), (-1,-1), 5),
        ("TOPPADDING", (0,0), (-1,-1), 5),
        ("BOTTOMPADDING", (0,0), (-1,-1), 5),
    ]))
    story.append(header_table)
    story.append(Spacer(1, 5*mm))

    details_data = [
        [Paragraph("Invoice No #", styles["InvHeaderCell"]), Paragraph(data["invoice_no"], styles["InvCell"]), Paragraph("Invoice Date", styles["InvHeaderCell"]), Paragraph(data["invoice_date"], styles["InvCell"])],
        [Paragraph("Unit Type", styles["InvHeaderCell"]), Paragraph(data["unit_type"], styles["InvCell"]), Paragraph("Work Type", styles["InvHeaderCell"]), Paragraph(data["work_type"], styles["InvCell"])],
        [Paragraph("Payment Status", styles["InvHeaderCell"]), Paragraph(data["payment_status"], styles["InvCell"]), Paragraph("", styles["InvHeaderCell"]), Paragraph("", styles["InvCell"])],
    ]
    details_table = Table(details_data, colWidths=[38*mm, 58*mm, 38*mm, 58*mm])
    details_table.setStyle(TableStyle([
        ("GRID", (0,0), (-1,-1), 0.35, colors.black),
        ("BACKGROUND", (0,0), (0,-1), ACCENT),
        ("BACKGROUND", (2,0), (2,-1), ACCENT),
        ("VALIGN", (0,0), (-1,-1), "MIDDLE"),
        ("LEFTPADDING", (0,0), (-1,-1), 4),
        ("RIGHTPADDING", (0,0), (-1,-1), 4),
    ]))
    story.append(details_table)
    story.append(Spacer(1, 5*mm))

    item_data = _prepare_item_data(data, font, bold, styles)
    item_table = Table(item_data, colWidths=[20*mm, 30*mm, 15*mm, 16*mm, 20*mm, 24*mm, 20*mm, 20*mm, 25*mm], repeatRows=1)
    item_table.setStyle(TableStyle([
        ("GRID", (0,0), (-1,-1), 0.35, colors.black),
        ("BACKGROUND", (0,0), (-1,0), PRIMARY),
        ("VALIGN", (0,0), (-1,-1), "TOP"),
        ("ALIGN", (2,1), (-1,-1), "RIGHT"),
        ("ALIGN", (0,1), (1,-1), "LEFT"),
        ("LEFTPADDING", (0,0), (-1,-1), 3),
        ("RIGHTPADDING", (0,0), (-1,-1), 3),
        ("TOPPADDING", (0,0), (-1,-1), 3),
        ("BOTTOMPADDING", (0,0), (-1,-1), 3),
    ]))
    story.append(item_table)

    story.append(Spacer(1, 4*mm))
    story.append(Paragraph("TERMS AND CONDITIONS", styles["InvSection"]))
    for term in data["terms"]:
        story.append(Paragraph("- " + escape(term), styles["InvTerm"]))

    discount = money_amount(data["discount"])
    discount_display = f"({money(discount)})" if discount > 0 else money(ZERO)
    summary_data = [
        [Paragraph("Amount", styles["InvCell"]), Paragraph(money(data["subtotal"]), styles["InvCellRight"])],
        [Paragraph("CGST", styles["InvCell"]), Paragraph(money(data["cgst_total"]), styles["InvCellRight"])],
        [Paragraph("SGST", styles["InvCell"]), Paragraph(money(data["sgst_total"]), styles["InvCellRight"])],
        [Paragraph("Discounts", styles["InvCell"]), Paragraph(discount_display, styles["InvCellRight"])],
        [Paragraph("Total (INR)", styles["InvCell"]), Paragraph(money(data["grand_total"]), styles["InvCellRight"])],
    ]
    summary_table = Table(summary_data, colWidths=[55*mm, 45*mm])
    summary_table.setStyle(TableStyle([
        ("GRID", (0,0), (-1,-1), 0.35, colors.black),
        ("BACKGROUND", (0,-1), (0,-1), ACCENT),
        ("BACKGROUND", (1,-1), (1,-1), ACCENT),
        ("FONTNAME", (0,-1), (-1,-1), bold),
        ("VALIGN", (0,0), (-1,-1), "MIDDLE"),
        ("LEFTPADDING", (0,0), (-1,-1), 5),
        ("RIGHTPADDING", (0,0), (-1,-1), 5),
    ]))
    story.append(summary_table)

    story.append(Spacer(1, 3*mm))
    story.append(Paragraph("TOTAL (IN WORDS) :", styles["InvSection"]))
    story.append(Paragraph(escape(data["amount_in_words"]), styles["InvWords"]))

    story.append(Spacer(1, 6*mm))
    story.append(Paragraph("This is a Proforma Invoice and not a Tax Invoice.", styles["InvSmall"]))
    story.append(Paragraph("Thank you for your business.", styles["InvSmall"]))

    doc.build(story, onFirstPage=add_page_number, onLaterPages=add_page_number)


# ==================== TEMPLATE B: MODERN MINIMALIST ====================
def build_template_b(data, path):
    """Modern Minimalist - Clean white/grey with subtle accents"""
    font, bold = get_fonts()
    styles = _prepare_styles(font, bold)
    DARK = HexColor("#2c3e50")
    GREY = HexColor("#ecf0f1")
    BORDER = HexColor("#bdc3c7")

    doc = SimpleDocTemplate(path, pagesize=A4, rightMargin=15*mm, leftMargin=15*mm, topMargin=12*mm, bottomMargin=12*mm)
    story = []

    story.append(Paragraph(escape(data["company_name"]), ParagraphStyle("Co", parent=styles["InvCo"], fontSize=22, leading=26, textColor=DARK, spaceAfter=2)))
    story.append(HRFlowable(width="100%", thickness=1.5, color=DARK, spaceAfter=2, hAlign="LEFT"))

    story.append(Paragraph("Proforma Invoice", ParagraphStyle("Ti", parent=styles["InvTitle"], fontSize=14, alignment=TA_RIGHT, textColor=HexColor("#7f8c8d"), spaceAfter=2)))

    company_lines, customer_lines = _prepare_header(data, font)
    company_para = Paragraph(br_html(company_lines), ParagraphStyle("BL", parent=styles["InvBlock"], fontSize=9, leading=12))
    customer_para = Paragraph(br_html(customer_lines), ParagraphStyle("BL2", parent=styles["InvBlock"], fontSize=9, leading=12))
    header_table = Table([[company_para, customer_para]], colWidths=[85*mm, 85*mm])
    header_table.setStyle(TableStyle([
        ("VALIGN", (0,0), (-1,-1), "TOP"),
        ("LEFTPADDING", (0,0), (-1,-1), 0),
        ("RIGHTPADDING", (0,0), (-1,-1), 0),
        ("TOPPADDING", (0,0), (-1,-1), 0),
        ("BOTTOMPADDING", (0,0), (-1,-1), 0),
    ]))
    story.append(header_table)
    story.append(Spacer(1, 4*mm))

    details_data = [
        [Paragraph("Invoice No", styles["InvCell"]), Paragraph(data["invoice_no"], styles["InvCell"]), Paragraph("Date", styles["InvCell"]), Paragraph(data["invoice_date"], styles["InvCell"])],
        [Paragraph("Unit", styles["InvCell"]), Paragraph(data["unit_type"], styles["InvCell"]), Paragraph("Work", styles["InvCell"]), Paragraph(data["work_type"], styles["InvCell"])],
        [Paragraph("Status", styles["InvCell"]), Paragraph(data["payment_status"], styles["InvCell"]), Paragraph("", styles["InvCell"]), Paragraph("", styles["InvCell"])],
    ]
    details_table = Table(details_data, colWidths=[40*mm, 55*mm, 40*mm, 55*mm])
    details_table.setStyle(TableStyle([
        ("LINEBELOW", (0,0), (-1,-1), 0.5, BORDER),
        ("VALIGN", (0,0), (-1,-1), "MIDDLE"),
        ("LEFTPADDING", (0,0), (-1,-1), 2),
        ("RIGHTPADDING", (0,0), (-1,-1), 2),
        ("TOPPADDING", (0,0), (-1,-1), 4),
        ("BOTTOMPADDING", (0,0), (-1,-1), 4),
        ("FONTNAME", (0,0), (0,-1), bold),
        ("FONTNAME", (2,0), (2,-1), bold),
        ("TEXTCOLOR", (0,0), (0,-1), DARK),
        ("TEXTCOLOR", (2,0), (2,-1), DARK),
    ]))
    story.append(details_table)
    story.append(Spacer(1, 5*mm))

    item_data = _prepare_item_data(data, font, bold, styles)
    # Modern: only horizontal rules, no vertical grid
    item_table = Table(item_data, colWidths=[20*mm, 30*mm, 15*mm, 16*mm, 20*mm, 24*mm, 20*mm, 20*mm, 25*mm], repeatRows=1)
    item_table.setStyle(TableStyle([
        ("LINEBELOW", (0,0), (-1,0), 1, DARK),
        ("LINEBELOW", (0,0), (-1,-1), 0.3, BORDER),
        ("BACKGROUND", (0,0), (-1,0), GREY),
        ("VALIGN", (0,0), (-1,-1), "TOP"),
        ("ALIGN", (2,1), (-1,-1), "RIGHT"),
        ("ALIGN", (0,1), (1,-1), "LEFT"),
        ("LEFTPADDING", (0,0), (-1,-1), 3),
        ("RIGHTPADDING", (0,0), (-1,-1), 3),
        ("TOPPADDING", (0,0), (-1,-1), 3),
        ("BOTTOMPADDING", (0,0), (-1,-1), 3),
    ]))
    story.append(item_table)

    story.append(Spacer(1, 4*mm))

    discount = money_amount(data["discount"])
    discount_display = f"({money(discount)})" if discount > 0 else money(ZERO)
    summary_data = [
        [Paragraph("", styles["InvCell"]), Paragraph("Subtotal", styles["InvCell"]), Paragraph(money(data["subtotal"]), styles["InvCellRight"])],
        [Paragraph("", styles["InvCell"]), Paragraph("CGST", styles["InvCell"]), Paragraph(money(data["cgst_total"]), styles["InvCellRight"])],
        [Paragraph("", styles["InvCell"]), Paragraph("SGST", styles["InvCell"]), Paragraph(money(data["sgst_total"]), styles["InvCellRight"])],
        [Paragraph("", styles["InvCell"]), Paragraph("Discount", styles["InvCell"]), Paragraph(discount_display, styles["InvCellRight"])],
        [Paragraph("", styles["InvCell"]), Paragraph("Grand Total", ParagraphStyle("GT", parent=styles["InvCell"], fontName=bold, fontSize=10, leading=12)), Paragraph(money(data["grand_total"]), ParagraphStyle("GTR", parent=styles["InvCellRight"], fontName=bold, fontSize=10, leading=12))],
    ]
    summary_table = Table(summary_data, colWidths=[100*mm, 45*mm, 55*mm])
    summary_table.setStyle(TableStyle([
        ("LINEBELOW", (1,0), (-1,-1), 0.3, BORDER),
        ("LINEBELOW", (1,-1), (-1,-1), 1.5, DARK),
        ("VALIGN", (0,0), (-1,-1), "MIDDLE"),
        ("LEFTPADDING", (0,0), (-1,-1), 5),
        ("RIGHTPADDING", (0,0), (-1,-1), 5),
        ("TOPPADDING", (0,0), (-1,-1), 4),
        ("BOTTOMPADDING", (0,0), (-1,-1), 4),
        ("ALIGN", (1,0), (1,-1), "LEFT"),
        ("ALIGN", (2,0), (2,-1), "RIGHT"),
    ]))
    story.append(summary_table)

    story.append(Spacer(1, 3*mm))
    story.append(Paragraph("Amount in Words:", ParagraphStyle("AW", parent=styles["InvSection"], fontSize=9, textColor=DARK)))
    story.append(Paragraph(escape(data["amount_in_words"]), ParagraphStyle("AWT", parent=styles["InvWords"], fontSize=9, textColor=DARK)))

    story.append(Spacer(1, 5*mm))
    story.append(HRFlowable(width="100%", thickness=0.5, color=BORDER, spaceAfter=2, hAlign="LEFT"))
    story.append(Paragraph("TERMS & CONDITIONS", ParagraphStyle("TCS", parent=styles["InvSection"], fontSize=9, textColor=DARK, spaceAfter=2)))
    for term in data["terms"]:
        story.append(Paragraph(escape(term), ParagraphStyle("T", parent=styles["InvTerm"], fontSize=8, leading=11, textColor=HexColor("#7f8c8d"))))

    story.append(Spacer(1, 6*mm))
    story.append(Paragraph("This is a Proforma Invoice and not a Tax Invoice.", styles["InvSmall"]))
    story.append(Paragraph("Thank you for your business.", styles["InvSmall"]))

    doc.build(story, onFirstPage=add_page_number, onLaterPages=add_page_number)


# ==================== TEMPLATE C: CLASSIC FORMAL ====================
def build_template_c(data, path):
    """Classic Formal - Traditional business style with table layout"""
    font, bold = get_fonts()
    styles = _prepare_styles(font, bold)
    DARK_BLUE = HexColor("#0c2461")
    GOLD = HexColor("#c4a45a")
    LIGHT = HexColor("#f5f5f5")

    doc = SimpleDocTemplate(path, pagesize=A4, rightMargin=12*mm, leftMargin=12*mm, topMargin=10*mm, bottomMargin=12*mm)
    story = []

    # Top header band
    story.append(Paragraph("Proforma Invoice", ParagraphStyle("T1", parent=styles["InvTitle"], fontSize=20, leading=24, textColor=colors.white, spaceAfter=0)))
    story.append(Paragraph(escape(data["company_name"]), ParagraphStyle("T2", parent=styles["InvCo"], fontSize=14, leading=18, textColor=colors.white, spaceAfter=0)))
    story.append(Paragraph("", ParagraphStyle("T3", parent=styles["InvBlock"], fontSize=6, leading=8, textColor=colors.white, spaceAfter=0)))

    # Company details in a box
    company_lines, customer_lines = _prepare_header(data, font)
    header_box = Table([
        [Paragraph("", styles["InvCell"]), Paragraph("", styles["InvCell"])],
        [Paragraph("Company Details", ParagraphStyle("H1", parent=styles["InvBlock"], fontName=bold, fontSize=9, textColor=DARK_BLUE)), Paragraph("Customer Details", ParagraphStyle("H2", parent=styles["InvBlock"], fontName=bold, fontSize=9, textColor=DARK_BLUE))],
        [Paragraph(br_html(company_lines), ParagraphStyle("CL", parent=styles["InvBlock"], fontSize=8, leading=11)), Paragraph(br_html(customer_lines), ParagraphStyle("CL2", parent=styles["InvBlock"], fontSize=8, leading=11))],
    ], colWidths=[86*mm, 86*mm])
    header_box.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (-1,0), DARK_BLUE),
        ("TEXTCOLOR", (0,0), (-1,0), colors.white),
        ("FONTSIZE", (0,0), (-1,0), 10),
        ("FONTNAME", (0,0), (-1,0), bold),
        ("ALIGN", (0,0), (-1,0), "CENTER"),
        ("VALIGN", (0,0), (-1,0), "MIDDLE"),
        ("TOPPADDING", (0,0), (-1,0), 6),
        ("BOTTOMPADDING", (0,0), (-1,0), 6),
        ("BACKGROUND", (0,1), (-1,1), LIGHT),
        ("LEFTPADDING", (0,2), (-1,2), 6),
        ("RIGHTPADDING", (0,2), (-1,2), 6),
        ("TOPPADDING", (0,2), (-1,2), 6),
        ("BOTTOMPADDING", (0,2), (-1,2), 6),
        ("BOX", (0,0), (-1,-1), 1, DARK_BLUE),
        ("INNERGRID", (0,0), (-1,-1), 0.5, DARK_BLUE),
    ]))
    story.append(header_box)
    story.append(Spacer(1, 5*mm))

    # Invoice details
    details_data = [
        [Paragraph("Invoice No", ParagraphStyle("DL", parent=styles["InvCell"], fontName=bold, textColor=DARK_BLUE)), Paragraph(data["invoice_no"], styles["InvCell"]), Paragraph("Date", ParagraphStyle("DL2", parent=styles["InvCell"], fontName=bold, textColor=DARK_BLUE)), Paragraph(data["invoice_date"], styles["InvCell"])],
        [Paragraph("Unit", ParagraphStyle("DL3", parent=styles["InvCell"], fontName=bold, textColor=DARK_BLUE)), Paragraph(data["unit_type"], styles["InvCell"]), Paragraph("Work", ParagraphStyle("DL4", parent=styles["InvCell"], fontName=bold, textColor=DARK_BLUE)), Paragraph(data["work_type"], styles["InvCell"])],
        [Paragraph("Status", ParagraphStyle("DL5", parent=styles["InvCell"], fontName=bold, textColor=DARK_BLUE)), Paragraph(data["payment_status"], styles["InvCell"]), Paragraph("", ParagraphStyle("DL6", parent=styles["InvCell"], fontName=bold, textColor=DARK_BLUE)), Paragraph("", styles["InvCell"])],
    ]
    details_table = Table(details_data, colWidths=[38*mm, 58*mm, 38*mm, 58*mm])
    details_table.setStyle(TableStyle([
        ("BOX", (0,0), (-1,-1), 0.5, DARK_BLUE),
        ("INNERGRID", (0,0), (-1,-1), 0.5, DARK_BLUE),
        ("BACKGROUND", (0,0), (0,-1), LIGHT),
        ("BACKGROUND", (2,0), (2,-1), LIGHT),
        ("VALIGN", (0,0), (-1,-1), "MIDDLE"),
        ("LEFTPADDING", (0,0), (-1,-1), 4),
        ("RIGHTPADDING", (0,0), (-1,-1), 4),
    ]))
    story.append(details_table)
    story.append(Spacer(1, 5*mm))

    # Items table
    item_headers = ["S.No", "Description", "Unit", "GST", "Qty", "Rate", "Amount", "CGST", "SGST", "Total"]
    item_data = [[Paragraph(escape(h), ParagraphStyle("HC", parent=styles["InvHeaderCell"], fontSize=7, leading=8)) for h in item_headers]]
    for index, item in enumerate(data["items"], 1):
        item_data.append([
            Paragraph(str(index), styles["InvCell"]),
            Paragraph(item["description"], styles["InvCell"]),
            Paragraph(item["area"], styles["InvCell"]),
            Paragraph(item["gst"], styles["InvCell"]),
            Paragraph(fmt_decimal(item["qty"]), styles["InvCellRight"]),
            Paragraph(money(item["rate"]), styles["InvCellRight"]),
            Paragraph(money(item["amount"]), styles["InvCellRight"]),
            Paragraph(money(item["cgst"]), styles["InvCellRight"]),
            Paragraph(money(item["sgst"]), styles["InvCellRight"]),
            Paragraph(money(item["total"]), styles["InvCellRight"]),
        ])
    item_table = Table(item_data, colWidths=[14*mm, 40*mm, 22*mm, 12*mm, 14*mm, 20*mm, 22*mm, 18*mm, 18*mm, 22*mm], repeatRows=1)
    item_table.setStyle(TableStyle([
        ("BOX", (0,0), (-1,-1), 0.5, DARK_BLUE),
        ("GRID", (0,0), (-1,-1), 0.5, DARK_BLUE),
        ("BACKGROUND", (0,0), (-1,0), DARK_BLUE),
        ("TEXTCOLOR", (0,0), (-1,0), colors.white),
        ("VALIGN", (0,0), (-1,-1), "MIDDLE"),
        ("LEFTPADDING", (0,0), (-1,-1), 2),
        ("RIGHTPADDING", (0,0), (-1,-1), 2),
        ("TOPPADDING", (0,0), (-1,-1), 2),
        ("BOTTOMPADDING", (0,0), (-1,-1), 2),
    ]))
    story.append(item_table)

    story.append(Spacer(1, 5*mm))

    # Summary box
    discount = money_amount(data["discount"])
    discount_display = f"({money(discount)})" if discount > 0 else money(ZERO)
    summary_data = [
        [Paragraph("Summary", ParagraphStyle("SH", parent=styles["InvCell"], fontName=bold, fontSize=9, textColor=DARK_BLUE)), ""],
        [Paragraph("Amount", styles["InvCell"]), Paragraph(money(data["subtotal"]), styles["InvCellRight"])],
        [Paragraph("CGST", styles["InvCell"]), Paragraph(money(data["cgst_total"]), styles["InvCellRight"])],
        [Paragraph("SGST", styles["InvCell"]), Paragraph(money(data["sgst_total"]), styles["InvCellRight"])],
        [Paragraph("Discount", styles["InvCell"]), Paragraph(discount_display, styles["InvCellRight"])],
        [Paragraph("Grand Total", ParagraphStyle("GT", parent=styles["InvCell"], fontName=bold, fontSize=10, textColor=DARK_BLUE)), Paragraph(money(data["grand_total"]), ParagraphStyle("GTR", parent=styles["InvCellRight"], fontName=bold, fontSize=10, textColor=DARK_BLUE))],
    ]
    summary_table = Table(summary_data, colWidths=[60*mm, 50*mm])
    summary_table.setStyle(TableStyle([
        ("BOX", (0,0), (-1,-1), 1, DARK_BLUE),
        ("INNERGRID", (0,0), (-1,-1), 0.5, DARK_BLUE),
        ("BACKGROUND", (0,0), (-1,0), LIGHT),
        ("BACKGROUND", (0,-1), (-1,-1), HexColor("#e8e0c8")),
        ("VALIGN", (0,0), (-1,-1), "MIDDLE"),
        ("LEFTPADDING", (0,0), (-1,-1), 5),
        ("RIGHTPADDING", (0,0), (-1,-1), 5),
        ("TOPPADDING", (0,0), (-1,-1), 4),
        ("BOTTOMPADDING", (0,0), (-1,-1), 4),
    ]))
    story.append(summary_table)

    story.append(Spacer(1, 4*mm))
    story.append(Paragraph("Amount in Words:", ParagraphStyle("AWL", parent=styles["InvSection"], fontSize=10, textColor=DARK_BLUE)))
    story.append(Paragraph(escape(data["amount_in_words"]), ParagraphStyle("AWV", parent=styles["InvWords"], fontSize=9, textColor=DARK_BLUE)))

    story.append(Spacer(1, 5*mm))
    story.append(Paragraph("TERMS AND CONDITIONS", ParagraphStyle("TC", parent=styles["InvSection"], fontSize=10, textColor=DARK_BLUE)))
    for term in data["terms"]:
        story.append(Paragraph(escape(term), ParagraphStyle("TT", parent=styles["InvTerm"], fontSize=8, leading=11, textColor=HexColor("#555555"))))

    story.append(Spacer(1, 6*mm))
    story.append(Paragraph("This is a Proforma Invoice and not a Tax Invoice.", styles["InvSmall"]))
    story.append(Paragraph("Thank you for your business.", styles["InvSmall"]))

    doc.build(story, onFirstPage=add_page_number, onLaterPages=add_page_number)


# ==================== MAIN BUILDER ====================
def build_invoice(data, path, template="A"):
    """Build invoice with selected template."""
    if template == "B":
        build_template_b(data, path)
    elif template == "C":
        build_template_c(data, path)
    else:
        build_template_a(data, path)
