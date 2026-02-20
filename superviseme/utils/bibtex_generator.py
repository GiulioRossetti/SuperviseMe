import json

def generate_bibtex(activities):
    """
    Generates a BibTeX string from a list of OrcidActivity objects.
    """
    bibtex_entries = []

    for activity in activities:
        # Determine entry type
        # ORCID types: journal-article, conference-paper, book, etc.
        # BibTeX types: article, inproceedings, book, misc

        bib_type = "misc"
        orcid_type = (activity.type or "").lower()

        if "journal" in orcid_type or "article" in orcid_type:
            bib_type = "article"
        elif "conference" in orcid_type or "proceeding" in orcid_type:
            bib_type = "inproceedings"
        elif "book" in orcid_type:
            bib_type = "book"
        elif "thesis" in orcid_type:
            bib_type = "phdthesis"

        # Generate citation key
        # Use first word of title + year + id to be unique
        first_word = activity.title.split()[0] if activity.title else "Untitled"
        title_slug = "".join(x for x in first_word if x.isalnum())
        year = activity.publication_date if activity.publication_date else "nd"
        citation_key = f"{title_slug}{year}{activity.id}"

        entry = [f"@{bib_type}{{{citation_key},"]

        # Add fields
        # Escape curly braces in title
        safe_title = activity.title.replace("{", "\\{").replace("}", "\\}")
        entry.append(f"  title = {{{safe_title}}},")

        if activity.publication_date:
            entry.append(f"  year = {{{activity.publication_date}}},")

        if activity.url:
            entry.append(f"  url = {{{activity.url}}},")

        # Try to find DOI
        if activity.external_ids:
            try:
                ext_ids = json.loads(activity.external_ids)
                for eid in ext_ids:
                    if eid.get('type') == 'doi':
                        entry.append(f"  doi = {{{eid.get('value')}}},")
                        break
            except:
                pass

        # Close entry
        entry.append("}")
        bibtex_entries.append("\n".join(entry))

    return "\n\n".join(bibtex_entries)
