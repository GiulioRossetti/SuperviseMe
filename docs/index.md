---
hide:
  - navigation
  - toc
---

<div class="sm-hero">
  <img src="assets/img/logo.svg" alt="SuperviseMe logo"/>
  <h1>SuperviseMe</h1>
  <p>An intelligent, open-source platform for academic thesis supervision and research project management.</p>
  <div class="sm-cta">
    <a class="sm-btn-primary" href="installation/">⚡ Get Started</a>
    <a class="sm-btn-secondary" href="https://github.com/GiulioRossetti/SuperviseMe" target="_blank">★ GitHub</a>
  </div>
</div>

<div class="sm-cards">

<div class="sm-card">
<span class="sm-card-icon">🔐</span>
<h3>Secure Authentication</h3>
<p>PBKDF2-SHA256 password hashing, social login via <strong>Google</strong> and <strong>ORCID</strong>, and role-based access control for every stakeholder.</p>
</div>

<div class="sm-card">
<span class="sm-card-icon">🌐</span>
<h3>REST API v1</h3>
<p>Full JSON REST API with JWT authentication. Integrate SuperviseMe with external tools, mobile apps, or institutional systems.</p>
</div>

<div class="sm-card">
<span class="sm-card-icon">🔔</span>
<h3>Real-Time Notifications</h3>
<p>Server-Sent Events (SSE) push updates to the browser instantly. Telegram integration delivers urgent alerts to your phone.</p>
</div>

<div class="sm-card">
<span class="sm-card-icon">🌍</span>
<h3>Multilingual (i18n)</h3>
<p>Full English and Italian localisation with a one-click language switcher. Additional languages are easy to add via Flask-Babel.</p>
</div>

<div class="sm-card">
<span class="sm-card-icon">👨‍🏫</span>
<h3>Supervisor Dashboard</h3>
<p>Track student progress at a glance. Automated Monday-morning email digests highlight who needs attention.</p>
</div>

<div class="sm-card">
<span class="sm-card-icon">👩‍🎓</span>
<h3>Student Portal</h3>
<p>A focused workspace for submitting updates, accessing resources, and staying connected with supervisors.</p>
</div>

<div class="sm-card">
<span class="sm-card-icon">🔬</span>
<h3>Researcher Workspace</h3>
<p>Create projects, invite collaborators, and sync ORCID publications automatically.</p>
</div>

<div class="sm-card">
<span class="sm-card-icon">⚙️</span>
<h3>Admin Control Panel</h3>
<p>Manage users, monitor system health, configure notifications, and export data — all from one dashboard.</p>
</div>

<div class="sm-card">
<span class="sm-card-icon">🚀</span>
<h3>Production Ready</h3>
<p>Docker-first deployment, APScheduler background tasks, Flask-Caching, and support for SQLite and PostgreSQL.</p>
</div>

</div>

---

## Technology Stack

<span class="sm-badge">Python 3.11+</span>
<span class="sm-badge">Flask 3</span>
<span class="sm-badge">SQLAlchemy 2</span>
<span class="sm-badge">Flask-Login</span>
<span class="sm-badge">Flask-Babel</span>
<span class="sm-badge">Flask-Caching</span>
<span class="sm-badge">APScheduler</span>
<span class="sm-badge">JWT / Fernet</span>
<span class="sm-badge">SSE</span>
<span class="sm-badge">Bootstrap 5</span>
<span class="sm-badge">Docker</span>
<span class="sm-badge">PostgreSQL / SQLite</span>

---

## Quick Start

```bash
# 1. Clone
git clone https://github.com/GiulioRossetti/SuperviseMe.git
cd SuperviseMe

# 2. Install
pip install -r requirements.txt

# 3. Configure
cp .env.example .env   # edit as needed

# 4. Initialise & run
flask db upgrade
flask run
```

> See [Installation & First Run](installation.md) for the full guide, including Docker and production setup.

---

## License

SuperviseMe is open-source software licensed under the [GNU General Public License v3.0](https://github.com/GiulioRossetti/SuperviseMe/blob/main/LICENSE).
