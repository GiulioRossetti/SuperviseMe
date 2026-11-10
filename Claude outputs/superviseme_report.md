# SuperviseMe — Report Stato Progetto
*Analisi al 9 novembre 2026*

---

## 1. Panoramica generale

**SuperviseMe** è un'applicazione Flask (Python 3.11) per la gestione del percorso di tesi, con ruoli distinti per studenti, supervisori, ricercatori e admin. Il progetto usa SQLAlchemy + Flask-Migrate (Alembic) per il DB (SQLite in locale, PostgreSQL in produzione), APScheduler per le notifiche programmate, integrazione Telegram e ORCID.

---

## 2. Stato di `main`

**Ultimo commit significativo:** `e73e29d` — *feat(theses): add public catalog, interest workflow, and sidebar-aligned UI* (4 marzo 2026)

### Cosa c'è già in main
- Sistema completo di gestione tesi (CRUD, TODO, obiettivi, ipotesi, risorse, meeting notes)
- Integrazione ORCID (OAuth + fetch pubblicazioni) + Google login
- Catalogo pubblico delle tesi disponibili e workflow di manifestazione d'interesse degli studenti
- Integrazione Telegram per notifiche
- 5 migrazioni Alembic (baseline → ORCID → public thesis metadata → thesis interest → interest status history)
- Pipeline CI con lint ruff, compile checks, schema alignment, migration test e pytest
- Documentazione MkDocs con deploy automatico su gh-pages
- Suite di test con ~10 file per le varie aree funzionali

### Criticità già presenti in main

**Bug nell'admin dashboard (`superviseme/routes/admin.py`, funzione `dashboard`)**
Il codice che costruisce `available_theses_by_supervisor` assegna *tutte* le tesi non assegnate a *ogni* supervisore, invece di filtrare quelle di pertinenza:

```python
# CODICE ATTUALE (errato)
available_theses_by_supervisor = defaultdict(list)
available_theses = Thesis.query.filter(Thesis.author_id.is_(None)).all()
for supervisor in supervisors:
    available_theses_by_supervisor[supervisor].extend(
        [{"thesis": thesis} for thesis in available_theses]
    )
```

Ogni supervisore vede tutte le tesi libere, anziché solo le proprie. Va corretto con un join su `Thesis_Supervisor`.

**Potenziale `AmbiguousForeignKeysError` in `models.py`**
La tabella `Thesis` ha due FK verso `user_mgmt` (`author_id` e `publisher_id`). La relazione `thesis` su `User_mgmt` non specifica `foreign_keys=`, il che potrebbe causare un errore SQLAlchemy a runtime quando entrambe le FK sono presenti:

```python
# In User_mgmt:
thesis = db.relationship("Thesis", backref="author", lazy=True)  # manca foreign_keys=[Thesis.author_id]
```

**`.idea/` untracked ma non in `.gitignore`**
I file IntelliJ sono visibili come untracked da `git status`. Vanno aggiunti a `.gitignore` (di solito già presente come pattern — verificare che la riga `.idea/` ci sia effettivamente).

---

## 3. Analisi dei branch remoti

### Branch 1: `copilot/fix-seed-database-users-creation`
**Commit unico:** `9b9c4c8 Initial plan`
**Verdict: 🔴 Abbandonato — da chiudere**

Contiene solo la commit di pianificazione generata automaticamente dall'AI. Nessun codice reale. Il problema che doveva risolvere (creazione utenti nel seed) è già stato parzialmente gestito in main (commit `598d46e`). Il branch è un residuo di un'issue mai completata.

---

### Branch 2: `copilot/sub-pr-50`
**Commit unico:** `4b96ad7 Initial plan`
**Verdict: 🔴 Abbandonato — da chiudere**

Identico al precedente: solo la commit di piano, nessuna implementazione. Era un "sub-PR" di qualche issue #50. Ha esattamente lo stesso diff rispetto a main del branch sopra (entrambi divergono dallo stesso punto).

---

### Branch 3: `qa-improvements-4770210967680816835`
**Commit:** 4 commit (b30323b → 8b65bde → dbdc6f3 → e9d7d7d)
**Verdict: 🟡 NON MERGIABILE — contiene regressioni significative**

Questo è il branch più ricco di modifiche, ma **non può essere mergiato in main nella forma attuale** perché introduce regressioni nette rispetto alle feature già presenti.

#### Cosa aggiunge (positivo)
| File | Valore |
|------|--------|
| `tests/test_authorization.py` | Test di autorizzazione per ruoli (student non accede ad admin, etc.) |
| `tests/test_end_to_end.py` | Workflow end-to-end: admin CRUD utenti, gestione tesi, flow supervisor |
| `scripts/smoke_test.py` | Script di smoke test operativo post-deploy |
| `BACKUP_RESTORE_PROCEDURE.md` | Procedura di backup/restore documentata |
| `migrate_meeting_notes.py` | Script di migrazione per i meeting notes |
| `migrate_todo_references.py` | Script di migrazione per i riferimenti TODO |

#### Cosa rimuove (regressioni — CRITICO)
| Elemento rimosso | Impatto |
|-----------------|---------|
| Migrazioni 0002–0005 | **Rottura DB**: senza le migrazioni, una fresh install o un upgrade da legacy DB non porta le colonne ORCID, public thesis, publisher, interest |
| `superviseme/routes/public.py` | Rimuove il catalogo pubblico delle tesi (feature aggiunta nell'ultimo commit di main) |
| `superviseme/templates/public/` | Rimuove le view del catalogo pubblico |
| `superviseme/templates/student/interests.html` | Rimuove l'interfaccia studente per la manifestazione d'interesse |
| `superviseme/utils/orcid_client.py` | Rimuove l'integrazione ORCID |
| `superviseme/utils/bibtex_generator.py` | Rimuove l'export BibTeX |
| `superviseme/utils/thesis_interest.py` | Rimuove la logica del workflow d'interesse |
| `superviseme/utils/thesis_public.py` | Rimuove la logica del catalogo pubblico |
| Colonne `is_enabled`, `google_id`, `orcid_id`, `profile_pic`, `orcid_access_token`, `orcid_refresh_token` da `User_mgmt` | Rottura del modello utente |
| `oauth = OAuth()` da `__init__.py` | Rimuove l'infrastruttura OAuth |
| `_run_db_upgrade()` da `__init__.py` | Rimuove l'auto-upgrade del DB all'avvio |
| `Authlib`, `requests`, `bleach`, `python-dotenv` da `requirements.txt` | Dipendenze non più installate |
| `mkdocs.yml` + tutti i `docs/*.md` | Azzera la documentazione |
| `deploy_docs.yml` workflow | Rimuove il deploy automatico della documentazione |
| Intera suite test esistente (10 file) | Rimpiazza con soli 2 file, perdendo copertura su orcid, telegram, todo_parser, security, etc. |

#### Modifiche pericolose al comportamento
- `wsgi.py`: il default del DB passa dall'intelligente detection `"postgresql" if os.getenv("PG_HOST") else "sqlite"` al hardcoded `"postgresql"` — chi avvia in locale senza Docker ottiene un errore invece di SQLite
- `__init__.py`: `SECRET_KEY` mancante non solleva più `RuntimeError` ma usa `"dev-only-insecure-key"` — rischio sicurezza in staging/produzione dimenticata

---

## 4. Cosa mergiare in main per uno starting point stabile

### Risposta breve: nessuno dei branch va mergiato integralmente

Lo stato più stabile è `main` così com'è. Tuttavia, da `qa-improvements` conviene **cherry-pick** selettivo di quanto aggiunge senza togliere nulla:

| Da cherry-pick | Perché |
|----------------|--------|
| `tests/test_authorization.py` | Copertura mancante su autorizzazione per ruolo |
| `tests/test_end_to_end.py` | Workflow integrati assenti in main |
| `scripts/smoke_test.py` | Utile per validare il deploy |
| `BACKUP_RESTORE_PROCEDURE.md` | Documentazione operativa |
| `migrate_meeting_notes.py` | Script utile per migrazioni dati legacy |
| `migrate_todo_references.py` | Idem |

**Procedura consigliata:**
```bash
git checkout main
git cherry-pick b30323b   # Add comprehensive tests and operational docs
# Verificare il cherry-pick, risolvendo eventuali conflitti sulle parti distruttive
# NON includere i commit e9d7d7d, dbdc6f3, 8b65bde che portano le regressioni
```

---

## 5. Criticità prioritarie da trattare

### 🔴 Alta priorità

**C1. Chiudere i branch abbandonati**
`copilot/fix-seed-database-users-creation` e `copilot/sub-pr-50` sono rumore. Vanno chiusi su GitHub (se ci sono PR aperte) e i branch remoti eliminati.

**C2. Bug `available_theses_by_supervisor` in `admin.py`**
Già descritto sopra. Ogni supervisore vede tutte le tesi libere. Correzione: filtrare per `Thesis_Supervisor.supervisor_id == supervisor.id`.

**C3. `foreign_keys` mancante su `Thesis.thesis` relationship**
Con due FK da `Thesis` verso `user_mgmt`, SQLAlchemy può sollevare `AmbiguousForeignKeysError` a runtime. Specificare esplicitamente `foreign_keys=[Thesis.author_id]`.

### 🟡 Media priorità

**C4. Test coverage per le nuove feature (public catalog, thesis interest)**
L'ultimo commit di main (`e73e29d`) ha aggiunto ~600 righe di nuova logica senza test dedicati. I test presenti in `qa-improvements` per auth ed e2e sono un buon punto di partenza, ma mancano unit test per `thesis_interest.py`, `thesis_public.py`, e le route `/public/*`.

**C5. `wsgi.py`: ripristinare il default intelligente DB**
Se qualcuno fa deploy in ambienti misti (locale + Docker), il comportamento attuale di main è già corretto. Assicurarsi che non venga sovrascritto con un hardcoded `"postgresql"`.

**C6. Seed database per ambienti non-Docker**
La feature `_run_seed_if_needed()` in `superviseme.py` e il caricamento di `.env` via `python-dotenv` sono stati aggiunti in commit precedenti e poi contestati dal branch `qa-improvements`. La logica attuale in main è corretta, ma andrebbe documentata nel README il flusso di avvio non-Docker.

### 🟢 Bassa priorità

**C7. Documentazione**
Il `mkdocs.yml` e i `docs/` sono presenti in main ma alcune pagine sono vuote o obsolete (es. `docs/configuration.md` è stata rimossa in tutti i branch alternativi). Conviene un audit dei docs prima del prossimo deploy della documentazione.

**C8. Lock della versione Flask-SQLAlchemy**
Il branch `qa-improvements` pinnava a `Flask-SQLAlchemy==3.0.5`. Con `>=3.0.0` si rischia di prendere versioni con breaking changes. Valutare se pinnare a una versione LTS specifica anche in main.

---

## 6. Riepilogo decisioni raccomandate

| Azione | Priorità | Effort |
|--------|----------|--------|
| Chiudere/eliminare i 2 branch copilot abbandonati | Alta | 5 min |
| Fix bug `available_theses_by_supervisor` in admin.py | Alta | 1h |
| Fix `foreign_keys` su relazione `Thesis`/`User_mgmt` | Alta | 30 min |
| Cherry-pick dei soli test da `qa-improvements` | Media | 2h (review conflitti) |
| Aggiungere test unit per public catalog e thesis interest | Media | 4h |
| Audit docs e aggiornamento README (non-Docker startup) | Bassa | 2h |
| Valutare pin Flask-SQLAlchemy a versione fissa | Bassa | 30 min |

---

*Report generato il 9 novembre 2026 — analisi su commit `e73e29d` (main) e branch remoti `copilot/fix-seed-database-users-creation`, `copilot/sub-pr-50`, `qa-improvements-4770210967680816835`.*
