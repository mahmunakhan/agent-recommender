"""
ATS (Applicant Tracking System) Router

Two-phase pipeline for recruiters:
  Phase 1 – Pre-filter: knock out candidates that fail minimum criteria
             (match score, required skills, experience, excluded statuses).
  Phase 2 – ATS Scoring: score & rank candidates who passed the filter using
             a composite of skill match (50%), experience (30%), and profile
             completeness (20%), then classify each as Strong / Good / Partial /
             Low Fit.

Endpoints:
  POST /ats/jobs/{job_id}/run   – Run ATS filter + scoring on applicants
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import select
from typing import Optional, List
from pydantic import BaseModel
import logging

from app.services.database import get_db
from app.utils import get_current_user
from app.schemas import TokenData
from app.models import Job, JobSkill, Skill, Application, User, Profile, ProfileSkill

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/ats", tags=["ATS"])


# ── Request / Response schemas ─────────────────────────────────────────────────

class ATSConfig(BaseModel):
    """Recruiter-configurable filter thresholds."""
    min_match_score: float = 0.0              # 0–100; skip applicants below this
    require_all_required_skills: bool = False  # knock-out if any required skill is missing
    min_experience_years: Optional[int] = None # override job's experience_min_years
    exclude_statuses: List[str] = ["withdrawn", "rejected"]  # skip these pipeline stages


# ── Scoring helper ─────────────────────────────────────────────────────────────

def _calc_ats_score(
    user_skill_ids: set,
    job_skill_rows: list,          # list of (JobSkill row, Skill row) named-tuples
    years_experience: Optional[int],
    job_min_years: Optional[int],
    job_max_years: Optional[int],
    has_resume: bool,
    is_verified: bool,
    has_headline: bool,
) -> dict:
    """
    Composite ATS score:
      50% – Skill match   (required skills weighted 2×, preferred/nice_to_have 1×)
      30% – Experience fit
      20% – Profile completeness (resume uploaded + verified + headline present)
    Returns dict with scores, fit_label, matched/missing skill names.
    """
    # ── Skill score ──────────────────────────────────────────────────────────
    if job_skill_rows:
        required_ids   = {r.JobSkill.skill_id for r in job_skill_rows if r.JobSkill.requirement_type == "required"}
        preferred_ids  = {r.JobSkill.skill_id for r in job_skill_rows if r.JobSkill.requirement_type in ("preferred", "nice_to_have")}

        matched_required  = required_ids  & user_skill_ids
        matched_preferred = preferred_ids & user_skill_ids
        missed_required   = required_ids  - user_skill_ids

        total_weight   = len(required_ids) * 2 + len(preferred_ids)
        matched_weight = len(matched_required) * 2 + len(matched_preferred)
        skill_score    = (matched_weight / total_weight * 100) if total_weight else 50.0

        matched_names = [
            r.Skill.name for r in job_skill_rows
            if r.JobSkill.skill_id in (matched_required | matched_preferred)
        ]
        missing_names = [
            r.Skill.name for r in job_skill_rows
            if r.JobSkill.skill_id in missed_required
        ]
        missing_required_count = len(missed_required)
    else:
        skill_score = 50.0
        matched_names = []
        missing_names = []
        missing_required_count = 0

    # ── Experience score ─────────────────────────────────────────────────────
    if years_experience is not None and job_min_years is not None:
        if years_experience >= job_min_years:
            if job_max_years and years_experience > job_max_years:
                overshoot  = years_experience - job_max_years
                exp_score  = max(30.0, 100.0 - overshoot * 10)
            else:
                exp_score = 100.0
        else:
            shortfall = job_min_years - years_experience
            exp_score = max(0.0, 100.0 - shortfall * 20)
    elif years_experience is not None:
        exp_score = 70.0
    else:
        exp_score = 50.0

    # ── Profile completeness ─────────────────────────────────────────────────
    completeness = 0
    if has_resume:    completeness += 40
    if is_verified:   completeness += 35
    if has_headline:  completeness += 25

    # ── Composite ────────────────────────────────────────────────────────────
    composite = (skill_score * 0.50) + (exp_score * 0.30) + (completeness * 0.20)

    # ── Fit classification ───────────────────────────────────────────────────
    if composite >= 75:
        fit_label, fit_color = "Strong Fit", "green"
    elif composite >= 55:
        fit_label, fit_color = "Good Fit", "blue"
    elif composite >= 35:
        fit_label, fit_color = "Partial Fit", "yellow"
    else:
        fit_label, fit_color = "Low Fit", "red"

    return {
        "ats_score":              round(composite, 1),
        "skill_score":            round(skill_score, 1),
        "experience_score":       round(exp_score, 1),
        "completeness_score":     round(float(completeness), 1),
        "fit_label":              fit_label,
        "fit_color":              fit_color,
        "matched_skills":         matched_names,
        "missing_skills":         missing_names,
        "missing_required_count": missing_required_count,
    }


# ── POST /ats/jobs/{job_id}/run ────────────────────────────────────────────────

@router.post("/jobs/{job_id}/run")
async def run_ats(
    job_id: str,
    config: ATSConfig,
    current_user: TokenData = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Run two-phase ATS on all applicants for a job.

    Phase 1 – Pre-filter (knock-outs):
      • Skip statuses listed in exclude_statuses
      • Skip if match_score_at_apply < min_match_score
      • Skip if require_all_required_skills and any required skill is missing
      • Skip if candidate years_experience < effective min years

    Phase 2 – Score & rank:
      • Composite score (skill 50% + experience 30% + completeness 20%)
      • Fit label: Strong / Good / Partial / Low
      • Sorted by ATS score descending

    Returns:
      total_applicants, filtered_count, excluded_count,
      candidates (ranked, passed), excluded (with reason)
    """
    if current_user.role not in ["recruiter", "admin"]:
        raise HTTPException(status_code=403, detail="Recruiter access required")

    job = db.execute(select(Job).where(Job.id == job_id)).scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if current_user.role != "admin" and job.posted_by_id != current_user.user_id:
        raise HTTPException(status_code=403, detail="Not authorized for this job")

    # Fetch job skills once
    job_skill_rows = db.execute(
        select(JobSkill, Skill).join(Skill).where(JobSkill.job_id == job_id)
    ).all()
    required_skill_ids = {
        r.JobSkill.skill_id for r in job_skill_rows
        if r.JobSkill.requirement_type == "required"
    }

    # Effective minimum experience: config override → job setting → None
    effective_min_years = (
        config.min_experience_years
        if config.min_experience_years is not None
        else job.experience_min_years
    )

    # Fetch all applications (status filter applied at DB level)
    query = (
        select(Application, User, Profile)
        .join(User, Application.user_id == User.id)
        .outerjoin(Profile, User.id == Profile.user_id)
        .where(Application.job_id == job_id)
    )
    if config.exclude_statuses:
        query = query.where(~Application.status.in_(config.exclude_statuses))

    all_rows = db.execute(query).all()
    total_applicants = len(all_rows)

    passed   = []
    excluded = []

    for app, user, profile in all_rows:
        # Build candidate skill set
        if profile:
            skill_rows     = db.execute(
                select(ProfileSkill).where(ProfileSkill.profile_id == profile.id)
            ).scalars().all()
            user_skill_ids = {ps.skill_id for ps in skill_rows}
            years_exp      = profile.years_experience
            has_resume     = bool(profile.resume_s3_path)
            is_verified    = bool(profile.is_verified)
            has_headline   = bool(profile.headline)
        else:
            user_skill_ids = set()
            years_exp      = None
            has_resume     = False
            is_verified    = False
            has_headline   = False

        stored_score    = app.match_score_at_apply or 0.0
        candidate_name  = (
            f"{user.first_name or ''} {user.last_name or ''}".strip() or user.email
        )

        # ── Phase 1: Pre-filter ───────────────────────────────────────────
        exclusion_reason = None

        if config.min_match_score > 0 and stored_score < config.min_match_score:
            exclusion_reason = (
                f"Match score {stored_score:.0f}% is below "
                f"the minimum threshold of {config.min_match_score:.0f}%"
            )

        elif config.require_all_required_skills and required_skill_ids:
            missing_ids = required_skill_ids - user_skill_ids
            if missing_ids:
                missing_names = [
                    r.Skill.name for r in job_skill_rows
                    if r.JobSkill.skill_id in missing_ids
                ]
                listed = ", ".join(missing_names[:3])
                suffix = f" (+{len(missing_names)-3} more)" if len(missing_names) > 3 else ""
                exclusion_reason = f"Missing required skill(s): {listed}{suffix}"

        elif (
            effective_min_years is not None
            and years_exp is not None
            and years_exp < effective_min_years
        ):
            exclusion_reason = (
                f"Experience {years_exp} yr(s) is below "
                f"the required minimum of {effective_min_years} yr(s)"
            )

        if exclusion_reason:
            excluded.append({
                "application_id":      app.id,
                "user_id":             app.user_id,
                "name":                candidate_name,
                "email":               user.email,
                "status":              app.status,
                "exclusion_reason":    exclusion_reason,
                "match_score_at_apply": round(stored_score, 1),
                "years_experience":    years_exp,
            })
            continue

        # ── Phase 2: ATS scoring ──────────────────────────────────────────
        ats_data = _calc_ats_score(
            user_skill_ids  = user_skill_ids,
            job_skill_rows  = job_skill_rows,
            years_experience= years_exp,
            job_min_years   = effective_min_years,
            job_max_years   = job.experience_max_years,
            has_resume      = has_resume,
            is_verified     = is_verified,
            has_headline    = has_headline,
        )

        passed.append({
            "application_id":       app.id,
            "user_id":              app.user_id,
            "name":                 candidate_name,
            "email":                user.email,
            "headline":             profile.headline if profile else None,
            "years_experience":     years_exp,
            "status":               app.status,
            "applied_at":           app.applied_at.isoformat() if app.applied_at else None,
            "match_score_at_apply": round(stored_score, 1),
            "has_resume":           has_resume,
            "is_verified":          is_verified,
            **ats_data,
        })

    # Sort passed candidates by ATS score (highest first)
    passed.sort(key=lambda x: x["ats_score"], reverse=True)
    for rank, candidate in enumerate(passed, start=1):
        candidate["rank"] = rank

    # Fit-label summary counts
    fit_counts = {"Strong Fit": 0, "Good Fit": 0, "Partial Fit": 0, "Low Fit": 0}
    for c in passed:
        fit_counts[c["fit_label"]] = fit_counts.get(c["fit_label"], 0) + 1

    return {
        "job_id":           job_id,
        "job_title":        job.title,
        "total_applicants": total_applicants,
        "filtered_count":   len(passed),
        "excluded_count":   len(excluded),
        "fit_summary":      fit_counts,
        "config":           config.dict(),
        "candidates":       passed,
        "excluded":         excluded,
    }
