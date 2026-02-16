'use client';

import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import { useAuth } from '@/contexts/AuthContext';
import { api, Job } from '@/lib/api';
import NotificationBell from '@/components/NotificationBell';

export default function JobsPage() {
  const { user, loading, logout } = useAuth();
  const router = useRouter();
  const [jobs, setJobs] = useState<(Job & { similarity_score?: number })[]>([]);
  const [searchQuery, setSearchQuery] = useState('');
  const [loadingJobs, setLoadingJobs] = useState(false);
  const [searchMode, setSearchMode] = useState<'list' | 'semantic'>('list');

  useEffect(() => {
    if (!loading && !user) {
      router.push('/login');
    }
  }, [user, loading, router]);

  useEffect(() => {
    if (user) {
      loadJobs();
    }
  }, [user]);

  const loadJobs = async () => {
    setLoadingJobs(true);
    try {
      const data = await api.getJobs();
      setJobs(data || []);
      setSearchMode('list');
    } catch (err) {
      console.error('Failed to load jobs:', err);
      setJobs([]);
    } finally {
      setLoadingJobs(false);
    }
  };

  const handleSearch = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!searchQuery.trim()) {
      loadJobs();
      return;
    }

    setLoadingJobs(true);
    try {
      const data = await api.searchJobsSemantic(searchQuery);
      setJobs(data.jobs || []);
      setSearchMode('semantic');
    } catch (err) {
      console.error('Search failed:', err);
      setJobs([]);
    } finally {
      setLoadingJobs(false);
    }
  };

  if (loading || !user) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="text-lg">Loading...</div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-100">
      <nav className="bg-white shadow-sm">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex justify-between h-16">
            <div className="flex items-center">
              <h1 className="text-xl font-bold text-blue-600">JobMatch AI</h1>
              <div className="ml-10 flex space-x-4">
                <Link href="/dashboard" className="text-gray-500 hover:text-gray-900 px-3 py-2 rounded-md text-sm font-medium">
                  Dashboard
                </Link>
                <Link href="/jobs" className="text-gray-900 px-3 py-2 rounded-md text-sm font-medium">
                  Jobs
                </Link>
                <Link href="/applications" className="text-gray-500 hover:text-gray-900 px-3 py-2 rounded-md text-sm font-medium">
                  My Applications
                </Link>
                <Link href="/profile" className="text-gray-500 hover:text-gray-900 px-3 py-2 rounded-md text-sm font-medium">
                  Profile
                </Link>
              </div>
            </div>
            <div className="flex items-center space-x-4">
              <NotificationBell />
              <span className="text-sm text-gray-700">{user.first_name} {user.last_name}</span>
              <button onClick={logout} className="text-sm text-red-600 hover:text-red-800">Logout</button>
            </div>
          </div>
        </div>
      </nav>

      <main className="max-w-7xl mx-auto py-6 sm:px-6 lg:px-8">
        <div className="px-4 py-6 sm:px-0">
          <h2 className="text-2xl font-bold text-gray-900 mb-6">Find Jobs</h2>

          <form onSubmit={handleSearch} className="mb-6">
            <div className="flex gap-4">
              <input
                type="text"
                placeholder="Search jobs with AI..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="flex-1 px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
              />
              <button type="submit" className="px-6 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700">
                Search
              </button>
              {searchMode === 'semantic' && (
                <button type="button" onClick={loadJobs} className="px-4 py-2 bg-gray-200 text-gray-700 rounded-lg hover:bg-gray-300">
                  Clear
                </button>
              )}
            </div>
          </form>

          {searchMode === 'semantic' && (
            <p className="text-sm text-gray-600 mb-4">Showing AI-powered semantic search results</p>
          )}

          {loadingJobs ? (
            <div className="text-center py-8">Loading jobs...</div>
          ) : jobs && jobs.length > 0 ? (
            <div className="space-y-4">
              {jobs.map((job) => (
                <Link href={'/jobs/' + job.id} key={job.id}>
                  <div className="bg-white rounded-lg shadow p-6 hover:shadow-md transition-shadow cursor-pointer mb-4">
                    <div className="flex justify-between items-start">
                      <div className="flex-1">
                        <h3 className="text-lg font-semibold text-gray-900">{job.title}</h3>
                        <p className="text-gray-600">{job.company_name}</p>
                        <p className="text-sm text-gray-500 mt-1">
                          {job.location_city}, {job.location_country} - {job.location_type} - {job.employment_type}
                        </p>
                        {job.salary_min && job.salary_max && (
                          <p className="text-sm text-green-600 mt-1">
                            {job.salary_currency || 'USD'} {job.salary_min.toLocaleString()} - {job.salary_max.toLocaleString()}
                          </p>
                        )}
                        {job.experience_min_years > 0 && (
                          <p className="text-sm text-gray-500">{job.experience_min_years}+ years experience</p>
                        )}
                      </div>
                      <div className="text-right">
                        {job.similarity_score && (
                          <span className="inline-block bg-blue-100 text-blue-800 text-sm px-3 py-1 rounded-full">
                            {(job.similarity_score * 100).toFixed(1)}% match
                          </span>
                        )}
                      </div>
                    </div>
                  </div>
                </Link>
              ))}
            </div>
          ) : (
            <div className="text-center py-8 text-gray-500">No jobs found</div>
          )}
        </div>
      </main>
    </div>
  );
}

