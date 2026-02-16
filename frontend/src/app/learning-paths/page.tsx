'use client';

import { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import api from '@/lib/api';
import NotificationBell from '@/components/NotificationBell';

interface LearningTopic {
  order: number;
  topic: string;
  description: string;
  difficulty: string;
  estimated_hours: number;
  search_keywords: string[];
  platforms_to_check: string[];
}

interface SkillRecommendation {
  skill: string;
  learning_path: LearningTopic[];
  projects: string[];
  certifications: string[];
}

interface TrendingSkill {
  skill_name: string;
  relevance_score: number;
  trend_status: string;
  reason: string;
  learning_priority: string;
}

interface AILearningData {
  current_skills: string[];
  missing_skills: string[];
  target_role?: string;
  trend_analysis?: {
    skill_analysis: string;
    career_direction: string;
    trending_skills: TrendingSkill[];
  };
  ai_recommendations: SkillRecommendation[];
  error?: string;
}

export default function LearningPathsPage() {
  const router = useRouter();
  const [data, setData] = useState<AILearningData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [expandedSkills, setExpandedSkills] = useState<Set<string>>(new Set());

  useEffect(() => {
    const token = api.getToken();
    if (!token) {
      router.push('/login');
      return;
    }
    loadAILearningPath();
  }, [router]);

  const loadAILearningPath = async () => {
    setLoading(true);
    setError(null);
    try {
      const result = await api.getAILearningPath();
      setData(result);
      // Auto-expand first skill
      if (result.ai_recommendations?.length > 0) {
        setExpandedSkills(new Set([result.ai_recommendations[0].skill]));
      }
    } catch (err: any) {
      setError(err.message || 'Failed to load AI recommendations');
    } finally {
      setLoading(false);
    }
  };

  const toggleSkill = (skill: string) => {
    const newExpanded = new Set(expandedSkills);
    if (newExpanded.has(skill)) {
      newExpanded.delete(skill);
    } else {
      newExpanded.add(skill);
    }
    setExpandedSkills(newExpanded);
  };

  const getDifficultyColor = (level: string) => {
    switch (level?.toLowerCase()) {
      case 'beginner': return 'bg-green-100 text-green-700';
      case 'intermediate': return 'bg-yellow-100 text-yellow-700';
      case 'advanced': return 'bg-orange-100 text-orange-700';
      case 'expert': return 'bg-red-100 text-red-700';
      default: return 'bg-gray-100 text-gray-700';
    }
  };

  const getTrendColor = (status: string) => {
    switch (status?.toLowerCase()) {
      case 'rising': return 'text-green-600';
      case 'emerging': return 'text-blue-600';
      case 'stable': return 'text-gray-600';
      default: return 'text-gray-600';
    }
  };

  const getPriorityBadge = (priority: string) => {
    switch (priority?.toLowerCase()) {
      case 'high': return 'bg-red-100 text-red-700';
      case 'medium': return 'bg-yellow-100 text-yellow-700';
      case 'low': return 'bg-blue-100 text-blue-700';
      default: return 'bg-gray-100 text-gray-700';
    }
  };

  const searchOnPlatform = (platform: string, keyword: string) => {
    const urls: Record<string, string> = {
      'Coursera': 'https://www.coursera.org/search?query=',
      'Udemy': 'https://www.udemy.com/courses/search/?q=',
      'YouTube': 'https://www.youtube.com/results?search_query=',
      'freeCodeCamp': 'https://www.freecodecamp.org/news/search/?query=',
      'Pluralsight': 'https://www.pluralsight.com/search?q=',
      'LinkedIn Learning': 'https://www.linkedin.com/learning/search?keywords=',
      'GitHub': 'https://github.com/search?q=',
      'Dev.to': 'https://dev.to/search?q=',
      'Medium': 'https://medium.com/search?q=',
      'edX': 'https://www.edx.org/search?q=',
      'Udacity': 'https://www.udacity.com/courses/all?search=',
    };
    const baseUrl = urls[platform] || 'https://www.google.com/search?q=';
    window.open(baseUrl + encodeURIComponent(keyword), '_blank');
  };

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-50">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto"></div>
          <p className="mt-4 text-gray-600">AI is analyzing your skills...</p>
          <p className="mt-2 text-sm text-gray-400">This may take a few seconds</p>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50">
      <header className="bg-white shadow-sm">
        <div className="max-w-6xl mx-auto px-4 py-4 flex justify-between items-center">
          <div className="flex items-center gap-4">
            <Link href="/skill-gaps" className="text-gray-600 hover:text-gray-900">Back</Link>
            <h1 className="text-2xl font-bold text-gray-900">AI Learning Path</h1>
            <span className="bg-purple-100 text-purple-700 px-2 py-1 rounded text-xs font-medium">AI Powered</span>
          </div>
          <div className="flex items-center gap-4">
            <NotificationBell />
            <button onClick={loadAILearningPath} className="bg-blue-600 text-white px-4 py-2 rounded-md hover:bg-blue-700">
              Refresh Analysis
            </button>
          </div>
        </div>
      </header>

      <main className="max-w-6xl mx-auto px-4 py-8">
        {error ? (
          <div className="bg-red-50 border border-red-200 rounded-lg p-6 text-center">
            <p className="text-red-600 mb-4">{error}</p>
            <Link href="/profile" className="text-blue-600 hover:underline">Complete Your Profile</Link>
          </div>
        ) : !data || data.ai_recommendations?.length === 0 ? (
          <div className="bg-white rounded-lg shadow p-12 text-center">
            <div className="text-6xl mb-4">🤖</div>
            <h3 className="text-xl font-semibold text-gray-900 mb-2">Add skills to your profile</h3>
            <p className="text-gray-600 mb-4">The AI needs your current skills to generate personalized recommendations.</p>
            <Link href="/profile" className="inline-block bg-blue-600 text-white px-6 py-2 rounded-md hover:bg-blue-700">
              Update Profile
            </Link>
          </div>
        ) : (
          <>
            {/* Current Skills Summary */}
            <div className="bg-white rounded-lg shadow p-6 mb-6">
              <h2 className="text-lg font-semibold text-gray-900 mb-4">Your Current Skills</h2>
              <div className="flex flex-wrap gap-2">
                {data.current_skills?.map((skill, i) => (
                  <span key={i} className="bg-green-100 text-green-700 px-3 py-1 rounded-full text-sm">{skill}</span>
                ))}
              </div>
              {data.target_role && (
                <p className="mt-4 text-gray-600">Target Role: <span className="font-medium">{data.target_role}</span></p>
              )}
            </div>

            {/* AI Analysis */}
            {data.trend_analysis && (
              <div className="bg-gradient-to-r from-purple-50 to-blue-50 rounded-lg shadow p-6 mb-6 border border-purple-100">
                <div className="flex items-center gap-2 mb-4">
                  <span className="text-2xl">🤖</span>
                  <h2 className="text-lg font-semibold text-gray-900">AI Skill Analysis</h2>
                </div>
                {data.trend_analysis.skill_analysis && (
                  <p className="text-gray-700 mb-4">{data.trend_analysis.skill_analysis}</p>
                )}
                {data.trend_analysis.career_direction && (
                  <p className="text-gray-600 mb-4">
                    <span className="font-medium">Career Direction:</span> {data.trend_analysis.career_direction}
                  </p>
                )}
                
                {data.trend_analysis.trending_skills?.length > 0 && (
                  <div className="mt-4">
                    <h3 className="font-medium text-gray-900 mb-3">Trending Skills for You</h3>
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                      {data.trend_analysis.trending_skills.map((skill, i) => (
                        <div key={i} className="bg-white rounded-lg p-4 border">
                          <div className="flex justify-between items-start mb-2">
                            <span className="font-medium text-gray-900">{skill.skill_name}</span>
                            <span className={'px-2 py-0.5 rounded text-xs ' + getPriorityBadge(skill.learning_priority)}>
                              {skill.learning_priority} priority
                            </span>
                          </div>
                          <div className="flex items-center gap-2 text-sm mb-2">
                            <span className={'font-medium ' + getTrendColor(skill.trend_status)}>
                              {skill.trend_status === 'rising' ? '📈' : skill.trend_status === 'emerging' ? '🌟' : '📊'} {skill.trend_status}
                            </span>
                            <span className="text-gray-500">|</span>
                            <span className="text-gray-600">{skill.relevance_score}% relevant</span>
                          </div>
                          <p className="text-sm text-gray-600">{skill.reason}</p>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            )}

            {/* Learning Recommendations */}
            <h2 className="text-xl font-semibold text-gray-900 mb-4">Recommended Learning Path</h2>
            
            <div className="space-y-4">
              {data.ai_recommendations.map((rec, index) => (
                <div key={index} className="bg-white rounded-lg shadow overflow-hidden">
                  <button
                    onClick={() => toggleSkill(rec.skill)}
                    className="w-full px-6 py-4 flex justify-between items-center hover:bg-gray-50 transition"
                  >
                    <div className="flex items-center gap-3">
                      <span className="text-2xl">🎯</span>
                      <div className="text-left">
                        <h3 className="text-lg font-semibold text-gray-900">{rec.skill}</h3>
                        <p className="text-sm text-gray-500">{rec.learning_path?.length || 0} topics to learn</p>
                      </div>
                    </div>
                    <span className="text-2xl text-gray-400">
                      {expandedSkills.has(rec.skill) ? '−' : '+'}
                    </span>
                  </button>
                  
                  {expandedSkills.has(rec.skill) && (
                    <div className="px-6 pb-6 border-t">
                      {/* Learning Topics */}
                      <div className="mt-4 space-y-4">
                        {rec.learning_path?.map((topic, ti) => (
                          <div key={ti} className="bg-gray-50 rounded-lg p-4">
                            <div className="flex items-start gap-4">
                              <div className="flex-shrink-0 w-8 h-8 bg-blue-600 text-white rounded-full flex items-center justify-center font-bold">
                                {topic.order}
                              </div>
                              <div className="flex-1">
                                <div className="flex items-center gap-2 mb-2">
                                  <h4 className="font-semibold text-gray-900">{topic.topic}</h4>
                                  <span className={'px-2 py-0.5 rounded text-xs ' + getDifficultyColor(topic.difficulty)}>
                                    {topic.difficulty}
                                  </span>
                                  {topic.estimated_hours && (
                                    <span className="text-xs text-gray-500">~{topic.estimated_hours}h</span>
                                  )}
                                </div>
                                <p className="text-sm text-gray-600 mb-3">{topic.description}</p>
                                
                                {/* Search Keywords */}
                                <div className="mb-3">
                                  <p className="text-xs text-gray-500 mb-2">Search for:</p>
                                  <div className="flex flex-wrap gap-2">
                                    {topic.search_keywords?.map((kw, ki) => (
                                      <span key={ki} className="bg-blue-50 text-blue-700 px-2 py-1 rounded text-xs">
                                        "{kw}"
                                      </span>
                                    ))}
                                  </div>
                                </div>
                                
                                {/* Platform Buttons */}
                                <div>
                                  <p className="text-xs text-gray-500 mb-2">Find courses on:</p>
                                  <div className="flex flex-wrap gap-2">
                                    {topic.platforms_to_check?.map((platform, pi) => (
                                      <button
                                        key={pi}
                                        onClick={() => searchOnPlatform(platform, topic.search_keywords?.[0] || topic.topic)}
                                        className="bg-white border border-gray-200 text-gray-700 px-3 py-1 rounded text-sm hover:bg-gray-50 hover:border-blue-300 transition"
                                      >
                                        {platform}
                                      </button>
                                    ))}
                                  </div>
                                </div>
                              </div>
                            </div>
                          </div>
                        ))}
                      </div>

                      {/* Projects */}
                      {rec.projects?.length > 0 && (
                        <div className="mt-6">
                          <h4 className="font-medium text-gray-900 mb-3">💡 Practice Projects</h4>
                          <div className="flex flex-wrap gap-2">
                            {rec.projects.map((project, pi) => (
                              <span key={pi} className="bg-yellow-50 text-yellow-800 px-3 py-1 rounded-full text-sm border border-yellow-200">
                                {project}
                              </span>
                            ))}
                          </div>
                        </div>
                      )}

                      {/* Certifications */}
                      {rec.certifications?.length > 0 && (
                        <div className="mt-4">
                          <h4 className="font-medium text-gray-900 mb-3">🏆 Suggested Certifications</h4>
                          <div className="flex flex-wrap gap-2">
                            {rec.certifications.map((cert, ci) => (
                              <span key={ci} className="bg-purple-50 text-purple-800 px-3 py-1 rounded-full text-sm border border-purple-200">
                                {cert}
                              </span>
                            ))}
                          </div>
                        </div>
                      )}
                    </div>
                  )}
                </div>
              ))}
            </div>
          </>
        )}
      </main>
    </div>
  );
}
