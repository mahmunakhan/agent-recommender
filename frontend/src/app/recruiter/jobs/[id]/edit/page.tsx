'use client';

import { useState, useEffect } from 'react';
import { useRouter, useParams } from 'next/navigation';
import Link from 'next/link';
import api, { Job, Skill, User } from '@/lib/api';

interface JobForm {
  title: string;
  company_name: string;
  description_raw: string;
  location_city: string;
  location_country: string;
  location_type: string;
  employment_type: string;
  salary_min: string;
  salary_max: string;
  salary_currency: string;
  experience_min_years: string;
  experience_max_years: string;
}

export default function EditJobPage() {
  const router = useRouter();
  const params = useParams();
  const jobId = params.id as string;

  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState(false);

  const [form, setForm] = useState<JobForm>({
    title: '',
    company_name: '',
    description_raw: '',
    location_city: '',
    location_country: '',
    location_type: 'onsite',
    employment_type: 'full_time',
    salary_min: '',
    salary_max: '',
    salary_currency: 'USD',
    experience_min_years: '',
    experience_max_years: '',
  });

  // Skills
  const [allSkills, setAllSkills] = useState<Skill[]>([]);
  const [selectedSkills, setSelectedSkills] = useState<{ skill: Skill; requirement_type: string }[]>([]);
  const [skillSearch, setSkillSearch] = useState('');
  const [showSkillDropdown, setShowSkillDropdown] = useState(false);

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
      // Load user
      const userData = await api.getMe();
      setUser(userData);

      if (userData.role !== 'recruiter' && userData.role !== 'admin') {
        router.push('/dashboard');
        return;
      }

      // Load job details
      const job = await api.getJob(jobId);
      
      // Check if user owns this job
      if (job.posted_by_id !== userData.id && userData.role !== 'admin') {
        setError('You do not have permission to edit this job');
        return;
      }

      // Populate form
      setForm({
        title: job.title || '',
        company_name: job.company_name || '',
        description_raw: job.description_raw || '',
        location_city: job.location_city || '',
        location_country: job.location_country || '',
        location_type: job.location_type || 'onsite',
        employment_type: job.employment_type || 'full_time',
        salary_min: job.salary_min?.toString() || '',
        salary_max: job.salary_max?.toString() || '',
        salary_currency: job.salary_currency || 'USD',
        experience_min_years: job.experience_min_years?.toString() || '',
        experience_max_years: job.experience_max_years?.toString() || '',
      });

      // Load existing skills
      if (job.skills && job.skills.length > 0) {
        const existingSkills = job.skills.map(js => ({
          skill: { id: js.skill_id, name: js.skill_name, slug: '', skill_type: '' } as Skill,
          requirement_type: js.requirement_type
        }));
        setSelectedSkills(existingSkills);
      }

      // Load all skills for dropdown
      const skills = await api.getSkills();
      setAllSkills(skills);

    } catch (err: any) {
      setError(err.message || 'Failed to load job');
    } finally {
      setLoading(false);
    }
  };

  const handleChange = (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>) => {
    setForm({ ...form, [e.target.name]: e.target.value });
  };

  const handleAddSkill = (skill: Skill) => {
    if (!selectedSkills.find(s => s.skill.id === skill.id)) {
      setSelectedSkills([...selectedSkills, { skill, requirement_type: 'required' }]);
    }
    setSkillSearch('');
    setShowSkillDropdown(false);
  };

  const handleRemoveSkill = (skillId: string) => {
    setSelectedSkills(selectedSkills.filter(s => s.skill.id !== skillId));
  };

  const handleSkillRequirementChange = (skillId: string, requirement_type: string) => {
    setSelectedSkills(selectedSkills.map(s =>
      s.skill.id === skillId ? { ...s, requirement_type } : s
    ));
  };

  const filteredSkills = allSkills.filter(skill =>
    skill.name.toLowerCase().includes(skillSearch.toLowerCase()) &&
    !selectedSkills.find(s => s.skill.id === skill.id)
  ).slice(0, 10);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setSaving(true);

    try {
      // Validate required fields
      if (!form.title || !form.company_name || !form.description_raw) {
        throw new Error('Please fill in all required fields');
      }

      // Prepare job data
      const jobData: any = {
        title: form.title,
        company_name: form.company_name,
        description_raw: form.description_raw,
        location_city: form.location_city || null,
        location_country: form.location_country || null,
        location_type: form.location_type,
        employment_type: form.employment_type,
        salary_min: form.salary_min ? parseInt(form.salary_min) : null,
        salary_max: form.salary_max ? parseInt(form.salary_max) : null,
        salary_currency: form.salary_currency,
        experience_min_years: form.experience_min_years ? parseInt(form.experience_min_years) : null,
        experience_max_years: form.experience_max_years ? parseInt(form.experience_max_years) : null,
      };

      // Update job
      await api.updateJob(jobId, jobData);

      // Update skills - remove old ones and add new ones
      // For simplicity, we'll just update the skills through the API
      // Note: This requires backend support for bulk skill update

      setSuccess(true);
      setTimeout(() => {
        router.push('/recruiter/my-jobs');
      }, 1500);

    } catch (err: any) {
      setError(err.message || 'Failed to update job');
    } finally {
      setSaving(false);
    }
  };

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600"></div>
      </div>
    );
  }

  if (error && !form.title) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="bg-white p-8 rounded-lg shadow text-center">
          <div className="text-red-500 text-xl mb-4">⚠️</div>
          <p className="text-red-600 mb-4">{error}</p>
          <Link href="/recruiter/my-jobs" className="text-blue-600 hover:underline">
            ← Back to My Jobs
          </Link>
        </div>
      </div>
    );
  }

  if (success) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="bg-white p-8 rounded-lg shadow text-center">
          <div className="text-green-500 text-5xl mb-4">✓</div>
          <h2 className="text-2xl font-bold text-gray-900 mb-2">Job Updated!</h2>
          <p className="text-gray-600">Redirecting to My Jobs...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <header className="bg-white shadow-sm">
        <div className="max-w-4xl mx-auto px-4 py-4 flex justify-between items-center">
          <div className="flex items-center gap-4">
            <Link href="/recruiter/my-jobs" className="text-gray-600 hover:text-gray-900">
              ← Back to My Jobs
            </Link>
            <h1 className="text-2xl font-bold text-gray-900">Edit Job</h1>
          </div>
        </div>
      </header>

      <main className="max-w-4xl mx-auto px-4 py-8">
        {error && (
          <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded mb-6">
            {error}
          </div>
        )}

        <form onSubmit={handleSubmit} className="bg-white rounded-lg shadow p-6 space-y-6">
          {/* Basic Info */}
          <div>
            <h2 className="text-lg font-semibold text-gray-900 mb-4">Basic Information</h2>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Job Title <span className="text-red-500">*</span>
                </label>
                <input
                  type="text"
                  name="title"
                  value={form.title}
                  onChange={handleChange}
                  className="w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                  placeholder="e.g., Senior Software Engineer"
                  required
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Company Name <span className="text-red-500">*</span>
                </label>
                <input
                  type="text"
                  name="company_name"
                  value={form.company_name}
                  onChange={handleChange}
                  className="w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                  placeholder="e.g., Acme Corp"
                  required
                />
              </div>
            </div>
          </div>

          {/* Description */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Job Description <span className="text-red-500">*</span>
            </label>
            <textarea
              name="description_raw"
              value={form.description_raw}
              onChange={handleChange}
              rows={8}
              className="w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
              placeholder="Describe the role, responsibilities, and requirements..."
              required
            />
          </div>

          {/* Location */}
          <div>
            <h2 className="text-lg font-semibold text-gray-900 mb-4">Location</h2>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">City</label>
                <input
                  type="text"
                  name="location_city"
                  value={form.location_city}
                  onChange={handleChange}
                  className="w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                  placeholder="e.g., Riyadh"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Country</label>
                <input
                  type="text"
                  name="location_country"
                  value={form.location_country}
                  onChange={handleChange}
                  className="w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                  placeholder="e.g., Saudi Arabia"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Work Type</label>
                <select
                  name="location_type"
                  value={form.location_type}
                  onChange={handleChange}
                  className="w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                >
                  <option value="onsite">On-site</option>
                  <option value="remote">Remote</option>
                  <option value="hybrid">Hybrid</option>
                </select>
              </div>
            </div>
          </div>

          {/* Employment */}
          <div>
            <h2 className="text-lg font-semibold text-gray-900 mb-4">Employment Details</h2>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Employment Type</label>
                <select
                  name="employment_type"
                  value={form.employment_type}
                  onChange={handleChange}
                  className="w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                >
                  <option value="full_time">Full Time</option>
                  <option value="part_time">Part Time</option>
                  <option value="contract">Contract</option>
                  <option value="internship">Internship</option>
                </select>
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Min Experience (years)</label>
                <input
                  type="number"
                  name="experience_min_years"
                  value={form.experience_min_years}
                  onChange={handleChange}
                  min="0"
                  className="w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                  placeholder="0"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Max Experience (years)</label>
                <input
                  type="number"
                  name="experience_max_years"
                  value={form.experience_max_years}
                  onChange={handleChange}
                  min="0"
                  className="w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                  placeholder="10"
                />
              </div>
            </div>
          </div>

          {/* Salary */}
          <div>
            <h2 className="text-lg font-semibold text-gray-900 mb-4">Salary Range</h2>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Currency</label>
                <select
                  name="salary_currency"
                  value={form.salary_currency}
                  onChange={handleChange}
                  className="w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                >
                  <option value="USD">USD ($)</option>
                  <option value="SAR">SAR (ر.س)</option>
                  <option value="EUR">EUR (€)</option>
                  <option value="GBP">GBP (£)</option>
                  <option value="INR">INR (₹)</option>
                  <option value="AED">AED (د.إ)</option>
                </select>
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Min Salary</label>
                <input
                  type="number"
                  name="salary_min"
                  value={form.salary_min}
                  onChange={handleChange}
                  min="0"
                  className="w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                  placeholder="50000"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Max Salary</label>
                <input
                  type="number"
                  name="salary_max"
                  value={form.salary_max}
                  onChange={handleChange}
                  min="0"
                  className="w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                  placeholder="80000"
                />
              </div>
            </div>
          </div>

          {/* Skills */}
          <div>
            <h2 className="text-lg font-semibold text-gray-900 mb-4">Required Skills</h2>
            
            {/* Skill Search */}
            <div className="relative mb-4">
              <input
                type="text"
                value={skillSearch}
                onChange={(e) => {
                  setSkillSearch(e.target.value);
                  setShowSkillDropdown(true);
                }}
                onFocus={() => setShowSkillDropdown(true)}
                className="w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                placeholder="Search and add skills..."
              />
              
              {showSkillDropdown && skillSearch && filteredSkills.length > 0 && (
                <div className="absolute z-10 w-full mt-1 bg-white border border-gray-300 rounded-md shadow-lg max-h-60 overflow-auto">
                  {filteredSkills.map((skill) => (
                    <button
                      key={skill.id}
                      type="button"
                      onClick={() => handleAddSkill(skill)}
                      className="w-full px-4 py-2 text-left hover:bg-gray-100 flex justify-between items-center"
                    >
                      <span>{skill.name}</span>
                      <span className="text-xs text-gray-500">{skill.skill_type}</span>
                    </button>
                  ))}
                </div>
              )}
            </div>

            {/* Selected Skills */}
            {selectedSkills.length > 0 && (
              <div className="space-y-2">
                {selectedSkills.map(({ skill, requirement_type }) => (
                  <div key={skill.id} className="flex items-center gap-2 bg-gray-50 p-2 rounded">
                    <span className="flex-1 font-medium">{skill.name}</span>
                    <select
                      value={requirement_type}
                      onChange={(e) => handleSkillRequirementChange(skill.id, e.target.value)}
                      className="px-2 py-1 border border-gray-300 rounded text-sm"
                    >
                      <option value="required">Required</option>
                      <option value="preferred">Preferred</option>
                      <option value="nice_to_have">Nice to Have</option>
                    </select>
                    <button
                      type="button"
                      onClick={() => handleRemoveSkill(skill.id)}
                      className="text-red-500 hover:text-red-700 px-2"
                    >
                      ✕
                    </button>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Submit */}
          <div className="flex gap-4 pt-4 border-t">
            <button
              type="submit"
              disabled={saving}
              className="flex-1 bg-blue-600 text-white py-3 px-4 rounded-md hover:bg-blue-700 disabled:bg-blue-400 font-medium"
            >
              {saving ? 'Saving Changes...' : 'Save Changes'}
            </button>
            <Link
              href="/recruiter/my-jobs"
              className="px-6 py-3 border border-gray-300 rounded-md text-gray-700 hover:bg-gray-50 font-medium"
            >
              Cancel
            </Link>
          </div>
        </form>
      </main>
    </div>
  );
}
