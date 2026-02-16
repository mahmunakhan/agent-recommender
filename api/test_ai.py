import sys
sys.path.insert(0, '.')
from app.services.database import SessionLocal
from app.models.user import User, Profile
from app.models.skill import Skill, ProfileSkill
from app.models.recommendation import SkillGap
from app.services.skill_agent_service import skill_agent
from sqlalchemy import select

db = SessionLocal()

user = db.execute(select(User).where(User.email == 'demo@test.com')).scalar_one_or_none()
profile = db.execute(select(Profile).where(Profile.user_id == user.id)).scalar_one_or_none()

skills = db.execute(
    select(ProfileSkill, Skill)
    .join(Skill)
    .where(ProfileSkill.profile_id == profile.id)
).all()
current_skills = [ps.Skill.name for ps in skills]

gaps = db.execute(
    select(SkillGap, Skill)
    .join(Skill)
    .where(SkillGap.user_id == user.id)
).all()
missing_skills = [sg.Skill.name for sg in gaps]

print(f'Current Skills: {current_skills}')
print(f'Missing Skills: {missing_skills}')
print(f'Target Role: {profile.desired_role}')
print()
print('Calling AI Agent...')

result = skill_agent.get_complete_learning_recommendation(
    current_skills=current_skills,
    missing_skills=missing_skills,
    target_role=profile.desired_role
)

print(f'AI Result Keys: {list(result.keys())}')
recs = result.get('ai_recommendations', [])
print(f'Recommendations Count: {len(recs)}')
if recs:
    print(f'First Recommendation: {recs[0].get("skill", "N/A")}')

db.close()
