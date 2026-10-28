"""Render the current advisor draft as a compact, paginated PDF."""

from io import BytesIO
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import BaseDocTemplate, Frame, FrameBreak, PageTemplate, Paragraph, Spacer

from self_improving_ai.agents.briefing.schemas import BriefExportRequest


def render_brief_pdf(request: BriefExportRequest) -> bytes:
    brief = request.brief
    valid_refs = {source.id for source in brief.sources}
    if any(ref not in valid_refs for section in brief.sections for item in section.items for ref in item.source_ids):
        raise ValueError("An evidence reference is missing from the source index.")
    stream = BytesIO()
    width, height = A4
    margin, gap = 32, 22
    column_width = (width - 2 * margin - gap) / 2
    styles = {
        "name": ParagraphStyle("name", fontName="Helvetica-Bold", fontSize=17, leading=21, textColor=colors.HexColor("#1a1f2e")),
        "meta": ParagraphStyle("meta", fontName="Helvetica", fontSize=8, leading=11, textColor=colors.HexColor("#586174")),
        "focus": ParagraphStyle("focus", fontName="Helvetica-Bold", fontSize=10, leading=13, spaceBefore=5),
        "section": ParagraphStyle("section", fontName="Helvetica-Bold", fontSize=10, leading=13, textColor=colors.HexColor("#3563e9"), spaceBefore=8, spaceAfter=5, keepWithNext=True),
        "item": ParagraphStyle("item", fontName="Helvetica-Bold", fontSize=8.5, leading=11, spaceBefore=4, spaceAfter=2, keepWithNext=True),
        "body": ParagraphStyle("body", fontName="Helvetica", fontSize=8, leading=10.5, textColor=colors.HexColor("#3d4556"), spaceAfter=3),
        "ref": ParagraphStyle("ref", fontName="Helvetica", fontSize=7, leading=9, textColor=colors.HexColor("#586174"), spaceAfter=3),
    }

    def paragraph(text, style="body"):
        # Escape advisor content before passing it to ReportLab's markup parser.
        text = text.replace("\u2014", " - ").replace("\u2013", "-").replace("\u00b7", " | ")
        return Paragraph(escape(text).replace("\n", "<br/>"), styles[style])

    status = "Marked reviewed in this browser" if request.reviewed_at else "DRAFT - NOT REVIEWED"
    header = [paragraph(brief.client_name + " | Meeting Brief", "name"),
              paragraph(f"{brief.contact} | {brief.meeting_date} at {brief.meeting_time.strftime('%H:%M')} | New York", "meta"),
              paragraph(brief.focus, "focus"),
              paragraph(f"{status} | Revision {request.revision}" + (" | Advisor edited" if request.edited else ""), "meta")]
    header_height = sum(item.wrap(width - margin * 2, height)[1] for item in header) + 22
    bottom = 42
    frame_height = height - margin - header_height - bottom

    def decorate(canvas, document):
        canvas.saveState()
        cursor = height - margin
        for item in header:
            _, item_height = item.wrap(width - 2 * margin, height)
            item.drawOn(canvas, margin, cursor - item_height)
            cursor -= item_height + 2
        canvas.setStrokeColor(colors.HexColor("#e2e5ea"))
        canvas.line(margin, height - margin - header_height + 8, width - margin, height - margin - header_height + 8)
        canvas.setFont("Helvetica", 7)
        canvas.setFillColor(colors.HexColor("#586174"))
        canvas.drawString(margin, 24, f"Synthetic demo | Mock records through {brief.data_as_of} | No live market data")
        canvas.drawRightString(width - margin, 24, f"Page {document.page}")
        canvas.restoreState()

    document = BaseDocTemplate(stream, pagesize=A4, title=f"{brief.client_name} - Meeting Brief", author="Wealth Management Copilot")
    frames = [Frame(margin, bottom, column_width, frame_height, leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0),
              Frame(margin + column_width + gap, bottom, column_width, frame_height, leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0)]
    document.addPageTemplates(PageTemplate(id="brief", frames=frames, onPage=decorate))
    story = []

    def section_content(section):
        story.append(paragraph(section.title, "section"))
        if not section.items:
            story.append(paragraph("No open items are recorded."))
        for item in section.items:
            story.append(paragraph(item.title, "item"))
            story.append(paragraph(item.text))
            if item.why:
                story.append(paragraph("Why now: " + item.why))
            if item.question:
                story.append(paragraph("Ask: " + item.question))
            if item.source_ids:
                story.append(paragraph(" ".join(f"[{ref}]" for ref in item.source_ids), "ref"))

    for section in brief.sections[:3]:
        section_content(section)
    story.append(paragraph("Relevant News", "section"))
    for news in brief.news:
        story.append(paragraph(news.headline + f" [{news.id}]", "item"))
        story.append(paragraph(news.relevance))
    story.append(Spacer(1, 4))
    story.append(paragraph("Source Index", "section"))
    for source in brief.sources:
        story.append(paragraph(f"[{source.id}] {source.title} ({source.date or 'date not supplied'})", "ref"))
    story.append(FrameBreak())
    for section in brief.sections[3:]:
        section_content(section)
    if request.reviewed_at:
        story.append(paragraph("Review recorded: " + request.reviewed_at.isoformat(), "ref"))
    document.build(story)
    return stream.getvalue()
