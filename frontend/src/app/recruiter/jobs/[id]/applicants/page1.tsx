'use client';

import { useState, useEffect } from 'react';
import { useRouter, useParams } from 'next/navigation';
import Link from 'next/link';
import api, { Application } from '@/lib/api';
import NotificationBell from '@/components/NotificationBell';

export default function ViewApplicantsPage() {
  const router = useRouter();
  const params = useParams();
  const jobId = params.id as string;

  const [job, setJob] = useState<any>(null);
  const [applications, setApplications] = useState<Application[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [statusFilter, setStatusFilter] = useState('all');
  const [selectedApp, setSelectedApp] = useState<Application | null>(null);
  const [updating, setUpdating] = useState(false);
  const [newStatus, setNewStatus] = useState('');
  const [recruiterNotes, setRecruiterNotes] = useState('');

  const statuses = [
    { value: 'all', label: 'All Applicants' },
    { value: 'applied', label: 'Applied' },
    { value: 'screening', label: 'Screening' },
    { value: 'shortlisted', label: 'Shortlisted' },
    { value: 'interview_scheduled', label: 'Interview Scheduled' },
    { value: 'interviewed', label: 'Interviewed' },
    { value: 'offer_extended', label: 'Offer Extended' },
    { value: 'rejected', label: 'Rejected' },
    { value: 'withdrawn', label: 'Withdrawn' },
  ];

  useEffect(() => {
    const token = api.getToken();
    if (!token) {
      router.push('/login');
      return;
    }
    loadData();
  }, [router, jobId, statusFilter]);

  const loadData = async () => {
    try {
      const [userData, jobData] = await Promise.all([
        api.getMe(),
        api.getJob(jobId)
      ]);

      if (userData.role !== 'recruiter') {
        router.push('/dashboard');
        return;
      }

      if (jobData.posted_by_id !== userData.id) {
        setError('You do not have permission to view applicants for this job');
        setLoading(false);
        return;
      }

      setJob(jobData);

      const filterStatus = statusFilter === 'all' ? undefined : statusFilter;
      const apps = await api.getJobApplications(jobId, filterStatus);
      setApplications(apps.applications || []);
    } catch (err: any) {
      setError(err.message || 'Failed to load applicants');
    } finally {
      setLoading(false);
    }
  };

  const handleUpdateStatus = async () => {
    if (!selectedApp || !newStatus) return;
    
    setUpdating(true);
    try {
      await api.updateApplication(selectedApp.id, {
        status: newStatus,
        recruiter_notes: recruiterNotes || undefined
      });
      
      setApplications(apps => apps.map(a => 
        a.id === selectedApp.id 
          ? { ...a, status: newStatus, recruiter_notes: recruiterNotes }
          : a
      ));
      
      setSelectedApp(null);
      setNewStatus('');
      setRecruiterNotes('');
    } catch (err: any) {
      alert(err.message || 'Failed to update application');
    } finally {
      setUpdating(false);
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
      offer_declined: 'bg-orange-100 text-orange-800',
      rejected: 'bg-red-100 text-red-800',
      withdrawn: 'bg-gray-200 text-gray-600',
    };
    return colors[status] || 'bg-gray-100 text-gray-800';
  };

  const openUpdateModal = (app: Application) => {
    setSelectedApp(app);
    setNewStatus(app.status);
    setRecruiterNotes(app.recruiter_notes || '');
  };

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600"></div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="text-center">
          <p className="text-red-600 mb-4">{error}</p>
          <Link href="/recruiter/my-jobs" className="text-blue-600 hover:underline">Back to My Jobs</Link>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50">
      <header className="bg-white shadow-sm">
        <div className="max-w-6xl mx-auto px-4 py-4 flex justify-between items-center">
          <div>
            <Link href="/recruiter/my-jobs" className="text-gray-600 hover:text-gray-900">Back to My Jobs</Link>
            <h1 className="text-2xl font-bold text-gray-900 mt-2">Applicants for {job?.title}</h1>
            <p className="text-gray-600">{job?.company_name}</p>
          </div>
          <div className="flex items-center gap-4">
            <NotificationBell />
            <div className="text-right">
              <p className="text-2xl font-bold text-blue-600">{applications.length}</p>
              <p className="text-gray-500">Total Applicants</p>
            </div>
          </div>
        </div>
      </header>

      <main className="max-w-6xl mx-auto px-4 py-8">
        {/* Status Filter */}
        <div className="bg-white rounded-lg shadow p-4 mb-6">
          <div className="flex flex-wrap gap-2">
            {statuses.map(status => (
              <button
                key={status.value}
                onClick={() => setStatusFilter(status.value)}
                className={`px-4 py-2 rounded-md text-sm font-medium transition ${
                  statusFilter === status.value
                    ? 'bg-blue-600 text-white'
                    : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
                }`}
              >
                {status.label}
              </button>
            ))}
          </div>
        </div>

        {/* Applicants List */}
        {applications.length === 0 ? (
          <div className="bg-white rounded-lg shadow p-8 text-center">
            <p className="text-gray-500 text-lg">No applicants found</p>
            {statusFilter !== 'all' && (
              <button
                onClick={() => setStatusFilter('all')}
                className="mt-4 text-blue-600 hover:underline"
              >
                View all applicants
              </button>
            )}
          </div>
        ) : (
          <div className="space-y-4">
            {applications.map(app => (
              <div key={app.id} className="bg-white rounded-lg shadow p-6">
                <div className="flex justify-between items-start">
                  <div className="flex-1">
                    <div className="flex items-center gap-3 mb-2">
                      <h3 className="text-xl font-semibold text-gray-900">
                        {app.applicant_name || 'Unknown Applicant'}
                      </h3>
                      <span className={`px-3 py-1 rounded-full text-sm font-medium ${getStatusColor(app.status)}`}>
                        {app.status.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase())}
                      </span>
                    </div>
                    
                    <p className="text-gray-600 mb-2">{app.applicant_email}</p>
                    
                    <div className="flex flex-wrap gap-4 text-sm text-gray-500 mb-3">
                      {app.headline && <span>Title: {app.headline}</span>}
                      {app.years_experience !== null && app.years_experience !== undefined && (
                        <span>Experience: {app.years_experience} years</span>
                      )}
                      <span>Applied: {new Date(app.applied_at).toLocaleDateString()}</span>
                      {app.match_score_at_apply && (
                        <span className="text-green-600 font-medium">
                          Match Score: {app.match_score_at_apply.toFixed(0)}%
                        </span>
                      )}
                    </div>

                    {app.cover_letter && (
                      <div className="mt-3 p-3 bg-gray-50 rounded-md">
                        <p className="text-sm font-medium text-gray-700 mb-1">Cover Letter:</p>
                        <p className="text-sm text-gray-600 whitespace-pre-wrap">{app.cover_letter}</p>
                      </div>
                    )}

                    {app.recruiter_notes && (
                      <div className="mt-3 p-3 bg-yellow-50 rounded-md">
                        <p className="text-sm font-medium text-yellow-800 mb-1">Your Notes:</p>
                        <p className="text-sm text-yellow-700">{app.recruiter_notes}</p>
                      </div>
                    )}
                  </div>

                  <div className="ml-4 flex flex-col gap-2">
                    <button
                      onClick={() => openUpdateModal(app)}
                      className="px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 text-sm"
                    >
                      Update Status
                    </button>
                    <Link
                      href={`/profile/${app.user_id}`}
                      className="px-4 py-2 bg-gray-100 text-gray-700 rounded-md hover:bg-gray-200 text-sm text-center"
                    >
                      View Profile
                    </Link>
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </main>

      {/* Update Status Modal */}
      {selectedApp && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg shadow-xl max-w-md w-full mx-4 p-6">
            <h2 className="text-xl font-bold text-gray-900 mb-4">
              Update Application Status
            </h2>
            <p className="text-gray-600 mb-4">{selectedApp.applicant_name}</p>

            <div className="mb-4">
              <label className="block text-sm font-medium text-gray-700 mb-2">Status</label>
              <select
                value={newStatus}
                onChange={(e) => setNewStatus(e.target.value)}
                className="w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-blue-500 focus:border-blue-500"
              >
                <option value="applied">Applied</option>
                <option value="screening">Screening</option>
                <option value="shortlisted">Shortlisted</option>
                <option value="interview_scheduled">Interview Scheduled</option>
                <option value="interviewed">Interviewed</option>
                <option value="offer_extended">Offer Extended</option>
                <option value="offer_accepted">Offer Accepted</option>
                <option value="offer_declined">Offer Declined</option>
                <option value="rejected">Rejected</option>
              </select>
            </div>

            <div className="mb-4">
              <label className="block text-sm font-medium text-gray-700 mb-2">Notes (Private)</label>
              <textarea
                value={recruiterNotes}
                onChange={(e) => setRecruiterNotes(e.target.value)}
                rows={4}
                className="w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-blue-500 focus:border-blue-500"
                placeholder="Add private notes about this candidate..."
              />
            </div>

            <div className="flex gap-3 justify-end">
              <button
                onClick={() => setSelectedApp(null)}
                className="px-4 py-2 text-gray-700 bg-gray-100 rounded-md hover:bg-gray-200"
              >
                Cancel
              </button>
              <button
                onClick={handleUpdateStatus}
                disabled={updating}
                className="px-6 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 disabled:opacity-50"
              >
                {updating ? 'Updating...' : 'Update'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

