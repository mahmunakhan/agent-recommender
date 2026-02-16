'use client';

import { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import api from '@/lib/api';
import NotificationBell from '@/components/NotificationBell';

interface SkillGap {
  id: string;
  skill_name: string;
  skill_type: string;
  gap_type: string;
  current_level: number;
  target_level: number;
  priority_score: number;
  frequency_in_jobs: number;
  analysis_text?: string;
}

export default function SkillGapsPage() {
  const router = useRouter();
  const [skillGaps, setSkillGaps] = useState<SkillGap[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const token = api.getToken();
    if (!token) {
      router.push('/login');
      return;
    }
    loadSkillGaps();
  }, [router]);

  const loadSkillGaps = async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await api.getSkillGaps();
      setSkillGaps(data.skill_gaps || []);
    } catch (err: any) {
      setError(err.message || 'Failed to load skill gaps');
    } finally {
      setLoading(false);
    }
  };

  const getPriorityColor = (score: number) => {
    if (score >= 80) return 'bg-red-100 text-red-700 border-red-200';
    if (score >= 50) return 'bg-yellow-100 text-yellow-700 border-yellow-200';
    return 'bg-blue-100 text-blue-700 border-blue-200';
  };

  const getPriorityLabel = (score: number) => {
    if (score >= 80) return 'High Priority';
    if (score >= 50) return 'Medium Priority';
    return 'Low Priority';
  };

  const getSkillTypeIcon = (type: string) => {
    switch (type?.toLowerCase()) {
      case 'technical': return '💻';
      case 'soft': return '🤝';
      case 'domain': return '🏢';
      case 'tool': return '🔧';
      default: return '📚';
    }
  };

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-50">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto"></div>
          <p className="mt-4 text-gray-600">Analyzing your skill gaps...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50">
      <header className="bg-white shadow-sm">
        <div className="max-w-6xl mx-auto px-4 py-4 flex justify-between items-center">
          <div className="flex items-center gap-4">
            <Link href="/recommendations" className="text-gray-600 hover:text-gray-900">Back</Link>
            <h1 className="text-2xl font-bold text-gray-900">Skill Gap Analysis</h1>
          </div>
          <div className="flex items-center gap-4">
            <NotificationBell />
            <button onClick={loadSkillGaps} className="bg-blue-600 text-white px-4 py-2 rounded-md hover:bg-blue-700">
              Refresh
            </button>
          </div>
        </div>
      </header>

      <main className="max-w-6xl mx-auto px-4 py-8">
        {error ? (
          <div className="bg-red-50 border border-red-200 rounded-lg p-6 text-center">
            <p className="text-red-600 mb-4">{error}</p>
            <Link href="/recommendations" className="text-blue-600 hover:underline">Get Recommendations First</Link>
          </div>
        ) : skillGaps.length === 0 ? (
          <div className="bg-white rounded-lg shadow p-12 text-center">
            <div className="text-6xl mb-4">🎯</div>
            <h3 className="text-xl font-semibold text-gray-900 mb-2">No skill gaps found</h3>
            <p className="text-gray-600 mb-4">Get job recommendations first to identify skill gaps.</p>
            <Link href="/recommendations" className="inline-block bg-blue-600 text-white px-6 py-2 rounded-md hover:bg-blue-700">
              Get Recommendations
            </Link>
          </div>
        ) : (
          <>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6">
              <div className="bg-white rounded-lg shadow p-4 text-center">
                <div className="text-3xl font-bold text-blue-600">{skillGaps.length}</div>
                <div className="text-gray-500 text-sm">Total Skill Gaps</div>
              </div>
              <div className="bg-white rounded-lg shadow p-4 text-center">
                <div className="text-3xl font-bold text-red-600">
                  {skillGaps.filter(g => g.priority_score >= 80).length}
                </div>
                <div className="text-gray-500 text-sm">High Priority</div>
              </div>
              <div className="bg-white rounded-lg shadow p-4 text-center">
                <div className="text-3xl font-bold text-yellow-600">
                  {skillGaps.filter(g => g.priority_score >= 50 && g.priority_score < 80).length}
                </div>
                <div className="text-gray-500 text-sm">Medium Priority</div>
              </div>
            </div>

            <div className="bg-white rounded-lg shadow mb-6 p-6">
              <h2 className="text-lg font-semibold text-gray-900 mb-4">How to Use This Analysis</h2>
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4 text-sm">
                <div className="flex items-start gap-3">
                  <span className="text-2xl">1️⃣</span>
                  <div>
                    <p className="font-medium">Review Priority</p>
                    <p className="text-gray-600">High priority skills appear most in your target jobs</p>
                  </div>
                </div>
                <div className="flex items-start gap-3">
                  <span className="text-2xl">2️⃣</span>
                  <div>
                    <p className="font-medium">Check Frequency</p>
                    <p className="text-gray-600">See how many jobs require each skill</p>
                  </div>
                </div>
                <div className="flex items-start gap-3">
                  <span className="text-2xl">3️⃣</span>
                  <div>
                    <p className="font-medium">Learn & Grow</p>
                    <p className="text-gray-600">Focus on high-impact skills first</p>
                  </div>
                </div>
              </div>
            </div>

            <div className="space-y-4">
              {skillGaps.map((gap) => (
                <div key={gap.id} className={'bg-white rounded-lg shadow border-l-4 p-6 ' + getPriorityColor(gap.priority_score).split(' ')[2]}>
                  <div className="flex justify-between items-start mb-4">
                    <div className="flex items-center gap-3">
                      <span className="text-2xl">{getSkillTypeIcon(gap.skill_type)}</span>
                      <div>
                        <h3 className="text-lg font-semibold text-gray-900">{gap.skill_name}</h3>
                        <p className="text-sm text-gray-500">{gap.skill_type} Skill</p>
                      </div>
                    </div>
                    <span className={'px-3 py-1 rounded-full text-sm font-medium border ' + getPriorityColor(gap.priority_score)}>
                      {getPriorityLabel(gap.priority_score)}
                    </span>
                  </div>

                  <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-4">
                    <div className="bg-gray-50 rounded p-3">
                      <div className="text-sm text-gray-500">Current Level</div>
                      <div className="text-lg font-semibold">{gap.current_level || 0}/5</div>
                    </div>
                    <div className="bg-gray-50 rounded p-3">
                      <div className="text-sm text-gray-500">Target Level</div>
                      <div className="text-lg font-semibold">{gap.target_level || 3}/5</div>
                    </div>
                    <div className="bg-gray-50 rounded p-3">
                      <div className="text-sm text-gray-500">Priority Score</div>
                      <div className="text-lg font-semibold">{Math.round(gap.priority_score)}%</div>
                    </div>
                    <div className="bg-gray-50 rounded p-3">
                      <div className="text-sm text-gray-500">Required In</div>
                      <div className="text-lg font-semibold">{gap.frequency_in_jobs} jobs</div>
                    </div>
                  </div>

                  {gap.analysis_text && (
                    <p className="text-gray-600 text-sm mb-4">{gap.analysis_text}</p>
                  )}

                  <div className="flex gap-3">
                    <Link href="/learning-paths" className="bg-blue-600 text-white px-4 py-2 rounded-md hover:bg-blue-700 text-sm">
                      Find Learning Resources
                    </Link>
                  </div>
                </div>
              ))}
            </div>
          </>
        )}
      </main>
    </div>
  );
}
