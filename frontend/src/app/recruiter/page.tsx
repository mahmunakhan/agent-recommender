'use client';

import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { useAuth } from '@/contexts/AuthContext';
import api, { Job } from '@/lib/api';
import NotificationBell from '@/components/NotificationBell';
import Link from 'next/link';

export default function RecruiterDashboard() {
  const { user, loading } = useAuth();
  const router = useRouter();
  const [jobs, setJobs] = useState<Job[]>([]);
  const [stats, setStats] = useState({
    totalJobs: 0,
    activeJobs: 0,
    totalApplications: 0,
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
      
      setStats({
        totalJobs: myJobs.length,
        activeJobs: myJobs.filter((j: Job) => j.is_active).length,
        totalApplications: 0,
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
        <div className="text-xl">Loading...</div>
      </div>
    );
  }

  if (!user || user.role !== 'recruiter') {
    return null;
  }

  return (
    <div className="min-h-screen bg-gray-50">
      <nav className="bg-white shadow-sm">
        <div className="max-w-7xl mx-auto px-4 py-4 flex justify-between items-center">
          <h1 className="text-2xl font-bold text-blue-600">Recruiter Portal</h1>
          <div className="flex items-center gap-4">
              <NotificationBell />
            <span className="text-gray-600">Welcome, {user.first_name || user.email}</span>
            <Link href="/dashboard" className="text-blue-600 hover:text-blue-800">
              Main Dashboard
            </Link>
          </div>
        </div>
      </nav>

      <div className="max-w-7xl mx-auto px-4 py-8">
        {/* Stats Cards */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-8">
          <div className="bg-white rounded-lg shadow p-6">
            <div className="text-4xl font-bold text-blue-600">{stats.totalJobs}</div>
            <div className="text-gray-600 mt-1">Total Jobs Posted</div>
          </div>
          <div className="bg-white rounded-lg shadow p-6">
            <div className="text-4xl font-bold text-green-600">{stats.activeJobs}</div>
            <div className="text-gray-600 mt-1">Active Jobs</div>
          </div>
          <div className="bg-white rounded-lg shadow p-6">
            <div className="text-4xl font-bold text-purple-600">{stats.totalApplications}</div>
            <div className="text-gray-600 mt-1">Total Applications</div>
          </div>
        </div>

        {/* Quick Actions */}
        <div className="bg-white rounded-lg shadow p-6 mb-8">
          <h2 className="text-xl font-semibold mb-4">Quick Actions</h2>
          <div className="flex gap-4">
            <Link
              href="/recruiter/post-job"
              className="bg-blue-600 text-white px-6 py-3 rounded-lg hover:bg-blue-700 font-medium"
            >
              + Post New Job
            </Link>
            <Link
              href="/recruiter/my-jobs"
              className="bg-gray-100 text-gray-700 px-6 py-3 rounded-lg hover:bg-gray-200 font-medium"
            >
              View My Jobs
            </Link>
          </div>
        </div>

        {/* Recent Jobs */}
        <div className="bg-white rounded-lg shadow p-6">
          <div className="flex justify-between items-center mb-4">
            <h2 className="text-xl font-semibold">Recent Jobs</h2>
            <Link href="/recruiter/my-jobs" className="text-blue-600 hover:text-blue-800">
              View All â†’
            </Link>
          </div>
          
          {jobs.length === 0 ? (
            <div className="text-center py-8 text-gray-500">
              <p className="mb-4">You haven&apos;t posted any jobs yet.</p>
              <Link
                href="/recruiter/post-job"
                className="text-blue-600 hover:text-blue-800 font-medium"
              >
                Post your first job â†’
              </Link>
            </div>
          ) : (
            <div className="space-y-4">
              {jobs.slice(0, 5).map((job) => (
                <div
                  key={job.id}
                  className="border rounded-lg p-4 hover:border-blue-300 transition-colors"
                >
                  <div className="flex justify-between items-start">
                    <div>
                      <h3 className="font-semibold text-lg">{job.title}</h3>
                      <p className="text-gray-600">{job.company_name}</p>
                      <div className="flex gap-4 mt-2 text-sm text-gray-500">
                        <span>ðŸ“ {job.location_city}, {job.location_country}</span>
                        <span>ðŸ’¼ {job.employment_type?.replace('_', ' ')}</span>
                        <span>ðŸ  {job.location_type}</span>
                      </div>
                    </div>
                    <div className="flex flex-col items-end gap-2">
                      <span
                        className={`px-3 py-1 rounded-full text-sm ${
                          job.is_active
                            ? 'bg-green-100 text-green-800'
                            : 'bg-gray-100 text-gray-800'
                        }`}
                      >
                        {job.is_active ? 'Active' : 'Inactive'}
                      </span>
                      <Link
                        href={`/recruiter/jobs/${job.id}`}
                        className="text-blue-600 hover:text-blue-800 text-sm"
                      >
                        View Details â†’
                      </Link>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
