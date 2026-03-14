'use client';

import { useEffect, useState, useRef, useCallback } from 'react';
import { useRouter } from 'next/navigation';
import { useAuth } from '@/contexts/AuthContext';
import api, { Skill } from '@/lib/api';
import Link from 'next/link';
import Navbar from '@/components/Navbar';

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

interface SelectedSkill {
  id: string;
  name: string;
  requirement_type: string;
  in_taxonomy: boolean;
  is_verified: boolean;
}

interface SkillValidation {
  status: 'idle' | 'validating' | 'valid' | 'invalid' | 'error';
  message: string;
}

export default function PostJobPage() {
  const { user, loading } = useAuth();
  const router = useRouter();
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState(false);
  const [skills, setSkills] = useState<Skill[]>([]);
  const [selectedSkills, setSelectedSkills] = useState<SelectedSkill[]>([]);
  const [skillSearch, setSkillSearch] = useState('');
  const [showSkillDropdown, setShowSkillDropdown] = useState(false);
  const [skillValidation, setSkillValidation] = useState<SkillValidation>({ status: 'idle', message: '' });
  const [parsing, setParsing] = useState(false);
  const [parseMessage, setParseMessage] = useState('');
  const skillInputRef = useRef<HTMLInputElement>(null);
  const dropdownRef = useRef<HTMLDivElement>(null);

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
    salary_currency: 'INR',
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

  // Close dropdown when clicking outside
  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (dropdownRef.current && !dropdownRef.current.contains(e.target as Node)) {
        setShowSkillDropdown(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
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

  // ─────────────────────────────────────────────────
  // SKILL HANDLING — Taxonomy match + AI validation
  // ─────────────────────────────────────────────────

  const handleAddSkill = (skill: Skill) => {
    if (!selectedSkills.find(s => s.id === skill.id)) {
      setSelectedSkills(prev => [...prev, {
        id: skill.id,
        name: skill.name,
        requirement_type: 'required',
        in_taxonomy: true,
        is_verified: true,
      }]);
    }
    setSkillSearch('');
    setShowSkillDropdown(false);
    setSkillValidation({ status: 'idle', message: '' });
  };

  const handleRemoveSkill = (skillId: string) => {
    setSelectedSkills(prev => prev.filter(s => s.id !== skillId));
  };

  const handleSkillTypeChange = (skillId: string, type: string) => {
    setSelectedSkills(prev => prev.map(s =>
      s.id === skillId ? { ...s, requirement_type: type } : s
    ));
  };

  const filteredSkills = skills.filter(s =>
    s.name.toLowerCase().includes(skillSearch.toLowerCase()) &&
    !selectedSkills.find(sel => sel.id === s.id)
  ).slice(0, 10);

  // ★ AI SKILL VALIDATION — called when user types a skill not in the dropdown
  const handleValidateAndAddSkill = useCallback(async () => {
    const raw = skillSearch.trim();
    if (!raw || raw.length < 2) return;

    // Check if already selected
    if (selectedSkills.find(s => s.name.toLowerCase() === raw.toLowerCase())) {
      setSkillValidation({ status: 'invalid', message: 'Skill already added' });
      return;
    }

    // Check if it matches a taxonomy skill exactly
    const exactMatch = skills.find(s => s.name.toLowerCase() === raw.toLowerCase());
    if (exactMatch) {
      handleAddSkill(exactMatch);
      return;
    }

    // ★ Call AI Validation endpoint
    setSkillValidation({ status: 'validating', message: 'Verifying skill with AI...' });

    try {
      const token = localStorage.getItem('token');
      const resp = await fetch('http://localhost:8000/jobs/validate-skill', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`,
        },
        body: JSON.stringify({ skill_name: raw }),
      });

      if (!resp.ok) {
        const errData = await resp.json().catch(() => ({}));
        throw new Error(errData.detail || 'Validation failed');
      }

      const data = await resp.json();

      if (data.is_valid) {
        const skillId = data.existing_skill_id || data.newly_created_id;
        const alreadyAdded = selectedSkills.find(s => s.id === skillId);
        if (alreadyAdded) {
          setSkillValidation({ status: 'invalid', message: `Already added as "${alreadyAdded.name}"` });
          return;
        }

        const correctedMsg = data.corrected_name.toLowerCase() !== raw.toLowerCase()
          ? ` (corrected from "${raw}")`
          : '';

        setSelectedSkills(prev => [...prev, {
          id: skillId,
          name: data.canonical_name,
          requirement_type: 'required',
          in_taxonomy: !!data.existing_skill_id,
          is_verified: !!data.existing_skill_id,
        }]);

        setSkillValidation({
          status: 'valid',
          message: `✓ "${data.canonical_name}" verified${correctedMsg} — ${data.description}`,
        });
        setSkillSearch('');
        setShowSkillDropdown(false);

        if (data.newly_created_id) {
          fetchSkills();
        }

        setTimeout(() => setSkillValidation({ status: 'idle', message: '' }), 4000);
      } else {
        setSkillValidation({
          status: 'invalid',
          message: `✗ "${raw}" is not a recognized skill. ${data.description || 'Please check the spelling.'}`,
        });
      }
    } catch (err: any) {
      console.error('Skill validation error:', err);
      setSkillValidation({
        status: 'error',
        message: `Validation error: ${err.message}. The skill was not added.`,
      });
    }
  }, [skillSearch, selectedSkills, skills]);

  // Handle Enter key in skill input → trigger AI validation
  const handleSkillKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter') {
      e.preventDefault();
      if (filteredSkills.length > 0 && filteredSkills[0].name.toLowerCase() === skillSearch.toLowerCase()) {
        handleAddSkill(filteredSkills[0]);
      } else if (filteredSkills.length > 0) {
        handleAddSkill(filteredSkills[0]);
      } else {
        handleValidateAndAddSkill();
      }
    }
  };

  // ─────────────────────────────────────────────────
  // JOB DESCRIPTION AUTO-PARSER
  // ─────────────────────────────────────────────────

  const handleParseDescription = async () => {
    const desc = form.description_raw.trim();
    if (!desc || desc.length < 30) {
      setParseMessage('Please enter at least 30 characters in the Job Description first.');
      setTimeout(() => setParseMessage(''), 3000);
      return;
    }

    setParsing(true);
    setParseMessage('AI is analyzing the job description...');

    try {
      const token = localStorage.getItem('token');
      const resp = await fetch('http://localhost:8000/jobs/parse-description', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`,
        },
        body: JSON.stringify({ description: desc }),
      });

      if (!resp.ok) {
        const errData = await resp.json().catch(() => ({}));
        throw new Error(errData.detail || 'Parse failed');
      }

      const data = await resp.json();

      // ★ Auto-fill form fields (including generated JD if present)
      setForm(prev => ({
        ...prev,
        description_raw: data.description_generated || prev.description_raw,
        title: data.title || prev.title,
        company_name: data.company_name || prev.company_name,
        location_city: data.location_city || prev.location_city,
        location_country: data.location_country || prev.location_country,
        location_type: data.location_type || prev.location_type,
        employment_type: data.employment_type || prev.employment_type,
        salary_min: data.salary_min ? String(data.salary_min) : prev.salary_min,
        salary_max: data.salary_max ? String(data.salary_max) : prev.salary_max,
        salary_currency: data.salary_currency || prev.salary_currency,
        experience_min_years: data.experience_min_years != null ? String(data.experience_min_years) : prev.experience_min_years,
        experience_max_years: data.experience_max_years != null ? String(data.experience_max_years) : prev.experience_max_years,
      }));

      // ★ Auto-add extracted skills
      const extractedSkills = data.skills || [];
      let added = 0;
      for (const sk of extractedSkills) {
        if (sk.skill_id && !selectedSkills.find(s => s.id === sk.skill_id)) {
          setSelectedSkills(prev => [...prev, {
            id: sk.skill_id,
            name: sk.name,
            requirement_type: sk.requirement_type || 'required',
            in_taxonomy: sk.in_taxonomy ?? true,
            is_verified: sk.is_verified ?? true,
          }]);
          added++;
        }
      }

      if (added > 0) {
        fetchSkills();
        setParseMessage(`✓ Form auto-filled! ${added} new skill${added !== 1 ? 's' : ''} added.`);
      } else {
        setParseMessage('✓ Form fields auto-filled from description. No specific skills detected.');
      }

      setTimeout(() => setParseMessage(''), 6000);
    } catch (err: any) {
      console.error('JD parse error:', err);
      setParseMessage(`✗ ${err.message}`);
      setTimeout(() => setParseMessage(''), 5000);
    } finally {
      setParsing(false);
    }
  };

  // ─────────────────────────────────────────────────
  // FORM SUBMIT
  // ─────────────────────────────────────────────────

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
      <Navbar />

      <div className="max-w-4xl mx-auto px-4 py-8">
        {success ? (
          <div className="bg-green-50 border border-green-200 rounded-xl p-8 text-center">
            <div className="text-5xl mb-4">✓</div>
            <h2 className="text-2xl font-bold text-green-700 mb-2">Job Posted Successfully!</h2>
            <p className="text-green-600">Redirecting to your job listings...</p>
          </div>
        ) : (
          <form onSubmit={handleSubmit} className="space-y-6">
            <div className="flex justify-between items-center">
              <h2 className="text-2xl font-bold text-gray-900">Post New Job</h2>
              <Link href="/recruiter" className="text-blue-600 hover:text-blue-800 text-sm">
                ← Back to Dashboard
              </Link>
            </div>

            {error && (
              <div className="bg-red-50 border border-red-200 rounded-lg p-4 text-red-700 text-sm">
                {error}
              </div>
            )}

            {/* Job Title & Company */}
            <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6 space-y-4">
              <h3 className="text-lg font-semibold text-gray-800">Basic Information</h3>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Job Title *</label>
                  <input type="text" name="title" value={form.title} onChange={handleChange} required
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent text-sm"
                    placeholder="e.g. Senior AI/ML Engineer" />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Company Name *</label>
                  <input type="text" name="company_name" value={form.company_name} onChange={handleChange} required
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent text-sm"
                    placeholder="e.g. TechCorp India" />
                </div>
              </div>
            </div>

            {/* Job Description with AI Auto-Fill */}
            <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6 space-y-4">
              <div className="flex justify-between items-center">
                <h3 className="text-lg font-semibold text-gray-800">Job Description *</h3>
                <button
                  type="button"
                  onClick={handleParseDescription}
                  disabled={parsing}
                  className="px-4 py-2 bg-purple-600 text-white rounded-lg hover:bg-purple-700 disabled:bg-purple-400 text-sm font-medium transition-colors flex items-center gap-2"
                >
                  {parsing ? (
                    <>
                      <svg className="animate-spin h-4 w-4" viewBox="0 0 24 24"><circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none"/><path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"/></svg>
                      Parsing...
                    </>
                  ) : (
                    '✨ AI Auto-Fill from Description'
                  )}
                </button>
              </div>
              <textarea
                name="description_raw"
                value={form.description_raw}
                onChange={handleChange}
                rows={8}
                required
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent text-sm"
                placeholder="Paste the full job description here. Then click 'AI Auto-Fill' to automatically extract title, skills, location, salary, etc."
              />
              {parseMessage && (
                <div className={`text-sm px-3 py-2 rounded-lg ${
                  parseMessage.startsWith('✓') ? 'bg-green-50 text-green-700 border border-green-200' :
                  parseMessage.startsWith('✗') ? 'bg-red-50 text-red-700 border border-red-200' :
                  'bg-blue-50 text-blue-700 border border-blue-200'
                }`}>
                  {parseMessage}
                </div>
              )}
            </div>

            {/* Location */}
            <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6 space-y-4">
              <h3 className="text-lg font-semibold text-gray-800">Location</h3>
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">City</label>
                  <input type="text" name="location_city" value={form.location_city} onChange={handleChange}
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent text-sm"
                    placeholder="e.g. Pune" />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Country</label>
                  <input type="text" name="location_country" value={form.location_country} onChange={handleChange}
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent text-sm"
                    placeholder="e.g. India" />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Location Type</label>
                  <select name="location_type" value={form.location_type} onChange={handleChange}
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent text-sm">
                    <option value="onsite">Onsite</option>
                    <option value="remote">Remote</option>
                    <option value="hybrid">Hybrid</option>
                  </select>
                </div>
              </div>
            </div>

            {/* Employment & Salary */}
            <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6 space-y-4">
              <h3 className="text-lg font-semibold text-gray-800">Employment & Compensation</h3>
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Employment Type</label>
                  <select name="employment_type" value={form.employment_type} onChange={handleChange}
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent text-sm">
                    <option value="full_time">Full Time</option>
                    <option value="part_time">Part Time</option>
                    <option value="contract">Contract</option>
                    <option value="intern">Internship</option>
                  </select>
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Salary Min</label>
                  <input type="number" name="salary_min" value={form.salary_min} onChange={handleChange}
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent text-sm"
                    placeholder="50000" />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Salary Max</label>
                  <input type="number" name="salary_max" value={form.salary_max} onChange={handleChange}
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent text-sm"
                    placeholder="90000" />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Currency</label>
                  <select name="salary_currency" value={form.salary_currency} onChange={handleChange}
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent text-sm">
                    <option value="INR">INR</option>
                    <option value="USD">USD</option>
                    <option value="EUR">EUR</option>
                    <option value="GBP">GBP</option>
                  </select>
                </div>
              </div>
            </div>

            {/* Experience */}
            <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6 space-y-4">
              <h3 className="text-lg font-semibold text-gray-800">Experience Required</h3>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Min Years</label>
                  <input type="number" name="experience_min_years" value={form.experience_min_years} onChange={handleChange}
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent text-sm"
                    placeholder="3" />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Max Years</label>
                  <input type="number" name="experience_max_years" value={form.experience_max_years} onChange={handleChange}
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent text-sm"
                    placeholder="8" />
                </div>
              </div>
            </div>

            {/* Skills with AI Validation */}
            <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6 space-y-4">
              <h3 className="text-lg font-semibold text-gray-800">Required Skills</h3>

              {/* Selected skills */}
              {selectedSkills.length > 0 && (
                <div className="flex flex-wrap gap-2 mb-3">
                  {selectedSkills.map(skill => (
                    <div key={skill.id} className={`inline-flex items-center gap-1 px-3 py-1.5 rounded-full text-xs font-medium border ${
                      skill.in_taxonomy
                        ? 'bg-blue-50 text-blue-700 border-blue-200'
                        : 'bg-amber-50 text-amber-700 border-amber-200'
                    }`}>
                      {!skill.in_taxonomy && <span title="AI-validated, pending admin review">🤖</span>}
                      {skill.name}
                      <select
                        value={skill.requirement_type}
                        onChange={(e) => handleSkillTypeChange(skill.id, e.target.value)}
                        className="ml-1 bg-transparent border-none text-[10px] font-bold uppercase cursor-pointer focus:outline-none"
                      >
                        <option value="required">Required</option>
                        <option value="preferred">Preferred</option>
                        <option value="nice_to_have">Nice to have</option>
                      </select>
                      <button type="button" onClick={() => handleRemoveSkill(skill.id)}
                        className="ml-1 text-current opacity-50 hover:opacity-100">×</button>
                    </div>
                  ))}
                </div>
              )}

              {/* Skill search input with dropdown */}
              <div ref={dropdownRef} className="relative">
                <div className="flex gap-2">
                  <input
                    ref={skillInputRef}
                    type="text"
                    value={skillSearch}
                    onChange={(e) => {
                      setSkillSearch(e.target.value);
                      setShowSkillDropdown(e.target.value.length > 0);
                      setSkillValidation({ status: 'idle', message: '' });
                    }}
                    onKeyDown={handleSkillKeyDown}
                    onFocus={() => skillSearch.length > 0 && setShowSkillDropdown(true)}
                    className="flex-1 px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent text-sm"
                    placeholder="Type a skill name (e.g. Python, LangGraph, React)..."
                  />
                  <button
                    type="button"
                    onClick={handleValidateAndAddSkill}
                    disabled={skillValidation.status === 'validating' || !skillSearch.trim()}
                    className="px-4 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700 disabled:bg-gray-300 text-sm font-medium transition-colors"
                  >
                    {skillValidation.status === 'validating' ? '...' : '+ Add & Verify'}
                  </button>
                </div>

                {/* Dropdown */}
                {showSkillDropdown && filteredSkills.length > 0 && (
                  <div className="absolute z-10 w-full mt-1 bg-white border border-gray-200 rounded-lg shadow-lg max-h-48 overflow-y-auto">
                    {filteredSkills.map(skill => (
                      <button
                        key={skill.id}
                        type="button"
                        onClick={() => handleAddSkill(skill)}
                        className="w-full text-left px-4 py-2 hover:bg-blue-50 text-sm flex justify-between items-center"
                      >
                        <span>{skill.name}</span>
                        <span className="text-xs text-gray-400">{skill.category || 'skill'}</span>
                      </button>
                    ))}
                  </div>
                )}

                {/* Hint when no match */}
                {showSkillDropdown && filteredSkills.length === 0 && skillSearch.length > 1 && (
                  <div className="absolute z-10 w-full mt-1 bg-amber-50 border border-amber-200 rounded-lg shadow-lg px-4 py-3">
                    <p className="text-sm text-amber-700">
                      <strong>&quot;{skillSearch}&quot;</strong> not found in taxonomy.
                      Press <kbd className="px-1.5 py-0.5 bg-amber-100 border border-amber-300 rounded text-xs font-mono">Enter</kbd> or
                      click <strong>+ Add &amp; Verify</strong> to validate it with AI.
                    </p>
                  </div>
                )}
              </div>

              {/* Validation status message */}
              {skillValidation.message && (
                <div className={`mt-2 text-sm px-3 py-2 rounded-lg ${
                  skillValidation.status === 'valid' ? 'bg-green-50 text-green-700 border border-green-200' :
                  skillValidation.status === 'invalid' ? 'bg-red-50 text-red-700 border border-red-200' :
                  skillValidation.status === 'validating' ? 'bg-blue-50 text-blue-700 border border-blue-200' :
                  'bg-red-50 text-red-700 border border-red-200'
                }`}>
                  {skillValidation.message}
                </div>
              )}
            </div>

            {/* Submit buttons */}
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
