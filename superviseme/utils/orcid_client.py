import requests
import json
import time
from superviseme.models import OrcidActivity
from superviseme import db
from flask import current_app

ORCID_API_BASE = "https://pub.orcid.org/v3.0"

def parse_works(user, data):
    activities = []
    groups = data.get('group', [])

    for group in groups:
        work_summaries = group.get('work-summary', [])
        if not work_summaries:
            continue

        work = work_summaries[0]

        title_obj = work.get('title', {})
        title = title_obj.get('title', {}).get('value', 'Untitled') if title_obj else 'Untitled'

        type_val = work.get('type', 'work')

        # Date
        pub_date = work.get('publication-date', {})
        year = None
        if pub_date:
            year_obj = pub_date.get('year', {})
            if year_obj:
                year = year_obj.get('value')
        publication_date = year if year else ""

        url_obj = work.get('url', {})
        url_val = url_obj.get('value') if url_obj else None

        ext_ids = []
        external_ids_container = work.get('external-ids', {})
        if external_ids_container and external_ids_container.get('external-id'):
            for eid in external_ids_container.get('external-id'):
                ext_ids.append({
                    'type': eid.get('external-id-type'),
                    'value': eid.get('external-id-value'),
                    'url': eid.get('external-id-url', {}).get('value') if eid.get('external-id-url') else None
                })

        activity = OrcidActivity(
            user_id=user.id,
            title=title[:500],
            type=type_val,
            organization=None,
            publication_date=publication_date,
            url=url_val[:500] if url_val else None,
            external_ids=json.dumps(ext_ids),
            created_at=int(time.time()),
            updated_at=int(time.time())
        )
        activities.append(activity)
    return activities

def parse_affiliations(user, data, type_category):
    activities = []
    groups = data.get('affiliation-group', [])

    for group in groups:
        summaries = group.get('summaries', [])
        if not summaries:
            continue

        # Determine summary key based on type
        summary_key = 'employment-summary' if type_category == 'employment' else 'education-summary'

        # ORCID API structure for affiliation-group -> summaries -> [ { employment-summary: {...} } ]
        summary_container = summaries[0]
        summary_obj = summary_container.get(summary_key)

        if not summary_obj:
            continue

        # Role title
        role = summary_obj.get('role-title', 'Member')

        # Organization
        org = summary_obj.get('organization', {})
        org_name = org.get('name', 'Unknown Organization')

        # Date
        start_date = summary_obj.get('start-date', {})
        year = None
        if start_date:
            year_obj = start_date.get('year', {})
            if year_obj:
                year = year_obj.get('value')
        publication_date = year if year else ""

        # Url
        url_obj = summary_obj.get('url', {})
        url_val = url_obj.get('value') if url_obj else None

        activity = OrcidActivity(
            user_id=user.id,
            title=role[:500],
            type=type_category,
            organization=org_name[:255],
            publication_date=publication_date,
            url=url_val[:500] if url_val else None,
            external_ids=json.dumps([]),
            created_at=int(time.time()),
            updated_at=int(time.time())
        )
        activities.append(activity)
    return activities

def parse_fundings(user, data):
    activities = []
    groups = data.get('group', [])

    for group in groups:
        summaries = group.get('funding-summary', [])
        if not summaries:
            continue

        summary = summaries[0]

        title_obj = summary.get('title', {})
        title = title_obj.get('title', {}).get('value', 'Untitled Project') if title_obj else 'Untitled Project'

        # Funding Agency as Organization
        org = summary.get('organization', {})
        org_name = org.get('name', 'Unknown Agency')

        # Date
        start_date = summary.get('start-date', {})
        year = None
        if start_date:
            year_obj = start_date.get('year', {})
            if year_obj:
                year = year_obj.get('value')
        publication_date = year if year else ""

        url_obj = summary.get('url', {})
        url_val = url_obj.get('value') if url_obj else None

        ext_ids = []
        external_ids_container = summary.get('external-ids', {})
        if external_ids_container and external_ids_container.get('external-id'):
            for eid in external_ids_container.get('external-id'):
                ext_ids.append({
                    'type': eid.get('external-id-type'),
                    'value': eid.get('external-id-value'),
                    'url': eid.get('external-id-url', {}).get('value') if eid.get('external-id-url') else None
                })

        activity = OrcidActivity(
            user_id=user.id,
            title=title[:500],
            type='funding',
            organization=org_name[:255],
            publication_date=publication_date,
            url=url_val[:500] if url_val else None,
            external_ids=json.dumps(ext_ids),
            created_at=int(time.time()),
            updated_at=int(time.time())
        )
        activities.append(activity)
    return activities

def fetch_orcid_activities(user):
    """
    Fetches activities (works, affiliations, funding) from ORCID for the given user.
    """
    if not user.orcid_id:
        return {"success": False, "message": "User has no ORCID iD linked."}

    headers = {"Accept": "application/json"}
    if user.orcid_access_token:
        headers["Authorization"] = f"Bearer {user.orcid_access_token}"

    all_activities = []
    errors = []

    # 1. Works
    try:
        resp = requests.get(f"{ORCID_API_BASE}/{user.orcid_id}/works", headers=headers)
        if resp.status_code == 200:
            all_activities.extend(parse_works(user, resp.json()))
        elif resp.status_code == 401:
            errors.append("Unauthorized access for Works")
    except Exception as e:
        current_app.logger.error(f"Error fetching works: {e}")

    # 2. Employment
    try:
        resp = requests.get(f"{ORCID_API_BASE}/{user.orcid_id}/employments", headers=headers)
        if resp.status_code == 200:
            all_activities.extend(parse_affiliations(user, resp.json(), 'employment'))
    except Exception as e:
        current_app.logger.error(f"Error fetching employments: {e}")

    # 3. Education
    try:
        resp = requests.get(f"{ORCID_API_BASE}/{user.orcid_id}/educations", headers=headers)
        if resp.status_code == 200:
            all_activities.extend(parse_affiliations(user, resp.json(), 'education'))
    except Exception as e:
        current_app.logger.error(f"Error fetching educations: {e}")

    # 4. Funding
    try:
        resp = requests.get(f"{ORCID_API_BASE}/{user.orcid_id}/fundings", headers=headers)
        if resp.status_code == 200:
            all_activities.extend(parse_fundings(user, resp.json()))
    except Exception as e:
        current_app.logger.error(f"Error fetching fundings: {e}")

    if not all_activities and errors:
        return {"success": False, "message": "Failed to sync: " + "; ".join(errors)}

    try:
        OrcidActivity.query.filter_by(user_id=user.id).delete()
        if all_activities:
            db.session.add_all(all_activities)
        db.session.commit()
        return {"success": True, "message": f"Successfully synced {len(all_activities)} items (Works, Affiliations, Funding)."}
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Database error: {e}")
        return {"success": False, "message": "Database error during sync."}
