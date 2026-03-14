'use client';

import { useState, useEffect, useCallback } from 'react';
import { useRouter, useParams } from 'next/navigation';
import Link from 'next/link';
import api, { ATSConfig, ATSResult, ATSCandidate, ATSExcluded } from '@/lib/api';
import NotificationBell from '@/components/NotificationBell';

// ── Fit badge config ────────────────────────────────────────────────────────
const FIT_STYLES: Record<string, { badge: string; bar: string }> = {
  'Strong Fit': { badge: 'bg-green-100 text-green-800 border border-green-300',  bar: 'bg-green-500' },
  'Good Fit':   { badge: 'bg-blue-100 text-blue-800 border border-blue-300',     bar: 'bg-blue-500'  },
  'Partial Fit':{ badge: 'bg-yellow-100 text-yellow-800 border border-yellow-300', bar: 'bg-yellow-500' },
  'Low Fit':    { badge: 'bg-red-100 text-red-800 border border-red-300',        bar: 'bg-red-500'   },
};

const DEFAULT_CONFIG: ATSConfig = {
  min_match_score: 0,
  require_all_required_skills: false,
  min_experience_years: null,
  exclude_statuses: ['withdrawn', 'rejected'],
};

// ── Score bar ───────────────────────────────────────────────────────────────
function ScoreBar({ value, color }: { value: number; color: string }) {
  return (
    <div className="flex items-center gap-2">
      <div className="flex-1 h-1.5 bg-gray-200 rounded-full overflow-hidden">
        <div className={`h-full rounded-full ${color}`} style={{ width: `${Math.min(value, 100)}%` }} />
      </div>
      <span className="text-xs text-gray-600 w-8 text-right">{value}%</span>
    </div>
  );
}

// ── Main page ───────────────────────────────────────────────────────────────
export default function ATSPage() {
  const router = useRouter();
  const params = useParams();
  const jobId = params.id as string;

  const [job, setJob]           = useState<any>(null);
  const [loading, setLoading]   = useState(true);
  const [running, setRunning]   = useState(false);
  const [error, setError]       = useState('');
  const [result, setResult]     = useState<ATSResult | null>(null);
  const [config, setConfig]     = useState<ATSConfig>(DEFAULT_CONFIG);
  const [showExcluded, setShowExcluded] = useState(false);
  const [expandedId, setExpandedId]     = useState<string | null>(null);
  const [actionMsg, setActionMsg]       = useState<{ id: string; text: string } | null>(null);

  useEffect(() => {
    const token = api.getToken();
    if (!token) { router.push('/login'); return; }
    (async () => {
      try {
        const [userData, jobData] = await Promise.all([api.getMe(), api.getJob(jobId)]);
        if (userData.role !== 'recruiter') { router.push('/dashboard'); return; }
        if (jobData.posted_by_id !== userData.id) {
          setError('You do not have permission to run ATS for this job');
          setLoading(false);
          return;
        }
        setJob(jobData);
      } catch (e: any) {
        setError(e.message || 'Failed to load job');
      } finally {
        setLoading(false);
      }
    })();
  }, [jobId, router]);

  // ── Run ATS ───────────────────────────────────────────────────────────────
  const handleRunATS = useCallback(async () => {
    setRunning(true);
    setError('');
    try {
      const res = await api.runATS(jobId, config);
      setResult(res);
    } catch (e: any) {
      setError(e.message || 'ATS run failed');
    } finally {
      setRunning(false);
    }
  }, [jobId, config]);

  // ── Quick status action ───────────────────────────────────────────────────
  const quickAction = async (applicationId: string, status: string, candidateName: string) => {
    try {
      await api.updateApplication(applicationId, { status });
      setResult(prev => {
        if (!prev) return prev;
        return {
          ...prev,
          candidates: prev.candidates.map(c =>
            c.application_id === applicationId ? { ...c, status } : c
          ),
        };
      });
      setActionMsg({ id: applicationId, text: `${candidateName} moved to ${status}` });
      setTimeout(() => setActionMsg(null), 3000);
    } catch (e: any) {
      alert(e.message || 'Action failed');
    }
  };

  // ── Config helpers ────────────────────────────────────────────────────────
  const toggleExcludeStatus = (status: string) => {
    setConfig(prev => ({
      ...prev,
      exclude_statuses: prev.exclude_statuses.includes(status)
        ? prev.exclude_statuses.filter(s => s !== status)
        : [...prev.exclude_statuses, status],
    }));
  };

  // ── Loading / Error ───────────────────────────────────────────────────────
  if (loading) return (
    <div className="min-h-screen flex items-center justify-center">
      <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600" />
    </div>
  );
  if (error && !result) return (
    <div className="min-h-screen flex items-center justify-center">
      <div className="text-center">
        <p className="text-red-600 mb-4">{error}</p>
        <Link href={`/recruiter/jobs/${jobId}/applicants`} className="text-blue-600 hover:underline">
          ← Back to Applicants
        </Link>
      </div>
    </div>
  );

  return (
    <div className="min-h-screen bg-gray-50">
      {/* ── Header ── */}
      <header className="bg-white shadow-sm sticky top-0 z-10">
        <div className="max-w-7xl mx-auto px-4 py-4 flex justify-between items-start">
          <div>
            <div className="flex items-center gap-2 text-sm text-gray-500 mb-1">
              <Link href="/recruiter/my-jobs" className="hover:text-gray-800">My Jobs</Link>
              <span>/</span>
              <Link href={`/recruiter/jobs/${jobId}/applicants`} className="hover:text-gray-800">
                Applicants
              </Link>
              <span>/</span>
              <span className="text-gray-800 font-medium">ATS Filter</span>
            </div>
            <h1 className="text-2xl font-bold text-gray-900">ATS Filter</h1>
            {job && <p className="text-gray-500 text-sm mt-0.5">{job.title} · {job.company_name}</p>}
          </div>
          <NotificationBell />
        </div>
      </header>

      <main className="max-w-7xl mx-auto px-4 py-6 space-y-6">

        {/* ── Config Panel ── */}
        <div className="bg-white rounded-xl shadow p-6">
          <h2 className="text-lg font-semibold text-gray-900 mb-1">Filter Configuration</h2>
          <p className="text-sm text-gray-500 mb-5">
            Set knock-out rules. Candidates failing any rule are excluded before scoring.
          </p>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            {/* Min match score */}
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Minimum Match Score
                <span className="ml-2 text-blue-600 font-semibold">{config.min_match_score}%</span>
              </label>
              <input
                type="range" min={0} max={90} step={5}
                value={config.min_match_score}
                onChange={e => setConfig(p => ({ ...p, min_match_score: Number(e.target.value) }))}
                className="w-full accent-blue-600"
              />
              <div className="flex justify-between text-xs text-gray-400 mt-1">
                <span>0% (no filter)</span><span>90%</span>
              </div>
              <p className="text-xs text-gray-500 mt-1">
                Candidates with stored match score below this are excluded.
                Set to 0 to skip this filter.
              </p>
            </div>

            {/* Min experience */}
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Minimum Experience (years)
              </label>
              <input
                type="number" min={0} max={30} placeholder="Use job's default"
                value={config.min_experience_years ?? ''}
                onChange={e => setConfig(p => ({
                  ...p,
                  min_experience_years: e.target.value === '' ? null : Number(e.target.value),
                }))}
                className="w-full border rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
              />
              <p className="text-xs text-gray-500 mt-1">
                Leave empty to use the job's experience requirement
                {job?.experience_min_years ? ` (${job.experience_min_years} yrs)` : ' (none set)'}.
              </p>
            </div>

            {/* Require all required skills */}
            <div className="flex items-start gap-3">
              <div className="mt-0.5">
                <input
                  type="checkbox" id="req-skills"
                  checked={config.require_all_required_skills}
                  onChange={e => setConfig(p => ({ ...p, require_all_required_skills: e.target.checked }))}
                  className="w-4 h-4 rounded accent-blue-600"
                />
              </div>
              <div>
                <label htmlFor="req-skills" className="text-sm font-medium text-gray-700 cursor-pointer">
                  Require ALL required skills
                </label>
                <p className="text-xs text-gray-500 mt-0.5">
                  Exclude candidates missing even one skill marked as "required" on this job.
                </p>
              </div>
            </div>

            {/* Excluded statuses */}
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Skip applicants in these stages
              </label>
              <div className="flex flex-wrap gap-2">
                {['withdrawn', 'rejected', 'offer_accepted', 'offer_declined'].map(s => (
                  <button
                    key={s}
                    onClick={() => toggleExcludeStatus(s)}
                    className={`px-3 py-1 rounded-full text-xs border font-medium transition ${
                      config.exclude_statuses.includes(s)
                        ? 'bg-gray-700 text-white border-gray-700'
                        : 'bg-white text-gray-600 border-gray-300 hover:border-gray-500'
                    }`}
                  >
                    {s.replace(/_/g, ' ')}
                  </button>
                ))}
              </div>
            </div>
          </div>

          <div className="mt-6 flex items-center gap-4">
            <button
              onClick={handleRunATS}
              disabled={running}
              className="px-6 py-2.5 bg-blue-600 text-white font-semibold rounded-lg hover:bg-blue-700 disabled:opacity-50 flex items-center gap-2 transition"
            >
              {running ? (
                <>
                  <svg className="animate-spin h-4 w-4" fill="none" viewBox="0 0 24 24">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"/>
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8z"/>
                  </svg>
                  Running ATS...
                </>
              ) : (
                <>
                  <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 4a1 1 0 011-1h16a1 1 0 011 1v2a1 1 0 01-.293.707L13 13.414V19a1 1 0 01-.553.894l-4 2A1 1 0 017 21v-7.586L3.293 6.707A1 1 0 013 6V4z"/>
                  </svg>
                  Run ATS Filter
                </>
              )}
            </button>
            {result && (
              <span className="text-sm text-gray-500">
                Last run: {result.filtered_count} of {result.total_applicants} candidates passed
              </span>
            )}
          </div>
        </div>

        {/* ── Results ── */}
        {result && (
          <>
            {/* Summary bar */}
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              <div className="bg-white rounded-xl shadow p-4 text-center">
                <p className="text-3xl font-bold text-gray-900">{result.total_applicants}</p>
                <p className="text-sm text-gray-500 mt-1">Total Applicants</p>
              </div>
              <div className="bg-white rounded-xl shadow p-4 text-center">
                <p className="text-3xl font-bold text-blue-600">{result.filtered_count}</p>
                <p className="text-sm text-gray-500 mt-1">Passed Filter</p>
              </div>
              <div className="bg-white rounded-xl shadow p-4 text-center">
                <p className="text-3xl font-bold text-red-500">{result.excluded_count}</p>
                <p className="text-sm text-gray-500 mt-1">Excluded</p>
              </div>
              <div className="bg-white rounded-xl shadow p-4">
                <p className="text-xs font-medium text-gray-500 mb-2">Fit Distribution</p>
                {Object.entries(result.fit_summary).map(([label, count]) => (
                  count > 0 && (
                    <div key={label} className="flex items-center justify-between text-xs mb-1">
                      <span className={`px-2 py-0.5 rounded-full font-medium ${FIT_STYLES[label]?.badge || ''}`}>
                        {label}
                      </span>
                      <span className="font-bold text-gray-700">{count}</span>
                    </div>
                  )
                ))}
              </div>
            </div>

            {/* Action toast */}
            {actionMsg && (
              <div className="fixed bottom-6 right-6 bg-gray-900 text-white px-4 py-2.5 rounded-lg shadow-lg text-sm z-50">
                {actionMsg.text}
              </div>
            )}

            {/* Ranked candidates */}
            <div className="bg-white rounded-xl shadow overflow-hidden">
              <div className="px-6 py-4 border-b flex items-center justify-between">
                <h2 className="text-lg font-semibold text-gray-900">
                  Qualified Candidates
                  <span className="ml-2 text-sm font-normal text-gray-500">
                    ({result.filtered_count} ranked by ATS score)
                  </span>
                </h2>
                <Link
                  href={`/recruiter/jobs/${jobId}/applicants`}
                  className="text-sm text-blue-600 hover:underline"
                >
                  Full Pipeline View →
                </Link>
              </div>

              {result.candidates.length === 0 ? (
                <div className="p-12 text-center text-gray-500">
                  <svg className="w-12 h-12 mx-auto mb-3 text-gray-300" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9.172 16.172a4 4 0 015.656 0M9 10h.01M15 10h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"/>
                  </svg>
                  <p className="font-medium">No candidates passed the filter</p>
                  <p className="text-sm mt-1">Try lowering the thresholds and running ATS again.</p>
                </div>
              ) : (
                <div className="divide-y">
                  {result.candidates.map((c: ATSCandidate) => {
                    const fit   = FIT_STYLES[c.fit_label];
                    const isExp = expandedId === c.application_id;
                    return (
                      <div key={c.application_id} className="p-5 hover:bg-gray-50 transition">
                        <div className="flex items-start gap-4">
                          {/* Rank badge */}
                          <div className="flex-shrink-0 w-10 h-10 rounded-full bg-gray-100 flex items-center justify-center">
                            <span className="text-sm font-bold text-gray-600">#{c.rank}</span>
                          </div>

                          {/* Candidate info */}
                          <div className="flex-1 min-w-0">
                            <div className="flex items-center gap-2 flex-wrap mb-1">
                              <h3 className="text-base font-semibold text-gray-900">{c.name}</h3>
                              <span className={`text-xs px-2.5 py-0.5 rounded-full font-semibold ${fit.badge}`}>
                                {c.fit_label}
                              </span>
                              <span className="text-xs px-2.5 py-0.5 rounded-full bg-gray-100 text-gray-700 font-medium">
                                {c.status.replace(/_/g, ' ')}
                              </span>
                              {c.is_verified && (
                                <span className="text-xs px-2 py-0.5 rounded-full bg-teal-100 text-teal-700 font-medium">
                                  ✓ Verified
                                </span>
                              )}
                            </div>
                            <p className="text-sm text-gray-500">{c.email}</p>
                            <div className="flex flex-wrap gap-3 text-xs text-gray-400 mt-1">
                              {c.headline && <span>💼 {c.headline}</span>}
                              {c.years_experience != null && <span>📅 {c.years_experience} yrs exp</span>}
                              {c.has_resume && <span>📄 Resume uploaded</span>}
                            </div>

                            {/* Score bars */}
                            <div className="mt-3 grid grid-cols-1 sm:grid-cols-3 gap-2">
                              <div>
                                <div className="flex justify-between text-xs text-gray-500 mb-1">
                                  <span>Skill Match</span>
                                </div>
                                <ScoreBar value={c.skill_score} color={fit.bar} />
                              </div>
                              <div>
                                <div className="flex justify-between text-xs text-gray-500 mb-1">
                                  <span>Experience</span>
                                </div>
                                <ScoreBar value={c.experience_score} color={fit.bar} />
                              </div>
                              <div>
                                <div className="flex justify-between text-xs text-gray-500 mb-1">
                                  <span>Profile</span>
                                </div>
                                <ScoreBar value={c.completeness_score} color={fit.bar} />
                              </div>
                            </div>

                            {/* Expand toggle */}
                            {(c.matched_skills.length > 0 || c.missing_skills.length > 0) && (
                              <button
                                onClick={() => setExpandedId(isExp ? null : c.application_id)}
                                className="mt-2 text-xs text-blue-600 hover:underline"
                              >
                                {isExp ? '▲ Hide skill details' : '▼ Show skill details'}
                              </button>
                            )}

                            {isExp && (
                              <div className="mt-3 grid grid-cols-1 sm:grid-cols-2 gap-3">
                                {c.matched_skills.length > 0 && (
                                  <div>
                                    <p className="text-xs font-semibold text-green-700 mb-1">
                                      Matched Skills ({c.matched_skills.length})
                                    </p>
                                    <div className="flex flex-wrap gap-1">
                                      {c.matched_skills.map(s => (
                                        <span key={s} className="text-xs px-2 py-0.5 bg-green-100 text-green-800 rounded-full">
                                          {s}
                                        </span>
                                      ))}
                                    </div>
                                  </div>
                                )}
                                {c.missing_skills.length > 0 && (
                                  <div>
                                    <p className="text-xs font-semibold text-red-700 mb-1">
                                      Missing Required Skills ({c.missing_skills.length})
                                    </p>
                                    <div className="flex flex-wrap gap-1">
                                      {c.missing_skills.map(s => (
                                        <span key={s} className="text-xs px-2 py-0.5 bg-red-100 text-red-800 rounded-full">
                                          {s}
                                        </span>
                                      ))}
                                    </div>
                                  </div>
                                )}
                              </div>
                            )}
                          </div>

                          {/* ATS score + actions */}
                          <div className="flex-shrink-0 text-center min-w-[80px]">
                            <div className={`text-2xl font-bold ${
                              c.fit_color === 'green' ? 'text-green-600' :
                              c.fit_color === 'blue'  ? 'text-blue-600'  :
                              c.fit_color === 'yellow'? 'text-yellow-600':
                              'text-red-600'
                            }`}>
                              {c.ats_score}
                            </div>
                            <div className="text-xs text-gray-400">ATS score</div>

                            <div className="mt-3 flex flex-col gap-1.5">
                              {!['shortlisted', 'interview_scheduled', 'interviewed', 'offer_extended', 'offer_accepted'].includes(c.status) && (
                                <button
                                  onClick={() => quickAction(c.application_id, 'shortlisted', c.name)}
                                  className="px-3 py-1.5 bg-green-600 text-white rounded-lg text-xs font-medium hover:bg-green-700 transition"
                                >
                                  Shortlist
                                </button>
                              )}
                              {c.status === 'shortlisted' && (
                                <button
                                  onClick={() => quickAction(c.application_id, 'interview_scheduled', c.name)}
                                  className="px-3 py-1.5 bg-purple-600 text-white rounded-lg text-xs font-medium hover:bg-purple-700 transition"
                                >
                                  Schedule
                                </button>
                              )}
                              {!['rejected', 'withdrawn', 'offer_accepted'].includes(c.status) && (
                                <button
                                  onClick={() => quickAction(c.application_id, 'rejected', c.name)}
                                  className="px-3 py-1.5 bg-red-50 text-red-600 border border-red-200 rounded-lg text-xs font-medium hover:bg-red-100 transition"
                                >
                                  Reject
                                </button>
                              )}
                              <Link
                                href={`/profile/${c.user_id}`}
                                className="px-3 py-1.5 bg-gray-100 text-gray-700 rounded-lg text-xs font-medium hover:bg-gray-200 transition text-center"
                              >
                                Profile
                              </Link>
                            </div>
                          </div>
                        </div>
                      </div>
                    );
                  })}
                </div>
              )}
            </div>

            {/* Excluded candidates */}
            {result.excluded.length > 0 && (
              <div className="bg-white rounded-xl shadow overflow-hidden">
                <button
                  onClick={() => setShowExcluded(p => !p)}
                  className="w-full px-6 py-4 flex items-center justify-between hover:bg-gray-50 transition"
                >
                  <span className="text-base font-semibold text-gray-700">
                    Excluded Candidates
                    <span className="ml-2 text-sm font-normal text-red-500">
                      ({result.excluded.length} did not pass filter)
                    </span>
                  </span>
                  <svg
                    className={`w-5 h-5 text-gray-400 transition-transform ${showExcluded ? 'rotate-180' : ''}`}
                    fill="none" stroke="currentColor" viewBox="0 0 24 24"
                  >
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7"/>
                  </svg>
                </button>

                {showExcluded && (
                  <div className="divide-y border-t">
                    {result.excluded.map((e: ATSExcluded) => (
                      <div key={e.application_id} className="px-6 py-4 flex items-center gap-4">
                        <div className="flex-1 min-w-0">
                          <div className="flex items-center gap-2 flex-wrap">
                            <span className="font-medium text-gray-700 text-sm">{e.name}</span>
                            <span className="text-xs text-gray-400">{e.email}</span>
                            {e.years_experience != null && (
                              <span className="text-xs text-gray-400">· {e.years_experience} yrs</span>
                            )}
                          </div>
                          <div className="mt-1 flex items-center gap-2">
                            <svg className="w-3.5 h-3.5 text-red-400 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12"/>
                            </svg>
                            <span className="text-xs text-red-600">{e.exclusion_reason}</span>
                          </div>
                        </div>
                        <div className="text-right flex-shrink-0">
                          {e.match_score_at_apply != null && (
                            <span className="text-xs text-gray-400">{e.match_score_at_apply}% stored score</span>
                          )}
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            )}
          </>
        )}

        {/* Empty state before first run */}
        {!result && !running && (
          <div className="bg-white rounded-xl shadow p-12 text-center">
            <svg className="w-16 h-16 mx-auto mb-4 text-gray-200" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5}
                d="M3 4a1 1 0 011-1h16a1 1 0 011 1v2a1 1 0 01-.293.707L13 13.414V19a1 1 0 01-.553.894l-4 2A1 1 0 017 21v-7.586L3.293 6.707A1 1 0 013 6V4z"/>
            </svg>
            <h3 className="text-lg font-semibold text-gray-700 mb-2">Ready to filter candidates</h3>
            <p className="text-sm text-gray-400 max-w-md mx-auto">
              Configure your filter criteria above, then click <strong>Run ATS Filter</strong> to see
              which applicants qualify and how they rank.
            </p>
          </div>
        )}

      </main>
    </div>
  );
}
