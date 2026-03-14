'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { useAuth } from '@/contexts/AuthContext';

/* ── Role-based nav links ── */
const candidateLinks = [
  { href: '/dashboard', label: 'Dashboard' },
  { href: '/jobs', label: 'Jobs' },
  { href: '/applications', label: 'My Applications' },
  { href: '/profile', label: 'Profile' },
];

const recruiterLinks = [
  { href: '/recruiter/dashboard', label: 'Dashboard' },
  { href: '/recruiter/post-job', label: 'Post Job' },
  { href: '/recruiter/my-jobs', label: 'My Postings' },
  { href: '/recruiter/candidates', label: 'Candidates' },
  { href: '/recruiter/talents', label: 'Talents' },
  
];

const adminLinks = [
  { href: '/admin/dashboard', label: 'Dashboard' },
  { href: '/admin/users', label: 'Users' },
  { href: '/admin/jobs', label: 'Jobs' },
  { href: '/admin/skills', label: 'Skills Taxonomy' },
];

function getNavLinks(role: string | undefined) {
  switch (role) {
    case 'recruiter': return recruiterLinks;
    case 'admin':     return adminLinks;
    default:          return candidateLinks;
  }
}

function getHomePath(role: string | undefined) {
  switch (role) {
    case 'recruiter': return '/recruiter/dashboard';
    case 'admin':     return '/admin/dashboard';
    default:          return '/dashboard';
  }
}

export default function Navbar() {
  const { user, logout } = useAuth();
  const pathname = usePathname();

  if (!user) return null;

  const navLinks = getNavLinks(user.role);

  return (
    <nav className="bg-white shadow-sm border-b border-gray-200">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex justify-between h-16">
          {/* Left: Logo + Links */}
          <div className="flex items-center">
            <Link href={getHomePath(user.role)} className="text-xl font-bold text-blue-600">
              JobMatch AI
            </Link>
            <div className="ml-10 hidden sm:flex space-x-4">
              {navLinks.map((link) => {
                const isActive = pathname === link.href || pathname.startsWith(link.href + '/');
                return (
                  <Link
                    key={link.href}
                    href={link.href}
                    className={`px-3 py-2 rounded-md text-sm font-medium transition-colors ${
                      isActive
                        ? 'text-gray-900 bg-gray-100'
                        : 'text-gray-500 hover:text-gray-900'
                    }`}
                  >
                    {link.label}
                  </Link>
                );
              })}
            </div>
          </div>

          {/* Right: Bell + User + Role Badge + Logout */}
          <div className="flex items-center space-x-4">
            {/* Notification bell */}
            <button className="text-gray-400 hover:text-gray-600 transition-colors relative">
              <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor" className="w-5 h-5">
                <path strokeLinecap="round" strokeLinejoin="round" d="M14.857 17.082a23.848 23.848 0 005.454-1.31A8.967 8.967 0 0118 9.75v-.7V9A6 6 0 006 9v.75a8.967 8.967 0 01-2.312 6.022c1.733.64 3.56 1.085 5.455 1.31m5.714 0a24.255 24.255 0 01-5.714 0m5.714 0a3 3 0 11-5.714 0" />
              </svg>
            </button>

            {/* User info */}
            <div className="flex items-center gap-2">
              <div className="text-right">
                <span className="text-sm text-gray-700 font-medium">
                  {user.first_name} {user.last_name}
                </span>
                <span className={`ml-2 px-2 py-0.5 rounded-full text-[10px] font-semibold uppercase tracking-wider ${
                  user.role === 'recruiter'
                    ? 'bg-purple-100 text-purple-700'
                    : user.role === 'admin'
                    ? 'bg-red-100 text-red-700'
                    : 'bg-blue-100 text-blue-700'
                }`}>
                  {user.role}
                </span>
              </div>
              <button
                onClick={logout}
                className="text-sm text-red-600 hover:text-red-800 font-medium"
              >
                Logout
              </button>
            </div>
          </div>
        </div>
      </div>

      {/* Mobile nav */}
      <div className="sm:hidden flex items-center gap-1 px-4 pb-2 overflow-x-auto">
        {navLinks.map((link) => {
          const isActive = pathname === link.href || pathname.startsWith(link.href + '/');
          return (
            <Link
              key={link.href}
              href={link.href}
              className={`px-3 py-1.5 rounded-lg text-xs font-medium whitespace-nowrap transition-colors ${
                isActive
                  ? 'bg-blue-50 text-blue-700'
                  : 'text-gray-500 hover:text-gray-800'
              }`}
            >
              {link.label}
            </Link>
          );
        })}
      </div>
    </nav>
  );
}
