# Horizon Technovations

An all-in-one growth platform marketing site + working lead-capture backend,
built with Flask and SQLite.

## What's actually functional

- **Public site** — hero, features, process, pricing, FAQ (accordion), contact form.
- **Signup form** (`/signup`) — writes real leads to the database.
- **Contact form** — writes messages to the database.
- **Login** (`/login`) — session-based auth against a `users` table (passwords hashed with Werkzeug).
- **Dashboard** (`/dashboard`, login required) — a real mini-CRM: view all captured
  leads/opportunities, change their pipeline stage, add opportunities manually,
  and remove them. Stats (total leads, open, won, pipeline value) are computed
  live from the database.
- **Admin panel** (`/admin`, admin role only) — full control over every record:
  - **Leads** — edit every field on any opportunity (not just stage), or delete it.
  - **Messages** — see every contact-form submission, mark it new/read/archived, or delete it.
  - **Users** — create new member or admin accounts, promote/demote roles,
    deactivate or reactivate accounts, or delete them. Built-in guardrails:
    you can't demote, deactivate, or delete your own account, and you can't
    delete the last remaining admin.

Things like the phone system, AI SMS automation, and social ad sync are
represented as marketing copy only — they'd require real third-party
infrastructure (telephony providers, Meta APIs, etc.) that's out of scope for
a self-contained app.

## Roles

| Role | Can do |
|---|---|
| **Member** | Log in, view the pipeline, change a lead's stage, add/remove opportunities |
| **Admin**  | Everything a member can, plus the full `/admin` panel above |

## Run it locally

```bash
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
python app.py
```

Then open **http://localhost:5000**.

The SQLite database (`horizon.db`) is created automatically on first run, with:

- A demo **member** login: `demo@horizontechnovations.com` / `horizon2026`
- A demo **admin** login: `admin@horizontechnovations.com` / `admin2026`
- Three sample opportunities already in the pipeline, so the dashboard isn't empty.

## Project structure

```
horizon/
├── app.py                 # Flask app: routes, DB, auth
├── requirements.txt
├── templates/
│   ├── base.html           # shared shell (nav, flash messages, footer)
│   ├── index.html          # marketing homepage
│   ├── signup.html
│   ├── login.html
│   ├── dashboard.html
│   └── 404.html
└── static/
    ├── css/style.css       # full design system (black + mint-green theme)
    └── js/main.js
```

## Notes for production

- Change `SECRET_KEY` via the `SECRET_KEY` environment variable.
- Swap `app.run(debug=True)` for a production server (e.g. `gunicorn app:app`).
- SQLite is fine for a demo/small deployment; move to Postgres for real scale.

