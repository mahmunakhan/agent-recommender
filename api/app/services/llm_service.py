"""
Groq LLM Service
Handles AI-powered extraction and analysis using Groq API
"""

from groq import Groq
import logging
from typing import Optional, Dict, Any
import json
import re

from app.config import settings

logger = logging.getLogger(__name__)


class LLMService:
    """Service for Groq LLM operations"""
    
    def __init__(self):
        self.client = None
        self.model = "llama-3.1-8b-instant"  # Fast, capable model
    
    def connect(self) -> bool:
        """Initialize Groq client"""
        try:
            if not settings.GROQ_API_KEY:
                logger.error("GROQ_API_KEY not set")
                return False
            
            self.client = Groq(api_key=settings.GROQ_API_KEY)
            logger.info("Groq client initialized")
            return True
        except Exception as e:
            logger.error(f"Groq connection failed: {e}")
            return False
    
    def _call_llm(
        self, 
        prompt: str, 
        system_prompt: str = "",
        temperature: float = 0.1,
        max_tokens: int = 4096
    ) -> Optional[str]:
        """Make a call to Groq LLM"""
        if self.client is None:
            self.connect()
        
        try:
            messages = []
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})
            messages.append({"role": "user", "content": prompt})
            
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens
            )
            
            return response.choices[0].message.content
        except Exception as e:
            logger.error(f"LLM call failed: {e}")
            return None
    
    def _extract_json(self, text: str) -> Optional[dict]:
        """Extract JSON from LLM response"""
        try:
            # Try direct parse
            return json.loads(text)
        except:
            pass
        
        # Try to find JSON block
        patterns = [
            r'```json\s*([\s\S]*?)\s*```',
            r'```\s*([\s\S]*?)\s*```',
            r'\{[\s\S]*\}'
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                try:
                    json_str = match.group(1) if '```' in pattern else match.group(0)
                    return json.loads(json_str)
                except:
                    continue
        
        logger.error("Could not extract JSON from response")
        return None
    
    def parse_resume(self, resume_text: str) -> Optional[Dict[str, Any]]:
        """Parse resume text into structured data"""
        
        system_prompt = """You are an expert resume parser. Extract structured information from resumes accurately.
Always respond with valid JSON only, no additional text."""
        
        prompt = f"""Parse the following resume and extract information into this JSON structure:

{{
    "personal_info": {{
        "name": "string or null",
        "email": "string or null",
        "phone": "string or null",
        "linkedin": "string or null",
        "location": "string or null"
    }},
    "summary": "professional summary string or null",
    "experience": [
        {{
            "company": "string",
            "title": "string",
            "location": "string or null",
            "start_date": "YYYY-MM or null",
            "end_date": "YYYY-MM or present or null",
            "description": "string",
            "skills_used": ["skill1", "skill2"]
        }}
    ],
    "education": [
        {{
            "institution": "string",
            "degree": "string",
            "field": "string or null",
            "year": "integer or null"
        }}
    ],
    "skills": [
        {{
            "name": "string",
            "proficiency": "beginner|intermediate|advanced|expert",
            "years": "integer or null"
        }}
    ],
    "certifications": [
        {{
            "name": "string",
            "issuer": "string or null",
            "year": "integer or null"
        }}
    ]
}}

Resume Text:
{resume_text}

Respond with ONLY the JSON, no other text."""

        response = self._call_llm(prompt, system_prompt, temperature=0.1)
        if response:
            return self._extract_json(response)
        return None
    
    def parse_job_description(self, job_text: str) -> Optional[Dict[str, Any]]:
        """Parse job description into structured data"""
        
        system_prompt = """You are an expert job posting parser. Extract structured information accurately.
Always respond with valid JSON only, no additional text."""
        
        prompt = f"""Parse the following job posting and extract information into this JSON structure:

{{
    "title": "job title string",
    "company": "company name or null",
    "location": {{
        "city": "string or null",
        "country": "string or null",
        "type": "onsite|remote|hybrid"
    }},
    "employment_type": "full_time|part_time|contract|internship",
    "experience_years": {{
        "min": "integer or null",
        "max": "integer or null"
    }},
    "salary": {{
        "min": "integer or null",
        "max": "integer or null",
        "currency": "USD|EUR|etc or null"
    }},
    "required_skills": [
        {{
            "skill_name": "string",
            "importance": "critical|high|medium",
            "min_years": "integer or null"
        }}
    ],
    "preferred_skills": ["skill1", "skill2"],
    "education": {{
        "min_level": "high_school|bachelors|masters|phd|none",
        "preferred_fields": ["field1", "field2"]
    }},
    "responsibilities": ["responsibility1", "responsibility2"],
    "benefits": ["benefit1", "benefit2"]
}}

Job Posting:
{job_text}

Respond with ONLY the JSON, no other text."""

        response = self._call_llm(prompt, system_prompt, temperature=0.1)
        if response:
            return self._extract_json(response)
        return None
    
    def analyze_skill_gap(
        self, 
        user_skills: list, 
        job_requirements: list
    ) -> Optional[Dict[str, Any]]:
        """Analyze skill gaps between user and job requirements"""
        
        system_prompt = """You are a career advisor analyzing skill gaps.
Always respond with valid JSON only."""
        
        prompt = f"""Analyze the skill gap between a candidate and job requirements.

Candidate Skills:
{json.dumps(user_skills, indent=2)}

Job Required Skills:
{json.dumps(job_requirements, indent=2)}

Provide analysis in this JSON format:
{{
    "matching_skills": [
        {{
            "skill": "skill name",
            "user_level": "beginner|intermediate|advanced|expert",
            "required_level": "beginner|intermediate|advanced|expert",
            "match_quality": "exceeds|meets|partial|insufficient"
        }}
    ],
    "missing_skills": [
        {{
            "skill": "skill name",
            "importance": "critical|high|medium",
            "difficulty_to_learn": "easy|moderate|hard",
            "estimated_time_weeks": "integer"
        }}
    ],
    "overall_match_percentage": "integer 0-100",
    "recommendation": "brief recommendation string"
}}

Respond with ONLY the JSON."""

        response = self._call_llm(prompt, system_prompt, temperature=0.2)
        if response:
            return self._extract_json(response)
        return None
    
    def generate_recommendation_explanation(
        self,
        job_data: dict,
        match_score: float,
        matching_skills: list,
        missing_skills: list
    ) -> Optional[str]:
        """Generate human-readable recommendation explanation"""
        
        prompt = f"""Write a brief, helpful explanation (2-3 sentences) for why this job is recommended to a candidate.

Job Title: {job_data.get('title', 'Unknown')}
Company: {job_data.get('company_name', 'Unknown')}
Match Score: {match_score}%
Matching Skills: {', '.join(matching_skills[:5])}
Skills to Develop: {', '.join(missing_skills[:3]) if missing_skills else 'None'}

Write a concise, encouraging explanation focusing on the match and growth opportunity."""

        response = self._call_llm(prompt, temperature=0.3, max_tokens=200)
        return response
    
    def suggest_learning_path(
        self,
        skill_gaps: list,
        user_level: str = "intermediate"
    ) -> Optional[Dict[str, Any]]:
        """Suggest learning path for skill gaps"""
        
        system_prompt = """You are a learning advisor creating personalized learning paths.
Always respond with valid JSON only."""
        
        prompt = f"""Create a learning path for a {user_level} level professional to fill these skill gaps:

Skills to Learn:
{json.dumps(skill_gaps, indent=2)}

Provide a structured learning path in this JSON format:
{{
    "learning_path": [
        {{
            "skill": "skill name",
            "priority": "critical|high|medium|low",
            "sequence_order": "integer",
            "recommended_resources": [
                {{
                    "type": "course|tutorial|book|certification|project",
                    "name": "resource name",
                    "provider": "Coursera|Udemy|YouTube|etc",
                    "estimated_hours": "integer",
                    "difficulty": "beginner|intermediate|advanced"
                }}
            ],
            "milestones": ["milestone1", "milestone2"]
        }}
    ],
    "total_estimated_weeks": "integer",
    "quick_wins": ["skill that can be learned quickly"],
    "advice": "brief personalized advice"
}}

Respond with ONLY the JSON."""

        response = self._call_llm(prompt, system_prompt, temperature=0.3)
        if response:
            return self._extract_json(response)
        return None


# Global instance
llm_service = LLMService()