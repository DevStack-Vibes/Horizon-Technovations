import os
import sqlite3
from datetime import datetime, timezone
from functools import wraps

from flask import (
    Flask, g, render_template, request, redirect,
    url_for, session, flash, jsonify
)
from werkzeug.security import generate_password_hash, check_password_hash

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "horizon.db")

app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "dev-secret-change-me")


# ---------------------------------------------------------------------------
# Database helpers
# ---------------------------------------------------------------------------

def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db


@app.teardown_appcontext
def close_db(exception=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db():
    db = sqlite3.connect(DB_PATH)
    db.row_factory = sqlite3.Row
    db.executescript(
        """
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            company TEXT,
            role TEXT NOT NULL DEFAULT 'member',
            is_active INTEGER NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS leads (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT NOT NULL,
            company TEXT,
            phone TEXT,
            plan TEXT,
            source TEXT DEFAULT 'Signup Form',
            value REAL DEFAULT 0,
            stage TEXT DEFAULT 'New Lead',
            message TEXT,
            created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS contact_messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT NOT NULL,
            message TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'new',
            created_at TEXT NOT NULL
        );
        """
    )

    # Seed demo accounts so /login is testable out of the box: one regular
    # member and one admin, so the difference in permissions is visible.
    seed_users = [
        ("Demo Member", "demo@horizontechnovations.com", "horizon2026", "Horizon Technovations", "member"),
        ("Site Admin", "admin@horizontechnovations.com", "admin2026", "Horizon Technovations", "admin"),
    ]
    for name, email, password, company, role in seed_users:
        existing = db.execute("SELECT id FROM users WHERE email = ?", (email,)).fetchone()
        if not existing:
            db.execute(
                "INSERT INTO users (name, email, password_hash, company, role, is_active, created_at) "
                "VALUES (?, ?, ?, ?, ?, 1, ?)",
                (
                    name,
                    email,
                    generate_password_hash(password),
                    company,
                    role,
                    datetime.now(timezone.utc).isoformat(),
                ),
            )

    # Seed a couple of sample opportunities so the dashboard isn't empty.
    seeded = db.execute("SELECT COUNT(*) AS c FROM leads").fetchone()["c"]
    if seeded == 0:
        sample_leads = [
            ("Priya Nandwani", "priya@brightcoatworks.com", "BrightCoat Detailing", "555-0142",
             "Growth", "Facebook Ads", 6200, "Negotiation",
             "Interested in the annual plan, wants a demo of the pipeline view."),
            ("Marcus Webb", "marcus@webbhvac.com", "Webb HVAC Services", "555-0198",
             "Starter", "Website Form", 3400, "New Lead",
             "Asked about phone system integration."),
            ("Dana Ortiz", "dana@ortizlegal.co", "Ortiz Legal Co.", "555-0177",
             "Growth", "Instagram Ads", 8900, "Proposal Sent",
             "Wants LMS for onboarding paralegals."),
        ]
        db.executemany(
            "INSERT INTO leads (name, email, company, phone, plan, source, value, stage, message, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [(*row, datetime.now(timezone.utc).isoformat()) for row in sample_leads],
        )

    db.commit()
    db.close()


# ---------------------------------------------------------------------------
# Auth helpers
# ---------------------------------------------------------------------------

def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not session.get("user_id"):
            flash("Please log in to view the dashboard.", "error")
            return redirect(url_for("login", next=request.path))
        return view(*args, **kwargs)
    return wrapped


def admin_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not session.get("user_id"):
            flash("Please log in to continue.", "error")
            return redirect(url_for("login", next=request.path))
        if session.get("role") != "admin":
            flash("That page is only available to admins.", "error")
            return redirect(url_for("dashboard"))
        return view(*args, **kwargs)
    return wrapped


@app.context_processor
def inject_globals():
    return {
        "current_year": datetime.now(timezone.utc).year,
        "logged_in": bool(session.get("user_id")),
        "current_user_name": session.get("user_name"),
        "current_user_id": session.get("user_id"),
        "is_admin": session.get("role") == "admin",
    }


# ---------------------------------------------------------------------------
# Marketing site data (kept in code for simplicity — no CMS needed for a
# single-page marketing site)
# ---------------------------------------------------------------------------

FEATURES = [
    {
        "eyebrow": "Inbox",
        "title": "Unified Client Messaging",
        "body": "SMS, email, Instagram and Facebook messages land in one inbox, "
                "tied to the right contact automatically.",
    },
    {
        "eyebrow": "Pipeline",
        "title": "Automated Deal Tracking",
        "body": "Every lead moves through a visual pipeline so you always know "
                "what needs a follow-up and what's about to close.",
    },
    {
        "eyebrow": "Voice",
        "title": "One Business Phone Line",
        "body": "A single tracked number for the whole team, with every call "
                "logged straight to the contact record.",
    },
    {
        "eyebrow": "Capture",
        "title": "Smart Forms & Funnels",
        "body": "Build forms that feed directly into your pipeline — no "
                "spreadsheets, no copy-pasting leads by hand.",
    },
    {
        "eyebrow": "Web",
        "title": "Drag-and-Drop Site Builder",
        "body": "Launch conversion-focused pages without waiting on a "
                "developer or touching a line of code.",
    },
    {
        "eyebrow": "Social",
        "title": "Facebook & Instagram Sync",
        "body": "Ad leads sync in the moment they submit, so your team can "
                "respond while interest is still hot.",
    },
]

PROCESS_STEPS = [
    {
        "n": "01",
        "title": "Capture",
        "body": "Leads flow in from your site, forms, calls, texts, and social "
                "ads — nothing sits in someone's personal inbox.",
    },
    {
        "n": "02",
        "title": "Nurture",
        "body": "Automated follow-ups and reminders keep every lead warm "
                "without anyone chasing a spreadsheet.",
    },
    {
        "n": "03",
        "title": "Close",
        "body": "A clear pipeline and full conversation history mean you "
                "always know exactly who to call next.",
    },
]

PLANS = [
    {
        "name": "Monthly",
        "price": "$79",
        "period": "/mo",
        "note": None,
        "cta": "Start Monthly Plan",
    },
    {
        "name": "Annual",
        "price": "$59",
        "period": "/mo",
        "note": "Billed yearly — save 25%",
        "cta": "Start Yearly Plan",
        "highlight": True,
    },
]

PLAN_FEATURES = [
    "Full sales pipeline & opportunity tracking",
    "One tracked business phone line",
    "Unified SMS, email & social inbox",
    "Drag-and-drop website & funnel builder",
    "Custom lead-capture forms",
    "Facebook & Instagram ad sync",
    "Team learning & onboarding hub",
]

COMPANY = {
    "email": "hello@horizontechnovations.com",
    "support_email": "support@horizontechnovations.com",
    "phone": "+92 300 1234567",
    "address": "Suite 402, Horizon Business Center, Gulberg III, Lahore, Pakistan",
    "hours": "Mon – Fri, 9:00 AM – 6:00 PM (PKT)",
}

PILLARS = [
    {
        "title": "Innovate",
        "body": "We design and engineer software that reflects how a modern "
                "team actually works — not a generic template stretched to fit.",
    },
    {
        "title": "Automate",
        "body": "Repetitive, manual work gets replaced with pipelines, "
                "integrations, and workflows that run quietly in the background.",
    },
    {
        "title": "Elevate",
        "body": "Every engagement is judged by one thing: whether it moved "
                "the client's business forward, not just whether it shipped.",
    },
]

ABOUT_VALUES = [
    "Ship working software, not just wireframes and promises.",
    "Communicate in plain language — clients should never need a translator.",
    "Build for the client's next stage of growth, not just today's request.",
    "Treat every codebase and every client relationship as long-term.",
]

SERVICES = [
    {
        "icon": "code",
        "title": "Web Design & Development",
        "body": "Fast, responsive, conversion-focused websites built on modern "
                "frameworks — from marketing sites to full web applications.",
        "tags": ["Custom websites", "Landing pages & funnels", "E-commerce"],
    },
    {
        "icon": "layers",
        "title": "Custom Software & SaaS",
        "body": "Purpose-built platforms and internal tools designed around "
                "your workflow, backed by Python/Flask and modern databases.",
        "tags": ["SaaS products", "Internal tools", "API development"],
    },
    {
        "icon": "workflow",
        "title": "CRM & Business Automation",
        "body": "Pipelines, lead capture, and follow-up automation that keep "
                "leads from slipping through the cracks — like the platform "
                "powering this very site.",
        "tags": ["Lead pipelines", "Workflow automation", "Dashboards"],
    },
    {
        "icon": "search",
        "title": "SEO & Digital Growth",
        "body": "Technical SEO, content strategy, and guest-posting campaigns "
                "that build organic visibility instead of renting it with ads.",
        "tags": ["Technical SEO", "Content strategy", "Guest posting"],
    },
    {
        "icon": "phone",
        "title": "Mobile App Development",
        "body": "Cross-platform mobile apps that share a backend with your "
                "web product, so your data stays in one place.",
        "tags": ["iOS & Android", "Cross-platform builds", "App maintenance"],
    },
    {
        "icon": "support",
        "title": "IT Consulting & Support",
        "body": "Ongoing technical guidance, code audits, and support "
                "retainers for teams that need a technical partner on call.",
        "tags": ["Code audits", "Architecture guidance", "Support retainers"],
    },
    {
        "icon": "ms365",
        "title": "Microsoft 365 & Collaboration",
        "body": "End-to-end Microsoft 365 setup and administration — mailbox "
                "migrations, Teams rollout, and SharePoint workflows, backed "
                "by proper licensing and Purview compliance.",
        "tags": ["Exchange Online migration", "Teams & SharePoint", "Purview compliance"],
    },
    {
        "icon": "security",
        "title": "Security & Compliance",
        "body": "Defender-based SIEM and endpoint protection with SOC "
                "monitoring, threat detection, and incident response to keep "
                "your business audit-ready.",
        "tags": ["Microsoft Defender & SIEM", "SOC monitoring", "Compliance reporting"],
    },
    {
        "icon": "cloud",
        "title": "Cloud Solutions",
        "body": "Azure infrastructure, Intune device management, and hybrid "
                "on-prem/cloud setups designed to scale with you — including "
                "cloud email migrations.",
        "tags": ["Azure VMs & storage", "Intune device management", "Hybrid on-prem + cloud"],
    },
    {
        "icon": "network",
        "title": "Networking & Infrastructure",
        "body": "Wi-Fi and network design, server management, and backup or "
                "disaster recovery planning so your infrastructure stays "
                "fast, secure, and recoverable.",
        "tags": ["Wi-Fi & network design", "Server management", "Backup & disaster recovery"],
    },
    {
        "icon": "licensing",
        "title": "Licensing & Managed Support",
        "body": "SLA-backed helpdesk and Microsoft/Azure licensing "
                "management, with training sessions to keep your IT team "
                "confident and current.",
        "tags": ["Microsoft & Azure licensing", "SLA-based helpdesk", "IT team training"],
    },
]

SERVICE_PROCESS = [
    {"n": "01", "label": "Discover"},
    {"n": "02", "label": "Design"},
    {"n": "03", "label": "Build"},
    {"n": "04", "label": "Launch"},
    {"n": "05", "label": "Support"},
]

FAQS = [
    {
        "q": "Is Horizon Technovations a good fit for a small team?",
        "a": "Yes — most customers are small or growing service businesses "
             "replacing three or four separate tools. The platform is built "
             "to scale from a one-person operation to a full sales team "
             "without switching software later.",
    },
    {
        "q": "Do I need to bring my own tools, or is this really all-in-one?",
        "a": "It's genuinely all-in-one: pipeline, phone line, messaging, "
             "forms, website builder, and training hub live in the same "
             "account, so contact history stays in one place instead of "
             "scattered across five logins.",
    },
    {
        "q": "Can my whole team use one account?",
        "a": "Every plan supports unlimited team members, so your whole "
             "team can work from the same pipeline and inbox.",
    },
    {
        "q": "What happens to leads captured from ads or my website?",
        "a": "They land straight in your pipeline the moment they come in, "
             "tagged with their source, so nothing has to be re-entered by "
             "hand.",
    },
    {
        "q": "Can I train my team inside the platform?",
        "a": "Yes — the built-in learning hub lets you upload onboarding "
             "videos, SOPs, and courses so new hires ramp up without "
             "leaving the app.",
    },
]


# ---------------------------------------------------------------------------
# Public routes
# ---------------------------------------------------------------------------

@app.route("/")
def index():
    return render_template(
        "index.html",
        features=FEATURES,
        steps=PROCESS_STEPS,
        plans=PLANS,
        plan_features=PLAN_FEATURES,
        faqs=FAQS,
    )


@app.route("/about")
def about():
    return render_template("about.html", pillars=PILLARS, values=ABOUT_VALUES)


@app.route("/services")
def services():
    return render_template("services.html", services=SERVICES, process=SERVICE_PROCESS)


@app.route("/privacy-policy")
def privacy_policy():
    return render_template("privacy.html", company=COMPANY)


@app.route("/terms-conditions")
def terms_conditions():
    return render_template("terms.html", company=COMPANY)


@app.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip()
        company = request.form.get("company", "").strip()
        phone = request.form.get("phone", "").strip()
        plan = request.form.get("plan", "Monthly").strip()

        errors = []
        if not name:
            errors.append("Please enter your name.")
        if not email or "@" not in email:
            errors.append("Please enter a valid email address.")

        if errors:
            for e in errors:
                flash(e, "error")
            return render_template("signup.html", plans=PLANS, form=request.form), 400

        db = get_db()
        db.execute(
            "INSERT INTO leads (name, email, company, phone, plan, source, value, stage, message, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (name, email, company, phone, plan, "Signup Form", 0, "New Lead", "",
             datetime.now(timezone.utc).isoformat()),
        )
        db.commit()
        flash("You're in! Our team will reach out shortly to get you set up.", "success")
        return redirect(url_for("signup", success=1))

    return render_template("signup.html", plans=PLANS, form={})


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        db = get_db()
        user = db.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()

        if user and not user["is_active"]:
            flash("This account has been deactivated. Contact an admin.", "error")
            return render_template("login.html"), 403

        if user and check_password_hash(user["password_hash"], password):
            session.clear()
            session["user_id"] = user["id"]
            session["user_name"] = user["name"]
            session["role"] = user["role"]
            flash(f"Welcome back, {user['name']}.", "success")
            next_url = request.args.get("next") or url_for("dashboard")
            return redirect(next_url)

        flash("Incorrect email or password.", "error")
        return render_template("login.html"), 401

    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    flash("You've been logged out.", "success")
    return redirect(url_for("index"))


@app.route("/contact", methods=["GET", "POST"])
def contact():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip()
        message = request.form.get("message", "").strip()

        if not name or not email or not message:
            flash("Please fill in every field before sending.", "error")
            return redirect(url_for("contact"))

        db = get_db()
        db.execute(
            "INSERT INTO contact_messages (name, email, message, created_at) VALUES (?, ?, ?, ?)",
            (name, email, message, datetime.now(timezone.utc).isoformat()),
        )
        db.commit()
        flash("Message sent — we'll get back to you within one business day.", "success")
        return redirect(url_for("contact"))

    return render_template("contact.html", company=COMPANY)


# ---------------------------------------------------------------------------
# Dashboard (protected) — a small working CRM view over captured leads
# ---------------------------------------------------------------------------

STAGES = ["New Lead", "Contacted", "Proposal Sent", "Negotiation", "Won", "Lost"]


@app.route("/dashboard")
@login_required
def dashboard():
    db = get_db()
    leads = db.execute("SELECT * FROM leads ORDER BY created_at DESC").fetchall()

    total_value = sum(l["value"] or 0 for l in leads)
    open_leads = [l for l in leads if l["stage"] not in ("Won", "Lost")]
    won_leads = [l for l in leads if l["stage"] == "Won"]

    stats = {
        "total_leads": len(leads),
        "open_leads": len(open_leads),
        "won_leads": len(won_leads),
        "pipeline_value": total_value,
    }

    return render_template("dashboard.html", leads=leads, stats=stats, stages=STAGES)


@app.route("/dashboard/add", methods=["POST"])
@login_required
def dashboard_add():
    name = request.form.get("name", "").strip()
    email = request.form.get("email", "").strip()
    company = request.form.get("company", "").strip()
    source = request.form.get("source", "Manual Entry").strip()
    value = request.form.get("value", "0").strip()

    if not name:
        flash("Opportunity needs at least a name.", "error")
        return redirect(url_for("dashboard"))

    try:
        value_f = float(value) if value else 0.0
    except ValueError:
        value_f = 0.0

    db = get_db()
    db.execute(
        "INSERT INTO leads (name, email, company, phone, plan, source, value, stage, message, created_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (name, email, company, "", "", source, value_f, "New Lead", "",
         datetime.now(timezone.utc).isoformat()),
    )
    db.commit()
    flash(f"Added {name} to the pipeline.", "success")
    return redirect(url_for("dashboard"))


@app.route("/dashboard/stage/<int:lead_id>", methods=["POST"])
@login_required
def dashboard_update_stage(lead_id):
    new_stage = request.form.get("stage")
    if new_stage not in STAGES:
        flash("Unknown stage.", "error")
        return redirect(url_for("dashboard"))

    db = get_db()
    db.execute("UPDATE leads SET stage = ? WHERE id = ?", (new_stage, lead_id))
    db.commit()
    return redirect(url_for("dashboard"))


@app.route("/dashboard/delete/<int:lead_id>", methods=["POST"])
@login_required
def dashboard_delete(lead_id):
    db = get_db()
    db.execute("DELETE FROM leads WHERE id = ?", (lead_id,))
    db.commit()
    flash("Opportunity removed.", "success")
    return redirect(url_for("dashboard"))


# ---------------------------------------------------------------------------
# JSON API (small extra: powers the live pipeline-value counter on the
# dashboard without a full page reload)
# ---------------------------------------------------------------------------

@app.route("/api/stats")
@login_required
def api_stats():
    db = get_db()
    leads = db.execute("SELECT stage, value FROM leads").fetchall()
    total_value = sum(l["value"] or 0 for l in leads)
    by_stage = {}
    for l in leads:
        by_stage[l["stage"]] = by_stage.get(l["stage"], 0) + 1
    return jsonify({"total_leads": len(leads), "pipeline_value": total_value, "by_stage": by_stage})


# ---------------------------------------------------------------------------
# Admin panel (admin role only) — full control over leads, messages, users
# ---------------------------------------------------------------------------

@app.route("/admin")
@admin_required
def admin_overview():
    db = get_db()
    lead_count = db.execute("SELECT COUNT(*) AS c FROM leads").fetchone()["c"]
    pipeline_value = db.execute("SELECT COALESCE(SUM(value), 0) AS v FROM leads").fetchone()["v"]
    message_count = db.execute("SELECT COUNT(*) AS c FROM contact_messages").fetchone()["c"]
    new_message_count = db.execute(
        "SELECT COUNT(*) AS c FROM contact_messages WHERE status = 'new'"
    ).fetchone()["c"]
    user_count = db.execute("SELECT COUNT(*) AS c FROM users").fetchone()["c"]
    admin_count = db.execute("SELECT COUNT(*) AS c FROM users WHERE role = 'admin'").fetchone()["c"]

    recent_leads = db.execute(
        "SELECT * FROM leads ORDER BY created_at DESC LIMIT 5"
    ).fetchall()
    recent_messages = db.execute(
        "SELECT * FROM contact_messages ORDER BY created_at DESC LIMIT 5"
    ).fetchall()

    stats = {
        "lead_count": lead_count,
        "pipeline_value": pipeline_value,
        "message_count": message_count,
        "new_message_count": new_message_count,
        "user_count": user_count,
        "admin_count": admin_count,
    }
    return render_template(
        "admin/overview.html", stats=stats, recent_leads=recent_leads, recent_messages=recent_messages
    )


@app.route("/admin/leads")
@admin_required
def admin_leads():
    db = get_db()
    leads = db.execute("SELECT * FROM leads ORDER BY created_at DESC").fetchall()
    return render_template("admin/leads.html", leads=leads, stages=STAGES)


@app.route("/admin/leads/<int:lead_id>/edit", methods=["GET", "POST"])
@admin_required
def admin_lead_edit(lead_id):
    db = get_db()
    lead = db.execute("SELECT * FROM leads WHERE id = ?", (lead_id,)).fetchone()
    if not lead:
        flash("That opportunity no longer exists.", "error")
        return redirect(url_for("admin_leads"))

    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip()
        company = request.form.get("company", "").strip()
        phone = request.form.get("phone", "").strip()
        plan = request.form.get("plan", "").strip()
        source = request.form.get("source", "").strip()
        stage = request.form.get("stage", "New Lead")
        message = request.form.get("message", "").strip()
        try:
            value = float(request.form.get("value", "0") or 0)
        except ValueError:
            value = 0.0

        if not name:
            flash("Name is required.", "error")
            return render_template("admin/lead_edit.html", lead=lead, stages=STAGES), 400

        if stage not in STAGES:
            stage = "New Lead"

        db.execute(
            "UPDATE leads SET name=?, email=?, company=?, phone=?, plan=?, source=?, "
            "value=?, stage=?, message=? WHERE id=?",
            (name, email, company, phone, plan, source, value, stage, message, lead_id),
        )
        db.commit()
        flash(f"Updated {name}.", "success")
        return redirect(url_for("admin_leads"))

    return render_template("admin/lead_edit.html", lead=lead, stages=STAGES)


@app.route("/admin/leads/<int:lead_id>/delete", methods=["POST"])
@admin_required
def admin_lead_delete(lead_id):
    db = get_db()
    db.execute("DELETE FROM leads WHERE id = ?", (lead_id,))
    db.commit()
    flash("Opportunity deleted.", "success")
    return redirect(url_for("admin_leads"))


@app.route("/admin/messages")
@admin_required
def admin_messages():
    db = get_db()
    messages = db.execute("SELECT * FROM contact_messages ORDER BY created_at DESC").fetchall()
    return render_template("admin/messages.html", messages=messages)


@app.route("/admin/messages/<int:message_id>/status", methods=["POST"])
@admin_required
def admin_message_status(message_id):
    new_status = request.form.get("status")
    if new_status not in ("new", "read", "archived"):
        flash("Unknown status.", "error")
        return redirect(url_for("admin_messages"))
    db = get_db()
    db.execute("UPDATE contact_messages SET status = ? WHERE id = ?", (new_status, message_id))
    db.commit()
    return redirect(url_for("admin_messages"))


@app.route("/admin/messages/<int:message_id>/delete", methods=["POST"])
@admin_required
def admin_message_delete(message_id):
    db = get_db()
    db.execute("DELETE FROM contact_messages WHERE id = ?", (message_id,))
    db.commit()
    flash("Message deleted.", "success")
    return redirect(url_for("admin_messages"))


@app.route("/admin/users")
@admin_required
def admin_users():
    db = get_db()
    users = db.execute("SELECT * FROM users ORDER BY created_at DESC").fetchall()
    return render_template("admin/users.html", users=users)


@app.route("/admin/users/add", methods=["POST"])
@admin_required
def admin_user_add():
    name = request.form.get("name", "").strip()
    email = request.form.get("email", "").strip().lower()
    password = request.form.get("password", "")
    company = request.form.get("company", "").strip()
    role = request.form.get("role", "member")

    if role not in ("member", "admin"):
        role = "member"

    if not name or not email or len(password) < 6:
        flash("Name, email, and a password of at least 6 characters are required.", "error")
        return redirect(url_for("admin_users"))

    db = get_db()
    existing = db.execute("SELECT id FROM users WHERE email = ?", (email,)).fetchone()
    if existing:
        flash("A user with that email already exists.", "error")
        return redirect(url_for("admin_users"))

    db.execute(
        "INSERT INTO users (name, email, password_hash, company, role, is_active, created_at) "
        "VALUES (?, ?, ?, ?, ?, 1, ?)",
        (name, email, generate_password_hash(password), company, role,
         datetime.now(timezone.utc).isoformat()),
    )
    db.commit()
    flash(f"Created {role} account for {name}.", "success")
    return redirect(url_for("admin_users"))


@app.route("/admin/users/<int:user_id>/role", methods=["POST"])
@admin_required
def admin_user_role(user_id):
    new_role = request.form.get("role")
    if new_role not in ("member", "admin"):
        flash("Unknown role.", "error")
        return redirect(url_for("admin_users"))

    db = get_db()
    if user_id == session.get("user_id") and new_role != "admin":
        flash("You can't remove your own admin access.", "error")
        return redirect(url_for("admin_users"))

    db.execute("UPDATE users SET role = ? WHERE id = ?", (new_role, user_id))
    db.commit()
    flash("Role updated.", "success")
    return redirect(url_for("admin_users"))


@app.route("/admin/users/<int:user_id>/toggle-active", methods=["POST"])
@admin_required
def admin_user_toggle_active(user_id):
    if user_id == session.get("user_id"):
        flash("You can't deactivate your own account.", "error")
        return redirect(url_for("admin_users"))

    db = get_db()
    user = db.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    if not user:
        flash("User not found.", "error")
        return redirect(url_for("admin_users"))

    db.execute("UPDATE users SET is_active = ? WHERE id = ?", (0 if user["is_active"] else 1, user_id))
    db.commit()
    flash(("Deactivated " if user["is_active"] else "Reactivated ") + user["name"] + ".", "success")
    return redirect(url_for("admin_users"))


@app.route("/admin/users/<int:user_id>/delete", methods=["POST"])
@admin_required
def admin_user_delete(user_id):
    if user_id == session.get("user_id"):
        flash("You can't delete your own account while logged in.", "error")
        return redirect(url_for("admin_users"))

    db = get_db()
    remaining_admins = db.execute(
        "SELECT COUNT(*) AS c FROM users WHERE role = 'admin' AND id != ?", (user_id,)
    ).fetchone()["c"]
    target = db.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()

    if target and target["role"] == "admin" and remaining_admins == 0:
        flash("You can't delete the last remaining admin.", "error")
        return redirect(url_for("admin_users"))

    db.execute("DELETE FROM users WHERE id = ?", (user_id,))
    db.commit()
    flash("User deleted.", "success")
    return redirect(url_for("admin_users"))


# ---------------------------------------------------------------------------
# Error handlers
# ---------------------------------------------------------------------------

@app.errorhandler(404)
def not_found(e):
    return render_template("404.html"), 404


if __name__ == "__main__":
    if not os.path.exists(DB_PATH):
        init_db()
    else:
        init_db()  # idempotent — also backfills seed data if leads table empty
    app.run(debug=True, host="0.0.0.0", port=5000)
