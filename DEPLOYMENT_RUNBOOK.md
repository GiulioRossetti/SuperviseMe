# SuperviseMe Deployment Runbook

This runbook defines a repeatable deployment process for production.

## 1. Preconditions

- CI must pass on the target commit:
  - lint (`ruff` runtime-safety rules)
  - compile checks
  - schema alignment check
  - tests (`pytest`)
- Target environment must provide required secrets:
  - `SECRET_KEY` (strong, non-default)
  - `ADMIN_BOOTSTRAP_PASSWORD`
  - database credentials
  - mail/telegram credentials if used
- Exactly one process/service must run scheduler jobs:
  - `ENABLE_SCHEDULER=true` only for scheduler worker
  - set `ENABLE_SCHEDULER=false` for web app replicas

## 2. Pre-Deployment Checklist

1. Confirm current production health endpoint:
   - `GET /health` returns `200`.
2. Confirm backup availability and last successful backup timestamp.
3. Confirm rollback artifact exists (previous container image/tag).
4. Confirm `.env` values are present and valid in deployment target.
5. Confirm database schema file alignment in repo:
   - `python scripts/check_schema_alignment.py --db data_schema/database_dashboard.db --strict`

## 3. Deployment Procedure

1. Pull target release artifacts (or checkout release commit).
2. Install/update dependencies:
   - `pip install -r requirements.txt`
3. Ensure environment variables are set:
   - production `SECRET_KEY`
   - `ENABLE_SCHEDULER` set per role (web vs scheduler worker)
4. Restart services:
   - web service(s)
   - scheduler service (single instance only)
5. Wait for startup logs and confirm no initialization failures.

## 4. Post-Deploy Smoke Tests

Run immediately after rollout:

1. **Basic availability**
   - `GET /health` -> `200`
   - `GET /login` -> `200`
2. **Authentication + CSRF**
   - login form renders token
   - login POST without CSRF -> blocked (`400`)
   - login POST with CSRF -> accepted flow
3. **Role access sanity**
   - admin dashboard loads
   - supervisor thesis list loads
   - researcher projects/supervisor dashboards load
   - student thesis page loads
4. **Critical CRUD checks**
   - thesis delete (admin/supervisor/researcher) succeeds with expected permissions
   - todo toggle/delete works
   - student objective/resource delete works
5. **Scheduler sanity**
   - only one scheduler instance reports active jobs
   - no duplicate weekly notification job execution observed

## 5. Rollback Procedure

Trigger rollback if smoke tests fail or severe errors are detected.

1. Re-deploy previous known-good image/tag.
2. Restore previous environment variables if changed.
3. Restart services and verify:
   - `GET /health` returns `200`
   - core login/dashboard routes work
4. If database changes were applied and are incompatible, restore DB backup.
5. Document incident:
   - failed version
   - symptom
   - rollback time
   - follow-up owner

## 6. Backup and Restore

### Backup

1. Stop write-heavy jobs if possible.
2. Create database backup (engine-native dump/snapshot).
3. Store with timestamp and release tag.
4. Verify backup integrity (test restore metadata at minimum).

### Restore

1. Put app in maintenance mode.
2. Restore DB from selected backup.
3. Re-deploy app version compatible with restored schema/data.
4. Run smoke tests from section 4 before opening traffic.

## 7. Operational Notes

- Use `ENABLE_SCHEDULER=false` in test/CI and in all but one production worker.
- Keep `ADMIN_BOOTSTRAP_PASSWORD` for bootstrap only; rotate and store securely.
- Keep certs/keys out of repo; provide via secret manager/volume at runtime.

