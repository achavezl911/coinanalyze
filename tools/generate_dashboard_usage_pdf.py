from __future__ import annotations

import html
import re
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import LETTER
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    ListFlowable,
    ListItem,
    PageBreak,
    Paragraph,
    Preformatted,
    SimpleDocTemplate,
    Spacer,
)

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "docs" / "USO_DASHBOARD.md"
OUTPUT_DIR = ROOT / "output" / "pdf"
STATIC_DIR = ROOT / "static"
OUTPUT_PDF = OUTPUT_DIR / "guia_uso_dashboard.pdf"
STATIC_PDF = STATIC_DIR / "guia_uso_dashboard.pdf"


def register_fonts() -> tuple[str, str]:
    regular = Path(r"C:\Windows\Fonts\arial.ttf")
    bold = Path(r"C:\Windows\Fonts\arialbd.ttf")
    if regular.exists() and bold.exists():
        pdfmetrics.registerFont(TTFont("ManualRegular", str(regular)))
        pdfmetrics.registerFont(TTFont("ManualBold", str(bold)))
        return "ManualRegular", "ManualBold"
    return "Helvetica", "Helvetica-Bold"


FONT, FONT_BOLD = register_fonts()
PAGE_W, PAGE_H = LETTER


def make_styles() -> dict[str, ParagraphStyle]:
    sample = getSampleStyleSheet()
    return {
        "title": ParagraphStyle(
            "Title",
            parent=sample["Title"],
            fontName=FONT_BOLD,
            fontSize=26,
            leading=31,
            alignment=TA_CENTER,
            textColor=colors.HexColor("#0B1220"),
            spaceAfter=18,
        ),
        "subtitle": ParagraphStyle(
            "Subtitle",
            parent=sample["Normal"],
            fontName=FONT,
            fontSize=11,
            leading=16,
            alignment=TA_CENTER,
            textColor=colors.HexColor("#475569"),
            spaceAfter=8,
        ),
        "h1": ParagraphStyle(
            "H1",
            parent=sample["Heading1"],
            fontName=FONT_BOLD,
            fontSize=19,
            leading=24,
            textColor=colors.HexColor("#0F172A"),
            spaceBefore=14,
            spaceAfter=8,
        ),
        "h2": ParagraphStyle(
            "H2",
            parent=sample["Heading2"],
            fontName=FONT_BOLD,
            fontSize=13.5,
            leading=18,
            textColor=colors.HexColor("#1D4ED8"),
            spaceBefore=10,
            spaceAfter=5,
        ),
        "body": ParagraphStyle(
            "Body",
            parent=sample["BodyText"],
            fontName=FONT,
            fontSize=9.6,
            leading=13.7,
            textColor=colors.HexColor("#111827"),
            alignment=TA_LEFT,
            spaceAfter=5,
        ),
        "bullet": ParagraphStyle(
            "Bullet",
            parent=sample["BodyText"],
            fontName=FONT,
            fontSize=9.2,
            leading=12.8,
            textColor=colors.HexColor("#111827"),
            leftIndent=0,
            firstLineIndent=0,
        ),
        "code": ParagraphStyle(
            "Code",
            parent=sample["Code"],
            fontName="Courier",
            fontSize=8.2,
            leading=10.5,
            textColor=colors.HexColor("#0F172A"),
            backColor=colors.HexColor("#F1F5F9"),
            borderColor=colors.HexColor("#CBD5E1"),
            borderWidth=0.4,
            borderPadding=6,
            spaceBefore=4,
            spaceAfter=7,
        ),
        "note": ParagraphStyle(
            "Note",
            parent=sample["BodyText"],
            fontName=FONT,
            fontSize=9.2,
            leading=13,
            textColor=colors.HexColor("#334155"),
            backColor=colors.HexColor("#EFF6FF"),
            borderColor=colors.HexColor("#BFDBFE"),
            borderWidth=0.5,
            borderPadding=7,
            spaceBefore=6,
            spaceAfter=9,
        ),
    }


STYLES = make_styles()


def paragraph(text: str, style: ParagraphStyle = STYLES["body"]) -> Paragraph:
    safe = html.escape(text)
    safe = re.sub(r"`([^`]+)`", r"<font name='Courier'>\1</font>", safe)
    safe = re.sub(r"\*\*([^*]+)\*\*", r"<b>\1</b>", safe)
    return Paragraph(safe, style)


def flush_paragraph(buffer: list[str], story: list[object]) -> None:
    if buffer:
        story.append(paragraph(" ".join(buffer)))
        buffer.clear()


def flush_list(items: list[str], story: list[object], ordered: bool = False) -> None:
    if not items:
        return
    flowables = [
        ListItem(paragraph(item, STYLES["bullet"]), leftIndent=10, bulletColor=colors.HexColor("#2563EB"))
        for item in items
    ]
    story.append(
        ListFlowable(
            flowables,
            bulletType="1" if ordered else "bullet",
            leftIndent=18,
            bulletFontName=FONT_BOLD,
            bulletFontSize=8.5,
            bulletColor=colors.HexColor("#2563EB"),
            spaceAfter=6,
        )
    )
    items.clear()


def markdown_to_story(markdown: str) -> list[object]:
    story: list[object] = []
    paragraph_buffer: list[str] = []
    bullet_items: list[str] = []
    ordered_items: list[str] = []
    code_buffer: list[str] = []
    in_code = False

    lines = markdown.splitlines()
    for line in lines:
        raw = line.rstrip()
        stripped = raw.strip()

        if stripped.startswith("```"):
            if in_code:
                story.append(Preformatted("\n".join(code_buffer), STYLES["code"]))
                code_buffer.clear()
                in_code = False
            else:
                flush_paragraph(paragraph_buffer, story)
                flush_list(bullet_items, story)
                flush_list(ordered_items, story, ordered=True)
                in_code = True
            continue

        if in_code:
            code_buffer.append(raw)
            continue

        if not stripped:
            flush_paragraph(paragraph_buffer, story)
            flush_list(bullet_items, story)
            flush_list(ordered_items, story, ordered=True)
            continue

        if stripped.startswith("# "):
            flush_paragraph(paragraph_buffer, story)
            flush_list(bullet_items, story)
            flush_list(ordered_items, story, ordered=True)
            story.append(Spacer(1, 0.01 * inch))
            story.append(PageBreak())
            continue

        if stripped.startswith("## "):
            flush_paragraph(paragraph_buffer, story)
            flush_list(bullet_items, story)
            flush_list(ordered_items, story, ordered=True)
            story.append(paragraph(stripped[3:].strip(), STYLES["h2"]))
            continue

        if stripped.startswith("- "):
            flush_paragraph(paragraph_buffer, story)
            flush_list(ordered_items, story, ordered=True)
            bullet_items.append(stripped[2:].strip())
            continue

        ordered_match = re.match(r"^\d+\.\s+(.*)$", stripped)
        if ordered_match:
            flush_paragraph(paragraph_buffer, story)
            flush_list(bullet_items, story)
            ordered_items.append(ordered_match.group(1).strip())
            continue

        flush_list(bullet_items, story)
        flush_list(ordered_items, story, ordered=True)
        paragraph_buffer.append(stripped)

    flush_paragraph(paragraph_buffer, story)
    flush_list(bullet_items, story)
    flush_list(ordered_items, story, ordered=True)
    if code_buffer:
        story.append(Preformatted("\n".join(code_buffer), STYLES["code"]))
    return story


def cover(canvas, doc) -> None:
    canvas.saveState()
    canvas.setFillColor(colors.HexColor("#0B1220"))
    canvas.rect(0, 0, PAGE_W, PAGE_H, fill=1, stroke=0)
    canvas.setFillColor(colors.HexColor("#1D4ED8"))
    canvas.rect(0, PAGE_H - 0.34 * inch, PAGE_W, 0.34 * inch, fill=1, stroke=0)
    canvas.setFillColor(colors.white)
    canvas.setFont(FONT_BOLD, 28)
    canvas.drawCentredString(PAGE_W / 2, PAGE_H - 2.45 * inch, "Coinalyze Operator Dashboard")
    canvas.setFont(FONT, 16)
    canvas.drawCentredString(PAGE_W / 2, PAGE_H - 2.88 * inch, "Guia de uso operativo")
    canvas.setFont(FONT, 10.5)
    canvas.setFillColor(colors.HexColor("#CBD5E1"))
    canvas.drawCentredString(PAGE_W / 2, PAGE_H - 3.32 * inch, "Version 1.0 - Dashboard v1.2.5 - 2026-06-30")
    canvas.setFillColor(colors.HexColor("#EFF6FF"))
    canvas.roundRect(1.05 * inch, 4.3 * inch, PAGE_W - 2.1 * inch, 1.3 * inch, 8, fill=1, stroke=0)
    canvas.setFillColor(colors.HexColor("#0F172A"))
    canvas.setFont(FONT_BOLD, 12)
    canvas.drawString(1.3 * inch, 5.18 * inch, "Objetivo")
    canvas.setFont(FONT, 10.5)
    canvas.drawString(1.3 * inch, 4.86 * inch, "Leer el panel con una rutina consistente: salud de datos, flujo,")
    canvas.drawString(1.3 * inch, 4.62 * inch, "microestructura, derivados, contexto diario y Bridge Telegram.")
    canvas.setFillColor(colors.HexColor("#94A3B8"))
    canvas.setFont(FONT, 9)
    canvas.drawCentredString(PAGE_W / 2, 0.65 * inch, "Documento de consulta. No ejecuta ordenes ni reemplaza gestion de riesgo.")
    canvas.restoreState()


def body_page(canvas, doc) -> None:
    canvas.saveState()
    canvas.setFillColor(colors.HexColor("#F8FAFC"))
    canvas.rect(0, 0, PAGE_W, PAGE_H, fill=1, stroke=0)
    canvas.setFillColor(colors.HexColor("#1D4ED8"))
    canvas.rect(0.55 * inch, PAGE_H - 0.55 * inch, PAGE_W - 1.1 * inch, 0.03 * inch, fill=1, stroke=0)
    canvas.setFillColor(colors.HexColor("#64748B"))
    canvas.setFont(FONT, 8.5)
    canvas.drawString(0.55 * inch, 0.36 * inch, "Coinalyze Operator Dashboard - Guia de uso")
    canvas.drawRightString(PAGE_W - 0.55 * inch, 0.36 * inch, f"Pagina {doc.page}")
    canvas.restoreState()


def build_pdf() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    STATIC_DIR.mkdir(parents=True, exist_ok=True)

    story = markdown_to_story(SOURCE.read_text(encoding="utf-8"))
    doc = SimpleDocTemplate(
        str(OUTPUT_PDF),
        pagesize=LETTER,
        rightMargin=0.62 * inch,
        leftMargin=0.62 * inch,
        topMargin=0.68 * inch,
        bottomMargin=0.62 * inch,
        title="Guia de uso - Coinalyze Operator Dashboard",
        author="Coinalyze Operator Dashboard",
        subject="Uso operativo del dashboard",
    )
    doc.build(story, onFirstPage=cover, onLaterPages=body_page)
    STATIC_PDF.write_bytes(OUTPUT_PDF.read_bytes())
    print(f"Wrote {OUTPUT_PDF}")
    print(f"Wrote {STATIC_PDF}")


if __name__ == "__main__":
    build_pdf()
