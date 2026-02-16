import requests
import json

login_resp = requests.post(
    'http://localhost:8000/auth/login',
    json={'email': 'demo@test.com', 'password': 'password123'}
)
token = login_resp.json().get('access_token')

headers = {'Authorization': f'Bearer {token}'}
resp = requests.get('http://localhost:8000/recommendations/ai-learning-path', headers=headers)
data = resp.json()

print('AI recommendations count:', len(data.get('ai_recommendations', [])))
print()

recs = data.get('ai_recommendations', [])
if recs:
    for rec in recs[:2]:
        skill = rec.get('skill', 'Unknown')
        topics = rec.get('learning_path', [])
        print(f'Skill: {skill}')
        print(f'  Topics: {len(topics)}')
        if topics:
            print(f'  First topic: {topics[0].get("topic", "N/A")}')
        print()

print('Trending skills:')
trending = data.get('trend_analysis', {}).get('trending_skills', [])
for ts in trending[:3]:
    name = ts.get('skill_name', 'Unknown')
    reason = ts.get('reason', '')
    print(f'  - {name}: {reason}')
