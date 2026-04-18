from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional
import httpx
import json
import os
from database import get_db
from job_fetcher import fetch_all_jobs
from dotenv import load_dotenv

load_dotenv()

app = FastAPI(title="Career Radar API v2")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ═══════════════════════════════════════
#  MODELS
# ═══════════════════════════════════════
class ProfileModel(BaseModel):
    user_id: str
    name: str
    skills: List[str]
    experience: str
    location: str
    salary_min: Optional[int] = 0
    salary_max: Optional[int] = 200000
    preferred_roles: Optional[List[str]] = []

class FeedbackModel(BaseModel):
    user_id: str
    job_id: str
    feedback_type: str

class CoverLetterModel(BaseModel):
    job_title: str
    job_company: str
    job_description: str
    requirements: List[str]
    user_name: str
    user_skills: List[str]
    user_experience: str

class SkillGapModel(BaseModel):
    job_title: str
    job_description: str
    requirements: List[str]
    user_skills: List[str]
    user_experience: str


# ═══════════════════════════════════════
#  HEALTH
# ═══════════════════════════════════════
@app.get("/")
def root():
    return {
        "status": "Career Radar API Running",
        "version": "2.0",
        "endpoints": ["/jobs", "/jobs/refresh", "/profile/save", "/ai/cover-letter", "/ai/skill-gap"]
    }

@app.get("/health")
def health():
    return {"status": "ok"}


# ═══════════════════════════════════════
#  PROFILE
# ═══════════════════════════════════════
@app.post("/profile/save")
async def save_profile(profile: ProfileModel):
    try:
        db = get_db()
        data = profile.dict()
        existing = db.table("profiles").select("id").eq("user_id", profile.user_id).execute()
        if existing.data:
            db.table("profiles").update(data).eq("user_id", profile.user_id).execute()
        else:
            db.table("profiles").insert(data).execute()
        return {"success": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/profile/{user_id}")
async def get_profile(user_id: str):
    try:
        db = get_db()
        result = db.table("profiles").select("*").eq("user_id", user_id).execute()
        if result.data:
            return result.data[0]
        return {}
    except Exception as e:
        return {}


# ═══════════════════════════════════════
#  JOBS
# ═══════════════════════════════════════
@app.get("/jobs")
async def get_jobs():
    try:
        db = get_db()
        result = db.table("jobs").select("*").order("posted_hours_ago").limit(60).execute()
        return {"jobs": result.data or [], "total": len(result.data or [])}
    except Exception as e:
        return {"jobs": [], "total": 0, "error": str(e)}

@app.post("/jobs/refresh")
async def refresh_jobs():
    try:
        jobs = await fetch_all_jobs()
        db = get_db()
        saved = 0
        for job in jobs:
            try:
                existing = db.table("jobs").select("id").eq("external_id", job["external_id"]).execute()
                if not existing.data:
                    db.table("jobs").insert(job).execute()
                    saved += 1
            except:
                continue
        return {"success": True, "fetched": len(jobs), "new_saved": saved}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/jobs/clear")
async def clear_jobs():
    try:
        db = get_db()
        db.table("jobs").delete().neq("id", "00000000-0000-0000-0000-000000000000").execute()
        return {"success": True, "message": "All jobs cleared"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ═══════════════════════════════════════
#  FEEDBACK
# ═══════════════════════════════════════
@app.post("/feedback")
async def save_feedback(feedback: FeedbackModel):
    try:
        db = get_db()
        data = feedback.dict()
        existing = db.table("feedback").select("id")\
            .eq("user_id", feedback.user_id)\
            .eq("job_id", feedback.job_id).execute()
        if existing.data:
            db.table("feedback").update({"feedback_type": feedback.feedback_type})\
                .eq("user_id", feedback.user_id)\
                .eq("job_id", feedback.job_id).execute()
        else:
            db.table("feedback").insert(data).execute()
        return {"success": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/feedback/{user_id}")
async def get_feedback(user_id: str):
    try:
        db = get_db()
        result = db.table("feedback").select("*").eq("user_id", user_id).execute()
        return {item["job_id"]: item["feedback_type"] for item in (result.data or [])}
    except Exception as e:
        return {}


# ═══════════════════════════════════════
#  AI — COVER LETTER
# ═══════════════════════════════════════
@app.post("/ai/cover-letter")
async def generate_cover_letter(data: CoverLetterModel):
    api_key = os.environ.get("ANTHROPIC_KEY")
    if not api_key:
        raise HTTPException(status_code=400, detail="Anthropic API key not set")
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            res = await client.post(
                "https://api.anthropic.com/v1/messages",
                headers={
                    "x-api-key": api_key,
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json",
                },
                json={
                    "model": "claude-sonnet-4-20250514",
                    "max_tokens": 1000,
                    "messages": [{
                        "role": "user",
                        "content": f"""Write a professional cover letter (3 paragraphs ~200 words) for:
Job: {data.job_title} at {data.job_company}
Description: {data.job_description[:300]}
Requirements: {', '.join(data.requirements)}
Applicant: {data.user_name}
Skills: {', '.join(data.user_skills)}
Experience: {data.user_experience}
Address to Hiring Manager. Sign as {data.user_name}. Be genuine and enthusiastic."""
                    }]
                }
            )
            result = res.json()
            return {"letter": result["content"][0]["text"]}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ═══════════════════════════════════════
#  AI — SKILL GAP
# ═══════════════════════════════════════
@app.post("/ai/skill-gap")
async def analyze_skill_gap(data: SkillGapModel):
    api_key = os.environ.get("ANTHROPIC_KEY")
    if not api_key:
        raise HTTPException(status_code=400, detail="Anthropic API key not set")
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            res = await client.post(
                "https://api.anthropic.com/v1/messages",
                headers={
                    "x-api-key": api_key,
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json",
                },
                json={
                    "model": "claude-sonnet-4-20250514",
                    "max_tokens": 1000,
                    "messages": [{
                        "role": "user",
                        "content": f"""Analyze skill gap. Return ONLY valid JSON no markdown:
{{
  "matchedSkills": ["skill1", "skill2"],
  "missingSkills": [{{"skill":"name","priority":"high","reason":"why it matters"}}],
  "overallFit": "75",
  "verdict": "Strong match for entry level",
  "learningPath": [{{"skill":"name","resource":"what to study","timeEstimate":"2 weeks"}}],
  "interviewTips": ["tip1", "tip2", "tip3"]
}}

Job: {data.job_title}
Requirements: {', '.join(data.requirements)}
Description: {data.job_description[:300]}
Candidate Skills: {', '.join(data.user_skills)}
Experience: {data.user_experience}"""
                    }]
                }
            )
            result = res.json()
            text = result["content"][0]["text"]
            clean = text.replace("```json", "").replace("```", "").strip()
            return json.loads(clean)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))