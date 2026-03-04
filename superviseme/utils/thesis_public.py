def parse_bool(value):
    if value is None:
        return False
    return str(value).strip().lower() in {"1", "true", "on", "yes"}


def normalize_thesis_descriptions(short_description, long_description, fallback_description):
    short = (short_description or "").strip()
    long = (long_description or "").strip()
    fallback = (fallback_description or "").strip()

    if not long:
        long = fallback or short
    if not short:
        source = long or fallback
        short = source[:220] if source else ""

    description = long or fallback or short
    return short, long, description


def parse_keywords(raw_keywords):
    if not raw_keywords:
        return []
    seen = set()
    out = []
    for piece in raw_keywords.split(","):
        keyword = piece.strip()
        if not keyword:
            continue
        token = keyword.lower()
        if token in seen:
            continue
        seen.add(token)
        out.append(keyword)
    return out


def set_thesis_keywords(db, Thesis_Tag, thesis_id, raw_keywords):
    Thesis_Tag.query.filter_by(thesis_id=thesis_id).delete()
    for keyword in parse_keywords(raw_keywords):
        db.session.add(Thesis_Tag(thesis_id=thesis_id, tag=keyword))

