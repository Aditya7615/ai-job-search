"""Core services for the JobPilot Streamlit UI.

Wraps the existing ai-job-search portal CLIs, profile data, Groq (free tier),
optional local Ollama, the application tracker, and document generation.
"""

from __future__ import annotations

import hashlib
import io
import json
import os
import re
import shutil
import subprocess
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, datetime
from pathlib import Path
from typing import Any

import requests

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
DOCUMENTS_DIR = BASE_DIR / "documents"
APPLICATIONS_DIR = DOCUMENTS_DIR / "applications"
CV_DIR = DOCUMENTS_DIR / "cv"
PROFILE_PATH = DATA_DIR / "profile.json"
JOBS_PATH = DATA_DIR / "jobs.json"
TRACKER_PATH = BASE_DIR / "job_search_tracker.csv"
CLAUDE_MD_PATH = BASE_DIR / "CLAUDE.md"
CONFIG_PATH = Path.home() / ".jobpilot" / "config.json"

LINKEDIN_CLI = BASE_DIR / ".agents" / "skills" / "linkedin-search" / "cli" / "src" / "cli.ts"
FREEHIRE_CLI = BASE_DIR / ".agents" / "skills" / "freehire-search" / "cli" / "src" / "cli.ts"

TRACKER_COLUMNS = [
    "date",
    "company",
    "sector",
    "role",
    "role_type",
    "channel",
    "status",
    "contact_person",
    "fit_rating",
    "notes",
    "cv_file",
    "cover_letter_file",
    "source",
    "deadline",
]

STATUSES = [
    "drafted",
    "applied",
    "interview",
    "offer",
    "hired",
    "rejected",
    "no_response",
    "offer_declined",
    "withdrawn",
]

DEPRECATED_GROQ_MODELS = {
    "llama-3.1-8b-instant",
    "llama-3.3-70b-versatile",
    "qwen/qwen3.6-27b",
    "grok-4.7",
}

DEFAULT_SETTINGS = {
    "groq_api_key": "",
    "groq_model": "openai/gpt-oss-120b",
    "groq_base_url": "https://api.groq.com/openai/v1",
    "ollama_base_url": "http://localhost:11434",
    "ollama_model": "",
}

SYSTEM_PROMPT = """You are an expert career coach, ATS-aware resume writer, and cover-letter editor.
Use only facts contained in the candidate profile. Never invent employers, degrees, dates,
metrics, skills, or achievements. When a fact is genuinely missing, write a clear
[ADD: ...] placeholder instead of guessing. Keep language specific, concise, and human."""

DEFAULT_PROFILE = {
    "name": "Aditya Goyal",
    "email": "",
    "phone": "",
    "location": "India",
    "headline": "Data Scientist | NLP & LLM Engineer",
    "summary": "",
    "target_roles": ["Data Scientist", "NLP Engineer", "LLM Engineer"],
    "target_locations": ["India", "Remote"],
    "experience_level": "Student / New grad",
    "work_modes": ["remote", "hybrid", "onsite"],
    "languages": ["English"],
    "skills": [
        "Python",
        "Machine Learning",
        "Deep Learning",
        "NLP",
        "LLMs",
        "Transformers",
        "PyTorch",
        "TensorFlow",
        "scikit-learn",
        "Pandas",
        "NumPy",
        "SQL",
        "Streamlit",
        "Git",
        "Data Visualization",
    ],
    "education": "",
    "experience": "",
    "projects": "",
    "certifications": "",
    "links": {
        "linkedin": "",
        "github": "https://github.com/Aditya7615",
        "portfolio": "",
    },
    "dealbreakers": "",
    "cv_text": "",
    "updated_at": "",
}


# ---------------------------------------------------------------------------
# Small file helpers
# ---------------------------------------------------------------------------


def _read_json(path: Path, fallback: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return fallback


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    tmp.replace(path)


def _write_json(path: Path, value: Any) -> None:
    _write_text(path, json.dumps(value, indent=2, ensure_ascii=False))


def _now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _today() -> str:
    return date.today().isoformat()


def _as_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, str):
        return [item.strip() for item in re.split(r"[,\n;]+", value) if item.strip()]
    return []


# ---------------------------------------------------------------------------
# Profile
# ---------------------------------------------------------------------------


def default_profile() -> dict[str, Any]:
    profile = json.loads(json.dumps(DEFAULT_PROFILE))
    return profile


def load_profile() -> dict[str, Any]:
    saved = _read_json(PROFILE_PATH, {})
    profile = default_profile()
    for key, value in saved.items():
        if key == "links" and isinstance(value, dict):
            profile["links"].update(value)
        else:
            profile[key] = value
    for key in ("target_roles", "target_locations", "work_modes", "languages", "skills"):
        profile[key] = _as_list(profile.get(key))
    return profile


def save_profile(profile: dict[str, Any]) -> dict[str, Any]:
    profile = dict(profile)
    profile["updated_at"] = _now_iso()
    _write_json(PROFILE_PATH, profile)
    return profile


def profile_completeness(profile: dict[str, Any]) -> int:
    checks = [
        bool(profile.get("name")),
        bool(profile.get("email")),
        bool(profile.get("phone")),
        bool(profile.get("location")),
        bool(profile.get("headline")),
        bool(profile.get("summary")),
        bool(profile.get("target_roles")),
        len(profile.get("skills") or []) >= 5,
        bool(profile.get("education")),
        bool(profile.get("experience") or profile.get("projects")),
        bool((profile.get("links") or {}).get("github") or (profile.get("links") or {}).get("linkedin")),
        bool(profile.get("cv_text")),
    ]
    return round(100 * sum(checks) / len(checks))


def profile_to_text(profile: dict[str, Any]) -> str:
    links = profile.get("links") or {}
    parts = [
        f"Name: {profile.get('name', '')}",
        f"Headline: {profile.get('headline', '')}",
        f"Location: {profile.get('location', '')}",
        f"Email: {profile.get('email', '')}",
        f"Phone: {profile.get('phone', '')}",
        f"Experience level: {profile.get('experience_level', '')}",
        f"Target roles: {', '.join(profile.get('target_roles') or [])}",
        f"Target locations: {', '.join(profile.get('target_locations') or [])}",
        f"Work modes: {', '.join(profile.get('work_modes') or [])}",
        f"Languages: {', '.join(profile.get('languages') or [])}",
        f"Skills: {', '.join(profile.get('skills') or [])}",
        f"LinkedIn: {links.get('linkedin', '')}",
        f"GitHub: {links.get('github', '')}",
        f"Portfolio: {links.get('portfolio', '')}",
        f"Summary: {profile.get('summary', '')}",
        f"Education:\n{profile.get('education', '')}",
        f"Experience:\n{profile.get('experience', '')}",
        f"Projects:\n{profile.get('projects', '')}",
        f"Certifications:\n{profile.get('certifications', '')}",
        f"Deal-breakers: {profile.get('dealbreakers', '')}",
    ]
    cv_text = (profile.get("cv_text") or "").strip()
    if cv_text:
        parts.append(f"Source CV text (authoritative):\n{cv_text[:8000]}")
    return "\n".join(part for part in parts if part.strip())


def extract_document_text(filename: str, data: bytes) -> str:
    if filename.lower().endswith(".pdf"):
        try:
            import pdfplumber

            with pdfplumber.open(io.BytesIO(data)) as pdf:
                text = "\n".join(page.extract_text() or "" for page in pdf.pages)
            if text.strip():
                return text.strip()
        except Exception:
            pass
        from pypdf import PdfReader

        reader = PdfReader(io.BytesIO(data))
        return "\n".join(page.extract_text() or "" for page in reader.pages).strip()
    return data.decode("utf-8", errors="ignore").strip()


def save_cv_upload(filename: str, data: bytes) -> Path:
    CV_DIR.mkdir(parents=True, exist_ok=True)
    safe_name = re.sub(r"[^A-Za-z0-9._-]+", "_", Path(filename).name)
    path = CV_DIR / safe_name
    path.write_bytes(data)
    return path


# ---------------------------------------------------------------------------
# Job portal CLIs
# ---------------------------------------------------------------------------


def find_bun() -> str | None:
    candidates = [
        shutil.which("bun"),
        os.path.expanduser("~/.bun/bin/bun"),
        os.path.expanduser("~/.bun/bin/bun.exe"),
    ]
    for candidate in candidates:
        if candidate and Path(candidate).exists():
            return candidate
    return None


def cli_status() -> dict[str, bool]:
    return {
        "bun": find_bun() is not None,
        "linkedin_cli": LINKEDIN_CLI.exists(),
        "freehire_cli": FREEHIRE_CLI.exists(),
    }


def _run_cli(script: Path, args: list[str], timeout: int = 90) -> Any:
    bun = find_bun()
    if not bun:
        raise RuntimeError("bun is not installed. Install it from https://bun.sh and retry.")
    env = os.environ.copy()
    env["PATH"] = f"{Path(bun).parent}{os.pathsep}{env.get('PATH', '')}"
    proc = subprocess.run(
        [bun, "run", str(script), *args],
        cwd=str(BASE_DIR),
        capture_output=True,
        text=True,
        timeout=timeout,
        env=env,
    )
    if proc.returncode != 0:
        message = (proc.stderr or proc.stdout).strip()
        for line in reversed(message.splitlines()):
            try:
                payload = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(payload, dict) and payload.get("error"):
                message = payload["error"]
                break
        raise RuntimeError(message or f"CLI exited with code {proc.returncode}")
    try:
        return json.loads(proc.stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"CLI returned non-JSON output: {proc.stdout[:300]}") from exc


def search_linkedin(
    query: str,
    location: str,
    jobage: int,
    limit: int,
    remote_only: bool = False,
    experience: str | None = None,
) -> list[dict[str, Any]]:
    args = [
        "search",
        "-q",
        query,
        "-l",
        location or "India",
        "--jobage",
        str(jobage),
        "--limit",
        str(limit),
        "--format",
        "json",
    ]
    if remote_only:
        args.extend(["--remote", "remote"])
    if experience:
        args.extend(["--experience", experience])
    payload = _run_cli(LINKEDIN_CLI, args)
    results = payload.get("results", []) if isinstance(payload, dict) else []
    jobs = []
    for item in results:
        jobs.append(
            {
                "id": str(item.get("id", "")),
                "source": "LinkedIn",
                "title": item.get("title") or "Untitled",
                "company": item.get("company") or "",
                "location": item.get("location") or "",
                "date": item.get("date") or "",
                "url": item.get("url") or "",
                "description": item.get("description"),
                "skills": item.get("skills") or [],
                "work_mode": item.get("work_mode"),
                "seniority": item.get("seniority"),
                "salary": item.get("salary"),
                "query": query,
                "found_at": _now_iso(),
            }
        )
    return jobs


def search_freehire(
    query: str,
    country: str,
    jobage: int,
    limit: int,
    remote_only: bool = False,
) -> list[dict[str, Any]]:
    args = [
        "search",
        "-q",
        query,
        "--jobage",
        str(jobage),
        "--limit",
        str(limit),
        "--format",
        "json",
        "--no-description",
    ]
    if country:
        args.extend(["--country", country])
    if remote_only:
        args.extend(["--remote", "remote"])
    payload = _run_cli(FREEHIRE_CLI, args)
    results = payload.get("results", []) if isinstance(payload, dict) else []
    jobs = []
    for item in results:
        jobs.append(
            {
                "id": str(item.get("id", "")),
                "source": "freehire",
                "title": item.get("title") or "Untitled",
                "company": item.get("company") or "",
                "location": item.get("location") or "",
                "date": item.get("date") or "",
                "url": item.get("url") or "",
                "description": item.get("description"),
                "skills": item.get("skills") or [],
                "work_mode": item.get("work_mode"),
                "seniority": item.get("seniority"),
                "salary": item.get("salary"),
                "query": query,
                "found_at": _now_iso(),
            }
        )
    return jobs


def job_key(job: dict[str, Any]) -> str:
    url = (job.get("url") or "").strip().lower().rstrip("/")
    if url:
        return hashlib.sha1(url.encode("utf-8")).hexdigest()
    raw = f"{job.get('company', '')}|{job.get('title', '')}".lower()
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()


def score_job(job: dict[str, Any], profile: dict[str, Any]) -> dict[str, Any]:
    title = (job.get("title") or "").lower()
    description = (job.get("description") or "").lower()
    job_skills = " ".join(str(skill) for skill in (job.get("skills") or [])).lower()
    haystack = f"{title}\n{description}\n{job_skills}"
    location = (job.get("location") or "").lower()
    profile_skills = [skill for skill in (profile.get("skills") or []) if skill.strip()]
    target_roles = [role for role in (profile.get("target_roles") or []) if role.strip()]

    matched_skills = [skill for skill in profile_skills if skill.lower() in haystack]
    missing_skills = [skill for skill in profile_skills if skill not in matched_skills]

    role_hits = [role for role in target_roles if role.lower() in title]
    if not role_hits:
        role_tokens = set()
        for role in target_roles:
            role_tokens.update(
                token for token in re.findall(r"[a-z0-9]+", role.lower()) if len(token) > 2
            )
        partial_tokens = {token for token in role_tokens if token in title}
        role_score = 20 if len(partial_tokens) >= 2 else 5
    else:
        role_score = 30

    denominator = max(6, min(len(profile_skills), 12)) if profile_skills else 1
    skill_score = min(45, round(45 * len(matched_skills) / denominator))

    experience_level = (profile.get("experience_level") or "").lower()
    seniority_text = f"{title}\n{description}"
    senior_markers = re.findall(
        r"\b(senior|staff|principal|lead|manager|director|head|architect|[5-9]\+? years)\b",
        seniority_text,
    )
    junior_markers = re.findall(
        r"\b(intern|internship|graduate|new grad|junior|entry[- ]level|associate|trainee)\b",
        seniority_text,
    )
    if "student" in experience_level or "new grad" in experience_level:
        if junior_markers:
            seniority_score = 15
        elif senior_markers:
            seniority_score = 0
        else:
            seniority_score = 8
    else:
        seniority_score = 10

    if "india" in location or "remote" in location or "anywhere" in location:
        location_score = 10
    elif any(city in location for city in ("bengaluru", "hyderabad", "pune", "mumbai", "delhi", "chennai")):
        location_score = 10
    else:
        location_score = 3

    total = role_score + skill_score + seniority_score + location_score
    if not job.get("description"):
        total = min(total, 82)
    total = max(5, min(98, total))

    if total >= 75:
        verdict = "Strong fit"
    elif total >= 55:
        verdict = "Good fit"
    elif total >= 40:
        verdict = "Moderate fit"
    else:
        verdict = "Weak fit"

    reasons = []
    if role_hits:
        reasons.append(f"Title matches target role: {', '.join(role_hits)}")
    if matched_skills:
        reasons.append(f"{len(matched_skills)} profile skills appear in the posting")
    if junior_markers and ("student" in experience_level or "new grad" in experience_level):
        reasons.append("Entry-level or graduate-friendly language")
    if senior_markers and ("student" in experience_level or "new grad" in experience_level):
        reasons.append("Posting reads as senior; may be a stretch")

    return {
        "fit_score": total,
        "fit_verdict": verdict,
        "matched_skills": matched_skills,
        "missing_skills": missing_skills[:10],
        "fit_reasons": reasons,
        "has_description": bool(job.get("description")),
    }


def dedupe_jobs(jobs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    merged: dict[str, dict[str, Any]] = {}
    for job in jobs:
        key = job_key(job)
        if key not in merged:
            merged[key] = dict(job)
            merged[key]["key"] = key
            continue
        current = merged[key]
        for field in ("description", "seniority", "salary", "work_mode"):
            if not current.get(field) and job.get(field):
                current[field] = job[field]
        if not current.get("skills") and job.get("skills"):
            current["skills"] = job["skills"]
        if job.get("source") and job["source"] not in (current.get("source") or ""):
            current["source"] = f"{current.get('source')} + {job['source']}"
    return list(merged.values())


def search_jobs(
    profile: dict[str, Any],
    queries: list[str],
    location: str,
    sources: list[str],
    jobage: int = 30,
    limit: int = 10,
    remote_only: bool = False,
    freehire_country: str = "IN",
    experience: str | None = None,
) -> tuple[list[dict[str, Any]], list[str]]:
    tasks = []
    errors: list[str] = []
    queries = [query.strip() for query in queries if query.strip()]
    with ThreadPoolExecutor(max_workers=4) as pool:
        for query in queries:
            if "LinkedIn" in sources:
                tasks.append(
                    pool.submit(
                        search_linkedin,
                        query,
                        location,
                        jobage,
                        limit,
                        remote_only,
                        experience,
                    )
                )
            if "freehire" in sources:
                tasks.append(
                    pool.submit(search_freehire, query, freehire_country, jobage, limit, remote_only)
                )
        collected: list[dict[str, Any]] = []
        for future in as_completed(tasks):
            try:
                collected.extend(future.result())
            except Exception as exc:
                errors.append(str(exc))

    jobs = dedupe_jobs(collected)
    for job in jobs:
        job.update(score_job(job, profile))
    jobs.sort(key=lambda item: item.get("fit_score", 0), reverse=True)
    save_jobs(jobs)
    return jobs, errors


def load_jobs() -> list[dict[str, Any]]:
    payload = _read_json(JOBS_PATH, {"jobs": []})
    return payload.get("jobs", []) if isinstance(payload, dict) else []


def save_jobs(jobs: list[dict[str, Any]]) -> None:
    existing = {job.get("key"): job for job in load_jobs() if job.get("key")}
    for job in jobs:
        key = job.get("key") or job_key(job)
        job["key"] = key
        existing[key] = job
    ordered = sorted(
        existing.values(),
        key=lambda item: item.get("found_at", ""),
        reverse=True,
    )[:500]
    _write_json(JOBS_PATH, {"updated_at": _now_iso(), "jobs": ordered})


def fetch_job_detail(job: dict[str, Any], profile: dict[str, Any] | None = None) -> dict[str, Any]:
    source = job.get("source", "")
    if "LinkedIn" in source:
        payload = _run_cli(LINKEDIN_CLI, ["detail", str(job["id"]), "--format", "json"])
        merged = dict(job)
        merged.update(
            {
                "title": payload.get("title") or job.get("title"),
                "company": payload.get("company") or job.get("company"),
                "location": payload.get("location") or job.get("location"),
                "description": payload.get("description") or job.get("description"),
                "url": payload.get("url") or job.get("url"),
                "seniority": payload.get("seniority"),
                "employment_type": payload.get("employmentType"),
                "is_active": payload.get("isActive"),
            }
        )
    elif "freehire" in source:
        payload = _run_cli(FREEHIRE_CLI, ["detail", str(job["id"]), "--format", "json"])
        merged = dict(job)
        merged.update(
            {
                "title": payload.get("title") or job.get("title"),
                "company": payload.get("company") or job.get("company"),
                "location": payload.get("location") or job.get("location"),
                "description": payload.get("description") or job.get("description"),
                "url": payload.get("url") or job.get("url"),
                "skills": payload.get("skills") or job.get("skills") or [],
                "seniority": payload.get("seniority"),
                "salary": payload.get("salary"),
                "work_mode": payload.get("work_mode") or job.get("work_mode"),
            }
        )
    else:
        raise RuntimeError(f"Unknown job source: {source}")

    merged["key"] = job.get("key") or job_key(merged)
    if profile:
        merged.update(score_job(merged, profile))
    merged["detail_fetched_at"] = _now_iso()
    save_jobs([merged])
    return merged


def job_summary(job: dict[str, Any]) -> str:
    score = job.get("fit_score", 0)
    return f"{score}% · {job.get('title', 'Untitled')} @ {job.get('company', 'Unknown')}"


# ---------------------------------------------------------------------------
# Settings + LLM providers
# ---------------------------------------------------------------------------


def load_settings() -> dict[str, Any]:
    settings = dict(DEFAULT_SETTINGS)
    saved = _read_json(CONFIG_PATH, {})
    if isinstance(saved, dict):
        for key in DEFAULT_SETTINGS:
            if key in saved:
                settings[key] = saved[key]
    if settings.get("groq_model") in DEPRECATED_GROQ_MODELS:
        settings["groq_model"] = DEFAULT_SETTINGS["groq_model"]
    if not settings.get("groq_api_key"):
        settings["groq_api_key"] = os.environ.get("GROQ_API_KEY", "")
    return settings


def save_settings(settings: dict[str, Any]) -> None:
    payload = {key: settings.get(key, DEFAULT_SETTINGS[key]) for key in DEFAULT_SETTINGS}
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    _write_json(CONFIG_PATH, payload)
    try:
        CONFIG_PATH.chmod(0o600)
    except OSError:
        pass


def clear_saved_settings() -> None:
    try:
        CONFIG_PATH.unlink()
    except FileNotFoundError:
        pass


def _chat_groq(
    settings: dict[str, Any],
    messages: list[dict[str, str]],
    json_mode: bool,
    max_tokens: int,
    temperature: float,
    timeout: int = 180,
) -> str:
    api_key = (settings.get("groq_api_key") or "").strip()
    if not api_key:
        raise RuntimeError("No Groq API key configured. Add one in Settings.")
    base = (settings.get("groq_base_url") or DEFAULT_SETTINGS["groq_base_url"]).rstrip("/")
    model = (settings.get("groq_model") or DEFAULT_SETTINGS["groq_model"]).strip()
    if model in DEPRECATED_GROQ_MODELS:
        model = DEFAULT_SETTINGS["groq_model"]
    payload: dict[str, Any] = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    if json_mode:
        payload["response_format"] = {"type": "json_object"}
    response = None
    for attempt in range(3):
        response = requests.post(
            f"{base}/chat/completions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=timeout,
        )
        if response.status_code != 429:
            break
        try:
            wait = float(response.headers.get("retry-after", ""))
        except ValueError:
            wait = 6 * (attempt + 1)
        if attempt == 2:
            break
        time.sleep(min(wait, 30))
    if response is None:
        raise RuntimeError("Groq request failed before receiving a response.")
    if response.status_code != 200:
        detail = response.text[:400] if response.text else response.reason
        raise RuntimeError(f"Groq API error {response.status_code}: {detail}")
    data = response.json()
    try:
        return data["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as exc:
        raise RuntimeError(f"Unexpected Groq response: {str(data)[:300]}") from exc


def _chat_ollama(
    settings: dict[str, Any],
    messages: list[dict[str, str]],
    timeout: int = 300,
) -> str:
    model = (settings.get("ollama_model") or "").strip()
    if not model:
        raise RuntimeError("No Ollama model configured. Add one in Settings.")
    base = (settings.get("ollama_base_url") or DEFAULT_SETTINGS["ollama_base_url"]).rstrip("/")
    response = requests.post(
        f"{base}/api/chat",
        json={"model": model, "messages": messages, "stream": False},
        timeout=timeout,
    )
    if response.status_code != 200:
        raise RuntimeError(f"Ollama error {response.status_code}: {response.text[:300]}")
    data = response.json()
    content = (data.get("message") or {}).get("content")
    if not content:
        raise RuntimeError(f"Unexpected Ollama response: {str(data)[:300]}")
    return content


def generate_text(
    settings: dict[str, Any],
    system: str,
    user: str,
    json_mode: bool = False,
    max_tokens: int = 4000,
) -> tuple[str, str]:
    if (settings.get("groq_api_key") or "").strip():
        content = _chat_groq(
            settings,
            [{"role": "system", "content": system}, {"role": "user", "content": user}],
            json_mode=json_mode,
            max_tokens=max_tokens,
            temperature=0.35,
        )
        model = settings.get("groq_model") or DEFAULT_SETTINGS["groq_model"]
        if model in DEPRECATED_GROQ_MODELS:
            model = DEFAULT_SETTINGS["groq_model"]
        return content, f"Groq ({model})"
    if (settings.get("ollama_model") or "").strip():
        content = _chat_ollama(
            settings,
            [{"role": "system", "content": system}, {"role": "user", "content": user}],
        )
        return content, f"Ollama ({settings.get('ollama_model')})"
    raise RuntimeError("No AI engine configured. Add a Groq API key or an Ollama model in Settings.")


def test_groq(settings: dict[str, Any]) -> str:
    api_key = (settings.get("groq_api_key") or "").strip()
    if not api_key:
        raise RuntimeError("Enter a Groq API key first.")
    base = (settings.get("groq_base_url") or DEFAULT_SETTINGS["groq_base_url"]).rstrip("/")
    response = requests.get(
        f"{base}/models",
        headers={"Authorization": f"Bearer {api_key}"},
        timeout=30,
    )
    if response.status_code != 200:
        raise RuntimeError(f"Groq returned {response.status_code}: {response.text[:300]}")
    data = response.json()
    models = data.get("data") or []
    names = [item.get("id", "") for item in models if isinstance(item, dict)]
    preview = ", ".join(names[:8]) if names else "connection OK"
    return f"Connected. Available models: {preview}"


def test_ollama(settings: dict[str, Any]) -> str:
    base = (settings.get("ollama_base_url") or DEFAULT_SETTINGS["ollama_base_url"]).rstrip("/")
    response = requests.get(f"{base}/api/tags", timeout=10)
    if response.status_code != 200:
        raise RuntimeError(f"Ollama returned {response.status_code}")
    models = [item.get("name", "") for item in response.json().get("models", [])]
    return "Connected. Models: " + (", ".join(models) if models else "none installed")


def parse_json_response(text: str) -> dict[str, Any]:
    cleaned = text.strip()
    cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\s*```$", "", cleaned)
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        start = cleaned.find("{")
        end = cleaned.rfind("}")
        if start >= 0 and end > start:
            return json.loads(cleaned[start : end + 1])
        raise


def _job_text(job: dict[str, Any], limit: int = 8000) -> str:
    skills = ", ".join(str(skill) for skill in (job.get("skills") or []))
    description = (job.get("description") or "").strip()
    return (
        f"Title: {job.get('title', '')}\n"
        f"Company: {job.get('company', '')}\n"
        f"Location: {job.get('location', '')}\n"
        f"Work mode: {job.get('work_mode') or ''}\n"
        f"Seniority: {job.get('seniority') or ''}\n"
        f"Salary: {job.get('salary') or ''}\n"
        f"Skills: {skills}\n"
        f"URL: {job.get('url', '')}\n"
        f"Description:\n{description[:limit]}"
    )


def fit_prompt(profile: dict[str, Any], job: dict[str, Any]) -> str:
    return f"""Evaluate this candidate's fit for the job below.

Return ONLY a JSON object with exactly these keys:
- score: integer 0-100
- verdict: one of "Strong fit", "Good fit", "Moderate fit", "Weak fit"
- summary: 2 sentences
- strengths: array of 2-4 short bullets grounded in the candidate profile
- gaps: array of 1-4 short bullets (honest missing requirements)
- keywords: array of 5-10 exact terms from the posting worth mirroring in the CV
- recommendation: one of "apply", "maybe", "skip"

CANDIDATE PROFILE
{profile_to_text(profile)}

JOB
{_job_text(job)}
"""


def cv_prompt(profile: dict[str, Any], job: dict[str, Any]) -> str:
    return f"""Write a tailored, ATS-friendly CV in Markdown for this candidate and job.

Structure rules:
- Start with the candidate's name as an H1, then one contact line, then these exact H2
  headings in this order, only when the profile has content for them:
  Professional Summary, Technical Skills, Education, Experience, Projects,
  Certifications.
- Use bold text for employers, job titles, project names, and degrees. Use bullet points
  (one line each) for achievements. Keep the hierarchy obvious.
- Include at most 3 of the candidate's most job-relevant projects. Omit unrelated projects.
- Keep the rendered CV to 1-2 pages. Remove lower-school details if space is tight.

Content rules:
- Use only facts from the candidate profile. Never invent anything.
- Rewrite the summary and reorder skills to target this job.
- Use the posting's exact keywords only where the candidate truthfully has them.
- Add [ADD: ...] placeholders for important facts that are missing.
- Use normal ASCII hyphens and quotes, not non-breaking or fancy Unicode characters.
- No tables, columns, icons, images, horizontal rules, or "references available" lines.
- Output ONLY the Markdown CV, with no commentary.

CANDIDATE PROFILE
{profile_to_text(profile)}

JOB
{_job_text(job)}
"""


def cv_review_prompt(profile: dict[str, Any], job: dict[str, Any], cv_markdown: str) -> str:
    return f"""Audit this tailored CV against the candidate profile and the job posting.

Return ONLY a JSON object with exactly these keys:
- alignment_score: integer 0-100
- verdict: one of "Strong alignment", "Good alignment", "Needs work"
- grounding_issues: array of short strings for claims not supported by the profile
- alignment_issues: array of short strings for important job requirements the CV misses
- missing_keywords: array of exact posting terms absent from the CV that the candidate can
  truthfully claim
- formatting_issues: array of short strings for structure or ATS problems

Rules:
- Be specific and concise. Each array item must be one short sentence.
- Never suggest adding a fact the profile does not support.
- Output ONLY the JSON object, with no commentary.

CANDIDATE PROFILE
{profile_to_text(profile)}

JOB
{_job_text(job)}

CURRENT CV
{cv_markdown}
"""


def cv_revision_prompt(
    profile: dict[str, Any],
    job: dict[str, Any],
    cv_markdown: str,
    review: dict[str, Any],
) -> str:
    issues: list[str] = []
    for field in ("grounding_issues", "alignment_issues", "formatting_issues"):
        for item in review.get(field) or []:
            issues.append(f"- {item}")
    missing = review.get("missing_keywords") or []
    if missing:
        issues.append("- Consider truthful use of these posting terms: " + ", ".join(missing))
    issue_text = "\n".join(issues) or "- Improve clarity, structure, and job alignment."

    return f"""Rewrite the CV below to fix the audit findings. Keep every truthful fact.

AUDIT FINDINGS
{issue_text}

Rewrite rules:
- Start with the candidate's name as an H1, then one contact line, then these exact H2
  headings in this order, only when the profile has content for them:
  Professional Summary, Technical Skills, Education, Experience, Projects,
  Certifications.
- Use bold text for employers, job titles, project names, and degrees. Use bullet points
  (one line each) for achievements.
- Keep at most 3 of the most job-relevant projects. Keep it to 1-2 rendered pages.
- Never invent employers, degrees, dates, metrics, skills, or achievements.
- Remove or soften unsupported claims. Keep [ADD: ...] placeholders for missing facts.
- Use the posting's exact keywords only where the candidate truthfully has them.
- Use normal ASCII hyphens and quotes. No tables, columns, icons, images, or horizontal rules.
- Output ONLY the complete Markdown CV, with no commentary.

CANDIDATE PROFILE
{profile_to_text(profile)}

JOB
{_job_text(job)}

CURRENT CV
{cv_markdown}
"""

def cover_prompt(profile: dict[str, Any], job: dict[str, Any]) -> str:
    return f"""Write a one-page cover letter in Markdown for this candidate and job.

Rules:
- Use only facts from the candidate profile. Never invent anything.
- 250-350 words. Specific to this company and role, not generic.
- Warm, direct, professional tone. No clichés and no exaggerated claims.
- Address "Dear Hiring Manager" unless the posting names a person.
- Include one short paragraph connecting the candidate's actual projects/skills
  to the role's most important requirements.
- Acknowledge a genuine gap only if it is important, without undermining the application.
- End with a simple call to action and the candidate's name.
- Output ONLY the Markdown cover letter, with no commentary.

CANDIDATE PROFILE
{profile_to_text(profile)}

JOB
{_job_text(job)}
"""


def fallback_fit(profile: dict[str, Any], job: dict[str, Any]) -> dict[str, Any]:
    scored = score_job(job, profile)
    matched = scored["matched_skills"]
    missing = scored["missing_skills"]
    strengths = []
    if matched:
        strengths.append("Matching skills: " + ", ".join(matched[:6]))
    target_roles = ", ".join(profile.get("target_roles") or [])
    strengths.append(f"Target roles on this profile: {target_roles}")
    if (profile.get("experience_level") or "").lower().startswith(("student", "new")):
        strengths.append("Entry-level positioning is appropriate for a new-grad search")
    gaps = []
    if missing:
        gaps.append("Profile skills not mentioned in the posting: " + ", ".join(missing[:5]))
    if not job.get("description"):
        gaps.append("No full description fetched yet, so this score is a title-level estimate")
    summary = (
        f"{job.get('title', 'This role')} at {job.get('company', 'the company')} looks like a "
        f"{scored['fit_verdict'].lower()} based on title, location, and skill overlap. "
        "Fetch the full posting and add Groq in Settings for a deeper evaluation."
    )
    return {
        "score": scored["fit_score"],
        "verdict": scored["fit_verdict"],
        "summary": summary,
        "strengths": strengths,
        "gaps": gaps,
        "keywords": matched[:8],
        "recommendation": "apply" if scored["fit_score"] >= 60 else "maybe",
        "engine": "Heuristic (no AI key)",
    }


def generate_fit(
    profile: dict[str, Any], job: dict[str, Any], settings: dict[str, Any]
) -> dict[str, Any]:
    try:
        text, engine = generate_text(
            settings, SYSTEM_PROMPT, fit_prompt(profile, job), json_mode=True, max_tokens=1200
        )
        data = parse_json_response(text)
        data["engine"] = engine
        return data
    except Exception as exc:
        result = fallback_fit(profile, job)
        result["error"] = str(exc)
        return result


def _fallback_cv(profile: dict[str, Any]) -> str:
    links = profile.get("links") or {}
    contact = " · ".join(
        part
        for part in [
            profile.get("email"),
            profile.get("phone"),
            profile.get("location"),
            links.get("linkedin"),
            links.get("github"),
            links.get("portfolio"),
        ]
        if part
    )
    lines = [f"# {profile.get('name', 'Your Name')}", contact, ""]
    if profile.get("headline"):
        lines += [f"**{profile['headline']}**", ""]
    summary = profile.get("summary") or (
        "Add a 3-4 line professional summary in the Profile tab. Focus on your strongest "
        "projects, the problems you solve, and the roles you are targeting."
    )
    lines += ["## Summary", summary, "", "## Skills", ", ".join(profile.get("skills") or []), ""]
    education = profile.get("education") or "[ADD: degree, institution, graduation year, relevant coursework]"
    lines += ["## Education", education, ""]
    experience = profile.get("experience") or "[ADD: internships, research, freelance, or part-time experience]"
    lines += ["## Experience", experience, ""]
    projects = profile.get("projects") or "[ADD: 2-3 projects with the problem, approach, tools, and result]"
    lines += ["## Projects", projects, ""]
    if profile.get("certifications"):
        lines += ["## Certifications", profile["certifications"], ""]
    if profile.get("languages"):
        lines += ["## Languages", ", ".join(profile["languages"]), ""]
    return "\n".join(lines).strip() + "\n"


def _fallback_cover(profile: dict[str, Any], job: dict[str, Any]) -> str:
    name = profile.get("name", "Your Name")
    company = job.get("company") or "your team"
    role = job.get("title") or "this role"
    matched = score_job(job, profile)["matched_skills"]
    skills = ", ".join(matched[:5]) if matched else ", ".join((profile.get("skills") or [])[:5])
    summary = profile.get("summary") or (
        "I am building a career at the intersection of data science, natural language "
        "processing, and practical machine learning."
    )
    return f"""# Cover Letter

{name}
{profile.get('email', '')} · {profile.get('phone', '')} · {profile.get('location', '')}

Dear Hiring Manager,

I am applying for the **{role}** position at **{company}**. {summary}

The role's emphasis on {skills} lines up with the work I have been doing. My projects have
given me hands-on experience turning messy text and data into working models and usable
interfaces. [ADD: one concrete project result that proves this, with a number if possible.]

I am especially interested in {company} because [ADD: one specific, verified reason tied to
the company's product, team, or mission]. I would bring curiosity, careful evaluation habits,
and a willingness to learn quickly to the team.

Thank you for considering my application. I would welcome the chance to discuss how I can
contribute to {company}.

Sincerely,
{name}
"""


def generate_cv(
    profile: dict[str, Any], job: dict[str, Any], settings: dict[str, Any]
) -> tuple[str, str, str | None]:
    try:
        text, engine = generate_text(
            settings, SYSTEM_PROMPT, cv_prompt(profile, job), max_tokens=4000
        )
        return sanitize_document_text(text).strip(), engine, None
    except Exception as exc:
        return _fallback_cv(profile), "Template (no AI key)", str(exc)


def generate_cover(
    profile: dict[str, Any], job: dict[str, Any], settings: dict[str, Any]
) -> tuple[str, str, str | None]:
    try:
        text, engine = generate_text(
            settings, SYSTEM_PROMPT, cover_prompt(profile, job), max_tokens=2000
        )
        return sanitize_document_text(text).strip(), engine, None
    except Exception as exc:
        return _fallback_cover(profile, job), "Template (no AI key)", str(exc)


def verify_cv(
    profile: dict[str, Any], job: dict[str, Any], cv_markdown: str, settings: dict[str, Any]
) -> dict[str, Any]:
    prompt = cv_review_prompt(profile, job, cv_markdown)
    errors: list[str] = []
    for json_mode in (True, False):
        try:
            text, engine = generate_text(
                settings,
                SYSTEM_PROMPT,
                prompt,
                json_mode=json_mode,
                max_tokens=2000,
            )
            data = parse_json_response(text)
            if not isinstance(data, dict):
                raise RuntimeError("Groq returned an unexpected review format.")
            data["engine"] = engine
            return data
        except Exception as exc:
            errors.append(str(exc))
    return {"error": " | ".join(errors)}


def revise_cv(
    profile: dict[str, Any],
    job: dict[str, Any],
    cv_markdown: str,
    review: dict[str, Any],
    settings: dict[str, Any],
) -> tuple[str, str, str | None]:
    try:
        text, engine = generate_text(
            settings,
            SYSTEM_PROMPT,
            cv_revision_prompt(profile, job, cv_markdown, review),
            max_tokens=4000,
        )
        return sanitize_document_text(text).strip(), engine, None
    except Exception as exc:
        return cv_markdown, "Unchanged", str(exc)


# ---------------------------------------------------------------------------
# Markdown → HTML → PDF
# ---------------------------------------------------------------------------

DOCUMENT_CSS = """
@page { size: A4; margin: 15mm 16mm; }
body {
  font-family: Helvetica, Arial, sans-serif;
  font-size: 10pt;
  line-height: 1.38;
  color: #1b1f24;
}
h1 { font-size: 21pt; margin: 0 0 2pt 0; color: #111827; letter-spacing: 0.2pt; }
h2 { font-size: 11.5pt; margin: 12pt 0 4pt 0; padding-bottom: 2pt;
     border-bottom: 1.2px solid #cbd5e1; color: #111827; text-transform: uppercase;
     letter-spacing: 0.5pt; page-break-after: avoid; }
h3 { font-size: 10.5pt; margin: 7pt 0 1pt 0; page-break-after: avoid; }
p { margin: 2pt 0 4pt 0; }
ul { margin: 2pt 0 4pt 14pt; padding: 0; }
li { margin: 1.5pt 0; }
a { color: #1d4ed8; text-decoration: none; }
strong { color: #111827; }
em { color: #334155; }
"""

UNICODE_REPLACEMENTS = {
    "\u2010": "-",
    "\u2011": "-",
    "\u2012": "-",
    "\u2013": "-",
    "\u2014": "-",
    "\u00a0": " ",
    "\u2009": " ",
    "\u202f": " ",
    "\u200b": "",
}


def sanitize_document_text(text: str) -> str:
    """Normalize characters xhtml2pdf renders as ZapfDingbats glyphs."""
    for old, new in UNICODE_REPLACEMENTS.items():
        text = text.replace(old, new)
    return text


def markdown_to_html(markdown_text: str, title: str = "Document") -> str:
    import markdown as markdown_lib

    markdown_text = sanitize_document_text(markdown_text)
    body = markdown_lib.markdown(markdown_text, extensions=["extra", "sane_lists"])
    return (
        "<!DOCTYPE html><html><head><meta charset='utf-8'>"
        f"<title>{title}</title><style>{DOCUMENT_CSS}</style></head>"
        f"<body>{body}</body></html>"
    )


def markdown_to_pdf(markdown_text: str, title: str = "Document") -> bytes:
    from xhtml2pdf import pisa

    html = markdown_to_html(markdown_text, title)
    buffer = io.BytesIO()
    result = pisa.CreatePDF(io.StringIO(html), dest=buffer, encoding="utf-8")
    if result.err:
        raise RuntimeError("PDF rendering failed")
    return buffer.getvalue()


def safe_slug(text: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", (text or "").lower()).strip("-")
    return slug or "untitled"


# ---------------------------------------------------------------------------
# Tracker + archives
# ---------------------------------------------------------------------------


def load_tracker() -> Any:
    import pandas as pd

    if TRACKER_PATH.exists():
        try:
            frame = pd.read_csv(TRACKER_PATH, dtype=str).fillna("")
        except (pd.errors.ParserError, pd.errors.EmptyDataError, OSError):
            frame = pd.DataFrame(columns=TRACKER_COLUMNS)
        for column in TRACKER_COLUMNS:
            if column not in frame.columns:
                frame[column] = ""
        return frame[TRACKER_COLUMNS]
    return pd.DataFrame(columns=TRACKER_COLUMNS)


def save_tracker(frame: Any) -> None:
    import pandas as pd

    TRACKER_PATH.parent.mkdir(parents=True, exist_ok=True)
    cleaned = frame.copy()
    cleaned = cleaned.fillna("")
    cleaned = cleaned[
        ~(
            cleaned.apply(lambda row: "".join(str(v).strip() for v in row.values) == "", axis=1)
        )
    ]
    for column in TRACKER_COLUMNS:
        if column not in cleaned.columns:
            cleaned[column] = ""
    cleaned[TRACKER_COLUMNS].to_csv(TRACKER_PATH, index=False)


def upsert_tracker(
    profile: dict[str, Any],
    job: dict[str, Any],
    status: str = "drafted",
    notes: str = "",
    cv_file: str = "",
    cover_letter_file: str = "",
) -> Any:
    frame = load_tracker()
    company = job.get("company") or ""
    role = job.get("title") or ""
    mask = (
        frame["company"].str.lower().eq(company.lower())
        & frame["role"].str.lower().eq(role.lower())
    )
    row = {
        "date": _today(),
        "company": company,
        "sector": "",
        "role": role,
        "role_type": "full_time",
        "channel": job.get("source") or "JobPilot",
        "status": status,
        "contact_person": "",
        "fit_rating": str(job.get("fit_score", "")),
        "notes": notes,
        "cv_file": cv_file,
        "cover_letter_file": cover_letter_file,
        "source": job.get("url") or "",
        "deadline": "",
    }
    import pandas as pd

    if mask.any():
        index = frame.index[mask][0]
        for key, value in row.items():
            if value or key in ("status", "fit_rating"):
                frame.at[index, key] = value
    else:
        frame = pd.concat([frame, pd.DataFrame([row])], ignore_index=True)
    save_tracker(frame)
    return frame


def archive_application(
    profile: dict[str, Any],
    job: dict[str, Any],
    fit: dict[str, Any],
    cv_md: str,
    cover_md: str,
) -> Path:
    company = safe_slug(job.get("company") or "company")
    role = safe_slug(job.get("title") or "role")
    folder = APPLICATIONS_DIR / f"{company}_{role}"
    folder.mkdir(parents=True, exist_ok=True)

    _write_text(folder / "posting.md", _job_text(job, limit=20000))
    fit_lines = [
        f"# Fit analysis: {job.get('title')} at {job.get('company')}",
        "",
        f"**Score:** {fit.get('score')} / 100",
        f"**Verdict:** {fit.get('verdict')}",
        f"**Recommendation:** {fit.get('recommendation')}",
        f"**Engine:** {fit.get('engine')}",
        "",
        "## Summary",
        fit.get("summary", ""),
        "",
        "## Strengths",
        *[f"- {item}" for item in fit.get("strengths", [])],
        "",
        "## Gaps",
        *[f"- {item}" for item in fit.get("gaps", [])],
        "",
        "## Keywords",
        ", ".join(fit.get("keywords", [])),
    ]
    _write_text(folder / "fit_analysis.md", "\n".join(fit_lines))
    _write_text(folder / "cv.md", cv_md)
    _write_text(folder / "cover_letter.md", cover_md)

    try:
        (folder / "cv.pdf").write_bytes(markdown_to_pdf(cv_md, "CV"))
        (folder / "cover_letter.pdf").write_bytes(markdown_to_pdf(cover_md, "Cover Letter"))
    except Exception:
        pass

    outcome = folder / "outcome.md"
    if not outcome.exists():
        _write_text(
            outcome,
            f"# Outcome\n\n- Company: {job.get('company')}\n- Role: {job.get('title')}\n"
            f"- Status: in_progress\n- Source: {job.get('url')}\n",
        )

    try:
        cv_rel = str((folder / "cv.md").relative_to(BASE_DIR))
    except ValueError:
        cv_rel = str(folder / "cv.md")
    try:
        cover_rel = str((folder / "cover_letter.md").relative_to(BASE_DIR))
    except ValueError:
        cover_rel = str(folder / "cover_letter.md")
    upsert_tracker(
        profile,
        job,
        status="drafted",
        notes=f"Generated in JobPilot from {job.get('source', 'portal')}",
        cv_file=cv_rel,
        cover_letter_file=cover_rel,
    )
    return folder


# ---------------------------------------------------------------------------
# Repo personalization
# ---------------------------------------------------------------------------


def _profile_markdown(profile: dict[str, Any]) -> str:
    links = profile.get("links") or {}
    languages = profile.get("languages") or []
    language_rows = "\n".join(f"  | {language} | Professional |" for language in languages)
    skills = profile.get("skills") or []
    projects_md = re.sub(r"(?m)^### ", "#### ", profile.get("projects") or "")
    return f"""## Candidate Profile

### Identity
- **Name:** {profile.get('name', '')}
- **Email:** {profile.get('email', '')}
- **Phone:** {profile.get('phone', '')}
- **Location:** {profile.get('location', '')}
- **Languages:**
  | Language | Level |
  |----------|-------|
{language_rows or '  | English | Professional |'}
- **CV language:** English
- **Status:** {profile.get('experience_level', '')}
- **LinkedIn headline:** "{profile.get('headline', '')}"
- **Links:** GitHub: {links.get('github', '')} · LinkedIn: {links.get('linkedin', '')} · Portfolio: {links.get('portfolio', '')}

### Education
{profile.get('education') or '- [ADD: degree, institution, dates]'}

### Professional Experience
{profile.get('experience') or '- [ADD: internships, research, freelance, or part-time experience]'}

### Selected Projects
{projects_md or '- [ADD: projects with tools, approach, and results]'}

### Technical Skills
- **Primary:** {', '.join(skills[:10]) or '[ADD: primary skills]'}
- **Secondary:** {', '.join(skills[10:]) or '[ADD: secondary skills]'}
- **Domain:** {', '.join(profile.get('target_roles') or [])}
- **Software:** {', '.join(skills) or '[ADD: tools and software]'}

### Certifications
{profile.get('certifications') or '- [ADD: certifications with dates]'}

### Publications
- [ADD: publications, if any]

### Awards
- [ADD: awards, hackathons, competitions]

### Behavioral Profile
- **Strengths:** [ADD: strengths]
- **Growth areas:** [ADD: growth areas]
- **Thrives in:** [ADD: ideal environment]

### What Excites You
- {', '.join(profile.get('target_roles') or ['[ADD: what motivates you]'])}

### Target Sectors
- {', '.join(profile.get('target_roles') or ['[ADD: target sectors]'])}

### Deal-breakers
{profile.get('dealbreakers') or '- [ADD: hard constraints]'}

### Links
- GitHub: {links.get('github', '')}
- LinkedIn: {links.get('linkedin', '')}
- Portfolio: {links.get('portfolio', '')}

"""


def personalize_claude_md(profile: dict[str, Any]) -> Path:
    if not CLAUDE_MD_PATH.exists():
        raise FileNotFoundError("CLAUDE.md not found in the repository root.")
    original = CLAUDE_MD_PATH.read_text(encoding="utf-8")
    backup = DATA_DIR / "CLAUDE.md.bak"
    if not backup.exists():
        _write_text(backup, original)
    content = re.sub(
        r"## Candidate Profile.*?(?=## Repo Structure)",
        _profile_markdown(profile),
        original,
        flags=re.DOTALL,
    )
    content = content.replace("[YOUR_NAME]", profile.get("name", "Your Name"))
    _write_text(CLAUDE_MD_PATH, content)
    return CLAUDE_MD_PATH
