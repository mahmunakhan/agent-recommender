'use client';

import { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import api, { Job, User } from '@/lib/api';
import NotificationBell from '@/components/NotificationBell';

export default function MyJobsPage() {
  const router = useRouter();
  const [user, setUser] = useState<User | null>(null);
  const [jobs, setJobs] = useState<Job[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [filter, setFilter] = useState<'all' | 'active' | 'inactive'>('all');
  const [actionLoading, setActionLoading] = useState<string | null>(null);

  useEffect(() => {
    const token = api.getToken();
    if (!token) {
      router.push('/login');
      return;
    }
    loadData();
  }, [router]);

  const loadData = async () => {
    try {
      const userData = await api.getMe();
      setUser(userData);

      if (userData.role !== 'recruiter' && userData.role !== 'admin') {
        router.push('/dashboard');
        return;
      }

      // Use the new getMyJobs API endpoint
      const response = await api.getMyJobs();
      setJobs(response.jobs || []);
    } catch (err: any) {
      setError(err.message || 'Failed to load jobs');
    } finally {
      setLoading(false);
    }
  };

  const handleToggleActive = async (job: Job) => {
    setActionLoading(job.id);
    try {
      await api.updateJob(job.id, { is_active: !job.is_active });
      // Refresh jobs list
      const response = await api.getMyJobs();
      setJobs(response.jobs || []);
    } catch (err: any) {
      alert('Failed to update job: ' + err.message);
    } finally {
      setActionLoading(null);
    }
  };

  const handleDelete = async (jobId: string) => {
    if (!confirm('Are you sure you want to delete this job? This action cannot be undone.')) {
      return;
    }

    setActionLoading(jobId);
    try {
      await api.deleteJob(jobId);
      // Refresh jobs list
      const response = await api.getMyJobs();
      setJobs(response.jobs || []);
    } catch (err: any) {
      alert('Failed to delete job: ' + err.message);
    } finally {
      setActionLoading(null);
    }
  };

  const filteredJobs = jobs.filter(job => {
    if (filter === 'active') return job.is_active;
    if (filter === 'inactive') return !job.is_active;
    return true;
  });

  const activeCount = jobs.filter(j => j.is_active).length;
  const inactiveCount = jobs.filter(j => !j.is_active).length;

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600"></div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <header className="bg-white shadow-sm">
        <div className="max-w-7xl mx-auto px-4 py-4 flex justify-between items-center">
          <div className="flex items-center gap-4">
            <Link href="/recruiter" className="text-gray-600 hover:text-gray-900">
              â† Back to Dashboard
            </Link>
            <h1 className="text-2xl font-bold text-gray-900">My Posted Jobs</h1>
          </div>
          <div className="flex items-center gap-4">
            <NotificationBell />
            <Link
              href="/recruiter/post-job"
              className="bg-blue-600 text-white px-4 py-2 rounded-md hover:bg-blue-700"
            >
              + Post New Job
            </Link>
          </div>
        </div>
      </header>

      <main className="max-w-7xl mx-auto px-4 py-8">
        {error && (
          <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded mb-6">
            {error}
          </div>
        )}

        {/* Stats Summary */}
        <div className="bg-white rounded-lg shadow p-6 mb-6">
          <div className="grid grid-cols-3 gap-4 text-center">
            <div>
              <p className="text-3xl font-bold text-gray-900">{jobs.length}</p>
              <p className="text-gray-600">Total Jobs</p>
            </div>
            <div>
              <p className="text-3xl font-bold text-green-600">{activeCount}</p>
              <p className="text-gray-600">Active</p>
            </div>
            <div>
              <p className="text-3xl font-bold text-gray-400">{inactiveCount}</p>
              <p className="text-gray-600">Inactive</p>
            </div>
          </div>
        </div>

        {/* Filter Tabs */}
        <div className="flex gap-2 mb-6">
          <button
            onClick={() => setFilter('all')}
            className={`px-4 py-2 rounded-md font-medium ${
              filter === 'all'
                ? 'bg-blue-600 text-white'
                : 'bg-white text-gray-700 hover:bg-gray-50'
            }`}
          >
            All ({jobs.length})
          </button>
          <button
            onClick={() => setFilter('active')}
            className={`px-4 py-2 rounded-md font-medium ${
              filter === 'active'
                ? 'bg-green-600 text-white'
                : 'bg-white text-gray-700 hover:bg-gray-50'
            }`}
          >
            Active ({activeCount})
          </button>
          <button
            onClick={() => setFilter('inactive')}
            className={`px-4 py-2 rounded-md font-medium ${
              filter === 'inactive'
                ? 'bg-gray-600 text-white'
                : 'bg-white text-gray-700 hover:bg-gray-50'
            }`}
          >
            Inactive ({inactiveCount})
          </button>
        </div>

        {/* Jobs List */}
        {filteredJobs.length === 0 ? (
          <div className="bg-white rounded-lg shadow p-12 text-center">
            <div className="text-gray-400 text-6xl mb-4">ðŸ“‹</div>
            <h3 className="text-xl font-medium text-gray-900 mb-2">
              {filter === 'all' ? 'No jobs posted yet' : `No ${filter} jobs`}
            </h3>
            <p className="text-gray-600 mb-6">
              {filter === 'all'
                ? 'Start by posting your first job to attract candidates.'
                : `You don't have any ${filter} jobs at the moment.`}
            </p>
            {filter === 'all' && (
              <Link
                href="/recruiter/post-job"
                className="inline-block bg-blue-600 text-white px-6 py-3 rounded-md hover:bg-blue-700"
              >
                Post Your First Job
              </Link>
            )}
          </div>
        ) : (
          <div className="space-y-4">
            {filteredJobs.map((job) => (
              <div
                key={job.id}
                className={`bg-white rounded-lg shadow p-6 border-l-4 ${
                  job.is_active ? 'border-green-500' : 'border-gray-300'
                }`}
              >
                <div className="flex justify-between items-start">
                  <div className="flex-1">
                    <div className="flex items-center gap-3 mb-2">
                      <h3 className="text-xl font-semibold text-gray-900">{job.title}</h3>
                      <span
                        className={`px-2 py-1 text-xs font-medium rounded ${
                          job.is_active
                            ? 'bg-green-100 text-green-800'
                            : 'bg-gray-100 text-gray-600'
                        }`}
                      >
                        {job.is_active ? 'Active' : 'Inactive'}
                      </span>
                    </div>
                    <p className="text-gray-600 mb-2">{job.company_name}</p>
                    <div className="flex flex-wrap gap-4 text-sm text-gray-500">
                      <span>ðŸ“ {job.location_city || 'Not specified'}, {job.location_country || ''}</span>
                      <span>ðŸ¢ {job.location_type}</span>
                      <span>ðŸ’¼ {job.employment_type?.replace('_', ' ')}</span>
                      {job.salary_min && job.salary_max && (
                        <span>
                          ðŸ’° {job.salary_currency || 'USD'} {job.salary_min.toLocaleString()} - {job.salary_max.toLocaleString()}
                        </span>
                      )}
                      {job.experience_min_years !== undefined && job.experience_min_years !== null && (
                        <span>ðŸ“… {job.experience_min_years}+ years exp</span>
                      )}
                    </div>
                    {job.description_raw && (
                      <p className="text-gray-600 mt-3 text-sm">
                        {job.description_raw.substring(0, 200)}
                        {job.description_raw.length > 200 ? '...' : ''}
                      </p>
                    )}
                    <p className="text-xs text-gray-400 mt-2">
                      Posted: {job.posted_at ? new Date(job.posted_at).toLocaleDateString() : 'N/A'}
                    </p>
                  </div>

                  <div className="flex flex-col gap-2 ml-4">
                    <Link
                      href={`/jobs/${job.id}`}
                      className="px-4 py-2 text-sm text-blue-600 bg-blue-50 rounded hover:bg-blue-100 text-center"
                    >
                      View Details
                    </Link>
                    <Link
                      href={`/recruiter/jobs/${job.id}/edit`}
                      className="px-4 py-2 text-sm text-purple-600 bg-purple-50 rounded hover:bg-purple-100 text-center"
                    >
                      âœï¸ Edit
                    </Link>
                    <button
                      onClick={() => handleToggleActive(job)}
                      disabled={actionLoading === job.id}
                      className={`px-4 py-2 text-sm rounded text-center ${
                        job.is_active
                          ? 'text-orange-600 bg-orange-50 hover:bg-orange-100'
                          : 'text-green-600 bg-green-50 hover:bg-green-100'
                      } disabled:opacity-50`}
                    >
                      {actionLoading === job.id ? '...' : job.is_active ? 'Deactivate' : 'Activate'}
                    </button>
                    <button
                      onClick={() => handleDelete(job.id)}
                      disabled={actionLoading === job.id}
                      className="px-4 py-2 text-sm text-red-600 bg-red-50 rounded hover:bg-red-100 disabled:opacity-50"
                    >
                      {actionLoading === job.id ? '...' : 'ðŸ—‘ï¸ Delete'}
                    </button>
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </main>
    </div>
  );
}

