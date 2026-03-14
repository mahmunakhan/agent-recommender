'use client';

import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { useAuth } from '@/contexts/AuthContext';
import Navbar from '@/components/Navbar';
import { api } from '@/lib/api';

export default function RecruiterCandidatesPage() {
  const { user, loading } = useAuth();
  const router = useRouter();
  const [candidates, setCandidates] = useState<any[]>([]);
  const [loadingCandidates, setLoadingCandidates] = useState(true);

  useEffect(() => {
    if (!loading && !user) router.push('/login');
    if (!loading && user && user.role !== 'recruiter') router.push('/dashboard');
  }, [user, loading, router]);

  useEffect(() => {
    if (user && user.role === 'recruiter') {
      // Try to load candidates - this endpoint may not exist yet
      fetch('http://localhost:8000/recruiter/candidates', {
        headers: { 'Authorization': `Bearer ${localStorage.getItem('token')}` }
      })
        .then(r => r.ok ? r.json() : { candidates: [] })
        .then((data: any) => setCandidates(data.candidates || []))
        .catch(() => setCandidates([]))
        .finally(() => setLoadingCandidates(false));
    }
  }, [user]);

  if (loading || !user) {
    return <div className="min-h-screen flex items-center justify-center"><div className="text-lg">Loading...</div></div>;
  }

  return (
    <div className="min-h-screen bg-gray-100">
      <Navbar />

      <main className="max-w-7xl mx-auto py-6 px-4 sm:px-6 lg:px-8">
        <h2 className="text-2xl font-bold text-gray-900 mb-6">Candidates</h2>

        {loadingCandidates ? (
          <div className="text-center py-12 text-gray-400">Loading candidates...</div>
        ) : candidates.length === 0 ? (
          <div className="bg-white rounded-xl shadow-sm p-12 text-center border border-gray-200">
            <div className="text-5xl mb-4">👥</div>
            <h3 className="text-lg font-semibold text-gray-700 mb-2">No Candidates Yet</h3>
            <p className="text-gray-500 text-sm">
              Candidates who apply to your jobs will appear here.<br />
              Post a job to start receiving applications.
            </p>
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {candidates.map((candidate: any, idx: number) => (
              <div key={candidate.id || idx} className="bg-white rounded-xl shadow-sm p-6 border border-gray-200">
                <h4 className="font-semibold text-gray-800">
                  {candidate.first_name} {candidate.last_name}
                </h4>
                <p className="text-sm text-gray-500 mt-1">{candidate.headline || 'No headline'}</p>
                <p className="text-xs text-gray-400 mt-2">{candidate.email}</p>
              </div>
            ))}
          </div>
        )}
      </main>
    </div>
  );
}
