"""JobPilot - a Streamlit studio for the ai-job-search workflow.

Run with: streamlit run app.py
"""

from __future__ import annotations

import html
import json
import re

import pandas as pd
import streamlit as st

import jobpilot_core as core

PAGES = ["Dashboard", "Profile", "Find jobs", "Tailor application", "Tracker", "Settings"]
EXPERIENCE_OPTIONS = [
    "Student / New grad",
    "0-2 years",
    "2-5 years",
    "5+ years",
    "Career switcher",
]
COUNTRY_OPTIONS = {
    "India": "IN",
    "United States": "US",
    "United Kingdom": "GB",
    "Canada": "CA",
    "Australia": "AU",
    "Germany": "DE",
    "Singapore": "SG",
    "United Arab Emirates": "AE",
}

st.set_page_config(
    page_title="JobPilot",
    page_icon=str(core.BASE_DIR / "assets" / "mascot" / "pip_flight_loop.gif"),
    layout="wide",
    initial_sidebar_state="expanded",
)
st.markdown(
    """
    <style>
      :root {
        --jp-accent: #4f46e5;
        --jp-accent-soft: rgba(79, 70, 229, 0.12);
        --jp-border: rgba(148, 163, 184, 0.28);
        --jp-muted: #64748b;
      }
      .block-container { padding-top: 1.6rem; padding-bottom: 3rem; max-width: 1200px; }
      div[data-testid="stMetric"] {
        background: rgba(148, 163, 184, 0.08);
        border: 1px solid var(--jp-border);
        border-radius: 12px;
        padding: 12px 16px;
      }
      div[data-testid="stVerticalBlockBorderWrapper"] { border-radius: 14px; }
      section[data-testid="stSidebar"] { border-right: 1px solid var(--jp-border); }
      .jp-hero {
        background: linear-gradient(120deg, rgba(79, 70, 229, 0.14), rgba(14, 165, 233, 0.10));
        border: 1px solid var(--jp-border);
        border-radius: 16px;
        padding: 22px 26px;
        margin-bottom: 18px;
      }
      .jp-hero h2 { margin: 0 0 4px 0; font-size: 1.55rem; }
      .jp-hero p { margin: 0; color: var(--jp-muted); }
      .jp-eyebrow {
        text-transform: uppercase; letter-spacing: 0.12em; font-size: 0.72rem;
        font-weight: 700; color: var(--jp-accent); margin-bottom: 6px;
      }
      .small-muted { color: var(--jp-muted); font-size: 0.82rem; }
      .pill {
        display: inline-block; padding: 2px 9px; border-radius: 999px;
        background: var(--jp-accent-soft); color: var(--jp-accent);
        font-size: 0.76rem; font-weight: 600; margin: 2px 5px 2px 0;
      }
      .pill-ok { background: rgba(16, 185, 129, 0.14); color: #047857; }
      .pill-warn { background: rgba(245, 158, 11, 0.16); color: #b45309; }
      .pill-muted { background: rgba(100, 116, 139, 0.14); color: var(--jp-muted); }
      .fit-good { color: #047857; }
      .fit-mid { color: #b45309; }
      .fit-low { color: #b91c1c; }
      .job-meta { color: var(--jp-muted); font-size: 0.85rem; margin: 2px 0 8px 0; }
      .job-desc { font-size: 0.92rem; line-height: 1.5; }
    </style>
    """,
    unsafe_allow_html=True,
)

if "profile" not in st.session_state:
    st.session_state.profile = core.load_profile()
if "settings" not in st.session_state:
    st.session_state.settings = core.load_settings()
if "jobs" not in st.session_state:
    st.session_state.jobs = core.load_jobs()
if "fits" not in st.session_state:
    st.session_state.fits = {}
if "docs" not in st.session_state:
    st.session_state.docs = {}
if "selected_job_key" not in st.session_state:
    st.session_state.selected_job_key = None
if "_pending_nav" in st.session_state:
    st.session_state["nav"] = st.session_state.pop("_pending_nav")
if "nav" not in st.session_state:
    st.session_state["nav"] = "Dashboard"

profile = st.session_state.profile
settings = st.session_state.settings
jobs = st.session_state.jobs


def flash(message: str, kind: str = "success") -> None:
    st.session_state["_flash"] = {"message": message, "kind": kind}


def show_flash() -> None:
    item = st.session_state.pop("_flash", None)
    if not item:
        return
    renderer = getattr(st, item.get("kind", "info"), st.info)
    renderer(item.get("message", ""))


def go(page: str) -> None:
    st.session_state["_pending_nav"] = page
    st.rerun()


def open_job(key: str, page: str = "Tailor application") -> None:
    st.session_state.selected_job_key = key
    st.session_state.pop("tailor_pick", None)
    go(page)


def current_fit(key: str) -> dict | None:
    return st.session_state.fits.get(key)


def current_docs(key: str) -> dict:
    return st.session_state.docs.setdefault(key, {})


def as_int(value, fallback: int = 0) -> int:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return fallback


def clean_text(text: str, limit: int = 280) -> str:
    text = re.sub(r"\s+", " ", text or "").strip()
    return text if len(text) <= limit else text[: limit - 1].rstrip() + "…"


def job_by_key(key: str) -> dict | None:
    return next((job for job in jobs if job.get("key") == key), None)


def score_of(job: dict) -> int:
    return as_int(job.get("fit_score"), 0)


@st.cache_data(show_spinner=False)
def pdf_bytes(markdown_text: str, title: str) -> bytes:
    return core.markdown_to_pdf(markdown_text, title)


def fit_class(score: int) -> str:
    if score >= 75:
        return "fit-good"
    if score >= 50:
        return "fit-mid"
    return "fit-low"


def sidebar() -> str:
    profile_pct = core.profile_completeness(profile)
    try:
        tracker_count = len(core.load_tracker())
    except Exception:
        tracker_count = 0
    has_key = bool((settings.get("xai_api_key") or "").strip())
    has_resume = bool((profile.get("cv_text") or "").strip())

    mascot = core.BASE_DIR / "assets" / "mascot" / "pip_flight_loop.gif"
    if mascot.exists():
        st.sidebar.image(str(mascot), width=92)
    st.sidebar.markdown("## JobPilot")
    st.sidebar.caption("Your private job search studio")
    page = st.sidebar.radio("Workspace", PAGES, key="nav", label_visibility="collapsed")
    st.sidebar.divider()
    st.sidebar.markdown(
        f"""
        <span class="pill">Profile {profile_pct}%</span>
        <span class="pill">{len(jobs)} jobs</span>
        <span class="pill">{tracker_count} applications</span>
        """,
        unsafe_allow_html=True,
    )
    st.sidebar.markdown(
        f"""
        <div class="small-muted" style="margin-top:8px">
          Resume <span class="pill {'pill-ok' if has_resume else 'pill-warn'}">
          {'indexed' if has_resume else 'missing'}</span><br>
          AI engine <span class="pill {'pill-ok' if has_key else 'pill-warn'}">
          {'Grok ready' if has_key else 'key needed'}</span>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.sidebar.divider()
    st.sidebar.caption("Results come from the repo's LinkedIn and freehire CLIs.")
    return page


def page_header(title: str, subtitle: str, eyebrow: str = "JobPilot") -> None:
    st.markdown(f'<div class="jp-eyebrow">{html.escape(eyebrow)}</div>', unsafe_allow_html=True)
    st.title(title)
    st.caption(subtitle)
    st.write("")


def render_job_card(job: dict, prefix: str) -> None:
    key = job["key"]
    fit = score_of(job)
    title = html.escape(job.get("title") or "Untitled")
    meta = " · ".join(
        html.escape(str(part))
        for part in [
            job.get("company"),
            job.get("location"),
            job.get("date"),
            job.get("source"),
        ]
        if part
    )
    with st.container(border=True):
        left, right = st.columns([5.2, 1.3], vertical_alignment="center")
        with left:
            st.markdown(f"#### {title}")
            st.markdown(f'<div class="job-meta">{meta}</div>', unsafe_allow_html=True)
            if job.get("description"):
                st.markdown(
                    f'<div class="job-desc">{html.escape(clean_text(job["description"], 260))}</div>',
                    unsafe_allow_html=True,
                )
            else:
                st.caption("No description cached. Open the posting to fetch full details.")
            matched = job.get("matched_skills") or []
            if matched:
                pills = "".join(
                    f'<span class="pill">{html.escape(str(skill))}</span>'
                    for skill in matched[:8]
                )
                st.markdown(pills, unsafe_allow_html=True)
        with right:
            st.markdown(
                f'<div style="font-size:0.75rem;color:#64748b;font-weight:600">FIT SCORE</div>'
                f'<div class="{fit_class(fit)}" style="font-size:2rem;font-weight:700;'
                f'line-height:1.1">{fit}%</div>',
                unsafe_allow_html=True,
            )
            st.progress(min(1.0, max(0.0, fit / 100)))
            if st.button("Tailor", key=f"{prefix}_tailor_{key}", type="primary", width="stretch"):
                open_job(key)
            if st.button("Details", key=f"{prefix}_detail_{key}", width="stretch"):
                open_job(key)


def show_errors(errors: list[str]) -> None:
    if not errors:
        return
    unique = list(dict.fromkeys(error for error in errors if error))
    for error in unique[:4]:
        st.warning(error)


# ---------------------------------------------------------------------------
# Dashboard
# ---------------------------------------------------------------------------


def page_dashboard() -> None:
    first_name = (profile.get("name") or "there").split()[0]
    roles = ", ".join(profile.get("target_roles") or ["your next role"])
    st.markdown(
        f"""
        <div class="jp-hero">
          <div class="jp-eyebrow">JobPilot workspace</div>
          <h2>Welcome back, {html.escape(first_name)}.</h2>
          <p>Targeting {html.escape(roles)}. Search, score, tailor, and track in one place.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )
    tracker = core.load_tracker()
    strong = sum(1 for job in jobs if score_of(job) >= 75)
    applied = int(tracker["status"].isin(["applied", "interview", "offer", "hired"]).sum())
    interviews = int(tracker["status"].eq("interview").sum())
    offers = int(tracker["status"].isin(["offer", "hired"]).sum())

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Jobs discovered", len(jobs))
    c2.metric("Strong fits", strong)
    c3.metric("Applications", applied)
    c4.metric("Interviews / offers", f"{interviews} / {offers}")

    st.write("")
    left, right = st.columns([1.55, 1])

    with left:
        st.subheader("Top matches")
        ranked = sorted(jobs, key=score_of, reverse=True)[:5]
        if not ranked:
            st.info("No jobs cached yet. Run your first search to populate this list.")
            if st.button("Find jobs", type="primary"):
                go("Find jobs")
        for job in ranked:
            score = score_of(job)
            with st.container(border=True):
                c1, c2, c3 = st.columns([4.6, 0.9, 1.1], vertical_alignment="center")
                with c1:
                    st.markdown(f"**{html.escape(job.get('title') or 'Untitled')}**")
                    st.caption(
                        " · ".join(
                            str(part)
                            for part in [
                                job.get("company"),
                                job.get("location"),
                                job.get("source"),
                            ]
                            if part
                        )
                    )
                with c2:
                    st.markdown(
                        f'<div class="{fit_class(score)}" style="font-size:1.25rem;'
                        f'font-weight:700;text-align:right">{score}%</div>',
                        unsafe_allow_html=True,
                    )
                with c3:
                    if st.button("Open", key=f"dash_open_{job['key']}", width="stretch"):
                        open_job(job["key"])

        st.subheader("Recent applications")
        if tracker.empty:
            st.caption("Nothing in the tracker yet. Tailor a role and save the package to start it.")
        else:
            recent = tracker.sort_values("date", ascending=False).head(6)
            st.dataframe(
                recent[["date", "company", "role", "status", "fit_rating"]],
                width="stretch",
                hide_index=True,
            )

    with right:
        st.subheader("Resume")
        cv_text = (profile.get("cv_text") or "").strip()
        if cv_text:
            st.success(f"Using your resume ({len(cv_text):,} characters indexed).")
            st.caption(
                "Every fit analysis, CV, and cover letter is generated from this resume plus "
                "your profile facts."
            )
        else:
            st.warning("No resume indexed yet. Upload it on the Profile page.")
        if st.button("Open profile", width="stretch"):
            go("Profile")

        st.subheader("AI engine")
        if (settings.get("xai_api_key") or "").strip():
            st.success(f"Grok ready ({settings.get('xai_model')}).")
        elif (settings.get("ollama_model") or "").strip():
            st.info(f"Using Ollama ({settings.get('ollama_model')}).")
        else:
            st.warning("No AI key yet. Fit scores and documents use templates.")
        if st.button("Open settings", width="stretch"):
            go("Settings")

        st.subheader("Quick actions")
        if st.button("Search for jobs", type="primary", width="stretch"):
            go("Find jobs")
        if st.button("Tailor an application", width="stretch"):
            go("Tailor application")
        if st.button("Update tracker", width="stretch"):
            go("Tracker")

        st.subheader("Profile check")
        items = [
            ("Email", bool(profile.get("email"))),
            ("Phone", bool(profile.get("phone"))),
            ("Summary", bool(profile.get("summary"))),
            ("Education", bool(profile.get("education"))),
            ("Projects", bool(profile.get("projects"))),
            ("Resume text", bool(cv_text)),
        ]
        for label, ok in items:
            st.caption(f"{label}: {'ready' if ok else 'missing'}")


# ---------------------------------------------------------------------------
# Profile
# ---------------------------------------------------------------------------


def page_profile() -> None:
    page_header(
        "Profile",
        "These facts are the only source of truth used by Grok. Keep them honest and current.",
    )
    pct = core.profile_completeness(profile)
    st.progress(pct / 100, text=f"Profile completeness: {pct}%")

    with st.expander("Resume on file", expanded=True):
        cv_text = (profile.get("cv_text") or "").strip()
        if cv_text:
            st.success(
                f"Resume indexed: {len(cv_text):,} characters. It is included with every "
                "AI request."
            )
            with st.expander("View extracted resume text"):
                st.text(cv_text)
            if st.button("Remove indexed resume", key="remove_resume"):
                updated = dict(profile)
                updated["cv_text"] = ""
                st.session_state.profile = core.save_profile(updated)
                st.rerun()
        else:
            st.info("Upload a PDF or text resume to ground fit analysis and document generation.")
        uploaded = st.file_uploader("Upload resume (PDF, TXT, MD)", type=["pdf", "txt", "md"])
        if uploaded is not None:
            if st.button("Import resume", type="primary"):
                try:
                    data = uploaded.getvalue()
                    text = core.extract_document_text(uploaded.name, data)
                    if not text.strip():
                        raise RuntimeError("No text could be extracted from that file.")
                    core.save_cv_upload(uploaded.name, data)
                    updated = dict(profile)
                    updated["cv_text"] = text
                    st.session_state.profile = core.save_profile(updated)
                    flash(f"Imported {len(text):,} characters from {uploaded.name}.")
                    st.rerun()
                except Exception as exc:
                    st.error(str(exc))

    with st.form("profile_form"):
        st.subheader("Identity")
        c1, c2 = st.columns(2)
        name = c1.text_input("Full name", value=profile.get("name", ""))
        email = c2.text_input("Email", value=profile.get("email", ""))
        phone = c1.text_input("Phone", value=profile.get("phone", ""))
        location = c2.text_input("Location", value=profile.get("location", ""))
        headline = st.text_input("Headline", value=profile.get("headline", ""))

        st.subheader("Search preferences")
        c1, c2 = st.columns(2)
        target_roles = c1.text_area(
            "Target roles (one per line or comma separated)",
            value="\n".join(profile.get("target_roles") or []),
            height=110,
        )
        target_locations = c2.text_area(
            "Target locations (one per line or comma separated)",
            value="\n".join(profile.get("target_locations") or []),
            height=110,
        )
        experience_value = profile.get("experience_level") or EXPERIENCE_OPTIONS[0]
        experience_options = EXPERIENCE_OPTIONS + (
            [experience_value] if experience_value not in EXPERIENCE_OPTIONS else []
        )
        c1, c2 = st.columns(2)
        experience_level = c1.selectbox(
            "Experience level",
            options=experience_options,
            index=experience_options.index(experience_value),
        )
        work_modes = c2.multiselect(
            "Work modes",
            options=["remote", "hybrid", "onsite"],
            default=[mode for mode in (profile.get("work_modes") or []) if mode in ("remote", "hybrid", "onsite")],
        )
        languages = st.text_input(
            "Languages (comma separated)",
            value=", ".join(profile.get("languages") or []),
        )

        st.subheader("Narrative")
        summary = st.text_area(
            "Professional summary",
            value=profile.get("summary", ""),
            height=130,
        )
        skills = st.text_area(
            "Skills (comma or newline separated)",
            value=", ".join(profile.get("skills") or []),
            height=100,
        )

        st.subheader("Evidence")
        education = st.text_area(
            "Education (Markdown)", value=profile.get("education", ""), height=150
        )
        experience = st.text_area(
            "Experience (Markdown)", value=profile.get("experience", ""), height=170
        )
        projects = st.text_area(
            "Projects (Markdown)", value=profile.get("projects", ""), height=260
        )
        certifications = st.text_area(
            "Certifications / achievements (Markdown)",
            value=profile.get("certifications", ""),
            height=120,
        )

        st.subheader("Links and constraints")
        links = profile.get("links") or {}
        c1, c2, c3 = st.columns(3)
        linkedin = c1.text_input("LinkedIn", value=links.get("linkedin", ""))
        github = c2.text_input("GitHub", value=links.get("github", ""))
        portfolio = c3.text_input("Portfolio", value=links.get("portfolio", ""))
        dealbreakers = st.text_area(
            "Deal-breakers (Markdown)",
            value=profile.get("dealbreakers", ""),
            height=100,
        )

        submitted = st.form_submit_button("Save profile", type="primary")
        if submitted:
            updated = dict(profile)
            updated.update(
                {
                    "name": name.strip(),
                    "email": email.strip(),
                    "phone": phone.strip(),
                    "location": location.strip(),
                    "headline": headline.strip(),
                    "target_roles": core._as_list(target_roles),
                    "target_locations": core._as_list(target_locations),
                    "experience_level": experience_level,
                    "work_modes": work_modes,
                    "languages": core._as_list(languages),
                    "summary": summary.strip(),
                    "skills": core._as_list(skills),
                    "education": education.strip(),
                    "experience": experience.strip(),
                    "projects": projects.strip(),
                    "certifications": certifications.strip(),
                    "links": {
                        "linkedin": linkedin.strip(),
                        "github": github.strip(),
                        "portfolio": portfolio.strip(),
                    },
                    "dealbreakers": dealbreakers.strip(),
                }
            )
            st.session_state.profile = core.save_profile(updated)
            flash("Profile saved.")
            st.rerun()

    st.divider()
    c1, c2 = st.columns(2)
    with c1:
        if st.button("Personalize repo CLAUDE.md", width="stretch"):
            try:
                path = core.personalize_claude_md(profile)
                st.success(f"Updated {path}. A backup is in data/CLAUDE.md.bak.")
            except Exception as exc:
                st.error(str(exc))
    with c2:
        st.download_button(
            "Download profile JSON",
            data=json.dumps(profile, indent=2, ensure_ascii=False),
            file_name="jobpilot_profile.json",
            mime="application/json",
            width="stretch",
        )
    st.caption(f"Profile file: {core.PROFILE_PATH}")


# ---------------------------------------------------------------------------
# Find jobs
# ---------------------------------------------------------------------------


def page_find_jobs() -> None:
    page_header(
        "Find jobs",
        "Search LinkedIn and freehire through the repo's Bun CLIs, then rank results against your profile.",
    )
    prereqs = core.cli_status()
    if not prereqs["bun"]:
        st.error("Bun is not installed, so the job CLIs cannot run. Install it from https://bun.sh.")
    if not prereqs["linkedin_cli"] or not prereqs["freehire_cli"]:
        st.warning("One or more search CLIs are missing from .agents/skills.")

    with st.form("search_form"):
        c1, c2 = st.columns([2, 1])
        default_queries = "\n".join(profile.get("target_roles") or ["Data Scientist"])
        queries_text = c1.text_area(
            "Search queries (one per line)",
            value=default_queries,
            height=110,
            help="Each query is run against each selected source.",
        )
        location = c2.text_input(
            "Location",
            value=(profile.get("target_locations") or ["India"])[0],
        )
        c1, c2, c3 = st.columns(3)
        sources = c1.multiselect(
            "Sources", options=["LinkedIn", "freehire"], default=["LinkedIn", "freehire"]
        )
        remote_only = c2.checkbox("Remote only", value=False)
        jobage = c3.selectbox("Posted within (days)", options=[7, 14, 30, 60], index=2)
        c1, c2, c3 = st.columns(3)
        limit = c1.selectbox("Results per query/source", options=[5, 10, 15, 20], index=1)
        country_label = c2.selectbox(
            "freehire country", options=list(COUNTRY_OPTIONS), index=0
        )
        experience_options = ["internship", "entry", "associate", "mid-senior", "director", "executive"]
        level = (profile.get("experience_level") or "").lower()
        default_experience = (
            ["entry", "associate"] if "student" in level or "new grad" in level else []
        )
        experience = c3.multiselect(
            "LinkedIn experience",
            options=experience_options,
            default=default_experience,
            help="Narrows LinkedIn results by seniority. Leave empty to include all levels.",
        )
        st.caption("Searches run in parallel and can take up to a minute.")
        submitted = st.form_submit_button(
            "Search jobs",
            type="primary",
            disabled=not prereqs["bun"] or not sources,
        )
        if submitted:
            queries = [line.strip() for line in queries_text.splitlines() if line.strip()]
            if not queries:
                st.error("Add at least one search query.")
            else:
                with st.spinner(f"Searching {len(queries) * len(sources)} combinations..."):
                    try:
                        found, errors = core.search_jobs(
                            profile,
                            queries=queries,
                            location=location,
                            sources=sources,
                            jobage=jobage,
                            limit=limit,
                            remote_only=remote_only,
                            freehire_country=COUNTRY_OPTIONS[country_label],
                            experience=",".join(experience) if experience else None,
                        )
                        st.session_state.jobs = core.load_jobs()
                        st.session_state["search_errors"] = errors
                        st.session_state["search_count"] = len(found)
                        if found:
                            flash(
                                f"Added {len(found)} results. "
                                f"{len(st.session_state.jobs)} jobs in your cache."
                            )
                        else:
                            flash("No new jobs matched. Try a broader query or location.", "info")
                    except Exception as exc:
                        st.session_state["search_errors"] = [str(exc)]
                st.rerun()

    show_errors(st.session_state.get("search_errors", []))

    jobs_now = st.session_state.jobs
    if not jobs_now:
        st.info("No cached jobs yet. Run a search above.")
        return

    st.subheader(f"Results ({len(jobs_now)})")
    f1, f2, f3, f4 = st.columns([1.2, 1.4, 1.2, 1.1])
    min_score = f1.slider("Minimum fit", 0, 100, 35, step=5)
    text_filter = f2.text_input("Filter title or company", "")
    all_sources = sorted(
        {
            source.strip()
            for job in jobs_now
            for source in (job.get("source") or "").split("+")
            if source.strip()
        }
    )
    selected_sources = f3.multiselect("Source filter", all_sources, default=all_sources)
    sort_by = f4.selectbox("Sort by", ["Fit score", "Newest"])

    filtered = []
    for job in jobs_now:
        if score_of(job) < min_score:
            continue
        if text_filter and text_filter.lower() not in (
            f"{job.get('title', '')} {job.get('company', '')}".lower()
        ):
            continue
        job_sources = {part.strip() for part in (job.get("source") or "").split("+") if part.strip()}
        if selected_sources and not (job_sources & set(selected_sources)):
            continue
        filtered.append(job)

    if sort_by == "Newest":
        filtered.sort(key=lambda item: item.get("found_at", ""), reverse=True)
    else:
        filtered.sort(key=score_of, reverse=True)

    st.caption(f"Showing {min(len(filtered), 40)} of {len(filtered)} matching jobs.")
    for job in filtered[:40]:
        render_job_card(job, "find")


# ---------------------------------------------------------------------------
# Tailor application
# ---------------------------------------------------------------------------


def page_tailor() -> None:
    page_header(
        "Tailor application",
        "Fetch the full posting, analyze the fit, and generate an editable CV and cover letter.",
    )
    jobs_now = st.session_state.jobs
    if not jobs_now:
        st.info("No jobs cached yet. Run a search first.")
        if st.button("Go to Find jobs", type="primary"):
            go("Find jobs")
        return

    by_key = {job["key"]: job for job in jobs_now}
    keys = sorted(
        by_key,
        key=lambda key: score_of(by_key[key]),
        reverse=True,
    )
    selected = st.session_state.selected_job_key
    if selected not in by_key:
        selected = keys[0]
    index = keys.index(selected)
    picked = st.selectbox(
        "Choose a job",
        options=keys,
        index=index,
        format_func=lambda key: core.job_summary(by_key[key]),
        key="tailor_pick",
    )
    st.session_state.selected_job_key = picked
    job = by_key[picked]
    key = job["key"]

    fit = current_fit(key)
    docs = current_docs(key)

    header_left, header_right = st.columns([4.5, 1.4])
    with header_left:
        st.subheader(job.get("title") or "Untitled")
        st.caption(
            " · ".join(
                part
                for part in [
                    job.get("company"),
                    job.get("location"),
                    job.get("date"),
                    job.get("source"),
                ]
                if part
            )
        )
        if job.get("url"):
            st.link_button("Open original posting", job["url"])
    with header_right:
        st.metric("Profile fit", f"{score_of(job)}%")
        if st.button("Refresh posting", width="stretch"):
            with st.spinner("Fetching full posting..."):
                try:
                    detail = core.fetch_job_detail(job, profile)
                    st.session_state.jobs = [
                        detail if item["key"] == key else item for item in jobs_now
                    ]
                    st.session_state.fits.pop(key, None)
                    st.rerun()
                except Exception as exc:
                    st.error(str(exc))

    tab_fit, tab_docs, tab_posting = st.tabs(["Fit analysis", "Documents", "Posting"])

    with tab_fit:
        c1, c2 = st.columns([1, 2])
        with c1:
            if st.button("Analyze fit", type="primary", width="stretch"):
                with st.spinner("Evaluating fit..."):
                    result = core.generate_fit(profile, job, settings)
                    st.session_state.fits[key] = result
                st.rerun()
            if (settings.get("xai_api_key") or "").strip():
                st.caption(f"Engine: Grok ({settings.get('xai_model')})")
            elif (settings.get("ollama_model") or "").strip():
                st.caption(f"Engine: Ollama ({settings.get('ollama_model')})")
            else:
                st.caption("No AI key: heuristic scoring will be used.")
        with c2:
            if not fit:
                st.info(
                    "Run an analysis to see strengths, gaps, and keywords. "
                    "The score already shown comes from title, skills, seniority, and location."
                )
            else:
                if fit.get("error"):
                    st.warning(f"AI unavailable, used a heuristic instead: {fit['error']}")
                score = as_int(fit.get("score"), score_of(job))
                m1, m2, m3 = st.columns(3)
                m1.metric("AI score", f"{score}/100")
                m2.metric("Verdict", fit.get("verdict") or "—")
                m3.metric("Recommendation", (fit.get("recommendation") or "—").title())
                st.write(fit.get("summary") or "")
                s1, s2 = st.columns(2)
                with s1:
                    st.markdown("**Strengths**")
                    for item in fit.get("strengths") or []:
                        st.markdown(f"- {item}")
                with s2:
                    st.markdown("**Gaps**")
                    for item in fit.get("gaps") or []:
                        st.markdown(f"- {item}")
                if fit.get("keywords"):
                    st.markdown("**Keywords from the posting**")
                    st.write(", ".join(fit["keywords"]))
                st.caption(f"Engine: {fit.get('engine') or 'unknown'}")

    with tab_docs:
        action1, action2, action3 = st.columns(3)
        if action1.button("Generate CV", type="primary", width="stretch"):
            with st.spinner("Drafting CV..."):
                text, engine, warning = core.generate_cv(profile, job, settings)
                docs["cv"] = text
                docs["cv_engine"] = engine
                docs["cv_warning"] = warning
                st.session_state.pop(f"cv_edit_{key}", None)
            st.rerun()
        if action2.button("Generate cover letter", width="stretch"):
            with st.spinner("Drafting cover letter..."):
                text, engine, warning = core.generate_cover(profile, job, settings)
                docs["cover"] = text
                docs["cover_engine"] = engine
                docs["cover_warning"] = warning
                st.session_state.pop(f"cover_edit_{key}", None)
            st.rerun()
        if action3.button("Generate both", width="stretch"):
            with st.spinner("Drafting CV and cover letter..."):
                cv_text, cv_engine, cv_warning = core.generate_cv(profile, job, settings)
                cover_text, cover_engine, cover_warning = core.generate_cover(
                    profile, job, settings
                )
                docs.update(
                    {
                        "cv": cv_text,
                        "cv_engine": cv_engine,
                        "cv_warning": cv_warning,
                        "cover": cover_text,
                        "cover_engine": cover_engine,
                        "cover_warning": cover_warning,
                    }
                )
                st.session_state.pop(f"cv_edit_{key}", None)
                st.session_state.pop(f"cover_edit_{key}", None)
            st.rerun()

        if not docs.get("cv") and not docs.get("cover"):
            st.info("Generate a CV and/or cover letter. You can edit both before saving.")
        else:
            cv_col, cover_col = st.columns(2)
            with cv_col:
                st.markdown("**CV**")
                if docs.get("cv_warning"):
                    st.caption(f"Fallback used: {docs['cv_warning']}")
                cv_value = st.text_area(
                    "CV draft (Markdown)",
                    value=docs.get("cv", ""),
                    height=430,
                    key=f"cv_edit_{key}",
                    label_visibility="collapsed",
                )
                st.caption(f"Engine: {docs.get('cv_engine', '—')}")
            with cover_col:
                st.markdown("**Cover letter**")
                if docs.get("cover_warning"):
                    st.caption(f"Fallback used: {docs['cover_warning']}")
                cover_value = st.text_area(
                    "Cover letter draft (Markdown)",
                    value=docs.get("cover", ""),
                    height=430,
                    key=f"cover_edit_{key}",
                    label_visibility="collapsed",
                )
                st.caption(f"Engine: {docs.get('cover_engine', '—')}")

            d1, d2, d3, d4 = st.columns(4)
            if cv_value:
                d1.download_button(
                    "Download CV (.md)",
                    data=cv_value,
                    file_name="cv.md",
                    mime="text/markdown",
                    width="stretch",
                )
                try:
                    d2.download_button(
                        "Download CV (.pdf)",
                        data=pdf_bytes(cv_value, "CV"),
                        file_name="cv.pdf",
                        mime="application/pdf",
                        width="stretch",
                    )
                except Exception as exc:
                    d2.caption(f"PDF unavailable: {exc}")
            if cover_value:
                d3.download_button(
                    "Download cover (.md)",
                    data=cover_value,
                    file_name="cover_letter.md",
                    mime="text/markdown",
                    width="stretch",
                )
                try:
                    d4.download_button(
                        "Download cover (.pdf)",
                        data=pdf_bytes(cover_value, "Cover Letter"),
                        file_name="cover_letter.pdf",
                        mime="application/pdf",
                        width="stretch",
                    )
                except Exception as exc:
                    d4.caption(f"PDF unavailable: {exc}")

            if fit is None and (cv_value or cover_value):
                st.caption("No fit analysis yet. Saving the package will use heuristic fit notes.")
            if st.button(
                "Save application package",
                type="primary",
                disabled=not (cv_value and cover_value),
                width="content",
            ):
                try:
                    effective_fit = fit or core.fallback_fit(profile, job)
                    folder = core.archive_application(
                        profile, job, effective_fit, cv_value, cover_value
                    )
                    st.success(f"Saved to {folder.relative_to(core.BASE_DIR)} and updated the tracker.")
                except Exception as exc:
                    st.error(str(exc))

    with tab_posting:
        if job.get("description"):
            st.markdown(job["description"])
        else:
            st.info("No description cached. Use “Refresh posting” above to fetch it.")
        if job.get("skills"):
            st.markdown("**Listed skills:** " + ", ".join(str(skill) for skill in job["skills"]))
        st.caption(f"Job key: {key}")


# ---------------------------------------------------------------------------
# Tracker
# ---------------------------------------------------------------------------


def page_tracker() -> None:
    page_header(
        "Tracker",
        "A single CSV log of every application. Edit rows inline and download a copy anytime.",
    )
    frame = core.load_tracker()
    if frame.empty:
        st.info("No applications tracked yet. Save an application package to create the first row.")
    else:
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Rows", len(frame))
        c2.metric("Applied", int(frame["status"].isin(["applied", "interview", "offer", "hired"]).sum()))
        c3.metric("Interviews", int(frame["status"].eq("interview").sum()))
        c4.metric("Offers", int(frame["status"].isin(["offer", "hired"]).sum()))

    st.caption(
        "Statuses: " + ", ".join(core.STATUSES) + ". Fit rating is 0-100."
    )
    edited = st.data_editor(
        frame,
        width="stretch",
        num_rows="dynamic",
        hide_index=True,
        column_config={
            "status": st.column_config.SelectboxColumn(options=core.STATUSES),
            "fit_rating": st.column_config.NumberColumn(min_value=0, max_value=100, step=1),
            "date": st.column_config.TextColumn(help="YYYY-MM-DD"),
            "source": st.column_config.LinkColumn(display_text="posting"),
        },
        key="tracker_editor",
    )
    c1, c2, c3 = st.columns(3)
    if c1.button("Save tracker", type="primary", width="stretch"):
        core.save_tracker(edited)
        flash("Tracker saved to job_search_tracker.csv.")
        st.rerun()
    c2.download_button(
        "Download CSV",
        data=edited.to_csv(index=False),
        file_name="job_search_tracker.csv",
        mime="text/csv",
        width="stretch",
    )
    if c3.button("Reload from disk", width="stretch"):
        st.rerun()
    st.caption(f"File: {core.TRACKER_PATH}")


# ---------------------------------------------------------------------------
# Settings
# ---------------------------------------------------------------------------


def page_settings() -> None:
    page_header(
        "Settings",
        "Connect Grok, optionally use a local Ollama model, and check the repo prerequisites.",
    )
    settings_now = st.session_state.settings
    prereqs = core.cli_status()
    has_resume = bool((profile.get("cv_text") or "").strip())

    st.subheader("Prerequisites")
    rows = [
        ("Bun runtime", prereqs["bun"], "Required to run the job search CLIs"),
        ("LinkedIn CLI", prereqs["linkedin_cli"], str(core.LINKEDIN_CLI.relative_to(core.BASE_DIR))),
        ("freehire CLI", prereqs["freehire_cli"], str(core.FREEHIRE_CLI.relative_to(core.BASE_DIR))),
        ("Resume indexed", has_resume, "Upload it on the Profile page"),
        ("PDF renderer", True, "xhtml2pdf"),
    ]
    for label, ok, detail in rows:
        st.caption(f"{label}: {'Ready' if ok else 'Missing'} — {detail}")

    st.divider()
    st.subheader("Grok (xAI)")
    st.caption(
        "Create a key at https://console.x.ai. The key is sent only to api.x.ai and is stored "
        f"locally at {core.CONFIG_PATH} when you choose to remember it."
    )
    c1, c2 = st.columns([2, 1])
    xai_key = c1.text_input(
        "xAI API key",
        value=settings_now.get("xai_api_key", ""),
        type="password",
        key="settings_xai_key",
    )
    xai_model = c2.text_input(
        "Model",
        value=settings_now.get("xai_model", "grok-4.7"),
        key="settings_xai_model",
    )
    xai_base = st.text_input(
        "API base URL",
        value=settings_now.get("xai_base_url", "https://api.x.ai/v1"),
        key="settings_xai_base",
    )
    remember = st.checkbox("Remember key on this Mac", value=True, key="settings_remember")

    def settings_payload() -> dict:
        return {
            **settings_now,
            "xai_api_key": xai_key.strip(),
            "xai_model": xai_model.strip() or "grok-4.7",
            "xai_base_url": xai_base.strip() or "https://api.x.ai/v1",
        }

    t1, t2 = st.columns(2)
    if t1.button("Test Grok connection", width="stretch"):
        try:
            message = core.test_xai(settings_payload())
            st.success(message)
        except Exception as exc:
            st.error(str(exc))
    if t2.button("Save AI settings", type="primary", width="stretch"):
        payload = settings_payload()
        st.session_state.settings = payload
        if remember:
            core.save_settings(payload)
            flash("AI settings saved.")
        else:
            core.clear_saved_settings()
            core.save_settings({**payload, "xai_api_key": ""})
            flash("Settings saved for this session only; the key was not written to disk.")
        st.rerun()

    st.divider()
    st.subheader("Ollama fallback (optional)")
    c1, c2 = st.columns(2)
    ollama_base = c1.text_input(
        "Ollama base URL",
        value=settings_now.get("ollama_base_url", "http://localhost:11434"),
        key="settings_ollama_base",
    )
    ollama_model = c2.text_input(
        "Ollama model",
        value=settings_now.get("ollama_model", ""),
        placeholder="e.g. llama3.1:8b",
        key="settings_ollama_model",
    )
    o1, o2 = st.columns(2)
    if o1.button("Test Ollama", width="stretch"):
        try:
            message = core.test_ollama({**settings_now, "ollama_base_url": ollama_base.strip()})
            st.success(message)
        except Exception as exc:
            st.error(str(exc))
    if o2.button("Save Ollama settings", width="stretch"):
        payload = {
            **settings_now,
            "xai_api_key": xai_key.strip(),
            "xai_model": xai_model.strip() or "grok-4.7",
            "xai_base_url": xai_base.strip() or "https://api.x.ai/v1",
            "ollama_base_url": ollama_base.strip() or "http://localhost:11434",
            "ollama_model": ollama_model.strip(),
        }
        st.session_state.settings = payload
        if remember:
            core.save_settings(payload)
        else:
            core.clear_saved_settings()
            core.save_settings({**payload, "xai_api_key": ""})
        flash("Ollama settings saved.")
        st.rerun()

    st.divider()
    st.subheader("Data and privacy")
    c1, c2, c3 = st.columns(3)
    with c1:
        if st.button("Clear saved API key", width="stretch"):
            fresh = dict(st.session_state.settings)
            fresh["xai_api_key"] = ""
            st.session_state.settings = fresh
            core.save_settings(fresh)
            flash("Saved key removed. Your other settings were kept.")
            st.rerun()
    with c2:
        if st.button("Clear cached jobs", width="stretch"):
            try:
                core.JOBS_PATH.unlink()
            except FileNotFoundError:
                pass
            st.session_state.jobs = []
            flash("Cached jobs cleared.")
            st.rerun()
    with c3:
        if st.button("Personalize CLAUDE.md", width="stretch"):
            try:
                path = core.personalize_claude_md(profile)
                st.success(f"Updated {path}.")
            except Exception as exc:
                st.error(str(exc))

    st.caption(
        f"Profile: {core.PROFILE_PATH} · Jobs cache: {core.JOBS_PATH} · "
        f"Tracker: {core.TRACKER_PATH} · Settings: {core.CONFIG_PATH}"
    )
    st.caption(
        "Generated documents and the tracker are gitignored. Do not commit API keys or personal data."
    )


# ---------------------------------------------------------------------------
# Router
# ---------------------------------------------------------------------------

page = sidebar()
show_flash()
if page == "Dashboard":
    page_dashboard()
elif page == "Profile":
    page_profile()
elif page == "Find jobs":
    page_find_jobs()
elif page == "Tailor application":
    page_tailor()
elif page == "Tracker":
    page_tracker()
elif page == "Settings":
    page_settings()
