"""Purchase Order PDF builder — Long Bond Paper (8.5in × 13in)."""
from __future__ import annotations

from io import BytesIO
from pathlib import Path

from django.conf import settings
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.pdfgen import canvas
from reportlab.platypus import (
    BaseDocTemplate,
    Frame,
    KeepTogether,
    NextPageTemplate,
    PageTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
)
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.units import cm
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image, PageBreak
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from reportlab.lib.enums import TA_RIGHT, TA_CENTER, TA_LEFT
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
import os
from django.conf import settings
from datetime import datetime

# Long Bond Paper only
PAGE_WIDTH = 8.5 * inch
PAGE_HEIGHT = 13 * inch
PAGE_SIZE = (PAGE_WIDTH, PAGE_HEIGHT)

BRAND = colors.HexColor('#0b3f73')
MUTED = colors.HexColor('#667085')
INK = colors.HexColor('#1d2939')
LINE = colors.HexColor('#d0d5dd')
SOFT = colors.HexColor('#fbfcfd')

SIDE_MARGIN = 0.45 * inch
# Gap between header image and body on page 1
HEADER_CONTENT_GAP = 0.28 * inch
# Extra gap on continued pages so table/content never touches the header
CONTINUATION_GAP = 0.42 * inch
FOOTER_CONTENT_GAP = 0.16 * inch


def _static_path(name: str) -> Path | None:
    for base in getattr(settings, 'STATICFILES_DIRS', []) or []:
        candidate = Path(base) / name
        if candidate.is_file():
            return candidate
    static_root = getattr(settings, 'STATIC_ROOT', None)
    if static_root:
        candidate = Path(static_root) / name
        if candidate.is_file():
            return candidate
    fallback = Path(settings.BASE_DIR) / 'static' / name
    return fallback if fallback.is_file() else None


def _money(value) -> str:
    try:
        return f'{float(value):,.2f}'
    except (TypeError, ValueError):
        return '0.00'


def _text(value, fallback='') -> str:
    if value is None:
        return fallback
    text = str(value).strip()
    return text if text else fallback


def _styles():
    base = getSampleStyleSheet()
    return {
        'title': ParagraphStyle(
            'POTitle', parent=base['Normal'], fontName='Helvetica-Bold',
            fontSize=16, textColor=BRAND, leading=20, spaceAfter=2,
        ),
        'subtitle': ParagraphStyle(
            'POSubtitle', parent=base['Normal'], fontName='Helvetica',
            fontSize=8, textColor=MUTED, leading=10, spaceAfter=8,
        ),
        'label': ParagraphStyle(
            'POLabel', parent=base['Normal'], fontName='Helvetica-Bold',
            fontSize=6.5, textColor=MUTED, leading=8, spaceAfter=1,
        ),
        'value': ParagraphStyle(
            'POValue', parent=base['Normal'], fontName='Helvetica-Bold',
            fontSize=9, textColor=INK, leading=12,
        ),
        'section': ParagraphStyle(
            'POSection', parent=base['Normal'], fontName='Helvetica-Bold',
            fontSize=8, textColor=BRAND, leading=11, spaceBefore=8, spaceAfter=4,
        ),
        'body': ParagraphStyle(
            'POBody', parent=base['Normal'], fontName='Helvetica',
            fontSize=8.5, textColor=INK, leading=12,
        ),
        'small': ParagraphStyle(
            'POSmall', parent=base['Normal'], fontName='Helvetica',
            fontSize=7.5, textColor=INK, leading=10,
        ),
        'th': ParagraphStyle(
            'POTh', parent=base['Normal'], fontName='Helvetica-Bold',
            fontSize=6.5, textColor=colors.white, leading=9, alignment=TA_LEFT,
        ),
        'td': ParagraphStyle(
            'POTd', parent=base['Normal'], fontName='Helvetica',
            fontSize=8, textColor=INK, leading=11,
        ),
        'td_center': ParagraphStyle(
            'POTdCenter', parent=base['Normal'], fontName='Helvetica',
            fontSize=8, textColor=INK, leading=11, alignment=TA_CENTER,
        ),
        'td_right': ParagraphStyle(
            'POTdRight', parent=base['Normal'], fontName='Helvetica',
            fontSize=8, textColor=INK, leading=11, alignment=TA_RIGHT,
        ),
        'footnote': ParagraphStyle(
            'POFootnote', parent=base['Normal'], fontName='Helvetica',
            fontSize=7, textColor=MUTED, leading=9, alignment=TA_CENTER, spaceBefore=10,
        ),
        'sign_role': ParagraphStyle(
            'POSignRole', parent=base['Normal'], fontName='Helvetica-Bold',
            fontSize=7.5, textColor=BRAND, leading=10, spaceAfter=6,
        ),
        'sign_line': ParagraphStyle(
            'POSignLine', parent=base['Normal'], fontName='Helvetica',
            fontSize=7, textColor=MUTED, leading=9, spaceBefore=2, spaceAfter=10,
        ),
    }


def _measure_image_height(path: Path | None, max_width: float) -> float:
    if not path:
        return 0
    try:
        from reportlab.lib.utils import ImageReader
        img = ImageReader(str(path))
        iw, ih = img.getSize()
        if iw <= 0:
            return 0
        return (ih / float(iw)) * max_width
    except Exception:
        return 0.85 * inch


class PurchaseOrderPDF:
    def __init__(self, data: dict):
        self.data = data or {}
        self.styles = _styles()
        self.header_path = _static_path('versatec_header.jpg')
        self.footer_path = _static_path('versatec_footer.jpg')
        usable_width = PAGE_WIDTH - (2 * SIDE_MARGIN)
        self.header_h = _measure_image_height(self.header_path, usable_width) or (0.95 * inch)
        self.footer_h = _measure_image_height(self.footer_path, usable_width) or (0.95 * inch)

    def _draw_header_footer(self, c: canvas.Canvas, _doc):
        usable_width = PAGE_WIDTH - (2 * SIDE_MARGIN)

        if self.header_path:
            c.drawImage(
                str(self.header_path),
                SIDE_MARGIN,
                PAGE_HEIGHT - SIDE_MARGIN / 2 - self.header_h,
                width=usable_width,
                height=self.header_h,
                preserveAspectRatio=True,
                mask='auto',
            )
        else:
            c.setFillColor(BRAND)
            c.setFont('Helvetica-Bold', 12)
            c.drawString(SIDE_MARGIN, PAGE_HEIGHT - 0.55 * inch, 'VERSATEC INDUSTRIAL CORPORATION')

        if self.footer_path:
            c.drawImage(
                str(self.footer_path),
                SIDE_MARGIN,
                SIDE_MARGIN / 3,
                width=usable_width,
                height=self.footer_h,
                preserveAspectRatio=True,
                mask='auto',
            )

        c.setStrokeColor(BRAND)
        c.setLineWidth(1.5)
        y_line = PAGE_HEIGHT - SIDE_MARGIN / 2 - self.header_h - 2
        c.line(SIDE_MARGIN, y_line, PAGE_WIDTH - SIDE_MARGIN, y_line)

    def _bottom_margin(self) -> float:
        return SIDE_MARGIN / 3 + self.footer_h + FOOTER_CONTENT_GAP

    def _top_margin(self, continued: bool = False) -> float:
        gap = HEADER_CONTENT_GAP + (CONTINUATION_GAP if continued else 0)
        return SIDE_MARGIN / 2 + self.header_h + gap

    def build(self) -> bytes:
        buffer = BytesIO()
        bottom = self._bottom_margin()
        top_first = self._top_margin(continued=False)
        top_later = self._top_margin(continued=True)
        frame_width = PAGE_WIDTH - 2 * SIDE_MARGIN

        doc = BaseDocTemplate(
            buffer,
            pagesize=PAGE_SIZE,
            leftMargin=SIDE_MARGIN,
            rightMargin=SIDE_MARGIN,
            topMargin=top_first,
            bottomMargin=bottom,
        )

        frame_first = Frame(
            SIDE_MARGIN, bottom, frame_width, PAGE_HEIGHT - top_first - bottom,
            id='first', showBoundary=0,
        )
        frame_later = Frame(
            SIDE_MARGIN, bottom, frame_width, PAGE_HEIGHT - top_later - bottom,
            id='later', showBoundary=0,
        )

        doc.addPageTemplates([
            PageTemplate(id='First', frames=[frame_first], onPage=self._draw_header_footer),
            PageTemplate(id='Later', frames=[frame_later], onPage=self._draw_header_footer),
        ])

        story = [NextPageTemplate('Later')]
        story.extend(self._title_block())
        story.append(Spacer(1, 8))
        story.append(self._parties_table())
        story.append(Spacer(1, 10))
        story.extend(self._items_flowables())
        story.append(Spacer(1, 8))
        story.append(self._totals_table())
        story.append(Spacer(1, 10))
        story.append(KeepTogether(self._payment_block()))
        story.append(Spacer(1, 8))
        story.append(KeepTogether(self._terms_block()))
        story.append(Spacer(1, 14))
        story.append(KeepTogether(self._signatures_block()))
        story.append(Paragraph(
            'This Purchase Order is generated by Versatec Industrial Corporation and is '
            'subject to the terms and conditions stated above.',
            self.styles['footnote'],
        ))

        doc.build(story)
        return buffer.getvalue()

    def _title_block(self):
        d = self.data
        currency = _text(d.get('currency'), 'PHP')
        if currency.upper() == 'OTHER':
            currency = _text(d.get('currency_other'), 'OTHER')
        elif currency.upper() == 'PHP':
            currency = 'PHP / PESO'

        meta = Table(
            [
                [
                    Paragraph('PO NUMBER', self.styles['label']),
                    Paragraph('CURRENCY', self.styles['label']),
                ],
                [
                    Paragraph(_text(d.get('po_number'), 'PO-____'), self.styles['value']),
                    Paragraph(currency, self.styles['value']),
                ],
                [
                    Paragraph('ORDER DATE', self.styles['label']),
                    Paragraph('REQUIRED DELIVERY DATE', self.styles['label']),
                ],
                [
                    Paragraph(_text(d.get('order_date'), '—'), self.styles['value']),
                    Paragraph(_text(d.get('delivery_date'), '—'), self.styles['value']),
                ],
            ],
            colWidths=[2.1 * inch, 2.1 * inch],
        )
        meta.setStyle(TableStyle([
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('LEFTPADDING', (0, 0), (-1, -1), 4),
            ('RIGHTPADDING', (0, 0), (-1, -1), 4),
            ('TOPPADDING', (0, 0), (-1, -1), 1),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
        ]))

        left = [
            Paragraph('PURCHASE ORDER', self.styles['title']),
            Paragraph('Versatec Industrial Corporation', self.styles['subtitle']),
        ]
        wrap = Table([[left, meta]], colWidths=[3.6 * inch, 4.2 * inch])
        wrap.setStyle(TableStyle([
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('LEFTPADDING', (0, 0), (-1, -1), 0),
            ('RIGHTPADDING', (0, 0), (-1, -1), 0),
        ]))
        return [wrap]

    def _party_cell(self, title: str, party: dict):
        party = party or {}
        lines = [
            Paragraph(title.upper(), self.styles['section']),
            Paragraph(f"<b>Company</b>  {_text(party.get('company'), '—')}", self.styles['small']),
            Paragraph(f"<b>Address</b>  {_text(party.get('address'), '—')}", self.styles['small']),
            Paragraph(f"<b>Contact No.</b>  {_text(party.get('contact'), '—')}", self.styles['small']),
            Paragraph(f"<b>Email</b>  {_text(party.get('email'), '—')}", self.styles['small']),
        ]
        inner = Table([[line] for line in lines], colWidths=[3.6 * inch])
        inner.setStyle(TableStyle([
            ('BOX', (0, 0), (-1, -1), 0.7, LINE),
            ('BACKGROUND', (0, 0), (-1, -1), colors.white),
            ('LEFTPADDING', (0, 0), (-1, -1), 8),
            ('RIGHTPADDING', (0, 0), (-1, -1), 8),
            ('TOPPADDING', (0, 0), (-1, -1), 3),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
        ]))
        return inner

    def _parties_table(self):
        buyer = self._party_cell('Buyer', self.data.get('buyer'))
        seller = self._party_cell('Seller', self.data.get('seller'))
        table = Table([[buyer, seller]], colWidths=[3.85 * inch, 3.85 * inch])
        table.setStyle(TableStyle([
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('LEFTPADDING', (0, 0), (-1, -1), 0),
            ('RIGHTPADDING', (0, 0), (0, 0), 6),
            ('LEFTPADDING', (1, 0), (1, 0), 6),
            ('RIGHTPADDING', (1, 0), (1, 0), 0),
        ]))
        return table

    def _items_header_row(self):
        s = self.styles
        return [
            Paragraph('ITEM NO.', s['th']),
            Paragraph('PRODUCT CODE', s['th']),
            Paragraph('DESCRIPTION', s['th']),
            Paragraph('QTY', s['th']),
            Paragraph('UNIT', s['th']),
            Paragraph('UNIT COST', s['th']),
            Paragraph('TOTAL AMOUNT', s['th']),
        ]

    def _item_row(self, item: dict):
        s = self.styles
        return [
            Paragraph(_text(item.get('no'), ''), s['td_center']),
            Paragraph(_text(item.get('code'), ''), s['td']),
            Paragraph(_text(item.get('description'), ''), s['td']),
            Paragraph(_text(item.get('qty'), ''), s['td_center']),
            Paragraph(_text(item.get('unit'), ''), s['td_center']),
            Paragraph(_money(item.get('unit_cost')), s['td_right']),
            Paragraph(_money(item.get('total')), s['td_right']),
        ]

    def _items_table_style(self):
        return TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), BRAND),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('GRID', (0, 0), (-1, -1), 0.6, LINE),
            ('BOX', (0, 0), (-1, -1), 0.8, BRAND),
            ('LEFTPADDING', (0, 0), (-1, -1), 5),
            ('RIGHTPADDING', (0, 0), (-1, -1), 5),
            ('TOPPADDING', (0, 0), (-1, -1), 7),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 7),
            ('BACKGROUND', (0, 1), (-1, -1), colors.white),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, SOFT]),
        ])

    def _items_flowables(self):
        items = self.data.get('items') or []
        if not items:
            items = [{
                'no': '1', 'code': '', 'description': '',
                'qty': '1', 'unit': '', 'unit_cost': 0, 'total': 0,
            }]

        col_widths = [
            0.55 * inch, 1.15 * inch, 2.55 * inch,
            0.55 * inch, 0.55 * inch, 1.1 * inch, 1.15 * inch,
        ]

        data = [self._items_header_row()]
        for item in items:
            data.append(self._item_row(item))

        # repeatRows=1 redraws column headers on every continued page,
        # and the Later page template already adds CONTINUATION_GAP under the header.
        table = Table(data, colWidths=col_widths, repeatRows=1)
        table.setStyle(self._items_table_style())
        return [table]

    def _totals_table(self):
        d = self.data
        rows = [
            ['Subtotal', _money(d.get('subtotal'))],
            ['Tax', _money(d.get('tax'))],
            ['Discount', _money(d.get('discount'))],
            ['Shipping / Other Charges', _money(d.get('shipping'))],
            ['GRAND TOTAL', _money(d.get('grand_total'))],
        ]
        table = Table(rows, colWidths=[2.2 * inch, 1.1 * inch], hAlign='RIGHT')
        table.setStyle(TableStyle([
            ('FONTNAME', (0, 0), (-1, -2), 'Helvetica'),
            ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 8.5),
            ('TEXTCOLOR', (0, 0), (-1, -2), INK),
            ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
            ('LINEBELOW', (0, 0), (-1, -2), 0.4, colors.HexColor('#eaecf0')),
            ('TOPPADDING', (0, 0), (-1, -1), 5),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
            ('LEFTPADDING', (0, 0), (-1, -1), 6),
            ('RIGHTPADDING', (0, 0), (-1, -1), 6),
            ('BACKGROUND', (0, -1), (-1, -1), BRAND),
            ('TEXTCOLOR', (0, -1), (-1, -1), colors.white),
            ('TOPPADDING', (0, -1), (-1, -1), 8),
            ('BOTTOMPADDING', (0, -1), (-1, -1), 8),
        ]))
        return table

    def _boxed_field(self, label: str, value: str, width: float):
        content = [
            Paragraph(label.upper(), self.styles['label']),
            Spacer(1, 3),
            Paragraph(_text(value, ' '), self.styles['body']),
        ]
        t = Table([[content]], colWidths=[width])
        t.setStyle(TableStyle([
            ('BOX', (0, 0), (-1, -1), 0.7, LINE),
            ('BACKGROUND', (0, 0), (-1, -1), SOFT),
            ('LEFTPADDING', (0, 0), (-1, -1), 8),
            ('RIGHTPADDING', (0, 0), (-1, -1), 8),
            ('TOPPADDING', (0, 0), (-1, -1), 8),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ]))
        return t

    def _payment_block(self):
        d = self.data
        blocks = [
            Paragraph('PAYMENT TERMS', self.styles['section']),
            Spacer(1, 2),
        ]
        fields = Table(
            [[
                self._boxed_field('Payment Terms', d.get('payment_terms'), 2.45 * inch),
                self._boxed_field('Payment Method', d.get('payment_method'), 2.45 * inch),
                self._boxed_field('Payment Due Date', d.get('payment_due_date'), 2.45 * inch),
            ]],
            colWidths=[2.55 * inch, 2.55 * inch, 2.55 * inch],
        )
        fields.setStyle(TableStyle([
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('LEFTPADDING', (0, 0), (-1, -1), 3),
            ('RIGHTPADDING', (0, 0), (-1, -1), 3),
        ]))
        blocks.append(fields)
        return blocks

    def _terms_block(self):
        d = self.data
        blocks = [
            Paragraph('TERMS AND CONDITIONS', self.styles['section']),
            Spacer(1, 2),
        ]
        grid = Table(
            [
                [
                    self._boxed_field('Return Policy', d.get('return_policy'), 3.7 * inch),
                    self._boxed_field('Warranty (optional)', d.get('warranty'), 3.7 * inch),
                ],
                [
                    self._boxed_field('Delivery Conditions', d.get('delivery_conditions'), 3.7 * inch),
                    self._boxed_field('Other Terms and Conditions', d.get('other_terms'), 3.7 * inch),
                ],
            ],
            colWidths=[3.85 * inch, 3.85 * inch],
        )
        grid.setStyle(TableStyle([
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('LEFTPADDING', (0, 0), (-1, -1), 3),
            ('RIGHTPADDING', (0, 0), (-1, -1), 3),
            ('TOPPADDING', (0, 0), (-1, -1), 3),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
        ]))
        blocks.append(grid)
        return blocks

    def _signatures_block(self):
        d = self.data
        prepared = d.get('prepared_by') or {}
        approved = d.get('approved_by') or {}

        # Shared row layout so Name / Position / Date align across both columns
        prepared_name = Paragraph(_text(prepared.get('name'), ' '), self.styles['value'])
        prepared_title = Paragraph(_text(prepared.get('title'), ' '), self.styles['small'])
        prepared_date = Paragraph(_text(prepared.get('date'), ' '), self.styles['value'])
        prepared_sig = Paragraph(_text(prepared.get('signature'), ' '), self.styles['value'])

        approved_name = Paragraph(
            _text(approved.get('name'), 'Engr. Arturo I. Davis, PME'),
            self.styles['value'],
        )
        approved_title = Paragraph(
            _text(approved.get('title'), 'President / CEO'),
            self.styles['small'],
        )
        approved_date = Paragraph(_text(approved.get('date'), ' '), self.styles['value'])
        approved_sig = Paragraph(_text(approved.get('signature'), ' '), self.styles['value'])

        rows = [
            [
                Paragraph('PREPARED BY', self.styles['sign_role']),
                Paragraph('APPROVED BY', self.styles['sign_role']),
            ],
            [Spacer(1, 40), Spacer(1, 40)],
            [prepared_sig, approved_sig],
            [prepared_name, approved_name],
            [prepared_title, approved_title],
            [prepared_date, approved_date],
        ]

        table = Table(rows, colWidths=[3.7 * inch, 3.7 * inch])
        table.setStyle(TableStyle([
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('LEFTPADDING', (0, 0), (-1, -1), 4),
            ('RIGHTPADDING', (0, 0), (-1, -1), 4),
            ('TOPPADDING', (0, 0), (-1, 0), 0),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 2),
            ('TOPPADDING', (0, 1), (-1, 1), 0),
            ('BOTTOMPADDING', (0, 1), (-1, 1), 0),
            ('TOPPADDING', (0, 2), (-1, 2), 2),
            ('BOTTOMPADDING', (0, 2), (-1, 2), 4),
            ('TOPPADDING', (0, 3), (-1, 3), 4),
            ('BOTTOMPADDING', (0, 3), (-1, 3), 1),
            ('TOPPADDING', (0, 4), (-1, 4), 1),
            ('BOTTOMPADDING', (0, 4), (-1, 4), 4),
            ('TOPPADDING', (0, 5), (-1, 5), 2),
            ('BOTTOMPADDING', (0, 5), (-1, 5), 0),
        ]))
        return [table]


def build_purchase_order_pdf(data: dict) -> bytes:
    return PurchaseOrderPDF(data).build()


# --- inside po_pdf.py after PurchaseOrderPDF class ---

class QuotationPDF:
    def __init__(self, quotation, lines, total_amount, generated_date, company_name="VERSATEC Industrial Corporation"):
        self.quotation = quotation
        self.lines = lines
        self.total_amount = total_amount
        self.generated_date = generated_date
        self.company_name = company_name
        self.styles = _styles()
        self.header_path = _static_path('versatec_header.jpg')
        self.footer_path = _static_path('versatec_footer.jpg')
        usable_width = PAGE_WIDTH - (2 * SIDE_MARGIN)
        self.header_h = _measure_image_height(self.header_path, usable_width) or (0.95 * inch)
        self.footer_h = _measure_image_height(self.footer_path, usable_width) or (0.95 * inch)

    def _draw_header_footer(self, c, doc):
        usable_width = PAGE_WIDTH - (2 * SIDE_MARGIN)
        if self.header_path:
            c.drawImage(
                str(self.header_path),
                SIDE_MARGIN,
                PAGE_HEIGHT - SIDE_MARGIN / 2 - self.header_h,
                width=usable_width,
                height=self.header_h,
                preserveAspectRatio=True,
                mask='auto',
            )
        else:
            c.setFillColor(BRAND)
            c.setFont('Helvetica-Bold', 12)
            c.drawString(SIDE_MARGIN, PAGE_HEIGHT - 0.55 * inch, 'VERSATEC INDUSTRIAL CORPORATION')

        if self.footer_path:
            c.drawImage(
                str(self.footer_path),
                SIDE_MARGIN,
                SIDE_MARGIN / 3,
                width=usable_width,
                height=self.footer_h,
                preserveAspectRatio=True,
                mask='auto',
            )

        c.setStrokeColor(BRAND)
        c.setLineWidth(1.5)
        y_line = PAGE_HEIGHT - SIDE_MARGIN / 2 - self.header_h - 2
        c.line(SIDE_MARGIN, y_line, PAGE_WIDTH - SIDE_MARGIN, y_line)

    def _bottom_margin(self):
        return SIDE_MARGIN / 3 + self.footer_h + FOOTER_CONTENT_GAP

    def _top_margin(self, continued=False):
        gap = HEADER_CONTENT_GAP + (CONTINUATION_GAP if continued else 0)
        return SIDE_MARGIN / 2 + self.header_h + gap


    def build(self) -> bytes:
        buffer = BytesIO()
        bottom = self._bottom_margin()
        top_first = self._top_margin(continued=False)
        top_later = self._top_margin(continued=True)
        frame_width = PAGE_WIDTH - 2 * SIDE_MARGIN

        doc = BaseDocTemplate(
            buffer,
            pagesize=PAGE_SIZE,
            leftMargin=SIDE_MARGIN,
            rightMargin=SIDE_MARGIN,
            topMargin=top_first,
            bottomMargin=bottom,
        )

        frame_first = Frame(
            SIDE_MARGIN,
            bottom,
            frame_width,
            PAGE_HEIGHT - top_first - bottom,
            id="first",
            showBoundary=0,
        )
        frame_later = Frame(
            SIDE_MARGIN,
            bottom,
            frame_width,
            PAGE_HEIGHT - top_later - bottom,
            id="later",
            showBoundary=0,
        )

        doc.addPageTemplates(
            [
                PageTemplate(
                    id="First", frames=[frame_first], onPage=self._draw_header_footer
                ),
                PageTemplate(
                    id="Later", frames=[frame_later], onPage=self._draw_header_footer
                ),
            ]
        )

        story = [NextPageTemplate("Later")]
        story.extend(self._title_block())
        story.append(Spacer(1, 8))
        story.append(self._customer_block())
        story.append(Spacer(1, 10))
        story.extend(self._items_flowables())
        story.append(Spacer(1, 8))
        story.append(self._totals_table())
        story.append(Spacer(1, 10))
        # Use KeepTogether for multi-element blocks
        story.append(KeepTogether(self._terms_block()))
        story.append(Spacer(1, 14))
        story.append(KeepTogether(self._signatures_block()))
        story.append(
            Paragraph(
                "This Quotation is generated by Versatec Industrial Corporation and is "
                "subject to the terms and conditions stated above.",
                self.styles["footnote"],
            )
        )

        doc.build(story)
        return buffer.getvalue()

    def _title_block(self):
        q = self.quotation
        currency = q.currency or 'PHP'
        if currency.upper() == 'OTHER':
            currency = q.currency_other or 'OTHER'
        elif currency.upper() == 'PHP':
            currency = 'PHP / PESO'

        meta = Table(
            [
                [
                    Paragraph('QUOTATION #', self.styles['label']),
                    Paragraph('CURRENCY', self.styles['label']),
                ],
                [
                    Paragraph(_text(q.quotation_number, 'QT-____'), self.styles['value']),
                    Paragraph(currency, self.styles['value']),
                ],
                [
                    Paragraph('QUOTATION DATE', self.styles['label']),
                    Paragraph('VALID UNTIL', self.styles['label']),
                ],
                [
                    Paragraph(q.quotation_date.strftime('%Y-%m-%d') if q.quotation_date else '—', self.styles['value']),
                    Paragraph(q.valid_until.strftime('%Y-%m-%d') if q.valid_until else '—', self.styles['value']),
                ],
            ],
            colWidths=[2.1 * inch, 2.1 * inch],
        )
        meta.setStyle(TableStyle([
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('LEFTPADDING', (0, 0), (-1, -1), 4),
            ('RIGHTPADDING', (0, 0), (-1, -1), 4),
            ('TOPPADDING', (0, 0), (-1, -1), 1),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
        ]))

        left = [
            Paragraph('QUOTATION', self.styles['title']),
            Paragraph(self.company_name, self.styles['subtitle']),
        ]
        wrap = Table([[left, meta]], colWidths=[3.6 * inch, 4.2 * inch])
        wrap.setStyle(TableStyle([
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('LEFTPADDING', (0, 0), (-1, -1), 0),
            ('RIGHTPADDING', (0, 0), (-1, -1), 0),
        ]))
        return [wrap]

    def _customer_block(self):
        q = self.quotation
        # Build a table similar to the parties table but for customer details
        rows = [
            ['Customer Company', _text(q.customer_company, '—')],
            ['Contact Person', _text(q.customer_contact, '—')],
            ['Address', _text(q.customer_address, '—')],
            ['Email', _text(q.customer_email, '—')],
            ['Phone', _text(q.customer_phone, '—')],
        ]
        # Use a table with two columns, left column bold label, right column value
        t = Table(rows, colWidths=[1.8 * inch, 5.8 * inch])
        t.setStyle(TableStyle([
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (0, -1), 8),
            ('FONTNAME', (1, 0), (1, -1), 'Helvetica'),
            ('FONTSIZE', (1, 0), (1, -1), 8),
            ('TEXTCOLOR', (0, 0), (0, -1), MUTED),
            ('TEXTCOLOR', (1, 0), (1, -1), INK),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
            ('TOPPADDING', (0, 0), (-1, -1), 3),
            ('LEFTPADDING', (0, 0), (-1, -1), 4),
            ('RIGHTPADDING', (0, 0), (-1, -1), 4),
            ('BOX', (0, 0), (-1, -1), 0.7, LINE),
            ('BACKGROUND', (0, 0), (-1, -1), SOFT),
        ]))
        return t

    def _items_header_row(self):
        s = self.styles
        return [
            Paragraph('ITEM NO.', s['th']),
            Paragraph('PRODUCT DESCRIPTION', s['th']),
            Paragraph('QTY', s['th']),
            Paragraph('UNIT', s['th']),
            Paragraph('UNIT PRICE', s['th']),
            Paragraph('TOTAL', s['th']),
        ]

    def _item_row(self, line):
        s = self.styles
        return [
            Paragraph(str(line.item_number), s['td_center']),
            Paragraph(_text(line.product_description, ''), s['td']),
            Paragraph(str(line.quantity), s['td_center']),
            Paragraph(_text(line.unit, ''), s['td_center']),
            Paragraph(f"₱{line.unit_price:.2f}", s['td_right']),
            Paragraph(f"₱{line.total_amount:.2f}", s['td_right']),
        ]

    def _items_table_style(self):
        return TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), BRAND),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('GRID', (0, 0), (-1, -1), 0.6, LINE),
            ('BOX', (0, 0), (-1, -1), 0.8, BRAND),
            ('LEFTPADDING', (0, 0), (-1, -1), 5),
            ('RIGHTPADDING', (0, 0), (-1, -1), 5),
            ('TOPPADDING', (0, 0), (-1, -1), 7),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 7),
            ('BACKGROUND', (0, 1), (-1, -1), colors.white),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, SOFT]),
        ])

    def _items_flowables(self):
        if not self.lines.exists():
            lines = [type('Line', (), {
                'item_number': 1,
                'product_description': 'No items',
                'quantity': 0,
                'unit': '',
                'unit_price': 0,
                'total_amount': 0,
            })()]
        else:
            lines = self.lines

        col_widths = [
            0.55 * inch, 3.2 * inch, 0.55 * inch,
            0.55 * inch, 1.2 * inch, 1.2 * inch,
        ]

        data = [self._items_header_row()]
        for line in lines:
            data.append(self._item_row(line))

        table = Table(data, colWidths=col_widths, repeatRows=1)
        table.setStyle(self._items_table_style())
        return [table]

    def _totals_table(self):
        q = self.quotation
        rows = [
            ['Subtotal', f"₱{q.subtotal:.2f}"],
        ]
        if q.tax:
            rows.append(['Tax', f"₱{q.tax:.2f}"])
        if q.discount:
            rows.append(['Discount', f"-₱{q.discount:.2f}"])
        if q.shipping:
            rows.append(['Shipping', f"₱{q.shipping:.2f}"])
        rows.append(['GRAND TOTAL', f"₱{self.total_amount:.2f}"])

        table = Table(rows, colWidths=[2.2 * inch, 1.1 * inch], hAlign='RIGHT')
        table.setStyle(TableStyle([
            ('FONTNAME', (0, 0), (-1, -2), 'Helvetica'),
            ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 8.5),
            ('TEXTCOLOR', (0, 0), (-1, -2), INK),
            ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
            ('LINEBELOW', (0, 0), (-1, -2), 0.4, colors.HexColor('#eaecf0')),
            ('TOPPADDING', (0, 0), (-1, -1), 5),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
            ('LEFTPADDING', (0, 0), (-1, -1), 6),
            ('RIGHTPADDING', (0, 0), (-1, -1), 6),
            ('BACKGROUND', (0, -1), (-1, -1), BRAND),
            ('TEXTCOLOR', (0, -1), (-1, -1), colors.white),
            ('TOPPADDING', (0, -1), (-1, -1), 8),
            ('BOTTOMPADDING', (0, -1), (-1, -1), 8),
        ]))
        return table

    def _boxed_field(self, label, value, width):
        content = [
            Paragraph(label.upper(), self.styles['label']),
            Spacer(1, 3),
            Paragraph(_text(value, ' '), self.styles['body']),
        ]
        t = Table([[content]], colWidths=[width])
        t.setStyle(TableStyle([
            ('BOX', (0, 0), (-1, -1), 0.7, LINE),
            ('BACKGROUND', (0, 0), (-1, -1), SOFT),
            ('LEFTPADDING', (0, 0), (-1, -1), 8),
            ('RIGHTPADDING', (0, 0), (-1, -1), 8),
            ('TOPPADDING', (0, 0), (-1, -1), 8),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ]))
        return t

    def _terms_block(self):
        q = self.quotation
        terms_data = [
            ['Payment Terms', q.payment_terms],
            ['Delivery Terms', q.delivery_terms],
            ['Warranty', q.warranty],
            ['Other Terms', q.other_terms],
        ]
        # Create a grid of boxed fields, two per row
        # We'll create a 2x2 table with boxed fields
        blocks = []
        # We'll make a simple vertical list of fields
        # For consistency with PO, we'll use the boxed field style
        rows = []
        # Build rows of two fields each
        field_pairs = [
            ('Payment Terms', q.payment_terms),
            ('Delivery Terms', q.delivery_terms),
            ('Warranty', q.warranty),
            ('Other Terms', q.other_terms),
        ]
        # Split into pairs
        row1 = field_pairs[0:2]
        row2 = field_pairs[2:4]
        # Build table rows
        table_data = []
        for row in [row1, row2]:
            cols = []
            for label, value in row:
                cols.append(self._boxed_field(label, value, 3.7 * inch))
            table_data.append(cols)
        grid = Table(table_data, colWidths=[3.85 * inch, 3.85 * inch])
        grid.setStyle(TableStyle([
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('LEFTPADDING', (0, 0), (-1, -1), 3),
            ('RIGHTPADDING', (0, 0), (-1, -1), 3),
            ('TOPPADDING', (0, 0), (-1, -1), 3),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
        ]))
        return [Paragraph('TERMS AND CONDITIONS', self.styles['section']), Spacer(1, 2), grid]

    def _signatures_block(self):
        q = self.quotation
        prepared_name = Paragraph(_text(q.prepared_name, ' '), self.styles['value'])
        prepared_title = Paragraph(_text(q.prepared_title, ' '), self.styles['small'])
        prepared_date = Paragraph(q.prepared_date.strftime('%Y-%m-%d') if q.prepared_date else ' ', self.styles['value'])
        prepared_sig = Paragraph(_text(q.prepared_signature, ' '), self.styles['value'])

        approved_name = Paragraph('Engr. Arturo I. Davis, PME', self.styles['value'])
        approved_title = Paragraph('President / CEO', self.styles['small'])
        approved_date = Paragraph(q.approved_date.strftime('%Y-%m-%d') if q.approved_date else ' ', self.styles['value'])
        approved_sig = Paragraph(_text(q.approved_signature, ' '), self.styles['value'])

        rows = [
            [
                Paragraph('PREPARED BY', self.styles['sign_role']),
                Paragraph('APPROVED BY', self.styles['sign_role']),
            ],
            [Spacer(1, 40), Spacer(1, 40)],
            [prepared_sig, approved_sig],
            [prepared_name, approved_name],
            [prepared_title, approved_title],
            [prepared_date, approved_date],
        ]

        table = Table(rows, colWidths=[3.7 * inch, 3.7 * inch])
        table.setStyle(TableStyle([
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('LEFTPADDING', (0, 0), (-1, -1), 4),
            ('RIGHTPADDING', (0, 0), (-1, -1), 4),
            ('TOPPADDING', (0, 0), (-1, 0), 0),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 2),
            ('TOPPADDING', (0, 1), (-1, 1), 0),
            ('BOTTOMPADDING', (0, 1), (-1, 1), 0),
            ('TOPPADDING', (0, 2), (-1, 2), 2),
            ('BOTTOMPADDING', (0, 2), (-1, 2), 4),
            ('TOPPADDING', (0, 3), (-1, 3), 4),
            ('BOTTOMPADDING', (0, 3), (-1, 3), 1),
            ('TOPPADDING', (0, 4), (-1, 4), 1),
            ('BOTTOMPADDING', (0, 4), (-1, 4), 4),
            ('TOPPADDING', (0, 5), (-1, 5), 2),
            ('BOTTOMPADDING', (0, 5), (-1, 5), 0),
        ]))
        return [table]


# --- Replace the existing build_quotation_pdf with this ---

def build_quotation_pdf(quotation, lines, total_amount, generated_date, company_name="VERSATEC Industrial Corporation"):
    return QuotationPDF(quotation, lines, total_amount, generated_date, company_name).build()
