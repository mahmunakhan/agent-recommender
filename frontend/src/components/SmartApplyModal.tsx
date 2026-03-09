'use client';

import { useState, useEffect } from 'react';
import Link from 'next/link';
import api from '@/lib/api';

/**
 * SmartApplyModal — Pre-check + warnings + auto-fill + AI cover letter
 *
 * Usage (in recommendations page):
 *   import SmartApplyModal from '@/components/SmartApplyModal';
 *
 *   const [applyJobId, setApplyJobId] = useState<string | null>(null);
 *
 *   // In your job card:
 *   <button onClick={() => setApplyJobId(job.id)}>Apply Now</button>
 *
 *   // At bottom of component:
 *   {applyJobId && (
 *     <SmartApplyModal jobId={applyJobId} onClose={() => setApplyJobId(null)} onApplied={() => load()} />
 *   )}
 */

interface Props {
  jobId: string;
  onClose: () => void;
  onApplied: () => void;
}

export default function SmartApplyModal({ jobId, onClose, onApplied }: Props) {
  const [check, setCheck] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [applying, setApplying] = useState(false);
  const [coverLetter, setCoverLetter] = useState('');
  const [generatingCL, setGeneratingCL] = useState(false);
  const [step, setStep] = useState<'loading' | 'review' | 'already' | 'done'>('loading');
  const [result, setResult] = useState<any>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    loadCheck();
  }, [jobId]);

  const loadCheck = async () => {
    setLoading(true);
    try {
      const data = await api.preCheckApplication(jobId);
      setCheck(data);
      setStep(data.can_apply ? 'review' : 'already');
    } catch (err: any) {
      setError(err.message || 'Failed to check application');
    } finally {
      setLoading(false);
    }
  };

  const handleGenerateCL = async () => {
    setGeneratingCL(true);
    try {
      const data = await api.generateCoverLetter(jobId);
      setCoverLetter(data.cover_letter || '');
    } catch (err: any) {
      alert('Failed to generate: ' + (err.message || 'Try again'));
    } finally {
      setGeneratingCL(false);
    }
  };

  const handleApply = async () => {
    setApplying(true);
    setError(null);
    try {
      const data = await api.applyToJob(jobId, coverLetter || undefined, 'recommendation');
      setResult(data);
      setStep('done');
      onApplied();
    } catch (err: any) {
      setError(err.message || 'Application failed');
    } finally {
      setApplying(false);
    }
  };

  const scoreColor = (s: number) => s >= 70 ? 'text-green-600' : s >= 50 ? 'text-yellow-600' : 'text-red-500';
  const scoreBg = (s: number) => s >= 70 ? 'bg-green-500' : s >= 50 ? 'bg-yellow-500' : 'bg-red-500';
  const highWarnings = check?.warnings?.filter((w: any) => w.severity === 'high').length || 0;

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4" onClick={onClose}>
      <div className="bg-white rounded-xl shadow-2xl max-w-2xl w-full max-h-[90vh] overflow-y-auto" onClick={e => e.stopPropagation()}>

        {/* ─── Header ─── */}
        <div className="flex justify-between items-center p-5 border-b bg-gradient-to-r from-blue-50 to-indigo-50">
          <div>
            <h2 className="text-lg font-bold text-gray-900">
              {step === 'done' ? '🎉 Application Sent!' : '📨 Smart Apply'}
            </h2>
            {check?.job && step !== 'done' && (
              <p className="text-sm text-gray-600">{check.job.title} at {check.job.company_name}</p>
            )}
          </div>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-700 text-2xl">&times;</button>
        </div>

        <div className="p-5">
          {/* Loading */}
          {loading && (
            <div className="text-center py-8">
              <div className="animate-spin rounded-full h-10 w-10 border-b-2 border-blue-600 mx-auto" />
              <p className="mt-3 text-gray-500 text-sm">Checking your profile match...</p>
            </div>
          )}

          {/* Error */}
          {error && <div className="bg-red-50 border border-red-200 rounded-lg p-3 mb-4 text-red-600 text-sm">{error}</div>}

          {/* Already Applied */}
          {step === 'already' && check && (
            <div className="text-center py-6">
              <div className="text-5xl mb-3">✅</div>
              <h3 className="text-lg font-semibold text-gray-900 mb-1">{check.message || 'Already applied'}</h3>
              <p className="text-gray-500 text-sm mb-4">Status: <span className="font-medium">{check.status}</span></p>
              <button onClick={onClose} className="bg-blue-600 text-white px-6 py-2 rounded-md hover:bg-blue-700 text-sm">Close</button>
            </div>
          )}

          {/* ─── Review Step ─── */}
          {step === 'review' && check && !loading && (
            <>
              {/* Match Score Bar */}
              {check.match && (
                <div className="mb-5">
                  <div className="flex items-center justify-between mb-2">
                    <span className="text-sm font-medium text-gray-700">Skill Match</span>
                    <span className={`text-2xl font-bold ${scoreColor(check.match.score)}`}>{Math.round(check.match.score)}%</span>
                  </div>
                  <div className="w-full bg-gray-200 rounded-full h-2.5">
                    <div className={`h-2.5 rounded-full ${scoreBg(check.match.score)}`} style={{ width: `${Math.min(100, check.match.score)}%` }} />
                  </div>
                  {check.match.overall_score && (
                    <p className="text-xs text-gray-500 mt-1">Overall recommendation: {Math.round(check.match.overall_score)}%</p>
                  )}
                </div>
              )}

              {/* Warnings */}
              {check.warnings?.length > 0 && (
                <div className="mb-5 space-y-2">
                  {check.warnings.map((w: any, i: number) => (
                    <div key={i} className={`rounded-lg p-3 text-sm flex items-start gap-2 ${
                      w.severity === 'high' ? 'bg-red-50 border border-red-200 text-red-700' : 'bg-yellow-50 border border-yellow-200 text-yellow-700'
                    }`}>
                      <span>{w.severity === 'high' ? '⚠️' : '💡'}</span>
                      <span>{w.message}</span>
                    </div>
                  ))}
                </div>
              )}

              {/* Skills: Matched vs Missing */}
              {check.match && (
                <div className="grid grid-cols-2 gap-3 mb-5">
                  <div className="bg-green-50 rounded-lg p-3">
                    <h4 className="text-xs font-semibold text-green-700 mb-2">Matching ({check.match.matched_skills?.length || 0})</h4>
                    <div className="flex flex-wrap gap-1">
                      {check.match.matched_skills?.slice(0, 8).map((s: string) => (
                        <span key={s} className="bg-green-100 text-green-700 px-2 py-0.5 rounded text-xs">{s}</span>
                      ))}
                      {(check.match.matched_skills?.length || 0) > 8 && <span className="text-green-600 text-xs">+{check.match.matched_skills.length - 8}</span>}
                    </div>
                  </div>
                  <div className="bg-red-50 rounded-lg p-3">
                    <h4 className="text-xs font-semibold text-red-700 mb-2">Missing ({check.match.missing_skills?.length || 0})</h4>
                    <div className="flex flex-wrap gap-1">
                      {check.match.missing_skills?.slice(0, 6).map((s: string) => (
                        <span key={s} className="bg-red-100 text-red-700 px-2 py-0.5 rounded text-xs">{s}</span>
                      ))}
                      {(check.match.missing_skills?.length || 0) > 6 && <span className="text-red-600 text-xs">+{check.match.missing_skills.length - 6}</span>}
                    </div>
                  </div>
                </div>
              )}

              {/* Auto-attached Profile */}
              {check.profile && (
                <div className="bg-blue-50 rounded-lg p-4 mb-5">
                  <h4 className="text-sm font-semibold text-blue-800 mb-2">Your Profile (auto-attached)</h4>
                  <div className="grid grid-cols-2 gap-x-4 gap-y-1 text-xs text-blue-700">
                    <div><b>Name:</b> {check.profile.name}</div>
                    <div><b>Email:</b> {check.profile.email}</div>
                    <div><b>Role:</b> {check.profile.headline || '—'}</div>
                    <div><b>Exp:</b> {check.profile.years_experience || 0} years</div>
                    <div><b>Location:</b> {check.profile.location || '—'}</div>
                    <div><b>Resume:</b> {check.profile.has_resume ? '✅ Attached' : '❌ Missing'}</div>
                  </div>
                  {check.profile.skills?.length > 0 && (
                    <div className="mt-2 flex flex-wrap gap-1">
                      {check.profile.skills.slice(0, 10).map((s: string) => (
                        <span key={s} className="bg-blue-100 text-blue-700 px-2 py-0.5 rounded text-xs">{s}</span>
                      ))}
                      {check.profile.skills.length > 10 && <span className="text-blue-600 text-xs">+{check.profile.skills.length - 10}</span>}
                    </div>
                  )}
                </div>
              )}

              {/* Cover Letter */}
              <div className="mb-5">
                <div className="flex justify-between items-center mb-2">
                  <label className="text-sm font-medium text-gray-700">Cover Letter <span className="text-gray-400 font-normal">(optional)</span></label>
                  <button onClick={handleGenerateCL} disabled={generatingCL}
                    className="text-sm text-blue-600 hover:text-blue-800 disabled:text-gray-400">
                    {generatingCL ? '⏳ Generating...' : '🤖 AI Generate'}
                  </button>
                </div>
                <textarea value={coverLetter} onChange={e => setCoverLetter(e.target.value)}
                  placeholder="Write a cover letter or use AI to generate one..."
                  className="w-full border rounded-lg p-3 text-sm h-28 resize-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500" />
              </div>

              {/* Apply */}
              <div className="flex gap-3">
                <button onClick={handleApply} disabled={applying}
                  className="flex-1 bg-blue-600 text-white py-3 rounded-lg font-medium hover:bg-blue-700 disabled:bg-gray-400 text-sm">
                  {applying ? 'Submitting...' : highWarnings > 0 ? '⚠️ Apply Anyway' : '🚀 Submit Application'}
                </button>
                <button onClick={onClose} className="px-6 py-3 border rounded-lg text-gray-600 hover:bg-gray-50 text-sm">Cancel</button>
              </div>
              {highWarnings > 0 && (
                <p className="text-xs text-gray-400 text-center mt-2">You can still apply despite warnings.</p>
              )}
            </>
          )}

          {/* ─── Done ─── */}
          {step === 'done' && result && (
            <div className="text-center py-6">
              <div className="text-6xl mb-3">🎉</div>
              <h3 className="text-xl font-semibold text-gray-900 mb-1">Application Submitted!</h3>
              <p className="text-gray-600 text-sm mb-1">{result.job_title} at {result.company_name}</p>
              {result.match_score_at_apply != null && (
                <p className={`text-lg font-bold ${scoreColor(result.match_score_at_apply)} mb-4`}>
                  {Math.round(result.match_score_at_apply)}% Match
                </p>
              )}
              <div className="flex justify-center gap-3">
                <Link href="/applications" className="bg-blue-600 text-white px-5 py-2 rounded-md hover:bg-blue-700 text-sm">View Applications</Link>
                <button onClick={onClose} className="border px-5 py-2 rounded-md text-gray-600 hover:bg-gray-50 text-sm">Close</button>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
