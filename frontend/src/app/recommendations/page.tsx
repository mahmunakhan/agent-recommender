'use client';

import { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import api, { Recommendation } from '@/lib/api';
import NotificationBell from '@/components/NotificationBell';

export default function RecommendationsPage() {
  const router = useRouter();
  const [recommendations, setRecommendations] = useState<Recommendation[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [filter, setFilter] = useState<'all' | 'high' | 'medium'>('all');

  useEffect(() => {
    const token = api.getToken();
    if (!token) {
      router.push('/login');
      return;
    }
    loadRecommendations();
  }, [router]);

  const loadRecommendations = async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await api.getRecommendations();
      setRecommendations(data.recommendations || []);
    } catch (err: any) {
      setError(err.message || 'Failed to load recommendations');
    } finally {
      setLoading(false);
    }
  };

  const getMatchColor = (score: number) => {
    if (score >= 80) return 'text-green-600 bg-green-100';
    if (score >= 60) return 'text-yellow-600 bg-yellow-100';
    return 'text-gray-600 bg-gray-100';
  };

  const formatSalary = (min?: number, max?: number) => {
    if (!min && !max) return 'Not specified';
    if (min && max) return '$' + (min/1000).toFixed(0) + 'K - $' + (max/1000).toFixed(0) + 'K';
    if (min) return 'From $' + (min/1000).toFixed(0) + 'K';
    return 'Up to $' + (max!/1000).toFixed(0) + 'K';
  };

  const filteredRecommendations = recommendations.filter(rec => {
    if (filter === 'high') return rec.match_score >= 80;
    if (filter === 'medium') return rec.match_score >= 60 && rec.match_score < 80;
    return true;
  });

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-50">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto"></div>
          <p className="mt-4 text-gray-600">Finding your perfect job matches...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50">
      <header className="bg-white shadow-sm">
        <div className="max-w-6xl mx-auto px-4 py-4 flex justify-between items-center">
          <div className="flex items-center gap-4">
            <Link href="/dashboard" className="text-gray-600 hover:text-gray-900">Back</Link>
            <h1 className="text-2xl font-bold text-gray-900">Job Recommendations</h1>
          </div>
          <div className="flex items-center gap-4">
            <NotificationBell />
            <button onClick={loadRecommendations} className="bg-blue-600 text-white px-4 py-2 rounded-md hover:bg-blue-700">
              Refresh
            </button>
          </div>
        </div>
      </header>

      <main className="max-w-6xl mx-auto px-4 py-8">
        {error ? (
          <div className="bg-red-50 border border-red-200 rounded-lg p-6 text-center">
            <p className="text-red-600 mb-4">{error}</p>
            <Link href="/profile" className="text-blue-600 hover:underline">Go to Profile</Link>
          </div>
        ) : (
          <>
            <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-6">
              <div className="bg-white rounded-lg shadow p-4 text-center">
                <div className="text-3xl font-bold text-blue-600">{recommendations.length}</div>
                <div className="text-gray-500 text-sm">Total Matches</div>
              </div>
              <div className="bg-white rounded-lg shadow p-4 text-center">
                <div className="text-3xl font-bold text-green-600">
                  {recommendations.filter(r => r.match_score >= 80).length}
                </div>
                <div className="text-gray-500 text-sm">Excellent (80%+)</div>
              </div>
              <div className="bg-white rounded-lg shadow p-4 text-center">
                <div className="text-3xl font-bold text-yellow-600">
                  {recommendations.filter(r => r.match_score >= 60 && r.match_score < 80).length}
                </div>
                <div className="text-gray-500 text-sm">Good (60-79%)</div>
              </div>
              <div className="bg-white rounded-lg shadow p-4 text-center">
                <div className="text-3xl font-bold text-purple-600">
                  {recommendations.length > 0 ? Math.round(recommendations[0].match_score) : 0}%
                </div>
                <div className="text-gray-500 text-sm">Best Match</div>
              </div>
            </div>

            <div className="bg-white rounded-lg shadow p-4 mb-6">
              <div className="flex gap-2">
                <button onClick={() => setFilter('all')} className={'px-4 py-2 rounded-md text-sm font-medium transition ' + (filter === 'all' ? 'bg-blue-600 text-white' : 'bg-gray-100 hover:bg-gray-200')}>
                  All ({recommendations.length})
                </button>
                <button onClick={() => setFilter('high')} className={'px-4 py-2 rounded-md text-sm font-medium transition ' + (filter === 'high' ? 'bg-green-600 text-white' : 'bg-gray-100 hover:bg-gray-200')}>
                  Excellent ({recommendations.filter(r => r.match_score >= 80).length})
                </button>
                <button onClick={() => setFilter('medium')} className={'px-4 py-2 rounded-md text-sm font-medium transition ' + (filter === 'medium' ? 'bg-yellow-600 text-white' : 'bg-gray-100 hover:bg-gray-200')}>
                  Good ({recommendations.filter(r => r.match_score >= 60 && r.match_score < 80).length})
                </button>
              </div>
            </div>

            {filteredRecommendations.length === 0 ? (
              <div className="bg-white rounded-lg shadow p-12 text-center">
                <div className="text-6xl mb-4">🎯</div>
                <h3 className="text-xl font-semibold text-gray-900 mb-2">No recommendations yet</h3>
                <p className="text-gray-600 mb-4">Complete your profile to get personalized job recommendations.</p>
                <Link href="/profile" className="inline-block bg-blue-600 text-white px-6 py-2 rounded-md hover:bg-blue-700">
                  Complete Profile
                </Link>
              </div>
            ) : (
              <div className="space-y-4">
                {filteredRecommendations.map((rec) => (
                  <div key={rec.id} className="bg-white rounded-lg shadow hover:shadow-md transition p-6">
                    <div className="flex justify-between items-start mb-4">
                      <div className="flex-1">
                        <div className="flex items-center gap-3 mb-2">
                          <span className="text-sm text-gray-400">#{rec.ranking_position}</span>
                          <Link href={'/jobs/' + rec.job.id} className="text-xl font-semibold text-gray-900 hover:text-blue-600">
                            {rec.job.title}
                          </Link>
                          <span className={'px-3 py-1 rounded-full text-sm font-medium ' + getMatchColor(rec.match_score)}>
                            {Math.round(rec.match_score)}% Match
                          </span>
                        </div>
                        <p className="text-gray-600 mb-2">{rec.job.company_name}</p>
                        <div className="flex flex-wrap gap-4 text-sm text-gray-500">
                          {rec.job.location_city && <span>📍 {rec.job.location_city}</span>}
                          {rec.job.location_type && <span>🏠 {rec.job.location_type}</span>}
                          <span>💰 {formatSalary(rec.job.salary_min, rec.job.salary_max)}</span>
                        </div>
                      </div>
                    </div>

                    <div className="grid grid-cols-3 gap-4 mb-4">
                      <div className="bg-gray-50 rounded p-3">
                        <div className="text-sm text-gray-500">Skills</div>
                        <div className="text-lg font-semibold">{Math.round(rec.skill_match_score)}%</div>
                        <div className="w-full bg-gray-200 rounded-full h-2 mt-1">
                          <div className="bg-blue-600 h-2 rounded-full" style={{ width: rec.skill_match_score + '%' }}></div>
                        </div>
                      </div>
                      <div className="bg-gray-50 rounded p-3">
                        <div className="text-sm text-gray-500">Experience</div>
                        <div className="text-lg font-semibold">{Math.round(rec.experience_match_score)}%</div>
                        <div className="w-full bg-gray-200 rounded-full h-2 mt-1">
                          <div className="bg-green-600 h-2 rounded-full" style={{ width: rec.experience_match_score + '%' }}></div>
                        </div>
                      </div>
                      <div className="bg-gray-50 rounded p-3">
                        <div className="text-sm text-gray-500">Location</div>
                        <div className="text-lg font-semibold">{Math.round(rec.location_match_score)}%</div>
                        <div className="w-full bg-gray-200 rounded-full h-2 mt-1">
                          <div className="bg-purple-600 h-2 rounded-full" style={{ width: rec.location_match_score + '%' }}></div>
                        </div>
                      </div>
                    </div>

                    <div className="flex flex-wrap gap-4">
                      {rec.matched_skills && rec.matched_skills.length > 0 && (
                        <div className="flex-1">
                          <div className="text-sm text-gray-500 mb-2">Matched Skills</div>
                          <div className="flex flex-wrap gap-2">
                            {rec.matched_skills.map((skill, i) => (
                              <span key={i} className="bg-green-100 text-green-700 px-2 py-1 rounded text-sm">{skill}</span>
                            ))}
                          </div>
                        </div>
                      )}
                      {rec.missing_skills && rec.missing_skills.length > 0 && (
                        <div className="flex-1">
                          <div className="text-sm text-gray-500 mb-2">Skills to Learn</div>
                          <div className="flex flex-wrap gap-2">
                            {rec.missing_skills.map((skill, i) => (
                              <span key={i} className="bg-orange-100 text-orange-700 px-2 py-1 rounded text-sm">{skill}</span>
                            ))}
                          </div>
                        </div>
                      )}
                    </div>

                    <div className="flex gap-3 mt-4 pt-4 border-t">
                      <Link href={'/jobs/' + rec.job.id} className="bg-blue-600 text-white px-4 py-2 rounded-md hover:bg-blue-700 text-sm">
                        View Job
                      </Link>
                      <Link href="/skill-gaps" className="bg-gray-100 text-gray-700 px-4 py-2 rounded-md hover:bg-gray-200 text-sm">
                        Analyze Skill Gaps
                      </Link>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </>
        )}
      </main>
    </div>
  );
}
