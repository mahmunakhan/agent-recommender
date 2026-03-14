'use client';

import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { useAuth } from '@/contexts/AuthContext';
import Navbar from '@/components/Navbar';
import { api } from '@/lib/api';

interface JobForm {
  title: string;
  company_name: string;
  description_raw: string;
  location_city: string;
  location_country: string;
  location_type: string;
  employment_type: string;
  salary_min: number | '';
  salary_max: number | '';
  salary_currency: string;
  experience_min_years: number | '';
  experience_max_years: number | '';
  required_skills: string[];
}

const EMPTY_FORM: JobForm = {
  title: '', company_name: '', description_raw: '',
  location_city: '', location_country: 'India',
  location_type: 'onsite', employment_type: 'full_time',
  salary_min: '', salary_max: '', salary_currency: 'INR',
  experience_min_years: '', experience_max_years: '',
  required_skills: [],
};

export default function PostJobPage() {
  const { user, loading } = useAuth();
  const router = useRouter();
  const [form, setForm] = useState<JobForm>(EMPTY_FORM);
  const [skillInput, setSkillInput] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [message, setMessage] = useState<{ type: 'success' | 'error'; text: string } | null>(null);

  useEffect(() => {
    if (!loading && !user) router.push('/login');
    if (!loading && user && user.role !== 'recruiter') router.push('/dashboard');
  }, [user, loading, router]);

  const updateField = (field: keyof JobForm, value: any) => {
    setForm(prev => ({ ...prev, [field]: value }));
  };

  const addSkill = () => {
    const skill = skillInput.trim();
    if (skill && !form.required_skills.includes(skill)) {
      updateField('required_skills', [...form.required_skills, skill]);
      setSkillInput('');
    }
  };

  const removeSkill = (skill: string) => {
    updateField('required_skills', form.required_skills.filter(s => s !== skill));
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!form.title || !form.company_name || !form.description_raw) {
      setMessage({ type: 'error', text: 'Please fill in title, company name, and description.' });
      return;
    }

    setSubmitting(true);
    setMessage(null);
    try {
      await api.createJob({
        title: form.title,
        company_name: form.company_name,
        description_raw: form.description_raw,
        location_city: form.location_city,
        location_country: form.location_country,
        location_type: form.location_type,
        employment_type: form.employment_type,
        salary_min: form.salary_min === '' ? null : Number(form.salary_min),
        salary_max: form.salary_max === '' ? null : Number(form.salary_max),
        salary_currency: form.salary_currency,
        experience_min_years: form.experience_min_years === '' ? null : Number(form.experience_min_years),
        experience_max_years: form.experience_max_years === '' ? null : Number(form.experience_max_years),
        required_skills: form.required_skills,
      });
      setMessage({ type: 'success', text: 'Job posted successfully!' });
      setForm(EMPTY_FORM);
    } catch (err: any) {
      setMessage({ type: 'error', text: err?.message || 'Failed to post job.' });
    } finally {
      setSubmitting(false);
    }
  };

  if (loading || !user) {
    return <div className="min-h-screen flex items-center justify-center"><div className="text-lg">Loading...</div></div>;
  }

  return (
    <div className="min-h-screen bg-gray-100">
      <Navbar />

      <main className="max-w-3xl mx-auto py-6 px-4 sm:px-6 lg:px-8">
        <h2 className="text-2xl font-bold text-gray-900 mb-6">Post a New Job</h2>

        {message && (
          <div className={`mb-6 px-4 py-3 rounded-lg text-sm font-medium ${
            message.type === 'success' ? 'bg-green-50 text-green-700 border border-green-200'
              : 'bg-red-50 text-red-700 border border-red-200'
          }`}>
            {message.text}
          </div>
        )}

        <form onSubmit={handleSubmit} className="bg-white rounded-xl shadow-sm border border-gray-200 p-6 space-y-6">
          {/* Title & Company */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Job Title *</label>
              <input type="text" value={form.title} onChange={e => updateField('title', e.target.value)}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent text-sm"
                placeholder="e.g. Senior AI/ML Engineer" />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Company Name *</label>
              <input type="text" value={form.company_name} onChange={e => updateField('company_name', e.target.value)}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent text-sm"
                placeholder="e.g. TechCorp India" />
            </div>
          </div>

          {/* Description */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Job Description *</label>
            <textarea value={form.description_raw} onChange={e => updateField('description_raw', e.target.value)}
              rows={6}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent text-sm"
              placeholder="Full job description, responsibilities, qualifications..." />
          </div>

          {/* Location */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">City</label>
              <input type="text" value={form.location_city} onChange={e => updateField('location_city', e.target.value)}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent text-sm"
                placeholder="e.g. Pune" />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Country</label>
              <input type="text" value={form.location_country} onChange={e => updateField('location_country', e.target.value)}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent text-sm" />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Location Type</label>
              <select value={form.location_type} onChange={e => updateField('location_type', e.target.value)}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent text-sm">
                <option value="onsite">Onsite</option>
                <option value="remote">Remote</option>
                <option value="hybrid">Hybrid</option>
              </select>
            </div>
          </div>

          {/* Employment & Salary */}
          <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Employment Type</label>
              <select value={form.employment_type} onChange={e => updateField('employment_type', e.target.value)}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent text-sm">
                <option value="full_time">Full Time</option>
                <option value="part_time">Part Time</option>
                <option value="contract">Contract</option>
                <option value="intern">Internship</option>
              </select>
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Salary Min</label>
              <input type="number" value={form.salary_min} onChange={e => updateField('salary_min', e.target.value ? Number(e.target.value) : '')}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent text-sm"
                placeholder="50000" />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Salary Max</label>
              <input type="number" value={form.salary_max} onChange={e => updateField('salary_max', e.target.value ? Number(e.target.value) : '')}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent text-sm"
                placeholder="90000" />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Currency</label>
              <select value={form.salary_currency} onChange={e => updateField('salary_currency', e.target.value)}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent text-sm">
                <option value="INR">INR</option>
                <option value="USD">USD</option>
                <option value="EUR">EUR</option>
                <option value="GBP">GBP</option>
              </select>
            </div>
          </div>

          {/* Experience */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Min Experience (years)</label>
              <input type="number" value={form.experience_min_years} onChange={e => updateField('experience_min_years', e.target.value ? Number(e.target.value) : '')}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent text-sm"
                placeholder="3" />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Max Experience (years)</label>
              <input type="number" value={form.experience_max_years} onChange={e => updateField('experience_max_years', e.target.value ? Number(e.target.value) : '')}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent text-sm"
                placeholder="8" />
            </div>
          </div>

          {/* Skills */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Required Skills</label>
            <div className="flex gap-2 mb-2">
              <input type="text" value={skillInput}
                onChange={e => setSkillInput(e.target.value)}
                onKeyDown={e => { if (e.key === 'Enter') { e.preventDefault(); addSkill(); } }}
                className="flex-1 px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent text-sm"
                placeholder="Type a skill and press Enter" />
              <button type="button" onClick={addSkill}
                className="px-4 py-2 bg-gray-100 text-gray-700 rounded-lg hover:bg-gray-200 text-sm font-medium">
                Add
              </button>
            </div>
            {form.required_skills.length > 0 && (
              <div className="flex flex-wrap gap-2">
                {form.required_skills.map(skill => (
                  <span key={skill} className="inline-flex items-center gap-1 px-3 py-1 bg-blue-50 text-blue-700 rounded-full text-xs font-medium">
                    {skill}
                    <button type="button" onClick={() => removeSkill(skill)} className="text-blue-400 hover:text-blue-700">×</button>
                  </span>
                ))}
              </div>
            )}
          </div>

          {/* Submit */}
          <button type="submit" disabled={submitting}
            className="w-full py-3 bg-blue-600 text-white rounded-lg hover:bg-blue-700 font-semibold text-sm disabled:opacity-50 transition-colors">
            {submitting ? 'Posting...' : 'Post Job'}
          </button>
        </form>
      </main>
    </div>
  );
}
