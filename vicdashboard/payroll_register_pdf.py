"""Landscape PDF builder for the payroll register."""

from __future__ import annotations

from io import BytesIO

from reportlab.lib import colors
from reportlab.lib.pagesizes import landscape, legal
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import (
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from .po_pdf import _ensure_unicode_fonts
from .payroll_register import LEAF_COLUMNS, YELLOW_LEAF_KEYS

BLUE_HEADER = colors.Color(0.72, 0.85, 0.95)
YELLOW_HEADER = colors.Color(1.0, 0.95, 0.55)
RED_HEADER = colors.Color(0.75, 0.22, 0.22)
RED_TEXT = colors.Color(0.75, 0.12, 0.12)
BLUE_TEXT = colors.Color(0.10, 0.25, 0.75)
GRID = colors.Color(0.35, 0.35, 0.35)
LIGHT_ROW = colors.Color(0.96, 0.97, 0.98)


def _money_str(value) -> str:
    try:
        n = float(value or 0)
    except (TypeError, ValueError):
        n = 0.0
    return f'{n:,.2f}'


def _num_str(value) -> str:
    try:
        n = float(value or 0)
    except (TypeError, ValueError):
        n = 0.0
    if abs(n - int(n)) < 1e-9:
        return str(int(n))
    return f'{n:.2f}'


def build_payroll_register_pdf(register: dict) -> bytes:
    font_reg, font_bold = _ensure_unicode_fonts()
    page_size = landscape(legal)
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=page_size,
        leftMargin=0.35 * inch,
        rightMargin=0.35 * inch,
        topMargin=0.35 * inch,
        bottomMargin=0.4 * inch,
    )
    page_width = page_size[0] - doc.leftMargin - doc.rightMargin

    title_style = ParagraphStyle(
        'RegisterTitle',
        fontName=font_bold,
        fontSize=11,
        alignment=1,
        spaceAfter=6,
    )
    cell_style = ParagraphStyle(
        'RegisterCell',
        fontName=font_reg,
        fontSize=5.5,
        leading=7,
    )
    cell_bold = ParagraphStyle(
        'RegisterCellBold',
        fontName=font_bold,
        fontSize=5.5,
        leading=7,
    )
    header_style = ParagraphStyle(
        'RegisterHeader',
        fontName=font_bold,
        fontSize=5,
        leading=6,
        alignment=1,
    )

    leaf_keys = [k for k, _ in LEAF_COLUMNS]
    leaf_labels = [label for _, label in LEAF_COLUMNS]
    n_cols = len(leaf_keys)

    # Column widths — name wider, others compact
    weights = []
    for key, _ in LEAF_COLUMNS:
        if key == 'name':
            weights.append(3.2)
        elif key == 'no':
            weights.append(0.55)
        elif key in ('sil_on_hand', 'late_ut_mins'):
            weights.append(0.85)
        else:
            weights.append(0.95)
    total_w = sum(weights)
    col_widths = [page_width * (w / total_w) for w in weights]

    # Group header row
    group_row = []
    group_spans = []
    col_idx = 0
    for label, start_key, span in register['group_headers']:
        start = leaf_keys.index(start_key)
        # pad if gap
        while col_idx < start:
            group_row.append('')
            col_idx += 1
        group_row.append(Paragraph(label, header_style) if label else '')
        for _ in range(span - 1):
            group_row.append('')
        if span > 1 and label:
            group_spans.append(('SPAN', (start, 0), (start + span - 1, 0)))
        col_idx = start + span
    while len(group_row) < n_cols:
        group_row.append('')

    sub_row = [Paragraph(lbl, header_style) for lbl in leaf_labels]

    data = [group_row, sub_row]
    money_keys = {
        'daily_rate', 'hourly_rate', 'reg_total', 'ot_reg_amount', 'ot_sun_amount',
        'ot_total_amount', 'snwd_amount', 'snw_sun_amount', 'rh_amount', 'gross_pay',
        'philhealth', 'sss', 'hdmf', 'hdmf_loan', 'sss_loan', 'late_ut_amount',
        'total_deductions', 'net_pay',
    }
    hours_keys = {'ot_reg_hours', 'ot_sun_hours', 'ot_total_hours', 'sil_on_hand'}

    def format_cell(key, value, bold=False):
        style = cell_bold if bold else cell_style
        if key == 'name':
            return Paragraph(str(value or ''), style)
        if key in money_keys:
            return Paragraph(_money_str(value), style)
        if key in hours_keys:
            return Paragraph(_num_str(value), style)
        return Paragraph(str(value if value is not None else ''), style)

    for row in register['rows']:
        data.append([format_cell(k, row.get(k)) for k in leaf_keys])

    totals = register['totals']
    data.append([format_cell(k, totals.get(k), bold=True) for k in leaf_keys])

    table = Table(data, colWidths=col_widths, repeatRows=2)
    style_cmds = [
        ('FONTNAME', (0, 0), (-1, 1), font_bold),
        ('FONTSIZE', (0, 0), (-1, -1), 5.5),
        ('ALIGN', (0, 0), (-1, 1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('GRID', (0, 0), (-1, -1), 0.4, GRID),
        ('BACKGROUND', (0, 0), (-1, 0), BLUE_HEADER),
        ('BACKGROUND', (0, 1), (-1, 1), colors.white),
        ('TOPPADDING', (0, 0), (-1, -1), 2),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
        ('LEFTPADDING', (0, 0), (-1, -1), 1),
        ('RIGHTPADDING', (0, 0), (-1, -1), 1),
        ('LINEABOVE', (0, -1), (-1, -1), 1.5, GRID),
        ('BACKGROUND', (0, -1), (-1, -1), LIGHT_ROW),
    ]
    style_cmds.extend(group_spans)

    # Color group headers
    for label, start_key, span in register['group_headers']:
        start = leaf_keys.index(start_key)
        end = start + span - 1
        if label == 'DEDUCTIONS':
            style_cmds.append(('BACKGROUND', (start, 0), (end, 0), RED_HEADER))
            style_cmds.append(('TEXTCOLOR', (start, 0), (end, 0), colors.white))
        elif label:
            style_cmds.append(('BACKGROUND', (start, 0), (end, 0), BLUE_HEADER))

    for key in YELLOW_LEAF_KEYS:
        if key in leaf_keys:
            i = leaf_keys.index(key)
            style_cmds.append(('BACKGROUND', (i, 1), (i, 1), YELLOW_HEADER))

    # Deduction amount columns red text; net blue
    for key in ('philhealth', 'sss', 'hdmf', 'hdmf_loan', 'sss_loan', 'late_ut_amount', 'total_deductions'):
        i = leaf_keys.index(key)
        style_cmds.append(('TEXTCOLOR', (i, 2), (i, -1), RED_TEXT))
    net_i = leaf_keys.index('net_pay')
    style_cmds.append(('TEXTCOLOR', (net_i, 2), (net_i, -1), BLUE_TEXT))

    table.setStyle(TableStyle(style_cmds))

    story = [
        Paragraph(register['meta']['period_title'], title_style),
        table,
        Spacer(1, 18),
    ]

    sig_label = ParagraphStyle(
        'SigLabel',
        fontName=font_bold,
        fontSize=7,
        alignment=1,
        spaceAfter=4,
    )
    sig_name = ParagraphStyle(
        'SigName',
        fontName=font_bold,
        fontSize=7,
        alignment=1,
        spaceBefore=14,
    )
    sig_title = ParagraphStyle(
        'SigTitle',
        fontName=font_reg,
        fontSize=6,
        alignment=1,
    )

    sig_row = []
    for sig in register['signatures']:
        parts = [
            Paragraph(sig['label'], sig_label),
            Paragraph('_________________________', sig_name),
            Paragraph(sig['name'], sig_name),
        ]
        if sig.get('title'):
            parts.append(Paragraph(sig['title'], sig_title))
        # Use a nested one-column table instead of KeepTogether-in-cell (avoids huge min height).
        nested = Table([[p] for p in parts], colWidths=[page_width / 4.0 - 6])
        nested.setStyle(TableStyle([
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('TOPPADDING', (0, 0), (-1, -1), 1),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 1),
        ]))
        sig_row.append(nested)

    sig_table = Table([sig_row], colWidths=[page_width / 4.0] * 4)
    sig_table.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('LEFTPADDING', (0, 0), (-1, -1), 3),
        ('RIGHTPADDING', (0, 0), (-1, -1), 3),
    ]))
    story.append(sig_table)

    net_total = _money_str(totals.get('net_pay'))
    story.append(Spacer(1, 10))
    story.append(Paragraph(
        f'<b>TOTAL NET PAY: &#8369;{net_total}</b>',
        ParagraphStyle('NetCallout', fontName=font_bold, fontSize=9, textColor=BLUE_TEXT, alignment=2),
    ))

    doc.build(story)
    return buffer.getvalue()
