'use client';

import { useState, useEffect, useCallback } from 'react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import api, { Application } from '@/lib/api';
import NotificationBell from '@/components/NotificationBell';

/* ─── Status display config ─── */
const STATUS: Record<string, { label: string; color: string; bg: string; icon: string }> = {
  applied:             { label: 'Applied',            color: 'text-blue-700',    bg: 'bg-blue-50 border-blue-200',     icon: '📨' },
  screening:           { label: 'Screening',          color: 'text-purple-700',  bg: 'bg-purple-50 border-purple-200', icon: '🔍' },
  shortlisted:         { label: 'Shortlisted',        color: 'text-green-700',   bg: 'bg-green-50 border-green-200',   icon: '⭐' },
  interview_scheduled: { label: 'Interview',          color: 'text-orange-700',  bg: 'bg-orange-50 border-orange-200', icon: '📅' },
  interviewed:         { label: 'Interviewed',        color: 'text-teal-700',    bg: 'bg-teal-50 border-teal-200',     icon: '💬' },
  offer_extended:      { label: 'Offer Received',     color: 'text-emerald-700', bg: 'bg-emerald-50 border-emerald-200', icon: '🎉' },
  offer_accepted:      { label: 'Accepted',           color: 'text-green-800',   bg: 'bg-green-100 border-green-300',  icon: '✅' },
  offer_declined:      { label: 'Declined',           color: 'text-gray-600',    bg: 'bg-gray-50 border-gray-200',     icon: '❌' },
  rejected:            { label: 'Rejected',           color: 'text-red-700',     bg: 'bg-red-50 border-red-200',       icon: '🚫' },
  withdrawn:           { label: 'Withdrawn',          color: 'text-gray-500',    bg: 'bg-gray-50 border-gray-200',     icon: '↩️' },
};

const getStatus = (s: string) => STATUS[s] || { label: s, color: 'text-gray-700', bg: 'bg-gray-50 border-gray-200', icon: '📋' };

const ACTIVE_STATUSES = new Set(['applied', 'screening', 'shortlisted', 'interview_scheduled', 'interviewed', 'offer_extended']);

export default function ApplicationsPage() {
  const router = useRouter();
  const [apps, setApps] = useState<any[]>([]);
  const [stats, setStats] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [filter, setFilter] = useState('all');
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [withdrawingId, setWithdrawingId] = useState<string | null>(null);

  useEffect(() => {
    if (!api.getToken()) { router.push('/login'); return; }
    load();
  }, [router]);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await api.getMyApplications();
      setApps(data.applications || []);
      setStats(data.stats || null);
    } catch (err: any) {
      setError(err.message || 'Failed to load applications');
    } finally {
      setLoading(false);
    }
  }, []);

  const handleWithdraw = async (id: string) => {
    if (!confirm('Withdraw this application? This cannot be undone.')) return;
    setWithdrawingId(id);
    try {
      await api.withdrawApplication(id);
      await load();
    } catch (err: any) {
      alert(err.message || 'Failed to withdraw');
    } finally {
      setWithdrawingId(null);
    }
  };

  const filtered = filter === 'all' ? apps : apps.filter(a => a.status === filter);

  /* ─── Loading ─── */
  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-50">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto" />
          <p className="mt-4 text-gray-600">Loading your applications...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50">
      {/* ─── Header ─── */}
      <header className="bg-white shadow-sm">
        <div className="max-w-6xl mx-auto px-4 py-4 flex justify-between items-center">
          <div className="flex items-center gap-4">
            <Link href="/dashboard" className="text-gray-500 hover:text-gray-900 text-sm">← Dashboard</Link>
            <h1 className="text-2xl font-bold text-gray-900">My Applications</h1>
          </div>
          <div className="flex items-center gap-3">
            <NotificationBell />
            <button onClick={load} className="bg-blue-600 text-white px-4 py-2 rounded-md hover:bg-blue-700 text-sm">Refresh</button>
            <Link href="/recommendations" className="bg-green-600 text-white px-4 py-2 rounded-md hover:bg-green-700 text-sm">Find Jobs</Link>
          </div>
        </div>
      </header>

      <main className="max-w-6xl mx-auto px-4 py-6">
        {error && (
          <div className="bg-red-50 border border-red-200 rounded-lg p-4 mb-6">
            <p className="text-red-600">{error}</p>
          </div>
        )}

        {/* ─── Stats ─── */}
        {stats && (
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
            <div className="bg-white rounded-lg shadow p-4 text-center">
              <div className="text-3xl font-bold text-blue-600">{stats.total}</div>
              <div className="text-gray-500 text-sm">Total Applied</div>
            </div>
            <div className="bg-white rounded-lg shadow p-4 text-center">
              <div className="text-3xl font-bold text-green-600">{stats.active}</div>
              <div className="text-gray-500 text-sm">Active</div>
            </div>
            <div className="bg-white rounded-lg shadow p-4 text-center">
              <div className="text-3xl font-bold text-purple-600">{stats.by_status?.shortlisted || 0}</div>
              <div className="text-gray-500 text-sm">Shortlisted</div>
            </div>
            <div className="bg-white rounded-lg shadow p-4 text-center">
              <div className="text-3xl font-bold text-orange-600">{stats.avg_match_score || 0}%</div>
              <div className="text-gray-500 text-sm">Avg Match</div>
            </div>
          </div>
        )}

        {/* ─── Filter Tabs ─── */}
        <div className="flex flex-wrap gap-2 mb-6">
          <button onClick={() => setFilter('all')}
            className={`px-4 py-2 rounded-full text-sm font-medium ${filter === 'all' ? 'bg-blue-600 text-white' : 'bg-white text-gray-600 border hover:bg-gray-50'}`}>
            All ({apps.length})
          </button>
          {Object.entries(STATUS).map(([key, cfg]) => {
            const count = apps.filter(a => a.status === key).length;
            if (!count) return null;
            return (
              <button key={key} onClick={() => setFilter(key)}
                className={`px-4 py-2 rounded-full text-sm font-medium ${filter === key ? 'bg-blue-600 text-white' : 'bg-white text-gray-600 border hover:bg-gray-50'}`}>
                {cfg.icon} {cfg.label} ({count})
              </button>
            );
          })}
        </div>

        {/* ─── Empty State ─── */}
        {apps.length === 0 ? (
          <div className="bg-white rounded-lg shadow p-12 text-center">
            <div className="text-6xl mb-4">📋</div>
            <h3 className="text-xl font-semibold text-gray-900 mb-2">No applications yet</h3>
            <p className="text-gray-600 mb-6">Your profile data is sent automatically when you apply — no re-uploading needed.</p>
            <Link href="/recommendations" className="inline-block bg-blue-600 text-white px-6 py-3 rounded-md hover:bg-blue-700">
              Browse Job Recommendations
            </Link>
          </div>
        ) : (
          /* ─── Application Cards ─── */
          <div className="space-y-3">
            {filtered.map((app) => {
              const st = getStatus(app.status);
              const open = expandedId === app.id;
              const active = ACTIVE_STATUSES.has(app.status);
              const borderColor = active ? '#2563eb' : app.status === 'shortlisted' ? '#16a34a' : app.status === 'rejected' ? '#dc2626' : '#d1d5db';

              return (
                <div key={app.id} className="bg-white rounded-lg shadow overflow-hidden" style={{ borderLeft: `4px solid ${borderColor}` }}>
                  {/* Card Header — click to expand */}
                  <div className="p-5 cursor-pointer hover:bg-gray-50 transition" onClick={() => setExpandedId(open ? null : app.id)}>
                    <div className="flex justify-between items-start">
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-3 mb-1 flex-wrap">
                          <h3 className="text-lg font-semibold text-gray-900 truncate">{app.job_title || 'Job Removed'}</h3>
                          <span className={`px-3 py-0.5 rounded-full text-xs font-medium border whitespace-nowrap ${st.bg} ${st.color}`}>
                            {st.icon} {st.label}
                          </span>
                        </div>
                        <p className="text-gray-600 text-sm">
                          {app.company_name || 'Unknown'}
                          {app.location_city ? ` · ${app.location_city}` : ''}
                          {app.location_type ? ` · ${app.location_type}` : ''}
                        </p>
                        <div className="flex items-center gap-4 mt-2 text-xs text-gray-500 flex-wrap">
                          <span>Applied {new Date(app.applied_at).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })}</span>
                          {app.match_score_at_apply != null && (
                            <span className={`font-semibold ${app.match_score_at_apply >= 70 ? 'text-green-600' : app.match_score_at_apply >= 50 ? 'text-yellow-600' : 'text-red-500'}`}>
                              {Math.round(app.match_score_at_apply)}% Match
                            </span>
                          )}
                          {app.salary_min && app.salary_max && (
                            <span>{app.salary_currency || '$'}{(app.salary_min/1000).toFixed(0)}K–{(app.salary_max/1000).toFixed(0)}K</span>
                          )}
                        </div>
                      </div>
                      <span className="text-gray-400 ml-4">{open ? '▲' : '▼'}</span>
                    </div>
                  </div>

                  {/* Expanded */}
                  {open && (
                    <div className="border-t px-5 py-4 bg-gray-50">
                      {/* Timeline */}
                      {app.timeline?.length > 0 && (
                        <div className="mb-4">
                          <h4 className="text-sm font-semibold text-gray-700 mb-3">Timeline</h4>
                          <div className="space-y-2">
                            {app.timeline.map((t: any, i: number) => {
                              const tc = getStatus(t.status);
                              return (
                                <div key={i} className="flex items-start gap-3">
                                  <div className="w-7 h-7 rounded-full bg-white border-2 border-blue-200 flex items-center justify-center text-xs flex-shrink-0">{tc.icon}</div>
                                  <div>
                                    <p className="text-sm font-medium text-gray-800">{tc.label}</p>
                                    <p className="text-xs text-gray-500">{t.note}</p>
                                    <p className="text-xs text-gray-400">{new Date(t.date).toLocaleString()}</p>
                                  </div>
                                </div>
                              );
                            })}
                          </div>
                        </div>
                      )}

                      {app.cover_letter && (
                        <div className="mb-4">
                          <h4 className="text-sm font-semibold text-gray-700 mb-1">Cover Letter</h4>
                          <div className="bg-white rounded border p-3 text-sm text-gray-700 whitespace-pre-wrap max-h-32 overflow-y-auto">{app.cover_letter}</div>
                        </div>
                      )}

                      {app.rejection_reason && (
                        <div className="bg-red-50 border border-red-200 rounded p-3 mb-4 text-sm text-red-700">
                          <span className="font-medium">Reason:</span> {app.rejection_reason}
                        </div>
                      )}

                      <div className="flex gap-3">
                        {app.job_id && (
                          <Link href={`/jobs/${app.job_id}`} className="bg-blue-600 text-white px-4 py-2 rounded-md hover:bg-blue-700 text-sm">View Job</Link>
                        )}
                        {active && (
                          <button onClick={(e) => { e.stopPropagation(); handleWithdraw(app.id); }}
                            disabled={withdrawingId === app.id}
                            className="bg-red-50 text-red-600 border border-red-200 px-4 py-2 rounded-md hover:bg-red-100 text-sm disabled:opacity-50">
                            {withdrawingId === app.id ? 'Withdrawing...' : 'Withdraw'}
                          </button>
                        )}
                      </div>
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        )}
      </main>
    </div>
  );
}
