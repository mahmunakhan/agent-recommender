'use client';

import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { useAuth } from '@/contexts/AuthContext';
import api, { Job, Application } from '@/lib/api';
import Navbar from '@/components/Navbar';
import NotificationBell from '@/components/NotificationBell';
import Link from 'next/link';

export default function RecruiterDashboard() {
  const { user, loading } = useAuth();
  const router = useRouter();
  const [jobs, setJobs] = useState<Job[]>([]);
  const [allApps, setAllApps] = useState<Application[]>([]);
  const [stats, setStats] = useState({
    totalJobs: 0,
    activeJobs: 0,
    totalApplications: 0,
    newToday: 0,
    shortlisted: 0,
    interviews: 0,
    offers: 0,
    avgMatchScore: 0,
  });
  const [loadingData, setLoadingData] = useState(true);

  useEffect(() => {
    if (!loading && !user) {
      router.push('/login');
    } else if (!loading && user?.role !== 'recruiter') {
      router.push('/dashboard');
    }
  }, [user, loading, router]);

  useEffect(() => {
    if (user?.role === 'recruiter') {
      fetchRecruiterData();
    }
  }, [user]);

  const fetchRecruiterData = async () => {
    try {
      const allJobs = await api.getJobs();
      const myJobs = allJobs.filter((job: Job) => job.posted_by_id === user?.id);
      setJobs(myJobs);

      // Fetch all applications across recruiter's jobs
      let apps: Application[] = [];
      try {
        const appsData = await api.getAllRecruiterApplications();
        apps = appsData.applications || [];
        setAllApps(apps);
      } catch {
        // Endpoint may not be available yet
      }

      const today = new Date().toISOString().split('T')[0];
      const scores = apps.filter(a => a.match_score_at_apply).map(a => a.match_score_at_apply || 0);

      setStats({
        totalJobs: myJobs.length,
        activeJobs: myJobs.filter((j: Job) => j.is_active).length,
        totalApplications: apps.length,
        newToday: apps.filter(a => a.applied_at?.startsWith(today)).length,
        shortlisted: apps.filter(a => a.status === 'shortlisted').length,
        interviews: apps.filter(a => ['interview_scheduled', 'interviewed'].includes(a.status)).length,
        offers: apps.filter(a => ['offer_extended', 'offer_accepted'].includes(a.status)).length,
        avgMatchScore: scores.length > 0 ? Math.round(scores.reduce((a, b) => a + b, 0) / scores.length) : 0,
      });
    } catch (error) {
      console.error('Error fetching recruiter data:', error);
    } finally {
      setLoadingData(false);
    }
  };

  if (loading || loadingData) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600"></div>
      </div>
    );
  }

  if (!user || user.role !== 'recruiter') return null;

  // Pipeline summary
  const pipeline: Record<string, number> = {};
  allApps.forEach(a => { pipeline[a.status] = (pipeline[a.status] || 0) + 1; });

  const pipelineStages = [
    { key: 'applied', label: 'Applied', color: 'bg-blue-500', light: 'bg-blue-50 text-blue-700' },
    { key: 'screening', label: 'Screening', color: 'bg-yellow-500', light: 'bg-yellow-50 text-yellow-700' },
    { key: 'shortlisted', label: 'Shortlisted', color: 'bg-green-500', light: 'bg-green-50 text-green-700' },
    { key: 'interview_scheduled', label: 'Interview', color: 'bg-purple-500', light: 'bg-purple-50 text-purple-700' },
    { key: 'interviewed', label: 'Interviewed', color: 'bg-indigo-500', light: 'bg-indigo-50 text-indigo-700' },
    { key: 'offer_extended', label: 'Offer', color: 'bg-emerald-500', light: 'bg-emerald-50 text-emerald-700' },
  ];

  // Recent applications (last 10)
  const recentApps = [...allApps].sort((a, b) =>
    new Date(b.applied_at).getTime() - new Date(a.applied_at).getTime()
  ).slice(0, 8);

  return (
    <div className="min-h-screen bg-gray-50">
      <Navbar />

      <div className="max-w-7xl mx-auto px-4 py-8">
        {/* ─── Stats Cards ─── */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-8">
          <div className="bg-white rounded-lg shadow p-5">
            <div className="text-3xl font-bold text-blue-600">{stats.totalJobs}</div>
            <div className="text-gray-500 text-sm">Total Jobs</div>
          </div>
          <div className="bg-white rounded-lg shadow p-5">
            <div className="text-3xl font-bold text-green-600">{stats.activeJobs}</div>
            <div className="text-gray-500 text-sm">Active Jobs</div>
          </div>
          <div className="bg-white rounded-lg shadow p-5">
            <div className="text-3xl font-bold text-purple-600">{stats.totalApplications}</div>
            <div className="text-gray-500 text-sm">Total Applications</div>
          </div>
          <div className="bg-white rounded-lg shadow p-5">
            <div className="text-3xl font-bold text-orange-600">{stats.avgMatchScore}%</div>
            <div className="text-gray-500 text-sm">Avg Match Score</div>
          </div>
        </div>

        {/* ─── Hiring Pipeline Overview ─── */}
        {allApps.length > 0 && (
          <div className="bg-white rounded-lg shadow p-6 mb-8">
            <h2 className="text-lg font-semibold text-gray-900 mb-4">Hiring Pipeline</h2>
            <div className="flex gap-2 items-end">
              {pipelineStages.map(stage => {
                const count = pipeline[stage.key] || 0;
                const maxCount = Math.max(...pipelineStages.map(s => pipeline[s.key] || 0), 1);
                const height = Math.max(20, (count / maxCount) * 100);
                return (
                  <div key={stage.key} className="flex-1 flex flex-col items-center">
                    <span className="text-lg font-bold text-gray-900 mb-1">{count}</span>
                    <div className="w-full rounded-t-md relative" style={{ height: `${height}px` }}>
                      <div className={`absolute inset-0 ${stage.color} rounded-t-md opacity-80`} />
                    </div>
                    <div className={`w-full text-center py-2 text-xs font-medium rounded-b-md ${stage.light}`}>
                      {stage.label}
                    </div>
                  </div>
                );
              })}
            </div>
            {(pipeline['rejected'] || pipeline['withdrawn']) && (
              <div className="flex gap-4 mt-3 text-xs text-gray-500">
                {pipeline['rejected'] && <span>🚫 {pipeline['rejected']} rejected</span>}
                {pipeline['withdrawn'] && <span>↩️ {pipeline['withdrawn']} withdrawn</span>}
              </div>
            )}
          </div>
        )}

        {/* ─── Quick Actions ─── */}
        <div className="bg-white rounded-lg shadow p-6 mb-8">
          <h2 className="text-lg font-semibold mb-4">Quick Actions</h2>
          <div className="flex flex-wrap gap-3">
            <Link href="/recruiter/post-job"
              className="bg-blue-600 text-white px-6 py-3 rounded-lg hover:bg-blue-700 font-medium text-sm">
              + Post New Job
            </Link>
            <Link href="/recruiter/my-jobs"
              className="bg-gray-100 text-gray-700 px-6 py-3 rounded-lg hover:bg-gray-200 font-medium text-sm">
              View My Jobs
            </Link>
            {stats.shortlisted > 0 && (
              <span className="bg-green-50 text-green-700 px-4 py-3 rounded-lg text-sm font-medium border border-green-200">
                ⭐ {stats.shortlisted} shortlisted
              </span>
            )}
            {stats.interviews > 0 && (
              <span className="bg-purple-50 text-purple-700 px-4 py-3 rounded-lg text-sm font-medium border border-purple-200">
                📅 {stats.interviews} in interviews
              </span>
            )}
            {stats.offers > 0 && (
              <span className="bg-emerald-50 text-emerald-700 px-4 py-3 rounded-lg text-sm font-medium border border-emerald-200">
                🎉 {stats.offers} offers pending
              </span>
            )}
          </div>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
          {/* ─── Recent Applications ─── */}
          <div className="bg-white rounded-lg shadow p-6">
            <h2 className="text-lg font-semibold mb-4">Recent Applications</h2>
            {recentApps.length === 0 ? (
              <p className="text-gray-500 text-sm py-4">No applications yet.</p>
            ) : (
              <div className="space-y-3">
                {recentApps.map(app => (
                  <div key={app.id} className="flex items-center justify-between py-2 border-b border-gray-100 last:border-0">
                    <div className="min-w-0 flex-1">
                      <p className="text-sm font-medium text-gray-900 truncate">{app.applicant_name || 'Unknown'}</p>
                      <p className="text-xs text-gray-500 truncate">
                        {app.job_title} · {new Date(app.applied_at).toLocaleDateString()}
                      </p>
                    </div>
                    <div className="flex items-center gap-2 ml-3">
                      {app.match_score_at_apply != null && (
                        <span className={`text-xs font-semibold px-2 py-0.5 rounded ${
                          app.match_score_at_apply >= 70 ? 'bg-green-100 text-green-700' :
                          app.match_score_at_apply >= 50 ? 'bg-yellow-100 text-yellow-700' :
                          'bg-gray-100 text-gray-600'
                        }`}>
                          {Math.round(app.match_score_at_apply)}%
                        </span>
                      )}
                      <span className={`text-xs px-2 py-0.5 rounded ${
                        app.status === 'applied' ? 'bg-blue-100 text-blue-700' :
                        app.status === 'shortlisted' ? 'bg-green-100 text-green-700' :
                        app.status === 'rejected' ? 'bg-red-100 text-red-700' :
                        'bg-gray-100 text-gray-600'
                      }`}>
                        {app.status.replace(/_/g, ' ')}
                      </span>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* ─── Recent Jobs ─── */}
          <div className="bg-white rounded-lg shadow p-6">
            <div className="flex justify-between items-center mb-4">
              <h2 className="text-lg font-semibold">My Jobs</h2>
              <Link href="/recruiter/my-jobs" className="text-blue-600 hover:text-blue-800 text-sm">
                View All →
              </Link>
            </div>

            {jobs.length === 0 ? (
              <div className="text-center py-6 text-gray-500">
                <p className="mb-3">No jobs posted yet.</p>
                <Link href="/recruiter/post-job" className="text-blue-600 hover:text-blue-800 font-medium text-sm">
                  Post your first job →
                </Link>
              </div>
            ) : (
              <div className="space-y-3">
                {jobs.slice(0, 5).map(job => {
                  const jobApps = allApps.filter(a => a.job_id === job.id);
                  return (
                    <div key={job.id} className="border rounded-lg p-4 hover:border-blue-300 transition">
                      <div className="flex justify-between items-start">
                        <div className="min-w-0 flex-1">
                          <h3 className="font-semibold text-gray-900 truncate">{job.title}</h3>
                          <p className="text-sm text-gray-500">{job.company_name}</p>
                          <div className="flex gap-3 mt-2 text-xs text-gray-400">
                            <span>📍 {job.location_city}</span>
                            <span>🏠 {job.location_type}</span>
                          </div>
                        </div>
                        <div className="flex flex-col items-end gap-1 ml-3">
                          <span className={`px-2 py-0.5 rounded-full text-xs ${
                            job.is_active ? 'bg-green-100 text-green-700' : 'bg-gray-100 text-gray-600'
                          }`}>
                            {job.is_active ? 'Active' : 'Inactive'}
                          </span>
                          {jobApps.length > 0 && (
                            <Link href={`/recruiter/jobs/${job.id}/applicants`}
                              className="text-blue-600 hover:text-blue-800 text-xs font-medium">
                              {jobApps.length} applicant{jobApps.length > 1 ? 's' : ''} →
                            </Link>
                          )}
                        </div>
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
