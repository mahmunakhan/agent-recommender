'use client';

import { useState, useEffect } from 'react';
import { useRouter, useParams } from 'next/navigation';
import Link from 'next/link';
import api, { Job, Skill } from '@/lib/api';

export default function JobDetailsPage() {
  const router = useRouter();
  const params = useParams();
  const jobId = params.id as string;

  const [job, setJob] = useState<Job | null>(null);
  const [user, setUser] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  
  const [hasApplied, setHasApplied] = useState(false);
  const [applicationStatus, setApplicationStatus] = useState<string | null>(null);
  const [showApplyModal, setShowApplyModal] = useState(false);
  const [coverLetter, setCoverLetter] = useState('');
  const [applying, setApplying] = useState(false);
  const [applySuccess, setApplySuccess] = useState(false);

  useEffect(() => {
    const token = api.getToken();
    if (!token) {
      router.push('/login');
      return;
    }
    loadData();
  }, [router, jobId]);

  const loadData = async () => {
    try {
      const [userData, jobData] = await Promise.all([
        api.getMe(),
        api.getJob(jobId)
      ]);
      
      setUser(userData);
      setJob(jobData);

      if (userData.role === 'candidate') {
        try {
          const appStatus = await api.checkApplicationStatus(jobId);
          setHasApplied(appStatus.applied);
          setApplicationStatus(appStatus.status || null);
        } catch (err) {}
      }
    } catch (err: any) {
      setError(err.message || 'Failed to load job details');
    } finally {
      setLoading(false);
    }
  };

  const handleApply = async () => {
    setApplying(true);
    try {
      await api.applyToJob(jobId, coverLetter || undefined, 'direct');
      setApplySuccess(true);
      setHasApplied(true);
      setApplicationStatus('applied');
      setShowApplyModal(false);
      setCoverLetter('');
    } catch (err: any) {
      alert(err.message || 'Failed to apply');
    } finally {
      setApplying(false);
    }
  };

  const getStatusColor = (status: string) => {
    const colors: Record<string, string> = {
      applied: 'bg-blue-100 text-blue-800',
      screening: 'bg-yellow-100 text-yellow-800',
      shortlisted: 'bg-green-100 text-green-800',
      interview_scheduled: 'bg-purple-100 text-purple-800',
      rejected: 'bg-red-100 text-red-800',
      withdrawn: 'bg-gray-200 text-gray-600',
    };
    return colors[status] || 'bg-gray-100 text-gray-800';
  };

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600"></div>
      </div>
    );
  }

  if (error || !job) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="text-center">
          <p className="text-red-600 mb-4">{error || 'Job not found'}</p>
          <Link href="/jobs" className="text-blue-600 hover:underline">Back to Jobs</Link>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50">
      <header className="bg-white shadow-sm">
        <div className="max-w-4xl mx-auto px-4 py-4">
          <Link href="/jobs" className="text-gray-600 hover:text-gray-900">Back to Jobs</Link>
        </div>
      </header>

      <main className="max-w-4xl mx-auto px-4 py-8">
        {applySuccess && (
          <div className="bg-green-50 border border-green-200 text-green-700 px-4 py-3 rounded mb-6">
            Application submitted successfully! <Link href="/applications" className="underline">View your applications</Link>
          </div>
        )}

        <div className="bg-white rounded-lg shadow p-6 mb-6">
          <div className="flex justify-between items-start">
            <div>
              <div className="flex items-center gap-3 mb-2">
                <h1 className="text-3xl font-bold text-gray-900">{job.title}</h1>
                {!job.is_active && (
                  <span className="px-2 py-1 text-xs font-medium rounded bg-gray-100 text-gray-600">Closed</span>
                )}
              </div>
              <p className="text-xl text-gray-600 mb-4">{job.company_name}</p>
              
              <div className="flex flex-wrap gap-4 text-gray-500">
                {job.location_city && <span>Location: {job.location_city}, {job.location_country}</span>}
                <span>Type: {job.location_type}</span>
                <span>Employment: {job.employment_type?.replace('_', ' ')}</span>
                {job.experience_min_years !== null && job.experience_min_years !== undefined && (
                  <span>Experience: {job.experience_min_years}+ years</span>
                )}
              </div>

              {job.salary_min && job.salary_max && (
                <p className="mt-3 text-lg font-medium text-green-600">
                  Salary: {job.salary_currency || 'USD'} {job.salary_min.toLocaleString()} - {job.salary_max.toLocaleString()}
                </p>
              )}
            </div>

            <div className="text-right">
              {user?.role === 'candidate' && (
                <>
                  {hasApplied ? (
                    <div className="text-center">
                      <span className={`inline-block px-4 py-2 rounded-md font-medium ${getStatusColor(applicationStatus || 'applied')}`}>
                        {applicationStatus?.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase()) || 'Applied'}
                      </span>
                      <p className="text-sm text-gray-500 mt-2">
                        <Link href="/applications" className="text-blue-600 hover:underline">View application</Link>
                      </p>
                    </div>
                  ) : job.is_active ? (
                    <button
                      onClick={() => setShowApplyModal(true)}
                      className="bg-blue-600 text-white px-6 py-3 rounded-md hover:bg-blue-700 font-medium text-lg"
                    >
                      Apply Now
                    </button>
                  ) : (
                    <span className="text-gray-500">No longer accepting applications</span>
                  )}
                </>
              )}

              {user?.role === 'recruiter' && job.posted_by_id === user.id && (
                <div className="flex flex-col gap-2">
                  <Link href={`/recruiter/jobs/${job.id}/applicants`} className="bg-green-600 text-white px-4 py-2 rounded-md hover:bg-green-700 text-center">
                    View Applicants
                  </Link>
                  <Link href={`/recruiter/jobs/${job.id}/edit`} className="bg-purple-600 text-white px-4 py-2 rounded-md hover:bg-purple-700 text-center">
                    Edit Job
                  </Link>
                </div>
              )}
            </div>
          </div>
        </div>

        <div className="bg-white rounded-lg shadow p-6 mb-6">
          <h2 className="text-xl font-semibold text-gray-900 mb-4">Job Description</h2>
          <div className="prose max-w-none text-gray-700 whitespace-pre-wrap">{job.description_raw}</div>
        </div>

        {job.skills && job.skills.length > 0 && (
          <div className="bg-white rounded-lg shadow p-6 mb-6">
            <h2 className="text-xl font-semibold text-gray-900 mb-4">Required Skills</h2>
            <div className="flex flex-wrap gap-2">
              {job.skills.map((skill: any, index: number) => (
                <span key={index} className={`px-3 py-1 rounded-full text-sm font-medium ${
                  skill.requirement_type === 'required' ? 'bg-red-100 text-red-800' :
                  skill.requirement_type === 'preferred' ? 'bg-yellow-100 text-yellow-800' : 'bg-gray-100 text-gray-800'
                }`}>
                  {skill.skill_name || skill.name}
                </span>
              ))}
            </div>
          </div>
        )}

        <div className="text-center text-gray-500 text-sm">
          Posted: {job.posted_at ? new Date(job.posted_at).toLocaleDateString() : 'N/A'}
        </div>
      </main>

      {showApplyModal && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg shadow-xl max-w-lg w-full mx-4 p-6">
            <h2 className="text-2xl font-bold text-gray-900 mb-4">Apply to {job.title}</h2>
            <p className="text-gray-600 mb-4">{job.company_name}</p>
            <div className="mb-4">
              <label className="block text-sm font-medium text-gray-700 mb-2">Cover Letter (Optional)</label>
              <textarea
                value={coverLetter}
                onChange={(e) => setCoverLetter(e.target.value)}
                rows={6}
                className="w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-blue-500 focus:border-blue-500"
                placeholder="Tell the employer why you are a great fit for this role..."
              />
            </div>
            <div className="flex gap-3 justify-end">
              <button onClick={() => setShowApplyModal(false)} className="px-4 py-2 text-gray-700 bg-gray-100 rounded-md hover:bg-gray-200">
                Cancel
              </button>
              <button onClick={handleApply} disabled={applying} className="px-6 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 disabled:opacity-50">
                {applying ? 'Submitting...' : 'Submit Application'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
