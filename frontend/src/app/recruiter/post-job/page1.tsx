'use client';

import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { useAuth } from '@/contexts/AuthContext';
import api, { Skill } from '@/lib/api';
import Link from 'next/link';

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

export default function PostJobPage() {
  const { user, loading } = useAuth();
  const router = useRouter();
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState(false);
  const [skills, setSkills] = useState<Skill[]>([]);
  const [selectedSkills, setSelectedSkills] = useState<{ id: string; name: string; requirement_type: string }[]>([]);
  const [skillSearch, setSkillSearch] = useState('');
  const [showSkillDropdown, setShowSkillDropdown] = useState(false);

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

  useEffect(() => {
    if (!loading && !user) {
      router.push('/login');
    } else if (!loading && user?.role !== 'recruiter') {
      router.push('/dashboard');
    }
  }, [user, loading, router]);

  useEffect(() => {
    fetchSkills();
  }, []);

  const fetchSkills = async () => {
    try {
      const data = await api.getSkills();
      setSkills(data);
    } catch (error) {
      console.error('Error fetching skills:', error);
    }
  };

  const handleChange = (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>) => {
    setForm({ ...form, [e.target.name]: e.target.value });
  };

  const handleAddSkill = (skill: Skill) => {
    if (!selectedSkills.find(s => s.id === skill.id)) {
      setSelectedSkills([...selectedSkills, { id: skill.id, name: skill.name, requirement_type: 'required' }]);
    }
    setSkillSearch('');
    setShowSkillDropdown(false);
  };

  const handleRemoveSkill = (skillId: string) => {
    setSelectedSkills(selectedSkills.filter(s => s.id !== skillId));
  };

  const handleSkillTypeChange = (skillId: string, type: string) => {
    setSelectedSkills(selectedSkills.map(s => 
      s.id === skillId ? { ...s, requirement_type: type } : s
    ));
  };

  const filteredSkills = skills.filter(s => 
    s.name.toLowerCase().includes(skillSearch.toLowerCase()) &&
    !selectedSkills.find(sel => sel.id === s.id)
  ).slice(0, 10);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setSubmitting(true);

    try {
      const jobData = {
        title: form.title,
        company_name: form.company_name,
        description_raw: form.description_raw,
        location_city: form.location_city || undefined,
        location_country: form.location_country || undefined,
        location_type: form.location_type,
        employment_type: form.employment_type,
        salary_min: form.salary_min ? parseInt(form.salary_min) : undefined,
        salary_max: form.salary_max ? parseInt(form.salary_max) : undefined,
        salary_currency: form.salary_currency,
        experience_min_years: form.experience_min_years ? parseInt(form.experience_min_years) : undefined,
        experience_max_years: form.experience_max_years ? parseInt(form.experience_max_years) : undefined,
        is_active: true,
        source_type: 'internal',
      };

      const job = await api.createJob(jobData);

      for (const skill of selectedSkills) {
        try {
          await api.addJobSkill(job.id, skill.id, skill.requirement_type);
        } catch (err) {
          console.error('Error adding skill:', err);
        }
      }

      setSuccess(true);
      setTimeout(() => {
        router.push('/recruiter/my-jobs');
      }, 2000);
    } catch (err: any) {
      setError(err.message || 'Failed to post job');
    } finally {
      setSubmitting(false);
    }
  };

  if (loading) {
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
          <h1 className="text-2xl font-bold text-blue-600">Post New Job</h1>
          <Link href="/recruiter" className="text-blue-600 hover:text-blue-800">
            â† Back to Dashboard
          </Link>
        </div>
      </nav>

      <div className="max-w-4xl mx-auto px-4 py-8">
        {success ? (
          <div className="bg-green-100 border border-green-400 text-green-700 px-6 py-4 rounded-lg">
            <h3 className="font-bold text-lg">Job Posted Successfully! ðŸŽ‰</h3>
            <p>Redirecting to your jobs...</p>
          </div>
        ) : (
          <form onSubmit={handleSubmit} className="bg-white rounded-lg shadow p-6 space-y-6">
            {error && (
              <div className="bg-red-100 border border-red-400 text-red-700 px-4 py-3 rounded">
                {error}
              </div>
            )}

            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Job Title *</label>
                <input
                  type="text"
                  name="title"
                  value={form.title}
                  onChange={handleChange}
                  required
                  placeholder="e.g., Senior Software Engineer"
                  className="w-full px-4 py-2 border rounded-lg focus:ring-2 focus:ring-blue-500"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Company Name *</label>
                <input
                  type="text"
                  name="company_name"
                  value={form.company_name}
                  onChange={handleChange}
                  required
                  placeholder="e.g., Tech Corp"
                  className="w-full px-4 py-2 border rounded-lg focus:ring-2 focus:ring-blue-500"
                />
              </div>
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Job Description *</label>
              <textarea
                name="description_raw"
                value={form.description_raw}
                onChange={handleChange}
                required
                rows={8}
                placeholder="Describe the role, responsibilities, and requirements..."
                className="w-full px-4 py-2 border rounded-lg focus:ring-2 focus:ring-blue-500"
              />
            </div>

            <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">City</label>
                <input
                  type="text"
                  name="location_city"
                  value={form.location_city}
                  onChange={handleChange}
                  placeholder="e.g., Riyadh"
                  className="w-full px-4 py-2 border rounded-lg focus:ring-2 focus:ring-blue-500"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Country</label>
                <input
                  type="text"
                  name="location_country"
                  value={form.location_country}
                  onChange={handleChange}
                  placeholder="e.g., Saudi Arabia"
                  className="w-full px-4 py-2 border rounded-lg focus:ring-2 focus:ring-blue-500"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Work Type</label>
                <select
                  name="location_type"
                  value={form.location_type}
                  onChange={handleChange}
                  className="w-full px-4 py-2 border rounded-lg focus:ring-2 focus:ring-blue-500"
                >
                  <option value="onsite">On-site</option>
                  <option value="remote">Remote</option>
                  <option value="hybrid">Hybrid</option>
                </select>
              </div>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Employment Type</label>
                <select
                  name="employment_type"
                  value={form.employment_type}
                  onChange={handleChange}
                  className="w-full px-4 py-2 border rounded-lg focus:ring-2 focus:ring-blue-500"
                >
                  <option value="full_time">Full-time</option>
                  <option value="part_time">Part-time</option>
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
                  placeholder="e.g., 3"
                  className="w-full px-4 py-2 border rounded-lg focus:ring-2 focus:ring-blue-500"
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
                  placeholder="e.g., 7"
                  className="w-full px-4 py-2 border rounded-lg focus:ring-2 focus:ring-blue-500"
                />
              </div>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Min Salary</label>
                <input
                  type="number"
                  name="salary_min"
                  value={form.salary_min}
                  onChange={handleChange}
                  min="0"
                  placeholder="e.g., 50000"
                  className="w-full px-4 py-2 border rounded-lg focus:ring-2 focus:ring-blue-500"
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
                  placeholder="e.g., 80000"
                  className="w-full px-4 py-2 border rounded-lg focus:ring-2 focus:ring-blue-500"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Currency</label>
                <select
                  name="salary_currency"
                  value={form.salary_currency}
                  onChange={handleChange}
                  className="w-full px-4 py-2 border rounded-lg focus:ring-2 focus:ring-blue-500"
                >
                  <option value="USD">USD ($)</option>
                  <option value="SAR">SAR (Ø±.Ø³)</option>
                  <option value="EUR">EUR (â‚¬)</option>
                  <option value="GBP">GBP (Â£)</option>
                  <option value="INR">INR (â‚¹)</option>
                  <option value="AED">AED (Ø¯.Ø¥)</option>
                </select>
              </div>
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Required Skills</label>
              
              {selectedSkills.length > 0 && (
                <div className="flex flex-wrap gap-2 mb-3">
                  {selectedSkills.map((skill) => (
                    <div key={skill.id} className="flex items-center gap-2 bg-blue-50 border border-blue-200 rounded-lg px-3 py-1">
                      <span className="font-medium">{skill.name}</span>
                      <select
                        value={skill.requirement_type}
                        onChange={(e) => handleSkillTypeChange(skill.id, e.target.value)}
                        className="text-xs bg-transparent border-none focus:ring-0"
                      >
                        <option value="required">Required</option>
                        <option value="preferred">Preferred</option>
                        <option value="nice_to_have">Nice to have</option>
                      </select>
                      <button type="button" onClick={() => handleRemoveSkill(skill.id)} className="text-red-500 hover:text-red-700">Ã—</button>
                    </div>
                  ))}
                </div>
              )}

              <div className="relative">
                <input
                  type="text"
                  value={skillSearch}
                  onChange={(e) => { setSkillSearch(e.target.value); setShowSkillDropdown(true); }}
                  onFocus={() => setShowSkillDropdown(true)}
                  placeholder="Search and add skills..."
                  className="w-full px-4 py-2 border rounded-lg focus:ring-2 focus:ring-blue-500"
                />
                
                {showSkillDropdown && skillSearch && filteredSkills.length > 0 && (
                  <div className="absolute z-10 w-full mt-1 bg-white border rounded-lg shadow-lg max-h-60 overflow-y-auto">
                    {filteredSkills.map((skill) => (
                      <button
                        key={skill.id}
                        type="button"
                        onClick={() => handleAddSkill(skill)}
                        className="w-full px-4 py-2 text-left hover:bg-blue-50"
                      >
                        {skill.name}
                        <span className="text-xs text-gray-500 ml-2">({skill.skill_type})</span>
                      </button>
                    ))}
                  </div>
                )}
              </div>
            </div>

            <div className="flex gap-4">
              <button
                type="submit"
                disabled={submitting}
                className="flex-1 bg-blue-600 text-white py-3 rounded-lg hover:bg-blue-700 font-medium disabled:bg-blue-400"
              >
                {submitting ? 'Posting...' : 'Post Job'}
              </button>
              <Link href="/recruiter" className="px-6 py-3 border border-gray-300 rounded-lg hover:bg-gray-50 font-medium text-center">
                Cancel
              </Link>
            </div>
          </form>
        )}
      </div>
    </div>
  );
}
