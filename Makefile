FLASK_ENV ?= development
SECRET_KEY ?= local-ci-key
ADMIN_BOOTSTRAP_PASSWORD ?= local-ci-bootstrap
ENABLE_SCHEDULER ?= false

export FLASK_ENV
export SECRET_KEY
export ADMIN_BOOTSTRAP_PASSWORD
export ENABLE_SCHEDULER

.PHONY: ci lint compile schema test smoke migrate

ci: lint compile schema migrate test

lint:
	ruff check --select E9,F63,F7,F82 superviseme scripts test_app_functionality.py recreate_database.py seed_database.py

compile:
	python -m py_compile superviseme/__init__.py superviseme/routes/*.py superviseme/utils/*.py scripts/check_schema_alignment.py

schema:
	python scripts/check_schema_alignment.py --db data_schema/database_dashboard.db --strict

migrate:
	FLASK_APP=superviseme.py SQLALCHEMY_DATABASE_URI="sqlite:////tmp/superviseme_ci_migrate.db" flask db upgrade

test:
	pytest -q

smoke:
	python test_app_functionality.py

