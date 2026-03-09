"""
Resume Processing Graph - Multi-Agent System v1.3
===================================================
Works with pdfplumber column-separated text (MAIN CONTENT vs SIDEBAR).
Clean experience extraction, no duplicates.
"""

import os
import re
import json
import logging
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime

logger = logging.getLogger(__name__)


def safe_parse_json(text: str, default=None):
    if not text or not isinstance(text, str):
        return default if default is not None else {}
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    for pat in [r'```json\s*([\s\S]*?)\s*```', r'```\s*([\s\S]*?)\s*```']:
        m = re.search(pat, text)
        if m:
            try:
                return json.loads(m.group(1).strip())
            except json.JSONDecodeError:
                continue
    for pat in [r'\{[\s\S]*\}', r'\[[\s\S]*\]']:
        m = re.search(pat, text)
        if m:
            try:
                return json.loads(m.group())
            except json.JSONDecodeError:
                raw = m.group()
                for fix in [']}', '}]}', '"]}', '"}]}']:
                    try:
                        return json.loads(raw + fix)
                    except json.JSONDecodeError:
                        continue
    return default if default is not None else {}


def _cv(v):
    if v is None or v == "null" or v == "None":
        return ""
    return str(v).strip() if isinstance(v, str) else v


class GroqClient:
    def __init__(self, api_key=None, model=None):
        self.api_key = api_key or os.getenv("GROQ_API_KEY", "")
        self.model = model or os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
        self._client = None

    @property
    def client(self):
        if self._client is None:
            from groq import Groq
            self._client = Groq(api_key=self.api_key)
        return self._client

    def generate(self, prompt, system_prompt="", temperature=0.1, max_tokens=8000):
        try:
            msgs = []
            if system_prompt:
                msgs.append({"role": "system", "content": system_prompt})
            msgs.append({"role": "user", "content": prompt})
            resp = self.client.chat.completions.create(
                model=self.model, messages=msgs,
                temperature=temperature, max_tokens=max_tokens
            )
            return resp.choices[0].message.content or ""
        except Exception as e:
            logger.error(f"LLM error: {e}")
            return ""


# ============================================================================
# EXTRACTOR A — Phase 1: Personal + Experience + Education
# ============================================================================

class ExtractorA:
    def __init__(self, llm):
        self.llm = llm

    def extract(self, text: str) -> Tuple[Dict, float]:
        logger.info("[ExtractorA] 2-phase extraction...")
        p1 = self._phase1(text)
        p2 = self._phase2(text)
        data = {**p1, **p2}
        conf = self._score(data)
        logger.info(f"[ExtractorA] conf={conf:.2f} exp={len(data.get('experience',[]))} skills={len(data.get('skills',[]))}")
        return data, conf

    def _phase1(self, text: str) -> Dict:
        prompt = f"""Extract personal info, work experience, and education from this resume.

The resume text has MAIN CONTENT (left column) and SIDEBAR (right column).
Focus on MAIN CONTENT for experience. The SIDEBAR contains tech stack and certifications.

IMPORTANT: In the MAIN CONTENT, work experience follows this EXACT pattern:
  Job Title
  Company Name
  Date Range   Location
  - responsibility 1
  - responsibility 2

Extract EACH experience entry by reading the title, then the company on the NEXT line, then the dates.

RESUME TEXT:
{text[:8000]}

Return JSON:
{{
  "personal_info": {{
    "full_name": "", "first_name": "", "last_name": "",
    "headline": "first/most recent job title found",
    "summary": "summary or objective text",
    "desired_role": "",
    "date_of_birth": "", "gender": "", "nationality": "",
    "location": {{"address": "", "city": "", "country": ""}},
    "contact": {{"email": "", "phone": "", "alternate_phone": ""}},
    "online_profiles": [{{"type": "linkedin", "url": ""}}],
    "work_authorization": "", "notice_period": ""
  }},
  "experience": [
    {{
      "job_title": "exact title from resume",
      "company": "exact company name from resume",
      "start_date": "exact date string",
      "end_date": "exact date string or Present",
      "location": "city, country",
      "employment_type": "full-time",
      "is_current": false,
      "responsibilities": ["each bullet point as-is"],
      "achievements": [],
      "technologies_used": []
    }}
  ],
  "education": [
    {{
      "degree": "", "field_of_study": "", "institution": "",
      "location": "", "start_date": "", "end_date": "", "grade": ""
    }}
  ]
}}

CRITICAL RULES:
1. Each experience MUST have both job_title AND company
2. The company name is the line RIGHT AFTER the job title
3. Do NOT confuse company names — read them carefully from the text
4. Do NOT create duplicate entries for the same company+dates
5. Split full_name into first_name and last_name
6. Use "" for missing, never null
7. Return ONLY valid JSON, no extra text"""

        return safe_parse_json(
            self.llm.generate(prompt, "Resume parser. Return ONLY valid JSON.", temperature=0.1, max_tokens=4000),
            {}
        )

    def _phase2(self, text: str) -> Dict:
        prompt = f"""Extract skills, certifications, projects, publications, and spoken languages from this resume.

The SIDEBAR sections contain TECH STACK and CERTIFICATIONS.
The MAIN CONTENT may also list projects.

RESUME TEXT:
{text[:8000]}

Return JSON:
{{
  "skills": [
    {{"name": "Python", "category": "skill"}},
    {{"name": "Docker", "category": "tool"}}
  ],
  "certifications": [
    {{"name": "cert name", "issuer": "issuing organization"}}
  ],
  "projects": [
    {{"name": "project name", "description": "brief description"}}
  ],
  "publications": [{{"title": "", "publisher": "", "date": ""}}],
  "languages": [{{"language": "Hindi", "proficiency": "fluent"}}],
  "interests": []
}}

RULES:
- skills: ALL technical skills, programming languages, frameworks, ML/AI concepts
- certifications: ALL certs with name and issuer (from SIDEBAR/CERTIFICATION section)
- projects: ALL projects mentioned
- languages: SPOKEN languages ONLY (Hindi, English, Urdu, Arabic, etc.) — NOT programming languages
- Use "" for missing fields
- Return ONLY valid JSON"""

        return safe_parse_json(
            self.llm.generate(prompt, "Resume parser. Return ONLY valid JSON.", temperature=0.1, max_tokens=4000),
            {}
        )

    def _score(self, d):
        s = 0.0
        pi = d.get("personal_info", {})
        if _cv(pi.get("full_name")) or _cv(pi.get("first_name")): s += 0.2
        if isinstance(pi.get("contact"), dict) and _cv(pi["contact"].get("email")): s += 0.1
        if d.get("experience"): s += 0.3
        if d.get("skills"): s += 0.2
        if d.get("education"): s += 0.2
        return min(s, 1.0)


# ============================================================================
# EXTRACTOR B — Precision
# ============================================================================

class ExtractorB:
    def __init__(self, llm):
        self.llm = llm

    def extract(self, text: str) -> Tuple[Dict, float]:
        logger.info("[ExtractorB] Precision extraction...")
        prompt = f"""You are a PRECISE resume parser. ONLY extract explicitly stated facts.

The text may have MAIN CONTENT and SIDEBAR sections.
For experience: title is followed by company on next line, then dates.

RESUME TEXT:
{text[:8000]}

Return JSON with these sections:
{{
  "personal_info": {{
    "full_name": "", "first_name": "", "last_name": "",
    "headline": "", "summary": "",
    "date_of_birth": "", "gender": "", "nationality": "",
    "location": {{"address": "", "city": "", "country": ""}},
    "contact": {{"email": "", "phone": "", "alternate_phone": ""}},
    "online_profiles": [],
    "work_authorization": "", "notice_period": ""
  }},
  "experience": [
    {{"job_title": "", "company": "", "start_date": "", "end_date": "",
      "location": "", "employment_type": "full-time", "is_current": false,
      "responsibilities": [], "achievements": [], "technologies_used": []}}
  ],
  "education": [
    {{"degree": "", "field_of_study": "", "institution": "",
      "location": "", "start_date": "", "end_date": "", "grade": ""}}
  ],
  "skills": [{{"name": "", "category": "skill/tool"}}],
  "certifications": [{{"name": "", "issuer": ""}}],
  "projects": [{{"name": "", "description": ""}}],
  "publications": [{{"title": "", "publisher": "", "date": ""}}],
  "languages": [{{"language": "", "proficiency": ""}}],
  "interests": []
}}

RULES:
- Each experience MUST have both job_title AND company (skip if either is missing)
- Do NOT create duplicate entries
- languages = spoken only (Hindi, English, etc.)
- Use "" for missing, NOT null
- Return ONLY valid JSON"""

        data = safe_parse_json(
            self.llm.generate(prompt, "Precision parser. Return ONLY valid JSON.", temperature=0.0, max_tokens=8000),
            {}
        )
        conf = self._score(data)
        logger.info(f"[ExtractorB] conf={conf:.2f} exp={len(data.get('experience',[]))}")
        return data, conf

    def _score(self, d):
        s = 0.0
        pi = d.get("personal_info", {})
        if _cv(pi.get("full_name")) or _cv(pi.get("first_name")): s += 0.25
        if d.get("experience"): s += 0.3
        if d.get("skills"): s += 0.25
        if d.get("education"): s += 0.2
        return min(s, 1.0)


# ============================================================================
# JUDGE — Strict Dedup
# ============================================================================

class JudgeAgent:
    def reconcile(self, a, ca, b, cb, text):
        logger.info(f"[JudgeAgent] A({ca:.2f}) + B({cb:.2f})")

        if ca < 0.2 and cb >= 0.5: return self._clean(b)
        if cb < 0.2 and ca >= 0.5: return self._clean(a)

        merged = {}
        merged["personal_info"] = self._merge_dicts(a.get("personal_info", {}), b.get("personal_info", {}))

        # Ensure name split
        pi = merged["personal_info"]
        fn = _cv(pi.get("full_name", ""))
        if fn and not _cv(pi.get("first_name")):
            parts = fn.strip().split(" ", 1)
            pi["first_name"] = parts[0]
            pi["last_name"] = parts[1] if len(parts) > 1 else ""

        # STRICT experience dedup — by company (normalized)
        merged["experience"] = self._dedup_experience(
            (a.get("experience") or []) + (b.get("experience") or [])
        )

        # Education dedup
        merged["education"] = self._dedup_by_keys(
            (a.get("education") or []) + (b.get("education") or []),
            ["degree", "institution"]
        )

        # Skills union
        merged["skills"] = self._merge_skills(a.get("skills", []), b.get("skills", []))

        # Certifications dedup
        merged["certifications"] = self._dedup_by_keys(
            (a.get("certifications") or []) + (b.get("certifications") or []),
            ["name"]
        )

        # Projects dedup
        merged["projects"] = self._dedup_by_keys(
            (a.get("projects") or []) + (b.get("projects") or []),
            ["name"]
        )

        merged["publications"] = self._dedup_by_keys(
            (a.get("publications") or []) + (b.get("publications") or []),
            ["title"]
        )

        merged["languages"] = self._dedup_by_keys(
            (a.get("languages") or []) + (b.get("languages") or []),
            ["language"]
        )

        merged["awards"] = a.get("awards", []) or b.get("awards", [])
        merged["interests"] = list(set((a.get("interests") or []) + (b.get("interests") or [])))
        merged["references"] = a.get("references", []) or b.get("references", [])

        merged = self._clean(merged)
        logger.info(f"[JudgeAgent] exp={len(merged.get('experience',[]))} edu={len(merged.get('education',[]))} "
                     f"skills={len(merged.get('skills',[]))} certs={len(merged.get('certifications',[]))} "
                     f"proj={len(merged.get('projects',[]))}")
        return merged

    def _dedup_experience(self, exps: List) -> List:
        """Strict dedup: normalize company name, keep best entry per company+start."""
        seen = {}
        for exp in exps:
            if not isinstance(exp, dict): continue
            company = _cv(exp.get("company", "")).strip()
            title = _cv(exp.get("job_title", "")).strip()
            if not company and not title: continue
            if not company: continue  # Skip entries without company

            # Normalize company for dedup
            cn = re.sub(r'[^a-z0-9]', '', company.lower())
            start = _cv(exp.get("start_date", "")).strip()
            sn = re.sub(r'[^a-z0-9]', '', start.lower()) if start else "nodate"
            key = f"{cn}|{sn}"

            if key not in seen:
                seen[key] = exp
            else:
                # Keep entry with more data
                existing = seen[key]
                merged = {}
                for k in set(list(existing.keys()) + list(exp.keys())):
                    ve = existing.get(k)
                    vn = exp.get(k)
                    if isinstance(ve, list) and isinstance(vn, list):
                        merged[k] = ve if len(ve) >= len(vn) else vn
                    else:
                        merged[k] = ve if _cv(ve) else vn
                seen[key] = merged

        result = list(seen.values())
        # Sort most recent first
        def sort_key(x):
            d = _cv(x.get("start_date", ""))
            m = re.search(r'(20\d{2}|19\d{2})', d)
            return int(m.group(1)) if m else 0
        result.sort(key=sort_key, reverse=True)
        return result

    def _dedup_by_keys(self, items: List, keys: List[str]) -> List:
        seen = {}
        for item in items:
            if not isinstance(item, dict): continue
            parts = []
            for k in keys:
                v = _cv(item.get(k, "")).lower().strip()
                parts.append(re.sub(r'[^a-z0-9]', '', v))
            key = "|".join(parts)
            if not key or key == "|" * (len(keys)-1): continue
            if key not in seen:
                seen[key] = item
            else:
                # Fill in missing fields
                ex = seen[key]
                for k, v in item.items():
                    if _cv(v) and not _cv(ex.get(k)):
                        ex[k] = v
        return list(seen.values())

    def _merge_skills(self, sa, sb):
        m = {}
        for s in (sa or []) + (sb or []):
            if isinstance(s, dict) and s.get("name"):
                n = _cv(s["name"]).lower().strip()
                if n and n not in m:
                    m[n] = s
        return list(m.values())

    def _merge_dicts(self, da, db):
        if not isinstance(da, dict) or not isinstance(db, dict):
            return db if _cv(db) else da
        r = {}
        for k in set(list(da.keys()) + list(db.keys())):
            va, vb = da.get(k), db.get(k)
            if isinstance(va, dict) and isinstance(vb, dict):
                r[k] = self._merge_dicts(va, vb)
            elif isinstance(va, list) and isinstance(vb, list):
                r[k] = vb if len(vb) >= len(va) else va
            else:
                r[k] = vb if _cv(vb) else va
        return r

    def _clean(self, obj):
        if isinstance(obj, dict): return {k: self._clean(v) for k, v in obj.items()}
        if isinstance(obj, list): return [self._clean(i) for i in obj]
        if obj is None or obj == "null" or obj == "None": return ""
        return obj


# ============================================================================
# SKILL NORMALIZER — 2 categories only
# ============================================================================

class SkillNormalizerAgent:
    BLOCKLIST = {
        'hazardous materials transportation', 'similitude', 'morality',
        'philosophy', 'dies', 'economics', 'tourism market', 'jan',
        'guidance', 'advise others', 'lead others', 'job market offers',
        'customer service', 'digital data processing', 'business processes',
        'customer relationship management', 'process data',
        'computer assisted language learning', 'information extraction',
        'predictive maintenance', 'publish academic research',
        'build predictive models', 'develop predictive models',
        'style sheet languages', 'optical character recognition software',
        'database',
    }
    SPOKEN = {'hindi','english','urdu','arabic','french','german','spanish','chinese','japanese','korean','bengali','tamil','telugu','marathi','gujarati','punjabi','malayalam','kannada','russian','portuguese','italian','turkish','persian'}
    TOOLS = {
        'docker','kubernetes','k8s','aws','azure','gcp','google cloud',
        'terraform','ansible','jenkins','github actions','gitlab ci',
        'git','github','jira','postman','grafana','prometheus','datadog',
        'tableau','power bi','powerbi','excel','mongodb','postgresql',
        'postgres','mysql','redis','elasticsearch','kafka','rabbitmq',
        'airflow','mlflow','dbt','snowflake','bigquery','spark','hadoop',
        'hive','pinecone','chroma','chromadb','faiss','milvus','weaviate',
        'linux','nginx','ci/cd','cicd','figma','neo4j','dynamodb',
        'firebase','supabase','vercel','heroku','sagemaker','vertex ai',
        'bedrock','databricks','nifi','apache nifi','n8n','zapier','make',
        'alteryx','dataiku','apache airflow','apache kafka','apache spark',
        'jupyter notebook','incorta','sas','ibm watson','ibm watsonx',
        'contentsquare','mlops','phidata','ci/cd pipelines','open-cv',
        'opencv','plotly','fastapi','fast api','vector db','autogen',
    }

    def __init__(self, taxonomy=None):
        self.taxonomy = taxonomy

    def normalize_and_categorize(self, skills, full_text=""):
        result = {"skills_technologies": [], "tools_platforms": []}
        seen = set()

        for s in (skills or []):
            if not isinstance(s, dict): continue
            name = _cv(s.get("name", "")).strip()
            if not name or len(name) < 2 or len(name) > 60: continue
            nl = name.lower()
            if nl in seen or nl in self.BLOCKLIST or nl in self.SPOKEN: continue
            seen.add(nl)

            canonical = name
            if self.taxonomy:
                entry = self.taxonomy.find_skill(name)
                if entry: canonical = entry.name

            cat = "tools_platforms" if nl in self.TOOLS else "skills_technologies"
            result[cat].append(canonical)

        # Taxonomy text search
        if full_text and self.taxonomy:
            for entry in self.taxonomy.find_skills_in_text(full_text):
                nl = entry.name.lower()
                if nl in seen or nl in self.BLOCKLIST or nl in self.SPOKEN: continue
                if len(entry.name) < 3 or len(entry.name.split()) > 3: continue
                seen.add(nl)
                cat = "tools_platforms" if nl in self.TOOLS else "skills_technologies"
                result[cat].append(entry.name)

        # Dedupe
        for k in result:
            result[k] = list(dict.fromkeys(result[k]))

        total = len(result["skills_technologies"]) + len(result["tools_platforms"])
        logger.info(f"[SkillNormalizer] skills={len(result['skills_technologies'])} tools={len(result['tools_platforms'])} total={total}")
        return result


# ============================================================================
# REVIEWER
# ============================================================================

class ReviewerAgent:
    def review(self, result):
        issues = []
        pi = result.get("personal_info", {})
        if not _cv(pi.get("full_name")) and not _cv(pi.get("first_name")): issues.append("No name")
        if not _cv((pi.get("contact") or {}).get("email")): issues.append("No email")
        if not result.get("experience"): issues.append("No experience")
        if not result.get("education"): issues.append("No education")

        skills = result.get("skills", {})
        total = sum(len(v) for v in skills.values() if isinstance(v, list)) if isinstance(skills, dict) else len(skills) if isinstance(skills, list) else 0
        if total < 3: issues.append(f"Only {total} skills")

        score = 0.0
        if _cv(pi.get("full_name")) or _cv(pi.get("first_name")): score += 0.2
        if _cv((pi.get("contact") or {}).get("email")): score += 0.1
        if result.get("experience"): score += 0.3
        if total >= 3: score += 0.2
        if result.get("education"): score += 0.2

        return {
            "is_complete": len(issues) == 0,
            "issues": issues,
            "needs_human_review": len(issues) > 1 or score < 0.7,
            "overall_confidence": round(min(score, 1.0), 2),
            "stats": {
                "total_skills": total,
                "experience_count": len(result.get("experience", [])),
                "education_count": len(result.get("education", [])),
                "certifications_count": len(result.get("certifications", [])),
                "projects_count": len(result.get("projects", [])),
            }
        }


# ============================================================================
# ORCHESTRATOR
# ============================================================================

class ResumeProcessingGraph:
    def __init__(self, taxonomy=None, api_key=None, model=None):
        self.llm = GroqClient(api_key=api_key, model=model)
        self.extractor_a = ExtractorA(self.llm)
        self.extractor_b = ExtractorB(self.llm)
        self.judge = JudgeAgent()
        self.normalizer = SkillNormalizerAgent(taxonomy)
        self.reviewer = ReviewerAgent()
        logger.info("ResumeProcessingGraph v1.3 initialized")

    def process(self, resume_text, source_file=""):
        start = datetime.now()
        logger.info(f"{'='*50}")
        logger.info(f"RESUME PROCESSING v1.3 — {len(resume_text)} chars")

        a, ca = self.extractor_a.extract(resume_text)
        b, cb = self.extractor_b.extract(resume_text)
        merged = self.judge.reconcile(a, ca, b, cb, resume_text)

        raw_skills = merged.get("skills", [])
        merged["skills"] = self.normalizer.normalize_and_categorize(raw_skills, resume_text)

        review = self.reviewer.review(merged)
        dur = (datetime.now() - start).total_seconds()

        merged["meta"] = {
            "source_file": source_file,
            "parser_version": "multi-agent-v1.3",
            "parsed_date": datetime.utcnow().isoformat(),
            "agents_used": ["ExtractorA(2-phase)", "ExtractorB", "JudgeAgent", "SkillNormalizer(2-cat)", "ReviewerAgent"],
            "confidence_a": ca, "confidence_b": cb,
            "overall_confidence": review["overall_confidence"],
            "duration_seconds": round(dur, 2),
            "review": review,
        }

        logger.info(f"DONE in {dur:.1f}s | conf={review['overall_confidence']} | "
                     f"exp={review['stats']['experience_count']} skills={review['stats']['total_skills']} "
                     f"certs={review['stats']['certifications_count']} proj={review['stats']['projects_count']}")
        return merged
