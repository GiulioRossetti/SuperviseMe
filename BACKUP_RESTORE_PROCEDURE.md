# Backup and Restore Rehearsal Procedure

This document details the procedure for rehearsing backup and restore operations to ensure data recovery capabilities.

## 1. Backup Procedure

### 1.1. Preparation
- **Notify:** Inform stakeholders of the backup rehearsal (if impacting).
- **Environment:** Use Staging or a dedicated Production-like environment. **Do not test restore on Production unless during a scheduled DR drill.**

### 1.2. Execution
1. **Identify Target Database:**
   - PostgreSQL (Production) or SQLite (Dev/Staging).
2. **Trigger Backup:**
   - **PostgreSQL:**
     ```bash
     pg_dump -h <host> -U <user> -F c -b -v -f backup_$(date +%Y%m%d_%H%M%S).dump <dbname>
     ```
   - **SQLite:**
     ```bash
     sqlite3 superviseme/db/dashboard.db ".backup 'backup_$(date +%Y%m%d_%H%M%S).db'"
     ```
3. **Verify Artifact:**
   - Check file size (should be > 0).
   - Check file type/header.

### 1.3. Storage
- Upload the backup artifact to secure storage (e.g., S3, separate volume).

## 2. Restore Procedure

### 2.1. Preparation
- **Isolate:** Ensure the restore target is isolated.
- **Clean:** Drop/Rename existing database to simulate loss or ensure clean state.

### 2.2. Execution
1. **Restore Database:**
   - **PostgreSQL:**
     ```bash
     pg_restore -h <host> -U <user> -d <dbname> -v backup_file.dump
     ```
   - **SQLite:**
     ```bash
     cp backup_file.db superviseme/db/dashboard.db
     ```
2. **Verify Data:**
   - Run a query to count records in critical tables (`user_mgmt`, `thesis`, `thesis_update`).
   - Compare counts with source.

### 2.3. Validation
- Start the application connected to the restored database.
- Run `scripts/smoke_test.py`.

## 3. Rehearsal Evidence Template

**Date:** [YYYY-MM-DD]
**Executor:** [Name]
**Environment:** [Staging/Prod]

### Backup Step
- [ ] Command executed: _____________________________
- [ ] Backup file name: _____________________________
- [ ] Backup file size: _____________________________
- [ ] Verification method: _____________________________

### Restore Step
- [ ] Target cleared: [Yes/No]
- [ ] Command executed: _____________________________
- [ ] Restore duration: _____________________________

### Validation
- [ ] Application started: [Yes/No]
- [ ] Record counts match:
  - Users: Source [___] / Target [___]
  - Theses: Source [___] / Target [___]
- [ ] Smoke Test Result: [Pass/Fail]

### Issues / Notes
- ________________________________________________________________
- ________________________________________________________________

**Sign-off:** _____________________________
