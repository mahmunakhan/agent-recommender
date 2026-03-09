"""
AI Skill Recommendation Agent Service
Uses LLM to analyze skills and recommend learning paths
"""
import os
import json
import re
import logging
from typing import List, Dict, Optional
from groq import Groq

logger = logging.getLogger(__name__)

class SkillRecommendationAgent:
    """AI Agent for skill analysis and recommendations"""
    
    def __init__(self):
        self.client = Groq(api_key=os.getenv("GROQ_API_KEY"))
        self.model = "llama-3.1-70b-versatile"
    
    def _extract_json(self, text: str) -> dict:
        """Extract JSON from LLM response, handling markdown code blocks"""
        try:
            # Try direct parse first
            return json.loads(text.strip())
        except:
            pass
        
        # Try to extract from markdown code block
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
                    return json.loads(json_str.strip())
                except:
                    continue
        
        return {}
    
    def _call_llm(self, system_prompt: str, user_prompt: str) -> str:
        """Make LLM API call"""
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.7,
                max_tokens=2000
            )
            return response.choices[0].message.content
        except Exception as e:
            logger.error(f"LLM call failed: {str(e)}")
            return ""

    def analyze_skill_trends(self, current_skills: List[str], target_role: Optional[str] = None) -> Dict:
        """Agent 1: Analyze current skills and identify trending related skills"""
        system_prompt = """You are a career skills analyst. Analyze skills and recommend trending skills to learn.
You MUST respond with ONLY valid JSON, no markdown, no explanation, no code blocks."""

        user_prompt = f"""Current Skills: {', '.join(current_skills)}
Target Role: {target_role or 'Software/Data Professional'}

Return this exact JSON structure with 5 trending skills:
{{"skill_analysis": "brief analysis", "career_direction": "suggested direction", "trending_skills": [{{"skill_name": "name", "relevance_score": 85, "trend_status": "rising", "reason": "why", "learning_priority": "high"}}]}}"""

        response = self._call_llm(system_prompt, user_prompt)
        result = self._extract_json(response)
        
        if not result.get("trending_skills"):
            # Fallback trending skills based on current skills
            result = self._get_fallback_trends(current_skills, target_role)
        
        return result

    def _get_fallback_trends(self, current_skills: List[str], target_role: Optional[str]) -> Dict:
        """Generate fallback trending skills when AI fails"""
        skill_set = set(s.lower() for s in current_skills)
        trending = []
        
        # Data/ML skills
        if any(s in skill_set for s in ['python', 'machine learning', 'deep learning']):
            trending.extend([
                {"skill_name": "MLOps", "relevance_score": 90, "trend_status": "rising", "reason": "Essential for deploying ML models to production", "learning_priority": "high"},
                {"skill_name": "LangChain", "relevance_score": 88, "trend_status": "emerging", "reason": "Key framework for building LLM applications", "learning_priority": "high"},
                {"skill_name": "RAG Systems", "relevance_score": 85, "trend_status": "emerging", "reason": "Critical for building AI applications with custom knowledge", "learning_priority": "high"},
            ])
        
        # DevOps skills
        if any(s in skill_set for s in ['docker', 'kubernetes']):
            trending.extend([
                {"skill_name": "Terraform", "relevance_score": 85, "trend_status": "stable", "reason": "Industry standard for infrastructure as code", "learning_priority": "high"},
                {"skill_name": "GitOps", "relevance_score": 80, "trend_status": "rising", "reason": "Modern approach to continuous deployment", "learning_priority": "medium"},
            ])
        
        # General high-demand skills
        if len(trending) < 5:
            trending.extend([
                {"skill_name": "FastAPI", "relevance_score": 82, "trend_status": "rising", "reason": "Modern Python web framework for APIs", "learning_priority": "medium"},
                {"skill_name": "System Design", "relevance_score": 88, "trend_status": "stable", "reason": "Critical for senior roles and interviews", "learning_priority": "high"},
            ])
        
        return {
            "skill_analysis": f"Based on your expertise in {', '.join(current_skills[:3])}, you have a strong foundation in data and software development.",
            "career_direction": target_role or "Senior Data/ML Engineer or AI Solutions Architect",
            "trending_skills": trending[:5]
        }

    def generate_learning_topics(self, skill_name: str, current_level: str = "beginner") -> Dict:
        """Agent 2: Generate specific learning topics for a skill"""
        system_prompt = """You are a learning path designer. Create structured learning topics.
You MUST respond with ONLY valid JSON, no markdown, no explanation."""

        user_prompt = f"""Create a learning path for: {skill_name}
Level: {current_level}

Return this exact JSON structure with 4-5 topics:
{{"skill": "{skill_name}", "learning_path": [{{"order": 1, "topic": "Topic Name", "description": "What to learn", "difficulty": "beginner", "estimated_hours": 10, "search_keywords": ["keyword1", "keyword2"], "platforms_to_check": ["Coursera", "Udemy", "YouTube"]}}], "recommended_projects": ["Project 1"], "certification_suggestions": ["Cert 1"]}}"""

        response = self._call_llm(system_prompt, user_prompt)
        result = self._extract_json(response)
        
        if not result.get("learning_path"):
            result = self._get_fallback_learning_path(skill_name)
        
        return result

    def _get_fallback_learning_path(self, skill_name: str) -> Dict:
        """Generate fallback learning path when AI fails"""
        skill_lower = skill_name.lower()
        
        return {
            "skill": skill_name,
            "learning_path": [
                {
                    "order": 1,
                    "topic": f"{skill_name} Fundamentals",
                    "description": f"Learn the core concepts and basics of {skill_name}",
                    "difficulty": "beginner",
                    "estimated_hours": 10,
                    "search_keywords": [skill_lower, f"{skill_lower} tutorial", f"learn {skill_lower} beginners"],
                    "platforms_to_check": ["Coursera", "Udemy", "YouTube", "freeCodeCamp"]
                },
                {
                    "order": 2,
                    "topic": f"{skill_name} Hands-on Practice",
                    "description": f"Build practical projects using {skill_name}",
                    "difficulty": "beginner",
                    "estimated_hours": 15,
                    "search_keywords": [f"{skill_lower} projects", f"{skill_lower} exercises", f"{skill_lower} practice"],
                    "platforms_to_check": ["GitHub", "Kaggle", "LeetCode", "HackerRank"]
                },
                {
                    "order": 3,
                    "topic": f"Intermediate {skill_name}",
                    "description": f"Advance your {skill_name} skills with complex concepts",
                    "difficulty": "intermediate",
                    "estimated_hours": 20,
                    "search_keywords": [f"{skill_lower} advanced", f"{skill_lower} intermediate", f"{skill_lower} deep dive"],
                    "platforms_to_check": ["Pluralsight", "LinkedIn Learning", "Udemy"]
                },
                {
                    "order": 4,
                    "topic": f"{skill_name} Best Practices",
                    "description": f"Learn industry best practices and patterns for {skill_name}",
                    "difficulty": "intermediate",
                    "estimated_hours": 10,
                    "search_keywords": [f"{skill_lower} best practices", f"{skill_lower} patterns", f"{skill_lower} production"],
                    "platforms_to_check": ["Medium", "Dev.to", "Official Documentation"]
                },
                {
                    "order": 5,
                    "topic": f"Real-world {skill_name} Projects",
                    "description": f"Apply {skill_name} in production-level projects",
                    "difficulty": "advanced",
                    "estimated_hours": 25,
                    "search_keywords": [f"{skill_lower} portfolio projects", f"{skill_lower} real world", f"build with {skill_lower}"],
                    "platforms_to_check": ["GitHub", "YouTube", "Udemy"]
                }
            ],
            "recommended_projects": [
                f"Build a {skill_name} portfolio project",
                f"Contribute to open source {skill_name} projects",
                f"Create a tutorial or blog about {skill_name}"
            ],
            "certification_suggestions": [
                f"{skill_name} Professional Certificate (if available)",
                "Related cloud certifications (AWS, GCP, Azure)"
            ]
        }

    def get_complete_learning_recommendation(
        self, 
        current_skills: List[str], 
        missing_skills: List[str],
        target_role: Optional[str] = None
    ) -> Dict:
        """Master function: Combine all agents for complete recommendation"""
        result = {
            "current_skills": current_skills,
            "missing_skills": missing_skills,
            "target_role": target_role,
            "ai_recommendations": []
        }
        
        # Step 1: Analyze trends
        logger.info("Agent 1: Analyzing skill trends...")
        trend_analysis = self.analyze_skill_trends(current_skills, target_role)
        result["trend_analysis"] = trend_analysis
        
        # Step 2: Combine missing skills with trending skills
        skills_to_learn = list(missing_skills) if missing_skills else []
        
        # Add top trending skills
        if trend_analysis.get("trending_skills"):
            for ts in trend_analysis["trending_skills"][:3]:
                skill_name = ts.get("skill_name", "")
                if skill_name and skill_name not in skills_to_learn:
                    skills_to_learn.append(skill_name)
        
        # Ensure we have skills to learn
        if not skills_to_learn:
            skills_to_learn = ["System Design", "API Development", "Cloud Computing"]
        
        # Step 3: Generate learning topics for each skill (limit to 5)
        logger.info("Agent 2: Generating learning topics...")
        for skill in skills_to_learn[:5]:
            topics = self.generate_learning_topics(skill)
            if topics.get("learning_path"):
                result["ai_recommendations"].append({
                    "skill": skill,
                    "learning_path": topics.get("learning_path", []),
                    "projects": topics.get("recommended_projects", []),
                    "certifications": topics.get("certification_suggestions", [])
                })
        
        return result


# Singleton instance
skill_agent = SkillRecommendationAgent()
