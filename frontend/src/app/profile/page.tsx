'use client';

import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import { useAuth } from '@/contexts/AuthContext';
import Navbar from '@/components/Navbar';
import { api, Profile } from '@/lib/api';

/* ─── Types ─── */
interface ExpItem {
  company: string; job_title: string; employment_type: string;
  location: string; start_date: string; end_date: string;
  is_current: boolean; responsibilities: string[]; achievements: string[];
  technologies_used: string[];
}
interface EduItem { degree: string; field_of_study: string; institution: string; location: string; start_date: string; end_date: string; grade: string; }
interface CertItem { name: string; issuer: string; }
interface ProjItem { name: string; description: string; role: string; technologies: string[]; }
interface LangItem { language: string; proficiency: string; }

interface Skills { skills_technologies: string[]; tools_platforms: string[]; }

interface ResumeData {
  personal_info: {
    full_name: string; first_name: string; last_name: string;
    headline: string; summary: string; date_of_birth: string;
    gender: string; nationality: string;
    location: { address: string; city: string; country: string };
    contact: { email: string; phone: string; alternate_phone: string };
    online_profiles: { type: string; url: string }[];
    work_authorization: string; notice_period: string;
  };
  experience: ExpItem[];
  education: EduItem[];
  skills: Skills;
  certifications: CertItem[];
  projects: ProjItem[];
  publications: { title: string; publisher: string; date: string }[];
  languages: LangItem[];
  interests: string[];
  meta?: any;
}

const EMPTY_PI = {
  full_name: '', first_name: '', last_name: '', headline: '', summary: '',
  date_of_birth: '', gender: '', nationality: '',
  location: { address: '', city: '', country: '' },
  contact: { email: '', phone: '', alternate_phone: '' },
  online_profiles: [] as { type: string; url: string }[],
  work_authorization: '', notice_period: '',
};

const EMPTY: ResumeData = {
  personal_info: EMPTY_PI,
  experience: [], education: [],
  skills: { skills_technologies: [], tools_platforms: [] },
  certifications: [], projects: [], publications: [],
  languages: [], interests: [],
};

/* ─── Helpers ─── */
function dedupe(arr: string[]): string[] {
  const s = new Set<string>(); return (arr || []).filter(v => { const k = (v||'').toLowerCase().trim(); if (!k || s.has(k)) return false; s.add(k); return true; });
}

function dedupeExp(exps: ExpItem[]): ExpItem[] {
  const seen = new Map<string, ExpItem>();
  for (const e of (exps || [])) {
    const co = (e.company || '').toLowerCase().replace(/[^a-z0-9]/g, '');
    const st = (e.start_date || '').toLowerCase().replace(/[^a-z0-9]/g, '') || 'nodate';
    if (!co && !e.job_title) continue;
    const key = co ? `${co}|${st}` : `notitle|${e.job_title?.toLowerCase()}|${st}`;
    if (!seen.has(key)) seen.set(key, e);
  }
  return Array.from(seen.values());
}

function dedupeEdu(edus: EduItem[]): EduItem[] {
  const seen = new Map<string, EduItem>();
  for (const e of (edus || [])) {
    const deg = (e.degree || '').toLowerCase().replace(/[^a-z0-9]/g, '');
    const inst = (e.institution || '').toLowerCase().replace(/[^a-z0-9]/g, '');
    if (!deg && !inst) continue;
    const key = `${deg}|${inst}`;
    if (!seen.has(key)) seen.set(key, e);
  }
  return Array.from(seen.values());
}

function dedupeCert(certs: CertItem[]): CertItem[] {
  const seen = new Set<string>();
  return (certs || []).filter(c => { const k = (c.name || '').toLowerCase().trim(); if (!k || seen.has(k)) return false; seen.add(k); return true; });
}

function dedupeProj(projs: ProjItem[]): ProjItem[] {
  const seen = new Set<string>();
  return (projs || []).filter(p => { const k = (p.name || '').toLowerCase().trim(); if (!k || seen.has(k)) return false; seen.add(k); return true; });
}

const TOOL_SET = new Set(['docker','kubernetes','aws','azure','gcp','terraform','ansible','jenkins','git','github','jira','postman','grafana','tableau','power bi','powerbi','mongodb','postgresql','mysql','redis','elasticsearch','kafka','rabbitmq','airflow','mlflow','snowflake','bigquery','spark','hadoop','pinecone','chroma','faiss','milvus','weaviate','linux','nginx','ci/cd','cicd','figma','neo4j','dynamodb','firebase','sagemaker','vertex ai','bedrock','databricks','nifi','apache nifi','n8n','zapier','make','alteryx','dataiku','apache airflow','apache kafka','incorta','ibm watsonx','contentsquare','mlops','phidata','ci/cd pipelines','open-cv','opencv','plotly','fastapi','fast api','vector db','autogen','jupyter notebook']);

function migrateSkills(raw: any): Skills {
  if (!raw || typeof raw !== 'object') return { skills_technologies: [], tools_platforms: [] };
  if (raw.skills_technologies || raw.tools_platforms) {
    return { skills_technologies: dedupe(raw.skills_technologies || []), tools_platforms: dedupe(raw.tools_platforms || []) };
  }
  // Old 5-category format → 2 categories. Global dedup.
  const allS: string[] = [], allT: string[] = [], seen = new Set<string>();
  for (const cat of ['programming_languages','frameworks','technical_skills','soft_skills']) {
    for (const s of (raw[cat] || [])) { const sl = (s||'').toLowerCase().trim(); if (!sl || seen.has(sl)) continue; seen.add(sl); if (TOOL_SET.has(sl)) allT.push(s); else allS.push(s); }
  }
  for (const s of (raw.tools || [])) { const sl = (s||'').toLowerCase().trim(); if (!sl || seen.has(sl)) continue; seen.add(sl); allT.push(s); }
  return { skills_technologies: allS, tools_platforms: allT };
}

/* ─── UI Components ─── */
const I = ({ d, c = '' }: { d: string; c?: string }) => (
  <svg className={`w-5 h-5 ${c}`} fill="none" stroke="currentColor" viewBox="0 0 24 24" strokeWidth={1.8}>
    <path strokeLinecap="round" strokeLinejoin="round" d={d} />
  </svg>
);
const ic = {
  user: 'M15.75 6a3.75 3.75 0 11-7.5 0 3.75 3.75 0 017.5 0zM4.501 20.118a7.5 7.5 0 0114.998 0',
  brief: 'M20.25 14.15v4.25c0 1.094-.787 2.036-1.872 2.18-2.087.277-4.216.42-6.378.42s-4.291-.143-6.378-.42c-1.085-.144-1.872-1.086-1.872-2.18v-4.25m16.5 0a2.18 2.18 0 00.75-1.661V8.706c0-1.081-.768-2.015-1.837-2.175a48.114 48.114 0 00-3.413-.387m4.5 8.006c-.194.165-.42.295-.673.38A23.978 23.978 0 0112 15.75c-2.648 0-5.195-.429-7.577-1.22a2.016 2.016 0 01-.673-.38m0 0A2.18 2.18 0 013 12.489V8.706c0-1.081.768-2.015 1.837-2.175a48.111 48.111 0 013.413-.387m7.5 0V5.25A2.25 2.25 0 0013.5 3h-3a2.25 2.25 0 00-2.25 2.25v.894m7.5 0a48.667 48.667 0 00-7.5 0',
  acad: 'M4.26 10.147a60.436 60.436 0 00-.491 6.347A48.627 48.627 0 0112 20.904a48.627 48.627 0 018.232-4.41 60.46 60.46 0 00-.491-6.347m-15.482 0a50.57 50.57 0 00-2.658-.813A59.905 59.905 0 0112 3.493a59.902 59.902 0 0110.399 5.84c-.896.248-1.783.52-2.658.814m-15.482 0A50.697 50.697 0 0112 13.489a50.702 50.702 0 017.74-3.342',
  code: 'M17.25 6.75L22.5 12l-5.25 5.25m-10.5 0L1.5 12l5.25-5.25m7.5-3l-4.5 16.5',
  cert: 'M9 12.75L11.25 15 15 9.75M21 12c0 1.268-.63 2.39-1.593 3.068a3.745 3.745 0 01-1.043 3.296 3.745 3.745 0 01-3.296 1.043A3.745 3.745 0 0112 21c-1.268 0-2.39-.63-3.068-1.593a3.746 3.746 0 01-3.296-1.043 3.745 3.745 0 01-1.043-3.296A3.745 3.745 0 013 12c0-1.268.63-2.39 1.593-3.068a3.745 3.745 0 011.043-3.296 3.746 3.746 0 013.296-1.043A3.746 3.746 0 0112 3c1.268 0 2.39.63 3.068 1.593a3.746 3.746 0 013.296 1.043 3.746 3.746 0 011.043 3.296A3.745 3.745 0 0121 12z',
  proj: 'M2.25 12.75V12A2.25 2.25 0 014.5 9.75h15A2.25 2.25 0 0121.75 12v.75m-8.69-6.44l-2.12-2.12a1.5 1.5 0 00-1.061-.44H4.5A2.25 2.25 0 002.25 6v12a2.25 2.25 0 002.25 2.25h15A2.25 2.25 0 0021.75 18V9a2.25 2.25 0 00-2.25-2.25h-5.379a1.5 1.5 0 01-1.06-.44z',
  globe: 'M12 21a9.004 9.004 0 008.716-6.747M12 21a9.004 9.004 0 01-8.716-6.747M12 21c2.485 0 4.5-4.03 4.5-9S14.485 3 12 3m0 18c-2.485 0-4.5-4.03-4.5-9S9.515 3 12 3m0 0a8.997 8.997 0 017.843 4.582M12 3a8.997 8.997 0 00-7.843 4.582',
  up: 'M3 16.5v2.25A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75V16.5m-13.5-9L12 3m0 0l4.5 4.5M12 3v13.5',
  x: 'M6 18L18 6M6 6l12 12',
  plus: 'M12 4.5v15m7.5-7.5h-15',
  trash: 'M14.74 9l-.346 9m-4.788 0L9.26 9m9.968-3.21c.342.052.682.107 1.022.166m-1.022-.165L18.16 19.673a2.25 2.25 0 01-2.244 2.077H8.084a2.25 2.25 0 01-2.244-2.077L4.772 5.79m14.456 0a48.108 48.108 0 00-3.478-.397m-12 .562c.34-.059.68-.114 1.022-.165m0 0a48.11 48.11 0 013.478-.397m7.5 0v-.916c0-1.18-.91-2.164-2.09-2.201a51.964 51.964 0 00-3.32 0c-1.18.037-2.09 1.022-2.09 2.201v.916m7.5 0a48.667 48.667 0 00-7.5 0',
  dn: 'M19.5 8.25l-7.5 7.5-7.5-7.5',
  upC: 'M4.5 15.75l7.5-7.5 7.5 7.5',
};

const Sec = ({ icon, title, count, open, toggle, color }: { icon: string; title: string; count?: number; open: boolean; toggle: () => void; color: string }) => (
  <button onClick={toggle} className="w-full flex items-center justify-between p-4 hover:bg-gray-50/50 transition-colors rounded-xl">
    <div className="flex items-center gap-3">
      <div className={`w-10 h-10 rounded-xl ${color} flex items-center justify-center shadow-sm`}><I d={icon} c="w-5 h-5 text-white" /></div>
      <div className="text-left">
        <h3 className="text-[15px] font-semibold text-gray-800">{title}</h3>
        {count !== undefined && <span className="text-xs text-gray-400">{count} items</span>}
      </div>
    </div>
    <I d={open ? ic.upC : ic.dn} c="text-gray-400" />
  </button>
);

const Inp = ({ label, value, onChange, type = 'text', cls = '' }: any) => (
  <div className={cls}>
    <label className="block text-xs font-medium text-gray-500 mb-1.5 uppercase tracking-wider">{label}</label>
    <input type={type} value={value ?? ''} onChange={(e: any) => onChange(type === 'number' ? parseInt(e.target.value) || 0 : e.target.value)}
      className="w-full px-3.5 py-2.5 bg-gray-50 border border-gray-200 rounded-xl text-sm text-gray-800 focus:outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-400 focus:bg-white transition-all" />
  </div>
);

const TArea = ({ label, value, onChange, rows = 3 }: any) => (
  <div>
    <label className="block text-xs font-medium text-gray-500 mb-1.5 uppercase tracking-wider">{label}</label>
    <textarea value={value ?? ''} onChange={(e: any) => onChange(e.target.value)} rows={rows}
      className="w-full px-3.5 py-2.5 bg-gray-50 border border-gray-200 rounded-xl text-sm text-gray-800 focus:outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-400 focus:bg-white transition-all resize-none" />
  </div>
);

const Tags = ({ label, items, onRemove, onAdd, color = 'blue' }: { label: string; items: string[]; onRemove: (i: number) => void; onAdd: (v: string) => void; color?: string }) => {
  const [inp, setInp] = useState('');
  const cm: Record<string, string> = { blue: 'bg-blue-50 text-blue-700 border-blue-200', green: 'bg-emerald-50 text-emerald-700 border-emerald-200', amber: 'bg-amber-50 text-amber-700 border-amber-200' };
  return (
    <div>
      {label && <label className="block text-xs font-medium text-gray-500 mb-1.5 uppercase tracking-wider">{label}</label>}
      <div className="flex flex-wrap gap-1.5 mb-2">
        {(items || []).map((item, i) => (
          <span key={i} className={`inline-flex items-center gap-1 px-2.5 py-1 text-xs font-medium rounded-lg border ${cm[color] || cm.blue}`}>
            {item}<button onClick={() => onRemove(i)} className="opacity-50 hover:opacity-100"><I d={ic.x} c="w-3 h-3" /></button>
          </span>
        ))}
      </div>
      <div className="flex gap-2">
        <input value={inp} onChange={e => setInp(e.target.value)}
          onKeyDown={e => { if (e.key === 'Enter' && inp.trim()) { e.preventDefault(); onAdd(inp.trim()); setInp(''); } }}
          placeholder={`Add ${(label || 'item').toLowerCase()}...`}
          className="flex-1 px-3 py-2 bg-gray-50 border border-gray-200 rounded-lg text-xs focus:outline-none focus:ring-2 focus:ring-blue-500/20 transition-all" />
        <button onClick={() => { if (inp.trim()) { onAdd(inp.trim()); setInp(''); } }}
          className="px-3 py-2 bg-gray-100 hover:bg-gray-200 text-gray-600 rounded-lg text-xs"><I d={ic.plus} c="w-3.5 h-3.5" /></button>
      </div>
    </div>
  );
};

/* ─── Main Page ─── */
export default function ProfilePage() {
  const { user, loading, logout } = useAuth();
  const router = useRouter();
  const [loadingP, setLoadingP] = useState(true);
  const [saving, setSaving] = useState(false);
  const [msg, setMsg] = useState<{ t: 'ok'|'err'; txt: string } | null>(null);
  const [uploading, setUploading] = useState(false);
  const [prog, setProg] = useState(0);
  const [rd, setRd] = useState<ResumeData>(EMPTY);
  const [os, setOs] = useState<Record<string, boolean>>({
    personal: true, exp: true, edu: true, skills: true,
    certs: false, proj: false, langs: false,
  });
  const [fd, setFd] = useState({
    headline: '', summary: '', location_city: '', location_country: '',
    years_experience: 0, desired_role: '',
    desired_salary_min: 0, desired_salary_max: 0, is_open_to_work: true,
  });

  useEffect(() => { if (!loading && !user) router.push('/login'); }, [user, loading, router]);

  /* ── Load parsed data + sync fd ── */
  const loadProfile = (profile: Profile) => {
    const pd = profile.parsed_json_draft;

    if (pd && typeof pd === 'object' && (pd.personal_info || pd.experience || pd.skills)) {
      // HAS PARSED DATA → derive everything from it
      const pi = pd.personal_info || {};
      const loc = pi.location || {};
      const contact = pi.contact || {};

      setRd({
        personal_info: {
          full_name: pi.full_name || '', first_name: pi.first_name || '', last_name: pi.last_name || '',
          headline: pi.headline || '', summary: pi.summary || '',
          date_of_birth: pi.date_of_birth || '', gender: pi.gender || '', nationality: pi.nationality || '',
          location: { address: loc.address || '', city: loc.city || '', country: loc.country || '' },
          contact: { email: contact.email || '', phone: contact.phone || '', alternate_phone: contact.alternate_phone || '' },
          online_profiles: pi.online_profiles || [],
          work_authorization: pi.work_authorization || '', notice_period: pi.notice_period || '',
        },
        experience: dedupeExp(pd.experience || []),
        education: dedupeEdu(pd.education || []),
        skills: migrateSkills(pd.skills),
        certifications: dedupeCert(pd.certifications || []),
        projects: dedupeProj(pd.projects || []),
        publications: pd.publications || [],
        languages: pd.languages || [],
        interests: pd.interests || [],
        meta: pd.meta,
      });

      // SYNC fd from parsed data ONLY — never fall back to old profile columns
      // This prevents stale data from previous resumes showing in the form
      const calcYears = () => {
        // Check explicit years in personal_info
        const piText = JSON.stringify(pi);
        const ym = piText.match(/(\d+)\+?\s*[Yy]ears?\s*[Ee]xperience/);
        if (ym) return parseInt(ym[1]);
        // Calculate from experience dates
        const years = new Set<number>();
        for (const exp of (pd.experience || [])) {
          const sm = String(exp.start_date || '').match(/(19|20)\d{2}/);
          const em = String(exp.end_date || 'present').match(/(19|20)\d{2}/);
          if (sm) years.add(parseInt(sm[0]));
          if (em) years.add(parseInt(em[0]));
          else if (/present|current|now/i.test(String(exp.end_date || ''))) years.add(new Date().getFullYear());
        }
        if (years.size >= 2) return Math.max(...years) - Math.min(...years);
        return 0;
      };

      setFd({
        headline: pi.headline || '',
        summary: pi.summary || '',
        location_city: loc.city || '',
        location_country: loc.country || '',
        years_experience: calcYears(),
        desired_role: pi.desired_role || pi.headline || '',
        desired_salary_min: 0,
        desired_salary_max: 0,
        is_open_to_work: true,
      });
    } else {
      // NO PARSED DATA → use profile fields only, rest empty
      setRd(EMPTY);
      setFd({
        headline: profile.headline || '',
        summary: profile.summary || '',
        location_city: profile.location_city || '',
        location_country: profile.location_country || '',
        years_experience: profile.years_experience || 0,
        desired_role: profile.desired_role || '',
        desired_salary_min: profile.desired_salary_min || 0,
        desired_salary_max: profile.desired_salary_max || 0,
        is_open_to_work: profile.is_open_to_work ?? true,
      });
    }
  };

  useEffect(() => {
    if (user) {
      api.getProfile().then(d => loadProfile(d)).catch(console.error).finally(() => setLoadingP(false));
    }
  }, [user]);

  const tog = (k: string) => setOs(p => ({ ...p, [k]: !p[k] }));

  const handleUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]; if (!file) return;
    setUploading(true); setMsg(null); setProg(0);
    const iv = setInterval(() => setProg(p => Math.min(p + 5, 90)), 600);
    try {
      const res = await api.uploadResume(file);
      clearInterval(iv); setProg(100);
      setMsg({ t: 'ok', txt: res.parsed ? '✓ Resume parsed — review below' : '✓ Uploaded' });
      // Reload entire profile and derive all state from it
      const upd = await api.getProfile();
      loadProfile(upd);
    } catch (err: any) {
      clearInterval(iv); setMsg({ t: 'err', txt: err.message || 'Upload failed' });
    } finally { setUploading(false); setTimeout(() => setProg(0), 2000); }
  };

  const handleSave = async () => {
    setSaving(true); setMsg(null);
    try {
      await api.updateProfile(fd);
      setMsg({ t: 'ok', txt: '✓ Profile saved' });
      // Reload to sync
      const upd = await api.getProfile();
      loadProfile(upd);
    } catch (err: any) {
      setMsg({ t: 'err', txt: err.message || 'Save failed' });
    } finally { setSaving(false); }
  };

  // Setters
  const sPI = (f: string, v: any) => setRd(p => ({ ...p, personal_info: { ...p.personal_info, [f]: v } }));
  const sPIC = (f: string, v: string) => setRd(p => ({ ...p, personal_info: { ...p.personal_info, contact: { ...p.personal_info.contact, [f]: v } } }));
  const sPIL = (f: string, v: string) => {
    setRd(p => ({ ...p, personal_info: { ...p.personal_info, location: { ...p.personal_info.location, [f]: v } } }));
    if (f === 'city') setFd(p => ({ ...p, location_city: v }));
    if (f === 'country') setFd(p => ({ ...p, location_country: v }));
  };
  const uExp = (i: number, f: string, v: any) => { const a = [...rd.experience]; a[i] = { ...a[i], [f]: v }; setRd(p => ({ ...p, experience: a })); };
  const uEdu = (i: number, f: string, v: any) => { const a = [...rd.education]; a[i] = { ...a[i], [f]: v }; setRd(p => ({ ...p, education: a })); };
  const uCert = (i: number, f: string, v: string) => { const a = [...rd.certifications]; a[i] = { ...a[i], [f]: v }; setRd(p => ({ ...p, certifications: a })); };
  const uLang = (i: number, f: string, v: string) => { const a = [...rd.languages]; a[i] = { ...a[i], [f]: v }; setRd(p => ({ ...p, languages: a })); };

  if (loading || !user) return <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-slate-50 to-blue-50"><div className="animate-pulse text-gray-400">Loading...</div></div>;

  const pi = rd.personal_info;
  const meta = rd.meta;
  const totalSkills = (rd.skills.skills_technologies?.length || 0) + (rd.skills.tools_platforms?.length || 0);

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-50 via-white to-blue-50/30">
      <Navbar />

      <main className="max-w-5xl mx-auto px-6 py-8">
        <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 mb-8">
          <div>
            <h1 className="text-2xl font-bold text-gray-900">My Profile</h1>
            <p className="text-sm text-gray-400 mt-0.5">Upload resume → AI extracts → Review & edit → Save</p>
          </div>
          <button onClick={handleSave} disabled={saving}
            className="px-5 py-2.5 bg-gradient-to-r from-blue-600 to-indigo-600 hover:from-blue-700 hover:to-indigo-700 text-white text-sm font-semibold rounded-xl shadow-lg shadow-blue-500/20 disabled:opacity-50 transition-all">
            {saving ? 'Saving...' : 'Save Profile'}
          </button>
        </div>

        {msg && <div className={`mb-6 px-4 py-3 rounded-xl text-sm font-medium ${msg.t === 'ok' ? 'bg-emerald-50 text-emerald-700 border border-emerald-200' : 'bg-red-50 text-red-700 border border-red-200'}`}>{msg.txt}</div>}

        {/* Upload */}
        <div className="mb-8 bg-white rounded-2xl border border-gray-100 shadow-sm overflow-hidden">
          <div className="p-6 flex items-center gap-4">
            <div className="w-12 h-12 rounded-xl bg-gradient-to-br from-blue-500 to-indigo-600 flex items-center justify-center shadow-lg shadow-blue-500/20"><I d={ic.up} c="w-6 h-6 text-white" /></div>
            <div className="flex-1">
              <h3 className="text-base font-semibold text-gray-800">Upload Resume</h3>
              <p className="text-xs text-gray-400 mt-0.5">PDF or Word — AI extracts all fields</p>
            </div>
            <label className={`px-4 py-2.5 rounded-xl text-sm font-semibold cursor-pointer transition-all ${uploading ? 'bg-gray-100 text-gray-400' : 'bg-blue-50 text-blue-700 hover:bg-blue-100 border border-blue-200'}`}>
              {uploading ? 'Processing...' : 'Choose File'}
              <input type="file" accept=".pdf,.doc,.docx" onChange={handleUpload} disabled={uploading} className="hidden" />
            </label>
          </div>
          {prog > 0 && <div className="px-6 pb-4"><div className="h-1.5 bg-gray-100 rounded-full overflow-hidden"><div className="h-full bg-gradient-to-r from-blue-500 to-indigo-500 rounded-full transition-all duration-500" style={{ width: `${prog}%` }} /></div></div>}
          {meta && <div className="px-6 py-3 bg-gray-50/50 border-t border-gray-100 flex flex-wrap gap-4 text-xs text-gray-400">
            <span>Parser: {meta.parser_version}</span><span>•</span><span>Confidence: {Math.round((meta.overall_confidence || 0) * 100)}%</span><span>•</span><span>Duration: {meta.duration_seconds}s</span><span>•</span><span>Skills: {meta.review?.stats?.total_skills || totalSkills}</span>
          </div>}
        </div>

        {loadingP ? <div className="text-center py-20 text-gray-400">Loading...</div> : (
          <div className="space-y-4">

            {/* PERSONAL INFO */}
            <div className="bg-white rounded-2xl border border-gray-100 shadow-sm overflow-hidden">
              <Sec icon={ic.user} title="Personal Information" open={os.personal} toggle={() => tog('personal')} color="bg-gradient-to-br from-blue-500 to-indigo-600" />
              {os.personal && <div className="px-6 pb-6 space-y-4">
                <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
                  <Inp label="Full Name" value={pi.full_name} onChange={(v: string) => sPI('full_name', v)} />
                  <Inp label="First Name" value={pi.first_name} onChange={(v: string) => sPI('first_name', v)} />
                  <Inp label="Last Name" value={pi.last_name} onChange={(v: string) => sPI('last_name', v)} />
                </div>
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                  <Inp label="Headline" value={fd.headline} onChange={(v: string) => setFd(p => ({ ...p, headline: v }))} />
                  <Inp label="Desired Role" value={fd.desired_role} onChange={(v: string) => setFd(p => ({ ...p, desired_role: v }))} />
                </div>
                <TArea label="Summary" value={fd.summary} onChange={(v: string) => setFd(p => ({ ...p, summary: v }))} />
                <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
                  <Inp label="Date of Birth" value={pi.date_of_birth} onChange={(v: string) => sPI('date_of_birth', v)} />
                  <Inp label="Gender" value={pi.gender} onChange={(v: string) => sPI('gender', v)} />
                  <Inp label="Nationality" value={pi.nationality} onChange={(v: string) => sPI('nationality', v)} />
                  <Inp label="Work Auth" value={pi.work_authorization} onChange={(v: string) => sPI('work_authorization', v)} />
                </div>
                <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
                  <Inp label="Email" value={pi.contact.email} onChange={(v: string) => sPIC('email', v)} />
                  <Inp label="Phone" value={pi.contact.phone} onChange={(v: string) => sPIC('phone', v)} />
                  <Inp label="Alt Phone" value={pi.contact.alternate_phone} onChange={(v: string) => sPIC('alternate_phone', v)} />
                </div>
                <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
                  <Inp label="City" value={fd.location_city} onChange={(v: string) => { setFd(p => ({ ...p, location_city: v })); sPIL('city', v); }} />
                  <Inp label="Country" value={fd.location_country} onChange={(v: string) => { setFd(p => ({ ...p, location_country: v })); sPIL('country', v); }} />
                  <Inp label="Address" value={pi.location.address} onChange={(v: string) => sPIL('address', v)} />
                </div>
                <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
                  <Inp label="Years Exp" type="number" value={fd.years_experience} onChange={(v: number) => setFd(p => ({ ...p, years_experience: v }))} />
                  <Inp label="Notice Period" value={pi.notice_period} onChange={(v: string) => sPI('notice_period', v)} />
                  <Inp label="Min Salary ($)" type="number" value={fd.desired_salary_min} onChange={(v: number) => setFd(p => ({ ...p, desired_salary_min: v }))} />
                  <Inp label="Max Salary ($)" type="number" value={fd.desired_salary_max} onChange={(v: number) => setFd(p => ({ ...p, desired_salary_max: v }))} />
                </div>
                <label className="flex items-center gap-2 cursor-pointer">
                  <input type="checkbox" checked={fd.is_open_to_work} onChange={e => setFd(p => ({ ...p, is_open_to_work: e.target.checked }))} className="h-4 w-4 text-blue-600 rounded border-gray-300" />
                  <span className="text-sm text-gray-600">Open to work</span>
                </label>
              </div>}
            </div>

            {/* EXPERIENCE */}
            <div className="bg-white rounded-2xl border border-gray-100 shadow-sm overflow-hidden">
              <Sec icon={ic.brief} title="Work Experience" count={rd.experience.length} open={os.exp} toggle={() => tog('exp')} color="bg-gradient-to-br from-emerald-500 to-teal-600" />
              {os.exp && <div className="px-6 pb-6 space-y-4">
                {rd.experience.map((exp, i) => (
                  <div key={i} className="p-4 bg-gray-50/50 rounded-xl border border-gray-100 space-y-3 relative group">
                    <button onClick={() => setRd(p => ({ ...p, experience: p.experience.filter((_, j) => j !== i) }))} className="absolute top-3 right-3 opacity-0 group-hover:opacity-100 text-red-400 hover:text-red-600 transition-all"><I d={ic.trash} c="w-4 h-4" /></button>
                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                      <Inp label="Job Title" value={exp.job_title} onChange={(v: string) => uExp(i, 'job_title', v)} />
                      <Inp label="Company" value={exp.company} onChange={(v: string) => uExp(i, 'company', v)} />
                    </div>
                    <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                      <Inp label="Start" value={exp.start_date} onChange={(v: string) => uExp(i, 'start_date', v)} />
                      <Inp label="End" value={exp.end_date} onChange={(v: string) => uExp(i, 'end_date', v)} />
                      <Inp label="Location" value={exp.location} onChange={(v: string) => uExp(i, 'location', v)} />
                      <Inp label="Type" value={exp.employment_type} onChange={(v: string) => uExp(i, 'employment_type', v)} />
                    </div>
                    <Tags label="Technologies" items={exp.technologies_used || []} color="blue"
                      onRemove={j => { const t = [...(exp.technologies_used||[])]; t.splice(j, 1); uExp(i, 'technologies_used', t); }}
                      onAdd={v => uExp(i, 'technologies_used', [...(exp.technologies_used||[]), v])} />
                    <Tags label="Responsibilities" items={exp.responsibilities || []} color="green"
                      onRemove={j => { const t = [...(exp.responsibilities||[])]; t.splice(j, 1); uExp(i, 'responsibilities', t); }}
                      onAdd={v => uExp(i, 'responsibilities', [...(exp.responsibilities||[]), v])} />
                  </div>
                ))}
                <button onClick={() => setRd(p => ({ ...p, experience: [...p.experience, { company: '', job_title: '', employment_type: 'full-time', location: '', start_date: '', end_date: '', is_current: false, responsibilities: [], achievements: [], technologies_used: [] }] }))}
                  className="w-full py-2.5 border-2 border-dashed border-gray-200 rounded-xl text-sm text-gray-400 hover:text-emerald-600 hover:border-emerald-300 transition-colors">+ Add Experience</button>
              </div>}
            </div>

            {/* EDUCATION */}
            <div className="bg-white rounded-2xl border border-gray-100 shadow-sm overflow-hidden">
              <Sec icon={ic.acad} title="Education" count={rd.education.length} open={os.edu} toggle={() => tog('edu')} color="bg-gradient-to-br from-violet-500 to-purple-600" />
              {os.edu && <div className="px-6 pb-6 space-y-4">
                {rd.education.map((edu, i) => (
                  <div key={i} className="p-4 bg-gray-50/50 rounded-xl border border-gray-100 space-y-3 relative group">
                    <button onClick={() => setRd(p => ({ ...p, education: p.education.filter((_, j) => j !== i) }))} className="absolute top-3 right-3 opacity-0 group-hover:opacity-100 text-red-400 hover:text-red-600 transition-all"><I d={ic.trash} c="w-4 h-4" /></button>
                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                      <Inp label="Degree" value={edu.degree} onChange={(v: string) => uEdu(i, 'degree', v)} />
                      <Inp label="Field" value={edu.field_of_study} onChange={(v: string) => uEdu(i, 'field_of_study', v)} />
                    </div>
                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                      <Inp label="Institution" value={edu.institution} onChange={(v: string) => uEdu(i, 'institution', v)} />
                      <Inp label="Location" value={edu.location} onChange={(v: string) => uEdu(i, 'location', v)} />
                    </div>
                    <div className="grid grid-cols-3 gap-3">
                      <Inp label="Start" value={edu.start_date} onChange={(v: string) => uEdu(i, 'start_date', v)} />
                      <Inp label="End" value={edu.end_date} onChange={(v: string) => uEdu(i, 'end_date', v)} />
                      <Inp label="Grade" value={edu.grade} onChange={(v: string) => uEdu(i, 'grade', v)} />
                    </div>
                  </div>
                ))}
                <button onClick={() => setRd(p => ({ ...p, education: [...p.education, { degree: '', field_of_study: '', institution: '', location: '', start_date: '', end_date: '', grade: '' }] }))}
                  className="w-full py-2.5 border-2 border-dashed border-gray-200 rounded-xl text-sm text-gray-400 hover:text-violet-600 hover:border-violet-300 transition-colors">+ Add Education</button>
              </div>}
            </div>

            {/* SKILLS — 2 CATEGORIES */}
            <div className="bg-white rounded-2xl border border-gray-100 shadow-sm overflow-hidden">
              <Sec icon={ic.code} title="Skills" count={totalSkills} open={os.skills} toggle={() => tog('skills')} color="bg-gradient-to-br from-amber-500 to-orange-600" />
              {os.skills && <div className="px-6 pb-6 space-y-5">
                <Tags label="Skills & Technologies" items={rd.skills.skills_technologies || []} color="blue"
                  onRemove={i => setRd(p => ({ ...p, skills: { ...p.skills, skills_technologies: p.skills.skills_technologies.filter((_, j) => j !== i) } }))}
                  onAdd={v => setRd(p => ({ ...p, skills: { ...p.skills, skills_technologies: [...p.skills.skills_technologies, v] } }))} />
                <Tags label="Tools & Platforms" items={rd.skills.tools_platforms || []} color="green"
                  onRemove={i => setRd(p => ({ ...p, skills: { ...p.skills, tools_platforms: p.skills.tools_platforms.filter((_, j) => j !== i) } }))}
                  onAdd={v => setRd(p => ({ ...p, skills: { ...p.skills, tools_platforms: [...p.skills.tools_platforms, v] } }))} />
              </div>}
            </div>

            {/* CERTIFICATIONS */}
            <div className="bg-white rounded-2xl border border-gray-100 shadow-sm overflow-hidden">
              <Sec icon={ic.cert} title="Certifications" count={rd.certifications.length} open={os.certs} toggle={() => tog('certs')} color="bg-gradient-to-br from-rose-500 to-pink-600" />
              {os.certs && <div className="px-6 pb-6 space-y-3">
                {rd.certifications.map((c, i) => (
                  <div key={i} className="p-3 bg-gray-50/50 rounded-xl border border-gray-100 relative group">
                    <button onClick={() => setRd(p => ({ ...p, certifications: p.certifications.filter((_, j) => j !== i) }))} className="absolute top-2 right-2 opacity-0 group-hover:opacity-100 text-red-400 hover:text-red-600"><I d={ic.trash} c="w-4 h-4" /></button>
                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                      <Inp label="Name" value={c.name} onChange={(v: string) => uCert(i, 'name', v)} />
                      <Inp label="Issuer" value={c.issuer} onChange={(v: string) => uCert(i, 'issuer', v)} />
                    </div>
                  </div>
                ))}
                <button onClick={() => setRd(p => ({ ...p, certifications: [...p.certifications, { name: '', issuer: '' }] }))}
                  className="w-full py-2.5 border-2 border-dashed border-gray-200 rounded-xl text-sm text-gray-400 hover:text-rose-600 hover:border-rose-300 transition-colors">+ Add Certification</button>
              </div>}
            </div>

            {/* PROJECTS */}
            <div className="bg-white rounded-2xl border border-gray-100 shadow-sm overflow-hidden">
              <Sec icon={ic.proj} title="Projects" count={rd.projects.length} open={os.proj} toggle={() => tog('proj')} color="bg-gradient-to-br from-cyan-500 to-blue-600" />
              {os.proj && <div className="px-6 pb-6 space-y-3">
                {rd.projects.map((p, i) => (
                  <div key={i} className="p-3 bg-gray-50/50 rounded-xl border border-gray-100 relative group">
                    <button onClick={() => setRd(pr => ({ ...pr, projects: pr.projects.filter((_, j) => j !== i) }))} className="absolute top-2 right-2 opacity-0 group-hover:opacity-100 text-red-400 hover:text-red-600"><I d={ic.trash} c="w-4 h-4" /></button>
                    <Inp label="Name" value={p.name} onChange={(v: string) => { const a = [...rd.projects]; a[i] = { ...a[i], name: v }; setRd(pr => ({ ...pr, projects: a })); }} />
                  </div>
                ))}
              </div>}
            </div>

            {/* LANGUAGES */}
            <div className="bg-white rounded-2xl border border-gray-100 shadow-sm overflow-hidden">
              <Sec icon={ic.globe} title="Languages" count={rd.languages.length} open={os.langs} toggle={() => tog('langs')} color="bg-gradient-to-br from-teal-500 to-emerald-600" />
              {os.langs && <div className="px-6 pb-6 space-y-3">
                {rd.languages.map((l, i) => (
                  <div key={i} className="flex items-end gap-3 relative group">
                    <Inp label="Language" value={l.language} onChange={(v: string) => uLang(i, 'language', v)} cls="flex-1" />
                    <Inp label="Proficiency" value={l.proficiency} onChange={(v: string) => uLang(i, 'proficiency', v)} cls="flex-1" />
                    <button onClick={() => setRd(p => ({ ...p, languages: p.languages.filter((_, j) => j !== i) }))} className="pb-3 opacity-0 group-hover:opacity-100 text-red-400 hover:text-red-600"><I d={ic.trash} c="w-4 h-4" /></button>
                  </div>
                ))}
                <button onClick={() => setRd(p => ({ ...p, languages: [...p.languages, { language: '', proficiency: '' }] }))}
                  className="w-full py-2.5 border-2 border-dashed border-gray-200 rounded-xl text-sm text-gray-400 hover:text-teal-600 hover:border-teal-300 transition-colors">+ Add Language</button>
              </div>}
            </div>

            <div className="pt-4 pb-8">
              <button onClick={handleSave} disabled={saving}
                className="w-full py-3.5 bg-gradient-to-r from-blue-600 to-indigo-600 hover:from-blue-700 hover:to-indigo-700 text-white font-semibold rounded-xl shadow-lg shadow-blue-500/20 disabled:opacity-50 transition-all text-sm">
                {saving ? 'Saving...' : 'Save Profile'}
              </button>
            </div>
          </div>
        )}
      </main>
    </div>
  );
}
