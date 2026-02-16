'use client';

import { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import api, { Application } from '@/lib/api';
import NotificationBell from '@/components/NotificationBell';

export default function MyApplicationsPage() {
  const router = useRouter();
  const [applications, setApplications] = useState<Application[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [filter, setFilter] = useState<string>('all');
  const [withdrawing, setWithdrawing] = useState<string | null>(null);

  useEffect(() => {
    const token = api.getToken();
    if (!token) {
      router.push('/login');
      return;
    }
    loadApplications();
  }, [router]);

  const loadApplications = async () => {
    try {
      const response = await api.getMyApplications();
      setApplications(response.applications || []);
    } catch (err: any) {
      setError(err.message || 'Failed to load applications');
    } finally {
      setLoading(false);
    }
  };

  const handleWithdraw = async (applicationId: string) => {
    if (!confirm('Are you sure you want to withdraw this application?')) {
      return;
    }

    setWithdrawing(applicationId);
    try {
      await api.withdrawApplication(applicationId);
      await loadApplications();
    } catch (err: any) {
      alert(err.message || 'Failed to withdraw application');
    } finally {
      setWithdrawing(null);
    }
  };

  const getStatusColor = (status: string) => {
    const colors: Record<string, string> = {
      applied: 'bg-blue-100 text-blue-800',
      screening: 'bg-yellow-100 text-yellow-800',
      shortlisted: 'bg-green-100 text-green-800',
      interview_scheduled: 'bg-purple-100 text-purple-800',
      interviewed: 'bg-indigo-100 text-indigo-800',
      offer_extended: 'bg-emerald-100 text-emerald-800',
      offer_accepted: 'bg-green-200 text-green-900',
      offer_declined: 'bg-gray-100 text-gray-800',
      rejected: 'bg-red-100 text-red-800',
      withdrawn: 'bg-gray-200 text-gray-600',
    };
    return colors[status] || 'bg-gray-100 text-gray-800';
  };

  const getStatusLabel = (status: string) => {
    return status.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase());
  };

  const filteredApplications = applications.filter(app => {
    if (filter === 'all') return true;
    if (filter === 'active') return !['rejected', 'withdrawn', 'offer_declined'].includes(app.status);
    if (filter === 'inactive') return ['rejected', 'withdrawn', 'offer_declined'].includes(app.status);
    return app.status === filter;
  });

  const statusCounts = applications.reduce((acc, app) => {
    acc[app.status] = (acc[app.status] || 0) + 1;
    return acc;
  }, {} as Record<string, number>);

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
            <Link href="/dashboard" className="text-gray-600 hover:text-gray-900">
              ← Back to Dashboard
            </Link>
            <h1 className="text-2xl font-bold text-gray-900">My Applications</h1>
          </div>
          <div className="flex items-center gap-4">
            <NotificationBell />
            <Link
              href="/jobs"
              className="bg-blue-600 text-white px-4 py-2 rounded-md hover:bg-blue-700"
            >
              Browse Jobs
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
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-center">
            <div>
              <p className="text-3xl font-bold text-gray-900">{applications.length}</p>
              <p className="text-gray-600">Total</p>
            </div>
            <div>
              <p className="text-3xl font-bold text-blue-600">{statusCounts['applied'] || 0}</p>
              <p className="text-gray-600">Applied</p>
            </div>
            <div>
              <p className="text-3xl font-bold text-green-600">{statusCounts['shortlisted'] || 0}</p>
              <p className="text-gray-600">Shortlisted</p>
            </div>
            <div>
              <p className="text-3xl font-bold text-purple-600">{statusCounts['interview_scheduled'] || 0}</p>
              <p className="text-gray-600">Interviews</p>
            </div>
          </div>
        </div>

        {/* Filter Tabs */}
        <div className="flex flex-wrap gap-2 mb-6">
          {['all', 'active', 'applied', 'shortlisted', 'interview_scheduled', 'rejected', 'withdrawn'].map((status) => (
            <button
              key={status}
              onClick={() => setFilter(status)}
              className={`px-4 py-2 rounded-md font-medium text-sm ${
                filter === status
                  ? 'bg-blue-600 text-white'
                  : 'bg-white text-gray-700 hover:bg-gray-50'
              }`}
            >
              {status === 'all' ? 'All' : getStatusLabel(status)}
            </button>
          ))}
        </div>

        {/* Applications List */}
        {filteredApplications.length === 0 ? (
          <div className="bg-white rounded-lg shadow p-12 text-center">
            <div className="text-gray-400 text-6xl mb-4">📄</div>
            <h3 className="text-xl font-medium text-gray-900 mb-2">No applications yet</h3>
            <p className="text-gray-600 mb-6">
              Start applying to jobs to see them here.
            </p>
            <Link
              href="/jobs"
              className="inline-block bg-blue-600 text-white px-6 py-3 rounded-md hover:bg-blue-700"
            >
              Browse Jobs
            </Link>
          </div>
        ) : (
          <div className="space-y-4">
            {filteredApplications.map((app) => (
              <div
                key={app.id}
                className="bg-white rounded-lg shadow p-6"
              >
                <div className="flex justify-between items-start">
                  <div className="flex-1">
                    <div className="flex items-center gap-3 mb-2">
                      <h3 className="text-xl font-semibold text-gray-900">{app.job_title}</h3>
                      <span className={`px-2 py-1 text-xs font-medium rounded ${getStatusColor(app.status)}`}>
                        {getStatusLabel(app.status)}
                      </span>
                    </div>
                    <p className="text-gray-600 mb-2">{app.company_name}</p>
                    <div className="flex flex-wrap gap-4 text-sm text-gray-500">
                      {app.location_city && (
                        <span>📍 {app.location_city}, {app.location_country}</span>
                      )}
                      {app.employment_type && (
                        <span>💼 {app.employment_type.replace('_', ' ')}</span>
                      )}
                      <span>📅 Applied: {new Date(app.applied_at).toLocaleDateString()}</span>
                    </div>
                    {app.rejection_reason && (
                      <p className="text-red-600 text-sm mt-2">
                        Reason: {app.rejection_reason}
                      </p>
                    )}
                  </div>

                  <div className="flex flex-col gap-2 ml-4">
                    <Link
                      href={`/jobs/${app.job_id}`}
                      className="px-4 py-2 text-sm text-blue-600 bg-blue-50 rounded hover:bg-blue-100 text-center"
                    >
                      View Job
                    </Link>
                    {['applied', 'screening'].includes(app.status) && (
                      <button
                        onClick={() => handleWithdraw(app.id)}
                        disabled={withdrawing === app.id}
                        className="px-4 py-2 text-sm text-red-600 bg-red-50 rounded hover:bg-red-100 disabled:opacity-50"
                      >
                        {withdrawing === app.id ? '...' : 'Withdraw'}
                      </button>
                    )}
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

