'use client';

import { useState, useEffect, useCallback } from 'react';
import { useRouter, useParams } from 'next/navigation';
import Link from 'next/link';
import api, { Application } from '@/lib/api';
import NotificationBell from '@/components/NotificationBell';

/* ─── Pipeline stage config ─── */
const STAGES = [
  { key: 'applied',             label: 'Applied',       icon: '📨', color: 'border-blue-400',   bg: 'bg-blue-50',    badge: 'bg-blue-100 text-blue-700' },
  { key: 'screening',           label: 'Screening',     icon: '🔍', color: 'border-yellow-400', bg: 'bg-yellow-50',  badge: 'bg-yellow-100 text-yellow-700' },
  { key: 'shortlisted',         label: 'Shortlisted',   icon: '⭐', color: 'border-green-400',  bg: 'bg-green-50',   badge: 'bg-green-100 text-green-700' },
  { key: 'interview_scheduled', label: 'Interview',     icon: '📅', color: 'border-purple-400', bg: 'bg-purple-50',  badge: 'bg-purple-100 text-purple-700' },
  { key: 'interviewed',         label: 'Interviewed',   icon: '💬', color: 'border-indigo-400', bg: 'bg-indigo-50',  badge: 'bg-indigo-100 text-indigo-700' },
  { key: 'offer_extended',      label: 'Offer',         icon: '🎉', color: 'border-emerald-400',bg: 'bg-emerald-50', badge: 'bg-emerald-100 text-emerald-700' },
  { key: 'offer_accepted',      label: 'Accepted',      icon: '✅', color: 'border-green-500',  bg: 'bg-green-50',   badge: 'bg-green-200 text-green-800' },
  { key: 'rejected',            label: 'Rejected',      icon: '🚫', color: 'border-red-400',    bg: 'bg-red-50',     badge: 'bg-red-100 text-red-700' },
  { key: 'withdrawn',           label: 'Withdrawn',     icon: '↩️', color: 'border-gray-300',   bg: 'bg-gray-50',    badge: 'bg-gray-100 text-gray-600' },
];

const getStage = (status: string) => STAGES.find(s => s.key === status) || STAGES[0];

const VALID_NEXT: Record<string, string[]> = {
  applied:             ['screening', 'shortlisted', 'rejected'],
  screening:           ['shortlisted', 'rejected'],
  shortlisted:         ['interview_scheduled', 'rejected'],
  interview_scheduled: ['interviewed', 'rejected'],
  interviewed:         ['offer_extended', 'rejected'],
  offer_extended:      ['offer_accepted', 'offer_declined', 'rejected'],
};

export default function ViewApplicantsPage() {
  const router = useRouter();
  const params = useParams();
  const jobId = params.id as string;

  const [job, setJob] = useState<any>(null);
  const [applications, setApplications] = useState<Application[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [view, setView] = useState<'pipeline' | 'list'>('list');
  const [statusFilter, setStatusFilter] = useState('all');
  const [sortBy, setSortBy] = useState<'date' | 'score'>('score');
  const [selectedApp, setSelectedApp] = useState<Application | null>(null);
  const [updating, setUpdating] = useState(false);
  const [newStatus, setNewStatus] = useState('');
  const [recruiterNotes, setRecruiterNotes] = useState('');
  const [rejectionReason, setRejectionReason] = useState('');
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  const [bulkAction, setBulkAction] = useState('');
  const [bulkUpdating, setBulkUpdating] = useState(false);

  useEffect(() => {
    const token = api.getToken();
    if (!token) { router.push('/login'); return; }
    loadData();
  }, [router, jobId]);

  const loadData = useCallback(async () => {
    try {
      const [userData, jobData] = await Promise.all([api.getMe(), api.getJob(jobId)]);
      if (userData.role !== 'recruiter') { router.push('/dashboard'); return; }
      if (jobData.posted_by_id !== userData.id) {
        setError('You do not have permission to view applicants for this job');
        setLoading(false);
        return;
      }
      setJob(jobData);
      const apps = await api.getJobApplications(jobId);
      setApplications(apps.applications || []);
    } catch (err: any) {
      setError(err.message || 'Failed to load applicants');
    } finally {
      setLoading(false);
    }
  }, [jobId, router]);

  /* ─── Status update ─── */
  const handleUpdateStatus = async () => {
    if (!selectedApp || !newStatus) return;
    setUpdating(true);
    try {
      const updateData: any = { status: newStatus };
      if (recruiterNotes) updateData.recruiter_notes = recruiterNotes;
      if (newStatus === 'rejected' && rejectionReason) updateData.rejection_reason = rejectionReason;

      await api.updateApplication(selectedApp.id, updateData);
      setApplications(prev => prev.map(a =>
        a.id === selectedApp.id ? { ...a, status: newStatus, recruiter_notes: recruiterNotes, rejection_reason: rejectionReason || a.rejection_reason } : a
      ));
      setSelectedApp(null);
      setNewStatus('');
      setRecruiterNotes('');
      setRejectionReason('');
    } catch (err: any) {
      alert(err.message || 'Failed to update');
    } finally {
      setUpdating(false);
    }
  };

  /* ─── Quick status change (no modal) ─── */
  const quickStatusChange = async (appId: string, status: string) => {
    try {
      await api.updateApplication(appId, { status });
      setApplications(prev => prev.map(a => a.id === appId ? { ...a, status } : a));
    } catch (err: any) {
      alert(err.message || 'Failed');
    }
  };

  /* ─── Bulk actions ─── */
  const handleBulkAction = async () => {
    if (!bulkAction || selectedIds.size === 0) return;
    setBulkUpdating(true);
    try {
      const ids = Array.from(selectedIds);
      for (const id of ids) {
        await api.updateApplication(id, { status: bulkAction });
      }
      setApplications(prev => prev.map(a => selectedIds.has(a.id) ? { ...a, status: bulkAction } : a));
      setSelectedIds(new Set());
      setBulkAction('');
    } catch (err: any) {
      alert(err.message || 'Bulk update failed');
    } finally {
      setBulkUpdating(false);
    }
  };

  const toggleSelect = (id: string) => {
    setSelectedIds(prev => {
      const next = new Set(prev);
      next.has(id) ? next.delete(id) : next.add(id);
      return next;
    });
  };

  const selectAll = () => {
    if (selectedIds.size === filtered.length) {
      setSelectedIds(new Set());
    } else {
      setSelectedIds(new Set(filtered.map(a => a.id)));
    }
  };

  /* ─── Open modal ─── */
  const openModal = (app: Application) => {
    setSelectedApp(app);
    setNewStatus(app.status);
    setRecruiterNotes(app.recruiter_notes || '');
    setRejectionReason(app.rejection_reason || '');
  };

  /* ─── Filtering & sorting ─── */
  const filtered = applications
    .filter(a => statusFilter === 'all' || a.status === statusFilter)
    .sort((a, b) => {
      if (sortBy === 'score') return (b.match_score_at_apply || 0) - (a.match_score_at_apply || 0);
      return new Date(b.applied_at).getTime() - new Date(a.applied_at).getTime();
    });

  const statusCounts: Record<string, number> = {};
  applications.forEach(a => { statusCounts[a.status] = (statusCounts[a.status] || 0) + 1; });

  const scoreColor = (s: number) => s >= 70 ? 'text-green-600 bg-green-100' : s >= 50 ? 'text-yellow-600 bg-yellow-100' : 'text-red-600 bg-red-100';

  /* ─── Loading / Error ─── */
  if (loading) return (
    <div className="min-h-screen flex items-center justify-center">
      <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600" />
    </div>
  );
  if (error) return (
    <div className="min-h-screen flex items-center justify-center">
      <div className="text-center">
        <p className="text-red-600 mb-4">{error}</p>
        <Link href="/recruiter/my-jobs" className="text-blue-600 hover:underline">Back to My Jobs</Link>
      </div>
    </div>
  );

  return (
    <div className="min-h-screen bg-gray-50">
      {/* ─── Header ─── */}
      <header className="bg-white shadow-sm">
        <div className="max-w-7xl mx-auto px-4 py-4">
          <div className="flex justify-between items-start">
            <div>
              <Link href="/recruiter/my-jobs" className="text-gray-500 hover:text-gray-900 text-sm">← My Jobs</Link>
              <h1 className="text-2xl font-bold text-gray-900 mt-1">Applicants: {job?.title}</h1>
              <p className="text-gray-500 text-sm">{job?.company_name} · {applications.length} applicant{applications.length !== 1 ? 's' : ''}</p>
            </div>
            <div className="flex items-center gap-3">
              <NotificationBell />
              <div className="flex bg-gray-100 rounded-md p-0.5">
                <button onClick={() => setView('list')}
                  className={`px-3 py-1.5 rounded text-sm font-medium ${view === 'list' ? 'bg-white shadow text-gray-900' : 'text-gray-500'}`}>
                  List
                </button>
                <button onClick={() => setView('pipeline')}
                  className={`px-3 py-1.5 rounded text-sm font-medium ${view === 'pipeline' ? 'bg-white shadow text-gray-900' : 'text-gray-500'}`}>
                  Pipeline
                </button>
              </div>
            </div>
          </div>
        </div>
      </header>

      <main className="max-w-7xl mx-auto px-4 py-6">
        {/* ─── Pipeline View ─── */}
        {view === 'pipeline' ? (
          <div className="overflow-x-auto pb-4">
            <div className="flex gap-4 min-w-max">
              {STAGES.filter(s => !['offer_accepted', 'withdrawn'].includes(s.key)).map(stage => {
                const stageApps = applications
                  .filter(a => a.status === stage.key)
                  .sort((a, b) => (b.match_score_at_apply || 0) - (a.match_score_at_apply || 0));
                return (
                  <div key={stage.key} className="w-72 flex-shrink-0">
                    <div className={`rounded-t-lg px-3 py-2 border-t-4 ${stage.color} ${stage.bg} flex justify-between items-center`}>
                      <span className="text-sm font-semibold">{stage.icon} {stage.label}</span>
                      <span className={`text-xs font-bold px-2 py-0.5 rounded-full ${stage.badge}`}>{stageApps.length}</span>
                    </div>
                    <div className="bg-gray-100 rounded-b-lg p-2 space-y-2 min-h-[200px]">
                      {stageApps.length === 0 ? (
                        <p className="text-xs text-gray-400 text-center py-6">No applicants</p>
                      ) : stageApps.map(app => (
                        <div key={app.id} className="bg-white rounded-lg shadow-sm p-3 border hover:shadow-md transition cursor-pointer"
                          onClick={() => openModal(app)}>
                          <div className="flex justify-between items-start mb-1">
                            <p className="text-sm font-semibold text-gray-900 truncate">{app.applicant_name || 'Unknown'}</p>
                            {app.match_score_at_apply != null && (
                              <span className={`text-xs font-bold px-1.5 py-0.5 rounded ${scoreColor(app.match_score_at_apply)}`}>
                                {Math.round(app.match_score_at_apply)}%
                              </span>
                            )}
                          </div>
                          <p className="text-xs text-gray-500 truncate">{app.headline || app.applicant_email}</p>
                          {app.years_experience != null && (
                            <p className="text-xs text-gray-400 mt-1">{app.years_experience} yrs exp</p>
                          )}
                          <div className="flex gap-1 mt-2">
                            {(VALID_NEXT[stage.key] || []).slice(0, 2).map(next => {
                              const ns = getStage(next);
                              return (
                                <button key={next} onClick={(e) => { e.stopPropagation(); quickStatusChange(app.id, next); }}
                                  className={`text-xs px-2 py-0.5 rounded ${ns.badge} hover:opacity-80`}
                                  title={`Move to ${ns.label}`}>
                                  {ns.icon}
                                </button>
                              );
                            })}
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        ) : (
          /* ─── List View ─── */
          <>
            {/* Controls Bar */}
            <div className="bg-white rounded-lg shadow p-4 mb-4">
              <div className="flex flex-wrap items-center justify-between gap-3">
                <div className="flex flex-wrap gap-2">
                  <button onClick={() => setStatusFilter('all')}
                    className={`px-3 py-1.5 rounded-md text-sm font-medium ${statusFilter === 'all' ? 'bg-blue-600 text-white' : 'bg-gray-100 hover:bg-gray-200'}`}>
                    All ({applications.length})
                  </button>
                  {STAGES.filter(s => statusCounts[s.key]).map(s => (
                    <button key={s.key} onClick={() => setStatusFilter(s.key)}
                      className={`px-3 py-1.5 rounded-md text-sm font-medium ${statusFilter === s.key ? 'bg-blue-600 text-white' : 'bg-gray-100 hover:bg-gray-200'}`}>
                      {s.icon} {s.label} ({statusCounts[s.key]})
                    </button>
                  ))}
                </div>
                <div className="flex items-center gap-2">
                  <select value={sortBy} onChange={e => setSortBy(e.target.value as any)}
                    className="border rounded-md px-3 py-1.5 text-sm">
                    <option value="score">Sort: Match Score</option>
                    <option value="date">Sort: Date Applied</option>
                  </select>
                </div>
              </div>
            </div>

            {/* Bulk Actions */}
            {selectedIds.size > 0 && (
              <div className="bg-blue-50 border border-blue-200 rounded-lg p-3 mb-4 flex items-center justify-between">
                <span className="text-sm font-medium text-blue-700">{selectedIds.size} selected</span>
                <div className="flex items-center gap-2">
                  <select value={bulkAction} onChange={e => setBulkAction(e.target.value)} className="border rounded-md px-3 py-1.5 text-sm">
                    <option value="">Choose action...</option>
                    <option value="screening">Move to Screening</option>
                    <option value="shortlisted">Shortlist</option>
                    <option value="interview_scheduled">Schedule Interview</option>
                    <option value="rejected">Reject</option>
                  </select>
                  <button onClick={handleBulkAction} disabled={!bulkAction || bulkUpdating}
                    className="bg-blue-600 text-white px-4 py-1.5 rounded-md text-sm hover:bg-blue-700 disabled:opacity-50">
                    {bulkUpdating ? 'Updating...' : 'Apply'}
                  </button>
                  <button onClick={() => setSelectedIds(new Set())} className="text-gray-500 hover:text-gray-700 text-sm">Clear</button>
                </div>
              </div>
            )}

            {/* Applicant Cards */}
            {filtered.length === 0 ? (
              <div className="bg-white rounded-lg shadow p-8 text-center">
                <p className="text-gray-500">No applicants found</p>
                {statusFilter !== 'all' && (
                  <button onClick={() => setStatusFilter('all')} className="mt-3 text-blue-600 hover:underline text-sm">View all</button>
                )}
              </div>
            ) : (
              <div className="space-y-3">
                {/* Select all */}
                <div className="flex items-center gap-2 px-1">
                  <input type="checkbox" checked={selectedIds.size === filtered.length && filtered.length > 0}
                    onChange={selectAll} className="rounded" />
                  <span className="text-xs text-gray-500">Select all ({filtered.length})</span>
                </div>

                {filtered.map(app => {
                  const stage = getStage(app.status);
                  return (
                    <div key={app.id} className={`bg-white rounded-lg shadow border-l-4 p-5 ${stage.color}`}>
                      <div className="flex items-start gap-3">
                        <input type="checkbox" checked={selectedIds.has(app.id)} onChange={() => toggleSelect(app.id)}
                          className="mt-1 rounded" onClick={e => e.stopPropagation()} />
                        <div className="flex-1 min-w-0">
                          <div className="flex items-center gap-3 mb-1 flex-wrap">
                            <h3 className="text-lg font-semibold text-gray-900">{app.applicant_name || 'Unknown'}</h3>
                            <span className={`px-2.5 py-0.5 rounded-full text-xs font-medium ${stage.badge}`}>
                              {stage.icon} {stage.label}
                            </span>
                            {app.match_score_at_apply != null && (
                              <span className={`px-2.5 py-0.5 rounded-full text-xs font-bold ${scoreColor(app.match_score_at_apply)}`}>
                                {Math.round(app.match_score_at_apply)}% Match
                              </span>
                            )}
                          </div>
                          <p className="text-sm text-gray-500">{app.applicant_email}</p>
                          <div className="flex flex-wrap gap-4 text-xs text-gray-400 mt-1">
                            {app.headline && <span>💼 {app.headline}</span>}
                            {app.years_experience != null && <span>📅 {app.years_experience} yrs</span>}
                            <span>Applied {new Date(app.applied_at).toLocaleDateString()}</span>
                          </div>

                          {app.cover_letter && (
                            <div className="mt-3 p-3 bg-gray-50 rounded text-sm text-gray-600 max-h-24 overflow-y-auto whitespace-pre-wrap">
                              {app.cover_letter}
                            </div>
                          )}
                          {app.recruiter_notes && (
                            <div className="mt-2 p-2 bg-yellow-50 rounded text-xs text-yellow-700 border border-yellow-200">
                              <b>Notes:</b> {app.recruiter_notes}
                            </div>
                          )}
                          {app.rejection_reason && (
                            <div className="mt-2 p-2 bg-red-50 rounded text-xs text-red-600 border border-red-200">
                              <b>Reason:</b> {app.rejection_reason}
                            </div>
                          )}

                          {/* Quick action buttons */}
                          <div className="flex flex-wrap gap-2 mt-3">
                            {(VALID_NEXT[app.status] || []).map(next => {
                              const ns = getStage(next);
                              return (
                                <button key={next} onClick={() => quickStatusChange(app.id, next)}
                                  className={`text-xs px-3 py-1 rounded-md border ${ns.badge} hover:opacity-80`}>
                                  {ns.icon} {ns.label}
                                </button>
                              );
                            })}
                          </div>
                        </div>

                        <div className="flex flex-col gap-2 ml-2 flex-shrink-0">
                          <button onClick={() => openModal(app)}
                            className="px-3 py-1.5 bg-blue-600 text-white rounded-md hover:bg-blue-700 text-xs">
                            Edit
                          </button>
                          <Link href={`/profile/${app.user_id}`}
                            className="px-3 py-1.5 bg-gray-100 text-gray-700 rounded-md hover:bg-gray-200 text-xs text-center">
                            Profile
                          </Link>
                        </div>
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </>
        )}
      </main>

      {/* ─── Update Modal ─── */}
      {selectedApp && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4" onClick={() => setSelectedApp(null)}>
          <div className="bg-white rounded-xl shadow-xl max-w-lg w-full p-6" onClick={e => e.stopPropagation()}>
            <h2 className="text-xl font-bold text-gray-900 mb-1">Update Application</h2>
            <p className="text-gray-500 text-sm mb-4">{selectedApp.applicant_name} · {selectedApp.applicant_email}</p>

            {selectedApp.match_score_at_apply != null && (
              <div className="mb-4 flex items-center gap-2">
                <span className="text-sm text-gray-600">Match Score:</span>
                <span className={`text-sm font-bold px-2 py-0.5 rounded ${scoreColor(selectedApp.match_score_at_apply)}`}>
                  {Math.round(selectedApp.match_score_at_apply)}%
                </span>
              </div>
            )}

            <div className="mb-4">
              <label className="block text-sm font-medium text-gray-700 mb-1">Status</label>
              <select value={newStatus} onChange={e => setNewStatus(e.target.value)}
                className="w-full px-3 py-2 border rounded-md focus:ring-blue-500 focus:border-blue-500">
                {STAGES.filter(s => s.key !== 'withdrawn').map(s => (
                  <option key={s.key} value={s.key}>{s.icon} {s.label}</option>
                ))}
              </select>
            </div>

            {newStatus === 'rejected' && (
              <div className="mb-4">
                <label className="block text-sm font-medium text-gray-700 mb-1">Rejection Reason</label>
                <input value={rejectionReason} onChange={e => setRejectionReason(e.target.value)}
                  placeholder="e.g., Not enough experience, other candidate selected..."
                  className="w-full px-3 py-2 border rounded-md focus:ring-blue-500 focus:border-blue-500" />
              </div>
            )}

            <div className="mb-4">
              <label className="block text-sm font-medium text-gray-700 mb-1">Private Notes</label>
              <textarea value={recruiterNotes} onChange={e => setRecruiterNotes(e.target.value)} rows={3}
                placeholder="Add private notes about this candidate..."
                className="w-full px-3 py-2 border rounded-md focus:ring-blue-500 focus:border-blue-500" />
            </div>

            <div className="flex gap-3 justify-end">
              <button onClick={() => setSelectedApp(null)}
                className="px-4 py-2 text-gray-700 bg-gray-100 rounded-md hover:bg-gray-200 text-sm">Cancel</button>
              <button onClick={handleUpdateStatus} disabled={updating}
                className="px-6 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 disabled:opacity-50 text-sm">
                {updating ? 'Updating...' : 'Save Changes'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
