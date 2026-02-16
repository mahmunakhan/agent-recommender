'use client';

import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { useAuth } from '@/contexts/AuthContext';
import api, { Job } from '@/lib/api';
import Link from 'next/link';

export default function MyJobsPage() {
  const { user, loading } = useAuth();
  const router = useRouter();
  const [jobs, setJobs] = useState<Job[]>([]);
  const [loadingJobs, setLoadingJobs] = useState(true);
  const [filter, setFilter] = useState<'all' | 'active' | 'inactive'>('all');

  useEffect(() => {
    if (!loading && !user) {
      router.push('/login');
    } else if (!loading && user?.role !== 'recruiter') {
      router.push('/dashboard');
    }
  }, [user, loading, router]);

  useEffect(() => {
    if (user?.role === 'recruiter') {
      fetchJobs();
    }
  }, [user]);

  const fetchJobs = async () => {
    try {
      const response = await api.getMyJobs();
      const myJobs = response.jobs || [];
      setJobs(myJobs);
    } catch (error) {
      console.error('Error fetching jobs:', error);
    } finally {
      setLoadingJobs(false);
    }
  };

  const handleToggleActive = async (jobId: string, currentStatus: boolean) => {
    try {
      await api.updateJob(jobId, { is_active: !currentStatus });
      setJobs(jobs.map(j => j.id === jobId ? { ...j, is_active: !currentStatus } : j));
    } catch (error) {
      console.error('Error updating job:', error);
    }
  };

  const handleDelete = async (jobId: string) => {
    if (!confirm('Are you sure you want to delete this job?')) return;
    
    try {
      await api.deleteJob(jobId);
      setJobs(jobs.filter(j => j.id !== jobId));
    } catch (error) {
      console.error('Error deleting job:', error);
    }
  };

  const filteredJobs = jobs.filter(job => {
    if (filter === 'active') return job.is_active;
    if (filter === 'inactive') return !job.is_active;
    return true;
  });

  if (loading || loadingJobs) {
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
          <h1 className="text-2xl font-bold text-blue-600">My Jobs</h1>
          <div className="flex items-center gap-4">
            <Link href="/recruiter/post-job" className="bg-blue-600 text-white px-4 py-2 rounded-lg hover:bg-blue-700">
              + Post New Job
            </Link>
            <Link href="/recruiter" className="text-blue-600 hover:text-blue-800">
              ← Dashboard
            </Link>
          </div>
        </div>
      </nav>

      <div className="max-w-7xl mx-auto px-4 py-8">
        <div className="bg-white rounded-lg shadow p-4 mb-6">
          <div className="flex gap-4">
            <button
              onClick={() => setFilter('all')}
              className={`px-4 py-2 rounded-lg ${filter === 'all' ? 'bg-blue-600 text-white' : 'bg-gray-100'}`}
            >
              All ({jobs.length})
            </button>
            <button
              onClick={() => setFilter('active')}
              className={`px-4 py-2 rounded-lg ${filter === 'active' ? 'bg-green-600 text-white' : 'bg-gray-100'}`}
            >
              Active ({jobs.filter(j => j.is_active).length})
            </button>
            <button
              onClick={() => setFilter('inactive')}
              className={`px-4 py-2 rounded-lg ${filter === 'inactive' ? 'bg-gray-600 text-white' : 'bg-gray-100'}`}
            >
              Inactive ({jobs.filter(j => !j.is_active).length})
            </button>
          </div>
        </div>

        {filteredJobs.length === 0 ? (
          <div className="bg-white rounded-lg shadow p-8 text-center">
            <p className="text-gray-500 mb-4">No jobs found.</p>
            <Link href="/recruiter/post-job" className="text-blue-600 hover:text-blue-800 font-medium">
              Post your first job →
            </Link>
          </div>
        ) : (
          <div className="space-y-4">
            {filteredJobs.map((job) => (
              <div key={job.id} className="bg-white rounded-lg shadow p-6">
                <div className="flex justify-between items-start">
                  <div className="flex-1">
                    <div className="flex items-center gap-3">
                      <h3 className="text-xl font-semibold">{job.title}</h3>
                      <span className={`px-3 py-1 rounded-full text-sm ${job.is_active ? 'bg-green-100 text-green-800' : 'bg-gray-100 text-gray-800'}`}>
                        {job.is_active ? 'Active' : 'Inactive'}
                      </span>
                    </div>
                    <p className="text-gray-600 mt-1">{job.company_name}</p>
                    <div className="flex flex-wrap gap-4 mt-3 text-sm text-gray-500">
                      <span>📍 {job.location_city || 'N/A'}, {job.location_country || 'N/A'}</span>
                      <span>💼 {job.employment_type?.replace('_', ' ')}</span>
                      <span>🏠 {job.location_type}</span>
                    </div>
                    <p className="text-gray-600 mt-3 line-clamp-2">
                      {job.description_raw?.substring(0, 200)}...
                    </p>
                  </div>
                  <div className="flex flex-col gap-2 ml-4">
                    <button
                      onClick={() => handleToggleActive(job.id, job.is_active)}
                      className={`px-4 py-2 rounded-lg ${job.is_active ? 'bg-yellow-50 text-yellow-600' : 'bg-green-50 text-green-600'}`}
                    >
                      {job.is_active ? 'Deactivate' : 'Activate'}
                    </button>
                    <button
                      onClick={() => handleDelete(job.id)}
                      className="px-4 py-2 bg-red-50 text-red-600 rounded-lg hover:bg-red-100"
                    >
                      Delete
                    </button>
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}