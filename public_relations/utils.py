"""
public_relations/utils.py
=========================
Binary-stream export utilities for the PR Office module.

Functions
---------
  export_archive_to_excel(queryset)
      Converts a PublicRelationsArchive queryset into a fully structured
      .xlsx binary stream returned as an HttpResponse.

  render_archive_pdf(request, archive_pk)
      Maps a single archive entry into a clean printable PDF via xhtml2pdf,
      returned as an HttpResponse. Falls back gracefully if xhtml2pdf is
      not installed.

Bangla-safety notes
-------------------
  openpyxl stores strings as UTF-8 internally and writes them correctly
  into .xlsx XML. No additional encoding step is needed; the Bangla text
  in CharField/TextField fields round-trips correctly.
"""

import io
import datetime

from django.http import HttpResponse
from django.template.loader import render_to_string

from .models import PublicRelationsArchive


# ---------------------------------------------------------------------------
# Helper: safe cell value (strips NoneType, normalises dates)
# ---------------------------------------------------------------------------

def _safe(val):
    """Return a spreadsheet-safe scalar from a model field value."""
    if val is None:
        return ''
    if isinstance(val, datetime.datetime):
        # openpyxl handles datetime natively; strip timezone awareness for
        # SQLite compatibility (SQLite datetimes may be naive).
        return val.replace(tzinfo=None) if val.tzinfo else val
    if isinstance(val, datetime.date):
        return val
    return str(val)


# ---------------------------------------------------------------------------
# Export 1: Excel (.xlsx) via openpyxl
# ---------------------------------------------------------------------------

def export_archive_to_excel(queryset):
    """
    Build a multi-sheet Excel workbook from a PublicRelationsArchive queryset.

    Sheet 1 — "প্রেস রিলিজ": core archive metadata (one row per entry).
    Sheet 2 — "মিডিয়া কভারেজ": all coverage rows for those entries, with
               a back-reference to the press_release_no.

    Returns
    -------
    HttpResponse
        Content-Type: application/vnd.openxmlformats-officedocument.spreadsheetml.sheet
        Content-Disposition triggers a file-download in the browser.
    """
    try:
        import openpyxl
        from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
        from openpyxl.utils import get_column_letter
    except ImportError:
        return HttpResponse(
            "openpyxl is not installed. Run: pip install openpyxl",
            status=500
        )

    wb = openpyxl.Workbook()

    # ── Shared style helpers ──────────────────────────────────────────────
    HEADER_FILL  = PatternFill("solid", fgColor="1B4F72")   # deep navy
    HEADER_FONT  = Font(bold=True, color="FFFFFF", size=11)
    ALT_FILL     = PatternFill("solid", fgColor="EBF5FB")   # light blue
    BORDER_SIDE  = Side(style='thin', color='CCCCCC')
    CELL_BORDER  = Border(
        left=BORDER_SIDE, right=BORDER_SIDE,
        top=BORDER_SIDE,  bottom=BORDER_SIDE
    )
    WRAP_ALIGN   = Alignment(wrap_text=True, vertical='top')

    def style_header_row(ws, col_count):
        for col in range(1, col_count + 1):
            cell = ws.cell(row=1, column=col)
            cell.fill   = HEADER_FILL
            cell.font   = HEADER_FONT
            cell.border = CELL_BORDER
            cell.alignment = Alignment(horizontal='center', vertical='center', wrap_text=True)

    def style_data_row(ws, row_idx, col_count):
        fill = ALT_FILL if row_idx % 2 == 0 else PatternFill()
        for col in range(1, col_count + 1):
            cell = ws.cell(row=row_idx, column=col)
            cell.fill      = fill
            cell.border    = CELL_BORDER
            cell.alignment = WRAP_ALIGN

    # ── Sheet 1: প্রেস রিলিজ ─────────────────────────────────────────────
    ws1 = wb.active
    ws1.title = "প্রেস রিলিজ"

    headers1 = [
        'ক্রমিক', 'প্রেস রিলিজ নং', 'তারিখ', 'অনুষ্ঠানের নাম',
        'বিভাগ', 'মোট কভারেজ', 'জাতীয়', 'স্থানীয়', 'অনলাইন',
        'মন্তব্য', 'তৈরি করেছেন', 'তৈরির সময়',
    ]
    for col_idx, header in enumerate(headers1, start=1):
        ws1.cell(row=1, column=col_idx, value=header)

    style_header_row(ws1, len(headers1))

    for row_idx, entry in enumerate(queryset.prefetch_related('coverages'), start=2):
        creator = entry.created_by.get_full_name() if entry.created_by else ''
        data = [
            row_idx - 1,
            _safe(entry.press_release_no),
            _safe(entry.press_release_date),
            _safe(entry.event_name),
            _safe(entry.department),
            entry.coverage_count,
            entry.national_count,
            entry.local_count,
            entry.online_count,
            _safe(entry.remarks),
            creator,
            _safe(entry.created_at),
        ]
        for col_idx, val in enumerate(data, start=1):
            ws1.cell(row=row_idx, column=col_idx, value=val)
        style_data_row(ws1, row_idx, len(headers1))

    # Auto-fit column widths (approximate)
    col_widths1 = [6, 18, 14, 45, 20, 12, 10, 10, 10, 30, 20, 20]
    for i, w in enumerate(col_widths1, start=1):
        ws1.column_dimensions[get_column_letter(i)].width = w
    ws1.row_dimensions[1].height = 30
    ws1.freeze_panes = 'A2'

    # ── Sheet 2: মিডিয়া কভারেজ ──────────────────────────────────────────
    ws2 = wb.create_sheet("মিডিয়া কভারেজ")

    headers2 = [
        'ক্রমিক', 'প্রেস রিলিজ নং', 'অনুষ্ঠান', 'মিডিয়া হাউস',
        'মিডিয়া ধরন', 'প্রকাশের তারিখ', 'অনলাইন লিংক',
    ]
    for col_idx, header in enumerate(headers2, start=1):
        ws2.cell(row=1, column=col_idx, value=header)
    style_header_row(ws2, len(headers2))

    serial = 0
    for entry in queryset.prefetch_related('coverages__media_house'):
        for cov in entry.coverages.all():
            serial += 1
            row_idx = serial + 1
            data = [
                serial,
                _safe(entry.press_release_no),
                _safe(entry.event_name),
                _safe(cov.media_house.name),
                cov.media_house.get_media_type_display(),
                _safe(cov.published_date),
                _safe(cov.online_link),
            ]
            for col_idx, val in enumerate(data, start=1):
                ws2.cell(row=row_idx, column=col_idx, value=val)
            style_data_row(ws2, row_idx, len(headers2))

    col_widths2 = [6, 18, 40, 30, 16, 14, 45]
    for i, w in enumerate(col_widths2, start=1):
        ws2.column_dimensions[get_column_letter(i)].width = w
    ws2.row_dimensions[1].height = 30
    ws2.freeze_panes = 'A2'

    # ── Serialise and return ──────────────────────────────────────────────
    buffer = io.BytesIO()
    wb.save(buffer)
    buffer.seek(0)

    timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
    filename  = f"PR_Archive_{timestamp}.xlsx"

    response = HttpResponse(
        buffer.getvalue(),
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response


# ---------------------------------------------------------------------------
# Export 2: PDF via xhtml2pdf
# ---------------------------------------------------------------------------

def render_archive_pdf(request, archive_pk):
    """
    Render a single PublicRelationsArchive entry as a printable PDF document.

    Uses xhtml2pdf to convert a Django HTML template
    (`public_relations/pr_print.html`) into a binary PDF stream.

    Parameters
    ----------
    request     : HttpRequest  – needed for template context (branding etc.)
    archive_pk  : int          – primary key of the archive entry to render

    Returns
    -------
    HttpResponse with content_type='application/pdf'
    """
    try:
        from xhtml2pdf import pisa
    except ImportError:
        return HttpResponse(
            "xhtml2pdf is not installed. Run: pip install xhtml2pdf",
            status=500
        )

    from django.shortcuts import get_object_or_404
    from core.models import SystemSettings

    entry    = get_object_or_404(
        PublicRelationsArchive.objects.prefetch_related('coverages__media_house', 'assets'),
        pk=archive_pk
    )
    settings = SystemSettings.objects.first()

    html_string = render_to_string('public_relations/pr_print.html', {
        'entry':        entry,
        'coverages':    entry.coverages.select_related('media_house').all(),
        'assets':       entry.assets.all(),
        'sys_settings': settings,
    }, request=request)

    buffer = io.BytesIO()
    pisa_status = pisa.CreatePDF(
        html_string,
        dest=buffer,
        encoding='utf-8',
    )

    if pisa_status.err:
        return HttpResponse(
            f"PDF রেন্ডারিং ব্যর্থ হয়েছে। (xhtml2pdf error: {pisa_status.err})",
            status=500
        )

    buffer.seek(0)
    safe_no  = entry.press_release_no.replace('/', '-').replace(' ', '_')
    filename = f"PR_{safe_no}.pdf"

    response = HttpResponse(buffer.getvalue(), content_type='application/pdf')
    response['Content-Disposition'] = f'inline; filename="{filename}"'
    return response
