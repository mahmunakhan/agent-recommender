'use client';

import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import { useAuth } from '@/contexts/AuthContext';
import { api, Profile } from '@/lib/api';

export default function ProfilePage() {
  const { user, loading, logout } = useAuth();
  const router = useRouter();
  const [profile, setProfile] = useState<Profile | null>(null);
  const [loadingProfile, setLoadingProfile] = useState(true);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState('');
  const [uploading, setUploading] = useState(false);

  const [formData, setFormData] = useState({
    headline: '',
    summary: '',
    location_city: '',
    location_country: '',
    years_experience: 0,
    desired_role: '',
    desired_salary_min: 0,
    desired_salary_max: 0,
    is_open_to_work: true,
  });

  useEffect(() => {
    if (!loading && !user) {
      router.push('/login');
    }
  }, [user, loading, router]);

  useEffect(() => {
    if (user) {
      api.getProfile()
        .then((data) => {
          setProfile(data);
          setFormData({
            headline: data.headline || '',
            summary: data.summary || '',
            location_city: data.location_city || '',
            location_country: data.location_country || '',
            years_experience: data.years_experience || 0,
            desired_role: data.desired_role || '',
            desired_salary_min: data.desired_salary_min || 0,
            desired_salary_max: data.desired_salary_max || 0,
            is_open_to_work: data.is_open_to_work ?? true,
          });
        })
        .catch(console.error)
        .finally(() => setLoadingProfile(false));
    }
  }, [user]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setSaving(true);
    setMessage('');

    try {
      await api.updateProfile(formData);
      setMessage('Profile updated successfully!');
      const updated = await api.getProfile();
      setProfile(updated);
    } catch (err: any) {
      setMessage('Error: ' + (err.message || 'Failed to update'));
    } finally {
      setSaving(false);
    }
  };

  const handleResumeUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    setUploading(true);
    setMessage('');

    try {
      const result = await api.uploadResume(file);
      setMessage(result.parsed ? 'Resume uploaded and parsed successfully!' : 'Resume uploaded!');
      const updated = await api.getProfile();
      setProfile(updated);
    } catch (err: any) {
      setMessage('Error: ' + (err.message || 'Upload failed'));
    } finally {
      setUploading(false);
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
                <Link href="/jobs" className="text-gray-500 hover:text-gray-900 px-3 py-2 rounded-md text-sm font-medium">
                  Jobs
                </Link>
                <Link href="/profile" className="text-gray-900 px-3 py-2 rounded-md text-sm font-medium">
                  Profile
                </Link>
              </div>
            </div>
            <div className="flex items-center space-x-4">
              <span className="text-sm text-gray-700">{user.first_name} {user.last_name}</span>
              <button onClick={logout} className="text-sm text-red-600 hover:text-red-800">Logout</button>
            </div>
          </div>
        </div>
      </nav>

      <main className="max-w-4xl mx-auto py-6 sm:px-6 lg:px-8">
        <div className="px-4 py-6 sm:px-0">
          <h2 className="text-2xl font-bold text-gray-900 mb-6">My Profile</h2>

          {message && (
            <div className={`mb-4 p-4 rounded ${message.startsWith('Error') ? 'bg-red-50 text-red-700' : 'bg-green-50 text-green-700'}`}>
              {message}
            </div>
          )}

          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            {/* Resume Upload */}
            <div className="bg-white rounded-lg shadow p-6">
              <h3 className="text-lg font-semibold mb-4">Resume</h3>
              <div className="space-y-4">
                <label className="block">
                  <span className="sr-only">Upload Resume</span>
                  <input
                    type="file"
                    accept=".pdf,.doc,.docx"
                    onChange={handleResumeUpload}
                    disabled={uploading}
                    className="block w-full text-sm text-gray-500 file:mr-4 file:py-2 file:px-4 file:rounded file:border-0 file:text-sm file:font-semibold file:bg-blue-50 file:text-blue-700 hover:file:bg-blue-100"
                  />
                </label>
                {uploading && <p className="text-sm text-gray-500">Uploading and parsing...</p>}
                <p className="text-xs text-gray-500">Upload PDF or Word document. AI will extract your skills and experience.</p>
              </div>

              {profile?.skills && profile.skills.length > 0 && (
                <div className="mt-6">
                  <h4 className="font-medium mb-2">Your Skills</h4>
                  <div className="flex flex-wrap gap-2">
                    {profile.skills.map((skill) => (
                      <span
                        key={skill.skill_id}
                        className={`px-2 py-1 text-xs rounded ${skill.is_primary ? 'bg-blue-100 text-blue-800' : 'bg-gray-100 text-gray-700'}`}
                      >
                        {skill.skill_name} ({skill.proficiency_level})
                      </span>
                    ))}
                  </div>
                </div>
              )}
            </div>

            {/* Profile Form */}
            <div className="lg:col-span-2 bg-white rounded-lg shadow p-6">
              <h3 className="text-lg font-semibold mb-4">Profile Details</h3>
              
              {loadingProfile ? (
                <p>Loading...</p>
              ) : (
                <form onSubmit={handleSubmit} className="space-y-4">
                  <div>
                    <label className="block text-sm font-medium text-gray-700">Headline</label>
                    <input
                      type="text"
                      value={formData.headline}
                      onChange={(e) => setFormData({ ...formData, headline: e.target.value })}
                      placeholder="e.g., Senior Python Developer"
                      className="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:ring-blue-500 focus:border-blue-500 sm:text-sm"
                    />
                  </div>

                  <div>
                    <label className="block text-sm font-medium text-gray-700">Summary</label>
                    <textarea
                      value={formData.summary}
                      onChange={(e) => setFormData({ ...formData, summary: e.target.value })}
                      rows={3}
                      placeholder="Brief description of your experience and goals"
                      className="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:ring-blue-500 focus:border-blue-500 sm:text-sm"
                    />
                  </div>

                  <div className="grid grid-cols-2 gap-4">
                    <div>
                      <label className="block text-sm font-medium text-gray-700">City</label>
                      <input
                        type="text"
                        value={formData.location_city}
                        onChange={(e) => setFormData({ ...formData, location_city: e.target.value })}
                        className="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:ring-blue-500 focus:border-blue-500 sm:text-sm"
                      />
                    </div>
                    <div>
                      <label className="block text-sm font-medium text-gray-700">Country</label>
                      <input
                        type="text"
                        value={formData.location_country}
                        onChange={(e) => setFormData({ ...formData, location_country: e.target.value })}
                        className="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:ring-blue-500 focus:border-blue-500 sm:text-sm"
                      />
                    </div>
                  </div>

                  <div>
                    <label className="block text-sm font-medium text-gray-700">Years of Experience</label>
                    <input
                      type="number"
                      min="0"
                      value={formData.years_experience}
                      onChange={(e) => setFormData({ ...formData, years_experience: parseInt(e.target.value) || 0 })}
                      className="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:ring-blue-500 focus:border-blue-500 sm:text-sm"
                    />
                  </div>

                  <div>
                    <label className="block text-sm font-medium text-gray-700">Desired Role</label>
                    <input
                      type="text"
                      value={formData.desired_role}
                      onChange={(e) => setFormData({ ...formData, desired_role: e.target.value })}
                      placeholder="e.g., Machine Learning Engineer"
                      className="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:ring-blue-500 focus:border-blue-500 sm:text-sm"
                    />
                  </div>

                  <div className="grid grid-cols-2 gap-4">
                    <div>
                      <label className="block text-sm font-medium text-gray-700">Min Salary ($)</label>
                      <input
                        type="number"
                        min="0"
                        value={formData.desired_salary_min}
                        onChange={(e) => setFormData({ ...formData, desired_salary_min: parseInt(e.target.value) || 0 })}
                        className="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:ring-blue-500 focus:border-blue-500 sm:text-sm"
                      />
                    </div>
                    <div>
                      <label className="block text-sm font-medium text-gray-700">Max Salary ($)</label>
                      <input
                        type="number"
                        min="0"
                        value={formData.desired_salary_max}
                        onChange={(e) => setFormData({ ...formData, desired_salary_max: parseInt(e.target.value) || 0 })}
                        className="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:ring-blue-500 focus:border-blue-500 sm:text-sm"
                      />
                    </div>
                  </div>

                  <div className="flex items-center">
                    <input
                      type="checkbox"
                      id="openToWork"
                      checked={formData.is_open_to_work}
                      onChange={(e) => setFormData({ ...formData, is_open_to_work: e.target.checked })}
                      className="h-4 w-4 text-blue-600 focus:ring-blue-500 border-gray-300 rounded"
                    />
                    <label htmlFor="openToWork" className="ml-2 block text-sm text-gray-900">
                      Open to work
                    </label>
                  </div>

                  <button
                    type="submit"
                    disabled={saving}
                    className="w-full py-2 px-4 border border-transparent rounded-md shadow-sm text-sm font-medium text-white bg-blue-600 hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500 disabled:opacity-50"
                  >
                    {saving ? 'Saving...' : 'Save Profile'}
                  </button>
                </form>
              )}
            </div>
          </div>
        </div>
      </main>
    </div>
  );
}