"""Thesis reports: CSV / PDF export of a thesis' history and the archive of concluded theses."""
import csv
import io
from datetime import datetime, timezone

from superviseme.models import (
    Meeting,
    MeetingNote,
    Thesis,
    Thesis_Status,
    Thesis_Supervisor,
    Thesis_Update,
    Todo,
    User_mgmt,
)


def fmt_ts(ts, with_time=False):
    if not ts:
        return ""
    return datetime.fromtimestamp(ts, timezone.utc).strftime("%Y-%m-%d %H:%M" if with_time else "%Y-%m-%d")


def latest_status(thesis):
    row = Thesis_Status.query.filter_by(thesis_id=thesis.id).order_by(Thesis_Status.updated_at.desc()).first()
    return row.status if row else None


def is_concluded(thesis):
    return bool(thesis.frozen) or (latest_status(thesis) or "").strip().lower() == "completed"


def safe_cell(value):
    """Neutralise spreadsheet formula injection (cells starting with = + - @ are prefixed with a quote)."""
    value = "" if value is None else str(value)
    return "'" + value if value[:1] in ("=", "+", "-", "@", "\t", "\r") else value


def _name(user_id):
    u = User_mgmt.query.get(user_id) if user_id else None
    return f"{u.name or ''} {u.surname or ''}".strip() if u else ""


def _in_range(ts, since, until):
    if ts is None:
        return since is None and until is None
    return (since is None or ts >= since) and (until is None or ts < until)


def thesis_report(thesis, since=None, until=None):
    """Plain-data snapshot of a thesis. ``since``/``until`` are unix timestamps (until is exclusive)."""
    student = User_mgmt.query.get(thesis.author_id) if thesis.author_id else None
    sups = Thesis_Supervisor.query.filter_by(thesis_id=thesis.id).all()
    rows = []  # (date_ts, kind, author, title, status, detail)
    for u in Thesis_Update.query.filter_by(thesis_id=thesis.id).all():
        if _in_range(u.created_at, since, until):
            rows.append((u.created_at, "update", _name(u.author_id), u.update_type, u.status, u.content))
    for t in Todo.query.filter_by(thesis_id=thesis.id).all():
        if _in_range(t.created_at, since, until):
            rows.append((t.created_at, "task", _name(t.author_id), t.title, t.status, t.description or ""))
    for n in MeetingNote.query.filter_by(thesis_id=thesis.id).all():
        if _in_range(n.created_at, since, until):
            rows.append((n.created_at, "meeting note", _name(n.author_id), n.title, "", n.content))
    for m in Meeting.query.filter_by(thesis_id=thesis.id).all():
        if _in_range(m.start_ts, since, until):
            rows.append((m.start_ts, "meeting", _name(m.supervisor_id), m.title, m.status, m.location or ""))
    for m in thesis.milestones:
        if _in_range(m.due_date, since, until):
            rows.append((m.due_date, "milestone", "", m.title, m.status, m.description or ""))
    for c in thesis.checklist:
        if c.due_date is None or _in_range(c.due_date, since, until):
            rows.append((c.due_date, "checklist", "", c.title, c.status, ""))
    for d in thesis.documents:
        for v in d.versions:
            if _in_range(v.created_at, since, until):
                rows.append((v.created_at, "document", _name(v.uploaded_by), f"{d.title} v{v.version}", "", v.note or ""))
    rows.sort(key=lambda r: (r[0] is None, r[0] or 0))
    return {
        "thesis": thesis, "student": student, "supervisors": [(User_mgmt.query.get(s.supervisor_id), s.role) for s in sups],
        "status": latest_status(thesis), "rows": rows, "since": since, "until": until,
        "generated": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
    }


def report_csv(data):
    buf = io.StringIO()
    w = csv.writer(buf)
    t = data["thesis"]
    w.writerow(["thesis", "student", "date", "type", "author", "title", "status", "detail"])
    student = f"{data['student'].name} {data['student'].surname}" if data["student"] else ""
    for ts, kind, author, title, status, detail in data["rows"]:
        w.writerow([safe_cell(x) for x in (t.title, student, fmt_ts(ts), kind, author, title, status, detail)])
    return buf.getvalue()


def activity_csv(reports):
    """One CSV for several theses (a supervisor's period report)."""
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["thesis", "student", "status", "date", "type", "author", "title", "detail"])
    for data in reports:
        t = data["thesis"]
        student = f"{data['student'].name} {data['student'].surname}" if data["student"] else ""
        for ts, kind, author, title, status, detail in data["rows"]:
            w.writerow([safe_cell(x) for x in (t.title, student, data["status"] or "", fmt_ts(ts), kind, author, title, detail)])
    return buf.getvalue()


def report_pdf(data):
    from xml.sax.saxutils import escape

    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.lib.units import cm
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

    styles = getSampleStyleSheet()
    small = styles["BodyText"].clone("small", fontSize=8, leading=10)
    t = data["thesis"]
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=1.6 * cm, rightMargin=1.6 * cm, topMargin=1.6 * cm, bottomMargin=1.6 * cm,
                            title=f"Report - {t.title}")
    story = [Paragraph(escape(t.title), styles["Title"])]
    meta = []
    if data["student"]:
        meta.append(f"Student: {escape(data['student'].name or '')} {escape(data['student'].surname or '')}")
    for u, role in data["supervisors"]:
        if u:
            meta.append(f"{'Co-supervisor' if role == 'co_supervisor' else 'Supervisor'}: {escape(u.name or '')} {escape(u.surname or '')}")
    meta.append(f"Status: {escape(data['status'] or 'n/a')}")
    if data["since"] or data["until"]:
        meta.append(f"Period: {fmt_ts(data['since']) or '…'} → {fmt_ts(data['until']) or '…'}")
    meta.append(f"Generated: {data['generated']}")
    story += [Paragraph("<br/>".join(meta), styles["BodyText"]), Spacer(1, 0.4 * cm)]
    table = [["Date", "Type", "Author", "Title / detail", "Status"]]
    for ts, kind, author, title, status, detail in data["rows"]:
        text = f"<b>{escape(title or '')}</b>" + (f"<br/>{escape((detail or '')[:400])}" if detail else "")
        table.append([fmt_ts(ts), kind, Paragraph(escape(author), small), Paragraph(text, small), status])
    if len(table) == 1:
        story.append(Paragraph("No activity recorded in this period.", styles["BodyText"]))
    else:
        tb = Table(table, colWidths=[2.0 * cm, 2.2 * cm, 3.0 * cm, 8.6 * cm, 2.0 * cm], repeatRows=1)
        tb.setStyle(TableStyle([("FONTSIZE", (0, 0), (-1, -1), 8), ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#4e73df")),
                                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white), ("VALIGN", (0, 0), (-1, -1), "TOP"),
                                ("GRID", (0, 0), (-1, -1), 0.25, colors.lightgrey)]))
        story.append(tb)
    doc.build(story)
    return buf.getvalue()


def theses_for_reports(user):
    """Theses a staff member can report on (admin: all)."""
    if user.user_type == "admin":
        return Thesis.query.order_by(Thesis.created_at.desc()).all()
    ids = {r.thesis_id for r in Thesis_Supervisor.query.filter_by(supervisor_id=user.id)}
    q = Thesis.query.filter(Thesis.id.in_(ids)) if ids else Thesis.query.filter(False)
    return q.order_by(Thesis.created_at.desc()).all()
