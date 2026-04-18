import httpx
import os
from datetime import datetime, timezone

async def fetch_remotive_jobs(query="python developer"):
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            res = await client.get(
                f"https://remotive.com/api/remote-jobs?search={query}&limit=20"
            )
            data = res.json()
            jobs = []
            for job in data.get("jobs", []):
                try:
                    posted = datetime.fromisoformat(
                        job["publication_date"].replace("Z", "+00:00")
                    )
                    hours_ago = int(
                        (datetime.now(timezone.utc) - posted).total_seconds() / 3600
                    )
                except:
                    hours_ago = 24
                jobs.append({
                    "external_id": f"remotive-{job['id']}",
                    "title": job["title"],
                    "company": job["company_name"],
                    "location": "Remote (Global)",
                    "job_type": job.get("job_type", "Full-time"),
                    "salary": job.get("salary", "Not specified"),
                    "description": job.get("description", "")
                        .replace("<br>", " ")
                        .replace("</p>", " ")
                        .replace("<p>", "")
                        .replace("<li>", " ")
                        .replace("</li>", " ")[:500],
                    "requirements": job.get("tags", []),
                    "apply_url": job["url"],
                    "source": "Remotive",
                    "is_remote": True,
                    "is_fresh": hours_ago < 48,
                    "is_fake": False,
                    "is_low_comp": hours_ago < 12,
                    "posted_hours_ago": hours_ago,
                    "match_score": 60,
                    "apply_priority": "APPLY SOON",
                    "tags": (job.get("tags", [])[:2]) + ["Remote", "Live"],
                })
            return jobs
    except Exception as e:
        print(f"Remotive error: {e}")
        return []


async def fetch_adzuna_jobs(query="developer", country="in"):
    app_id = os.environ.get("ADZUNA_APP_ID", "")
    app_key = os.environ.get("ADZUNA_APP_KEY", "")
    if not app_id:
        return []
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            res = await client.get(
                f"https://api.adzuna.com/v1/api/jobs/{country}/search/1"
                f"?app_id={app_id}&app_key={app_key}"
                f"&results_per_page=20&what={query}"
                f"&content-type=application/json"
            )
            data = res.json()
            jobs = []
            for job in data.get("results", []):
                try:
                    created = datetime.fromisoformat(
                        job["created"].replace("Z", "+00:00")
                    )
                    hours_ago = int(
                        (datetime.now(timezone.utc) - created).total_seconds() / 3600
                    )
                except:
                    hours_ago = 48
                salary = ""
                if job.get("salary_min"):
                    if country == "in":
                        salary = f"₹{int(job['salary_min']/1000)}k–₹{int(job.get('salary_max', 0)/1000)}k"
                    else:
                        salary = f"${int(job['salary_min']/1000)}k–${int(job.get('salary_max', 0)/1000)}k"
                jobs.append({
                    "external_id": f"adzuna-{job['id']}",
                    "title": job["title"],
                    "company": job.get("company", {}).get("display_name", "Unknown"),
                    "location": job.get("location", {}).get("display_name", "India"),
                    "job_type": job.get("contract_time", "Full-time"),
                    "salary": salary,
                    "description": job.get("description", "")[:500],
                    "requirements": [],
                    "apply_url": job.get("redirect_url", "#"),
                    "source": "Adzuna",
                    "is_remote": "remote" in job.get("title", "").lower(),
                    "is_fresh": hours_ago < 24,
                    "is_fake": False,
                    "is_low_comp": hours_ago < 6,
                    "posted_hours_ago": hours_ago,
                    "match_score": 55,
                    "apply_priority": "APPLY SOON",
                    "tags": [
                        "India" if country == "in" else "Global",
                        job.get("category", {}).get("label", "Tech")
                    ],
                })
            return jobs
    except Exception as e:
        print(f"Adzuna {country} error: {e}")
        return []


async def fetch_all_jobs():
    remotive = await fetch_remotive_jobs("python developer AI")
    remotive2 = await fetch_remotive_jobs("machine learning")
    remotive3 = await fetch_remotive_jobs("react developer")
    india = await fetch_adzuna_jobs("developer", "in")
    global_jobs = await fetch_adzuna_jobs("python developer", "gb")
    all_jobs = remotive + remotive2 + remotive3 + india + global_jobs
    seen = set()
    unique = []
    for job in all_jobs:
        if job["external_id"] not in seen:
            seen.add(job["external_id"])
            unique.append(job)
    return unique