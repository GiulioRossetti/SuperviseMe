"""Minimal RFC 5545 (iCalendar) writer for meetings."""
from datetime import datetime, timezone


def _esc(text):
    return (str(text or "").replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,")
            .replace("\r\n", "\\n").replace("\n", "\\n").replace("\r", "\\n"))


def _fold(line):
    """Fold to 75 octets per line, never splitting a UTF-8 character."""
    raw = line.encode("utf-8")
    if len(raw) <= 75:
        return line
    out, cur = [], b""
    for ch in line:
        b = ch.encode("utf-8")
        limit = 75 if not out else 74
        if len(cur) + len(b) > limit:
            out.append(cur.decode("utf-8"))
            cur = b
        else:
            cur += b
    out.append(cur.decode("utf-8"))
    return "\r\n ".join(out)


def _utc(ts):
    return datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def build_calendar(meetings, domain="superviseme", name="SuperviseMe meetings"):
    """``meetings``: iterable of dicts with uid, title, start, end, location, description."""
    lines = ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//SuperviseMe//Agenda//EN", "CALSCALE:GREGORIAN",
             "METHOD:PUBLISH", f"X-WR-CALNAME:{_esc(name)}"]
    stamp = _utc(int(datetime.now(tz=timezone.utc).timestamp()))
    for m in meetings:
        lines += ["BEGIN:VEVENT", f"UID:meeting-{m['uid']}@{domain}", f"DTSTAMP:{stamp}",
                  f"DTSTART:{_utc(m['start'])}", f"DTEND:{_utc(m['end'])}", f"SUMMARY:{_esc(m['title'])}"]
        if m.get("location"):
            lines.append(f"LOCATION:{_esc(m['location'])}")
        if m.get("description"):
            lines.append(f"DESCRIPTION:{_esc(m['description'])}")
        lines += ["STATUS:CONFIRMED", "END:VEVENT"]
    lines.append("END:VCALENDAR")
    return "\r\n".join(_fold(l) for l in lines) + "\r\n"
