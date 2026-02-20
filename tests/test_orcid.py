import sys
import os
import json
from unittest.mock import MagicMock, patch
import pytest

# Mock dependencies before import
def get_mocks():
    return {
        'flask': MagicMock(),
        'flask_sqlalchemy': MagicMock(),
        'flask_login': MagicMock(),
        'flask_mail': MagicMock(),
        'flask_wtf': MagicMock(),
        'flask_wtf.csrf': MagicMock(),
        'flask_migrate': MagicMock(),
        'requests': MagicMock(),
        'requests.auth': MagicMock(),
        'superviseme.db': MagicMock(),
        'superviseme.models': MagicMock(),
        'authlib': MagicMock(),
        'authlib.integrations': MagicMock(),
        'authlib.integrations.flask_client': MagicMock(),
        'bleach': MagicMock(),
        'markdown': MagicMock(),
        'flask_moment': MagicMock(),
        'werkzeug': MagicMock(),
        'werkzeug.security': MagicMock(),
    }

@pytest.fixture(scope="function")
def orcid_modules():
    mocks = get_mocks()
    with patch.dict(sys.modules, mocks):
        # Clear if already imported
        for mod in ['superviseme.utils.orcid_client', 'superviseme.utils.bibtex_generator']:
            if mod in sys.modules:
                del sys.modules[mod]

        sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

        # Importing client will trigger superviseme imports
        import superviseme.utils.orcid_client as client
        import superviseme.utils.bibtex_generator as bibtex

        yield client, bibtex

def test_generate_bibtex(orcid_modules):
    client, bibtex = orcid_modules

    # Mock OrcidActivity
    activity = MagicMock()
    activity.id = 123
    activity.title = "Test Article"
    activity.type = "journal-article"
    activity.publication_date = "2023"
    activity.url = "http://example.com"
    activity.external_ids = json.dumps([{"type": "doi", "value": "10.1234/5678"}])

    result = bibtex.generate_bibtex([activity])

    assert "@article{Test2023123," in result
    assert "title = {Test Article}" in result
    assert "year = {2023}" in result
    assert "doi = {10.1234/5678}" in result

def test_fetch_orcid_activities_success(orcid_modules):
    client, bibtex = orcid_modules

    # Mock User
    user = MagicMock()
    user.id = 1
    user.orcid_id = "0000-0001-2345-6789"
    user.orcid_access_token = "access_token"

    # Mock requests response
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "group": [{
            "work-summary": [{
                "title": {"title": {"value": "My Research"}},
                "type": "journal-article",
                "publication-date": {"year": {"value": "2024"}},
                "url": {"value": "http://research.com"},
                "external-ids": {"external-id": []}
            }]
        }]
    }

    # Since requests is mocked in sys.modules, we use that mock
    # client.requests is the Mock object
    client.requests.get.return_value = mock_response

    # Mock DB
    client.OrcidActivity = MagicMock()
    client.db.session = MagicMock()

    result = client.fetch_orcid_activities(user)

    assert result["success"] is True
    assert "Successfully synced" in result["message"]

    # Verify db add and commit called
    assert client.db.session.add_all.called
    assert client.db.session.commit.called

    # Verify requests called with token
    args, kwargs = client.requests.get.call_args
    assert kwargs['headers']['Authorization'] == "Bearer access_token"

def test_fetch_orcid_activities_no_orcid(orcid_modules):
    client, bibtex = orcid_modules
    user = MagicMock()
    user.orcid_id = None

    result = client.fetch_orcid_activities(user)
    assert result["success"] is False
    assert "no ORCID iD" in result["message"]

def test_fetch_orcid_activities_unauthorized(orcid_modules):
    client, bibtex = orcid_modules
    user = MagicMock()
    user.orcid_id = "123"
    user.orcid_access_token = "bad_token"

    mock_response = MagicMock()
    mock_response.status_code = 401
    client.requests.get.return_value = mock_response

    result = client.fetch_orcid_activities(user)
    assert result["success"] is False
    assert "Unauthorized" in result["message"]

def test_parse_affiliations(orcid_modules):
    client, bibtex = orcid_modules
    user = MagicMock()
    user.id = 1

    client.OrcidActivity.reset_mock()

    data = {
        "affiliation-group": [{
            "summaries": [{
                "employment-summary": {
                    "role-title": "Professor",
                    "organization": {"name": "University X"},
                    "start-date": {"year": {"value": "2020"}}
                }
            }]
        }]
    }

    activities = client.parse_affiliations(user, data, 'employment')

    args, kwargs = client.OrcidActivity.call_args
    assert kwargs['title'] == "Professor"
    assert kwargs['organization'] == "University X"
    assert kwargs['type'] == "employment"

def test_parse_fundings(orcid_modules):
    client, bibtex = orcid_modules
    user = MagicMock()
    user.id = 1

    client.OrcidActivity.reset_mock()

    data = {
        "group": [{
            "funding-summary": [{
                "title": {"title": {"value": "My Grant"}},
                "organization": {"name": "NSF"},
                "start-date": {"year": {"value": "2021"}}
            }]
        }]
    }

    activities = client.parse_fundings(user, data)

    args, kwargs = client.OrcidActivity.call_args
    assert kwargs['title'] == "My Grant"
    assert kwargs['organization'] == "NSF"
    assert kwargs['type'] == "funding"
