'use client';

import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import { useAuth } from '@/contexts/AuthContext';
import Navbar from '@/components/Navbar';
import { api } from '@/lib/api';

export default function RecruiterDashboardPage() {
  const { user, loading } = useAuth();
  const router = useRouter();
  const [stats, setStats] = useState({ totalJobs: 0, activeJobs: 0, totalApplications: 0 });
  const [recentJobs, setRecentJobs] = useState<any[]>([]);
  const [loadingData, setLoadingData] = useState(true);

  useEffect(() => {
    if (!loading && !user) router.push('/login');
    if (!loading && user && user.role !== 'recruiter') router.push('/dashboard');
  }, [user, loading, router]);

  useEffect(() => {
    if (user && user.role === 'recruiter') {
      loadDashboardData();
    }
  }, [user]);

  const loadDashboardData = async () => {
    try {
      const data = await api.getMyJobs();
      const jobs = data.jobs || [];
      setRecentJobs(jobs.slice(0, 5));
      setStats({
        totalJobs: data.total || jobs.length,
        activeJobs: jobs.filter((j: any) => j.is_active).length,
        totalApplications: 0,
      });
    } catch (err) {
      console.error('Failed to load dashboard:', err);
    } finally {
      setLoadingData(false);
    }
  };

  if (loading || !user) {
    return <div className="min-h-screen flex items-center justify-center"><div className="text-lg">Loading...</div></div>;
  }

  return (
    <div className="min-h-screen bg-gray-100">
      <Navbar />

      <main className="max-w-7xl mx-auto py-6 px-4 sm:px-6 lg:px-8">
        <h2 className="text-2xl font-bold text-gray-900 mb-6">Recruiter Dashboard</h2>

        {/* Stats Cards */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-8">
          <div className="bg-white rounded-xl shadow-sm p-6 border border-gray-200">
            <p className="text-sm text-gray-500 mb-1">Total Jobs Posted</p>
            <p className="text-3xl font-bold text-blue-600">{stats.totalJobs}</p>
          </div>
          <div className="bg-white rounded-xl shadow-sm p-6 border border-gray-200">
            <p className="text-sm text-gray-500 mb-1">Active Jobs</p>
            <p className="text-3xl font-bold text-green-600">{stats.activeJobs}</p>
          </div>
          <div className="bg-white rounded-xl shadow-sm p-6 border border-gray-200">
            <p className="text-sm text-gray-500 mb-1">Total Applications</p>
            <p className="text-3xl font-bold text-purple-600">{stats.totalApplications}</p>
          </div>
        </div>

        {/* Quick Actions */}
        <div className="bg-white rounded-xl shadow-sm p-6 border border-gray-200 mb-8">
          <h3 className="text-lg font-semibold text-gray-800 mb-4">Quick Actions</h3>
          <div className="flex gap-4 flex-wrap">
            <Link href="/recruiter/post-job"
              className="px-6 py-3 bg-blue-600 text-white rounded-lg hover:bg-blue-700 font-medium text-sm transition-colors">
              + Post New Job
            </Link>
            <Link href="/recruiter/jobs"
              className="px-6 py-3 bg-gray-100 text-gray-700 rounded-lg hover:bg-gray-200 font-medium text-sm transition-colors">
              View My Postings
            </Link>
            <Link href="/recruiter/candidates"
              className="px-6 py-3 bg-gray-100 text-gray-700 rounded-lg hover:bg-gray-200 font-medium text-sm transition-colors">
              Browse Candidates
            </Link>
          </div>
        </div>

        {/* Recent Jobs */}
        <div className="bg-white rounded-xl shadow-sm border border-gray-200">
          <div className="p-6 border-b border-gray-100">
            <h3 className="text-lg font-semibold text-gray-800">Recent Job Postings</h3>
          </div>
          {loadingData ? (
            <div className="p-6 text-center text-gray-400">Loading...</div>
          ) : recentJobs.length === 0 ? (
            <div className="p-6 text-center text-gray-400">
              <p className="mb-2">No jobs posted yet.</p>
              <Link href="/recruiter/post-job" className="text-blue-600 hover:underline">Post your first job</Link>
            </div>
          ) : (
            <div className="divide-y divide-gray-100">
              {recentJobs.map((job: any) => (
                <div key={job.id} className="p-4 hover:bg-gray-50 transition-colors">
                  <div className="flex justify-between items-start">
                    <div>
                      <h4 className="font-semibold text-gray-800">{job.title}</h4>
                      <p className="text-sm text-gray-500">{job.company_name}</p>
                      <p className="text-xs text-gray-400 mt-1">
                        {job.location_city}, {job.location_country} · {job.location_type} · {job.employment_type}
                      </p>
                    </div>
                    <span className={`px-2 py-1 rounded-full text-xs font-medium ${
                      job.is_active ? 'bg-green-100 text-green-700' : 'bg-gray-100 text-gray-500'
                    }`}>
                      {job.is_active ? 'Active' : 'Inactive'}
                    </span>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </main>
    </div>
  );
}
