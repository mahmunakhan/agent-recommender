'use client';

import { useEffect, useState, useCallback } from 'react';
import { useRouter } from 'next/navigation';
import { useAuth } from '@/contexts/AuthContext';
import Navbar from '@/components/Navbar';
import { api } from '@/lib/api';

interface TalentSkill {
  name: string;
  level: string;
}

interface Talent {
  user_id: string;
  profile_id: string;
  name: string;
  email: string;
  headline: string;
  summary: string;
  location_city: string;
  location_country: string;
  years_experience: number;
  desired_role: string;
  is_open_to_work: boolean;
  is_verified: boolean;
  skills: TalentSkill[];
  created_at: string | null;
}

interface RecruiterJob {
  id: string;
  title: string;
  company_name: string;
  is_active: boolean;
}

export default function TalentsPage() {
  const { user, loading } = useAuth();
  const router = useRouter();
  const [talents, setTalents] = useState<Talent[]>([]);
  const [loadingTalents, setLoadingTalents] = useState(true);
  const [totalPages, setTotalPages] = useState(1);
  const [currentPage, setCurrentPage] = useState(1);
  const [totalCount, setTotalCount] = useState(0);

  // Filters
  const [search, setSearch] = useState('');
  const [skillsFilter, setSkillsFilter] = useState('');
  const [locationFilter, setLocationFilter] = useState('');
  const [minExp, setMinExp] = useState('');
  const [maxExp, setMaxExp] = useState('');
  const [openOnly, setOpenOnly] = useState(false);
  const [sortBy, setSortBy] = useState('recent');

  // Invite modal
  const [inviteModal, setInviteModal] = useState<{ talent: Talent } | null>(null);
  const [recruiterJobs, setRecruiterJobs] = useState<RecruiterJob[]>([]);
  const [selectedJobId, setSelectedJobId] = useState('');
  const [inviteMessage, setInviteMessage] = useState('');
  const [sending, setSending] = useState(false);
  const [notification, setNotification] = useState<{ type: 'success' | 'error'; text: string } | null>(null);

  // Expanded profile
  const [expandedProfile, setExpandedProfile] = useState<string | null>(null);
  const [profileDetail, setProfileDetail] = useState<any>(null);
  const [loadingDetail, setLoadingDetail] = useState(false);

  useEffect(() => {
    if (!loading && !user) router.push('/login');
    if (!loading && user && user.role !== 'recruiter') router.push('/dashboard');
  }, [user, loading, router]);

  const loadTalents = useCallback(async (page = 1) => {
    setLoadingTalents(true);
    try {
      const params = new URLSearchParams();
      params.set('page', String(page));
      params.set('page_size', '20');
      params.set('sort_by', sortBy);
      if (search) params.set('search', search);
      if (skillsFilter) params.set('skills', skillsFilter);
      if (locationFilter) params.set('location', locationFilter);
      if (minExp) params.set('min_experience', minExp);
      if (maxExp) params.set('max_experience', maxExp);
      if (openOnly) params.set('is_open_to_work', 'true');

      const token = localStorage.getItem('token');
      const resp = await fetch(`http://localhost:8000/recruiter/talents?${params.toString()}`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!resp.ok) throw new Error('Failed to load talents');
      const data = await resp.json();
      setTalents(data.talents || []);
      setTotalPages(data.total_pages || 1);
      setTotalCount(data.total || 0);
      setCurrentPage(page);
    } catch (err) {
      console.error('Failed to load talents:', err);
    } finally {
      setLoadingTalents(false);
    }
  }, [search, skillsFilter, locationFilter, minExp, maxExp, openOnly, sortBy]);

  useEffect(() => {
    if (user && user.role === 'recruiter') {
      loadTalents(1);
    }
  }, [user, loadTalents]);

  // Load recruiter's jobs for invite modal
  const openInviteModal = async (talent: Talent) => {
    setInviteModal({ talent });
    setSelectedJobId('');
    setInviteMessage('');
    try {
      const data = await api.getMyJobs();
      setRecruiterJobs((data.jobs || []).filter((j: any) => j.is_active));
    } catch (err) {
      console.error('Failed to load jobs:', err);
    }
  };

  const sendInvite = async () => {
    if (!inviteModal || !selectedJobId) return;
    setSending(true);
    try {
      const token = localStorage.getItem('token');
      const resp = await fetch(`http://localhost:8000/recruiter/talents/${inviteModal.talent.user_id}/invite`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({
          job_id: selectedJobId,
          message: inviteMessage || undefined,
        }),
      });
      if (!resp.ok) {
        const err = await resp.json().catch(() => ({}));
        throw new Error(err.detail || 'Failed to send invite');
      }
      const data = await resp.json();
      setNotification({ type: 'success', text: data.message || 'Invitation sent!' });
      setInviteModal(null);
      setTimeout(() => setNotification(null), 4000);
    } catch (err: any) {
      setNotification({ type: 'error', text: err.message });
      setTimeout(() => setNotification(null), 4000);
    } finally {
      setSending(false);
    }
  };

  // View full profile
  const toggleProfile = async (userId: string) => {
    if (expandedProfile === userId) {
      setExpandedProfile(null);
      setProfileDetail(null);
      return;
    }
    setExpandedProfile(userId);
    setLoadingDetail(true);
    try {
      const token = localStorage.getItem('token');
      const resp = await fetch(`http://localhost:8000/recruiter/talents/${userId}`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (resp.ok) {
        const data = await resp.json();
        setProfileDetail(data);
      }
    } catch (err) {
      console.error('Failed to load profile:', err);
    } finally {
      setLoadingDetail(false);
    }
  };

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault();
    loadTalents(1);
  };

  if (loading || !user) {
    return <div className="min-h-screen flex items-center justify-center"><div className="text-lg">Loading...</div></div>;
  }

  return (
    <div className="min-h-screen bg-gray-50">
      <Navbar />

      <main className="max-w-7xl mx-auto py-6 px-4 sm:px-6 lg:px-8">
        {/* Header */}
        <div className="flex justify-between items-center mb-6">
          <div>
            <h2 className="text-2xl font-bold text-gray-900">Talent Pool</h2>
            <p className="text-sm text-gray-500 mt-1">
              Browse {totalCount} candidate{totalCount !== 1 ? 's' : ''} on the platform. Invite top talent to apply for your jobs.
            </p>
          </div>
        </div>

        {/* Notification */}
        {notification && (
          <div className={`mb-4 px-4 py-3 rounded-lg text-sm font-medium ${
            notification.type === 'success' ? 'bg-green-50 text-green-700 border border-green-200' : 'bg-red-50 text-red-700 border border-red-200'
          }`}>
            {notification.text}
          </div>
        )}

        {/* Filters */}
        <form onSubmit={handleSearch} className="bg-white rounded-xl shadow-sm border border-gray-200 p-4 mb-6">
          <div className="grid grid-cols-1 md:grid-cols-3 lg:grid-cols-6 gap-3">
            <input type="text" placeholder="Search by name, headline, role..." value={search}
              onChange={e => setSearch(e.target.value)}
              className="px-3 py-2 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-blue-500 focus:border-transparent" />
            <input type="text" placeholder="Skills (e.g. Python, React)" value={skillsFilter}
              onChange={e => setSkillsFilter(e.target.value)}
              className="px-3 py-2 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-blue-500 focus:border-transparent" />
            <input type="text" placeholder="Location" value={locationFilter}
              onChange={e => setLocationFilter(e.target.value)}
              className="px-3 py-2 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-blue-500 focus:border-transparent" />
            <div className="flex gap-2">
              <input type="number" placeholder="Min Exp" value={minExp}
                onChange={e => setMinExp(e.target.value)}
                className="w-1/2 px-3 py-2 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-blue-500 focus:border-transparent" />
              <input type="number" placeholder="Max Exp" value={maxExp}
                onChange={e => setMaxExp(e.target.value)}
                className="w-1/2 px-3 py-2 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-blue-500 focus:border-transparent" />
            </div>
            <select value={sortBy} onChange={e => setSortBy(e.target.value)}
              className="px-3 py-2 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-blue-500 focus:border-transparent">
              <option value="recent">Newest First</option>
              <option value="experience">Most Experienced</option>
              <option value="name">Name A-Z</option>
            </select>
            <div className="flex gap-2">
              <button type="submit"
                className="flex-1 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 text-sm font-medium transition-colors">
                Search
              </button>
              <label className="flex items-center gap-1.5 text-xs text-gray-600 cursor-pointer">
                <input type="checkbox" checked={openOnly} onChange={e => setOpenOnly(e.target.checked)}
                  className="rounded border-gray-300" />
                Open to work
              </label>
            </div>
          </div>
        </form>

        {/* Results */}
        {loadingTalents ? (
          <div className="text-center py-16 text-gray-400">Loading talents...</div>
        ) : talents.length === 0 ? (
          <div className="bg-white rounded-xl shadow-sm p-16 text-center border border-gray-200">
            <div className="text-5xl mb-4">🔍</div>
            <h3 className="text-lg font-semibold text-gray-700 mb-2">No Candidates Found</h3>
            <p className="text-gray-500 text-sm">Try adjusting your filters or search criteria.</p>
          </div>
        ) : (
          <div className="space-y-4">
            {talents.map(talent => (
              <div key={talent.user_id} className="bg-white rounded-xl shadow-sm border border-gray-200 overflow-hidden hover:shadow-md transition-shadow">
                <div className="p-5">
                  <div className="flex justify-between items-start">
                    {/* Left: Profile info */}
                    <div className="flex-1">
                      <div className="flex items-center gap-3 mb-2">
                        {/* Avatar */}
                        <div className="w-12 h-12 rounded-full bg-gradient-to-br from-blue-500 to-indigo-600 flex items-center justify-center text-white font-bold text-lg">
                          {(talent.name?.[0] || '?').toUpperCase()}
                        </div>
                        <div>
                          <div className="flex items-center gap-2">
                            <h3 className="text-lg font-semibold text-gray-800">{talent.name}</h3>
                            {talent.is_verified && (
                              <span className="px-1.5 py-0.5 bg-green-100 text-green-700 text-[10px] font-bold rounded-full">✓ Verified</span>
                            )}
                            {talent.is_open_to_work && (
                              <span className="px-2 py-0.5 bg-emerald-100 text-emerald-700 text-[10px] font-bold rounded-full">Open to Work</span>
                            )}
                          </div>
                          <p className="text-sm text-gray-500">{talent.headline || talent.desired_role || 'No headline'}</p>
                        </div>
                      </div>

                      {/* Meta info */}
                      <div className="flex flex-wrap gap-4 text-xs text-gray-400 mb-3">
                        {(talent.location_city || talent.location_country) && (
                          <span>📍 {[talent.location_city, talent.location_country].filter(Boolean).join(', ')}</span>
                        )}
                        {talent.years_experience > 0 && (
                          <span>💼 {talent.years_experience} years exp.</span>
                        )}
                        {talent.desired_role && (
                          <span>🎯 Seeking: {talent.desired_role}</span>
                        )}
                      </div>

                      {/* Summary */}
                      {talent.summary && (
                        <p className="text-sm text-gray-600 mb-3 line-clamp-2">{talent.summary}</p>
                      )}

                      {/* Skills */}
                      {talent.skills.length > 0 && (
                        <div className="flex flex-wrap gap-1.5">
                          {talent.skills.slice(0, 8).map((skill, idx) => (
                            <span key={idx} className={`px-2 py-0.5 rounded-full text-[11px] font-medium ${
                              skill.level === 'expert' ? 'bg-purple-100 text-purple-700' :
                              skill.level === 'advanced' ? 'bg-blue-100 text-blue-700' :
                              skill.level === 'intermediate' ? 'bg-gray-100 text-gray-700' :
                              'bg-gray-50 text-gray-500'
                            }`}>
                              {skill.name}
                            </span>
                          ))}
                          {talent.skills.length > 8 && (
                            <span className="px-2 py-0.5 rounded-full text-[11px] text-gray-400 bg-gray-50">
                              +{talent.skills.length - 8} more
                            </span>
                          )}
                        </div>
                      )}
                    </div>

                    {/* Right: Actions */}
                    <div className="flex flex-col gap-2 ml-4">
                      <button
                        onClick={() => openInviteModal(talent)}
                        className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 text-sm font-medium transition-colors whitespace-nowrap"
                      >
                        ✉ Invite to Apply
                      </button>
                      <button
                        onClick={() => toggleProfile(talent.user_id)}
                        className="px-4 py-2 border border-gray-300 text-gray-700 rounded-lg hover:bg-gray-50 text-sm font-medium transition-colors whitespace-nowrap"
                      >
                        {expandedProfile === talent.user_id ? 'Hide Profile' : 'View Profile'}
                      </button>
                    </div>
                  </div>
                </div>

                {/* Expanded profile detail */}
                {expandedProfile === talent.user_id && (
                  <div className="border-t border-gray-100 bg-gray-50 p-5">
                    {loadingDetail ? (
                      <div className="text-center py-4 text-gray-400">Loading profile...</div>
                    ) : profileDetail ? (
                      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                        {/* Experience */}
                        {profileDetail.experience?.length > 0 && (
                          <div>
                            <h4 className="font-semibold text-gray-800 mb-3 text-sm">Work Experience</h4>
                            <div className="space-y-3">
                              {profileDetail.experience.slice(0, 4).map((exp: any, idx: number) => (
                                <div key={idx} className="bg-white rounded-lg p-3 border border-gray-200">
                                  <p className="font-medium text-sm text-gray-800">{exp.job_title || exp.title || 'Role'}</p>
                                  <p className="text-xs text-gray-500">{exp.company || exp.organization || ''}</p>
                                  <p className="text-xs text-gray-400 mt-1">{exp.start_date || ''} — {exp.end_date || 'Present'}</p>
                                </div>
                              ))}
                            </div>
                          </div>
                        )}

                        {/* Education */}
                        {profileDetail.education?.length > 0 && (
                          <div>
                            <h4 className="font-semibold text-gray-800 mb-3 text-sm">Education</h4>
                            <div className="space-y-3">
                              {profileDetail.education.slice(0, 3).map((edu: any, idx: number) => (
                                <div key={idx} className="bg-white rounded-lg p-3 border border-gray-200">
                                  <p className="font-medium text-sm text-gray-800">{edu.degree || ''} {edu.field_of_study ? `in ${edu.field_of_study}` : ''}</p>
                                  <p className="text-xs text-gray-500">{edu.institution || ''}</p>
                                  <p className="text-xs text-gray-400 mt-1">{edu.start_date || ''} — {edu.end_date || ''}</p>
                                </div>
                              ))}
                            </div>
                          </div>
                        )}

                        {/* All Skills */}
                        {profileDetail.skills?.length > 0 && (
                          <div className="md:col-span-2">
                            <h4 className="font-semibold text-gray-800 mb-3 text-sm">All Skills</h4>
                            <div className="flex flex-wrap gap-2">
                              {profileDetail.skills.map((s: any, idx: number) => (
                                <span key={idx} className="px-2.5 py-1 bg-white border border-gray-200 rounded-full text-xs text-gray-700">
                                  {s.name} {s.level && <span className="text-gray-400">• {s.level}</span>}
                                  {s.years ? <span className="text-gray-400"> • {s.years}y</span> : ''}
                                </span>
                              ))}
                            </div>
                          </div>
                        )}

                        {/* Certifications */}
                        {profileDetail.certifications?.length > 0 && (
                          <div>
                            <h4 className="font-semibold text-gray-800 mb-3 text-sm">Certifications</h4>
                            <div className="space-y-2">
                              {profileDetail.certifications.map((c: any, idx: number) => (
                                <div key={idx} className="text-xs text-gray-600">
                                  🏆 {c.name || c} {c.issuer ? `— ${c.issuer}` : ''}
                                </div>
                              ))}
                            </div>
                          </div>
                        )}
                      </div>
                    ) : (
                      <div className="text-center py-4 text-gray-400">No profile data available</div>
                    )}
                  </div>
                )}
              </div>
            ))}
          </div>
        )}

        {/* Pagination */}
        {totalPages > 1 && (
          <div className="flex justify-center items-center gap-2 mt-8">
            <button onClick={() => loadTalents(currentPage - 1)} disabled={currentPage <= 1}
              className="px-3 py-1.5 border border-gray-300 rounded-lg text-sm disabled:opacity-50 hover:bg-gray-50">
              Previous
            </button>
            <span className="text-sm text-gray-500">
              Page {currentPage} of {totalPages}
            </span>
            <button onClick={() => loadTalents(currentPage + 1)} disabled={currentPage >= totalPages}
              className="px-3 py-1.5 border border-gray-300 rounded-lg text-sm disabled:opacity-50 hover:bg-gray-50">
              Next
            </button>
          </div>
        )}

        {/* Invite Modal */}
        {inviteModal && (
          <div className="fixed inset-0 bg-black/50 z-50 flex items-center justify-center p-4">
            <div className="bg-white rounded-2xl shadow-2xl max-w-md w-full p-6">
              <h3 className="text-lg font-bold text-gray-900 mb-1">Invite to Apply</h3>
              <p className="text-sm text-gray-500 mb-4">
                Send an invitation to <strong>{inviteModal.talent.name}</strong> for one of your job openings.
              </p>

              {/* Job selection */}
              <div className="mb-4">
                <label className="block text-sm font-medium text-gray-700 mb-1">Select Job Opening *</label>
                {recruiterJobs.length === 0 ? (
                  <p className="text-sm text-red-500">You don&apos;t have any active job postings. Post a job first.</p>
                ) : (
                  <select value={selectedJobId} onChange={e => setSelectedJobId(e.target.value)}
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-blue-500 focus:border-transparent">
                    <option value="">Choose a job...</option>
                    {recruiterJobs.map(job => (
                      <option key={job.id} value={job.id}>
                        {job.title} — {job.company_name}
                      </option>
                    ))}
                  </select>
                )}
              </div>

              {/* Custom message */}
              <div className="mb-4">
                <label className="block text-sm font-medium text-gray-700 mb-1">Personal Message (optional)</label>
                <textarea value={inviteMessage} onChange={e => setInviteMessage(e.target.value)}
                  rows={3}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                  placeholder="Hi, your profile stood out to us. We'd love for you to apply..." />
              </div>

              {/* Actions */}
              <div className="flex gap-3">
                <button onClick={sendInvite} disabled={!selectedJobId || sending}
                  className="flex-1 px-4 py-2.5 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:bg-gray-300 font-medium text-sm transition-colors">
                  {sending ? 'Sending...' : '✉ Send Invitation'}
                </button>
                <button onClick={() => setInviteModal(null)}
                  className="px-4 py-2.5 border border-gray-300 rounded-lg hover:bg-gray-50 text-sm font-medium transition-colors">
                  Cancel
                </button>
              </div>
            </div>
          </div>
        )}
      </main>
    </div>
  );
}
