import React, { useState, useEffect } from 'react';
import { AuthProvider, useAuth } from './context/AuthContext';
import { ToastProvider } from './context/ToastContext';
import { Navbar } from './components/layout/Navbar';
import { AdminDashboard } from './components/dashboards/AdminDashboard';
import { TeacherDashboard } from './components/dashboards/TeacherDashboard';
import { StudentDashboard } from './components/dashboards/StudentDashboard';
import { LoginModal } from './components/auth/LoginModal';
import { ShieldCheck } from 'lucide-react';

const DashboardContent: React.FC<{ darkMode: boolean; setDarkMode: (v: boolean) => void }> = ({
  darkMode,
  setDarkMode,
}) => {
  const { user, role, isLoading } = useAuth();

  if (isLoading) {
    return (
      <div className="flex items-center justify-center min-h-screen bg-slate-50 dark:bg-navy-950 relative overflow-hidden">
        {/* Ambient background */}
        <div className="ambient-orb-1 absolute -top-40 -left-40 w-96 h-96 rounded-full bg-gradient-to-br from-indigo-500/20 via-blue-600/15 to-transparent blur-3xl pointer-events-none" />
        <div className="ambient-orb-2 absolute -bottom-40 -right-40 w-96 h-96 rounded-full bg-gradient-to-tl from-amber-500/15 via-indigo-600/15 to-transparent blur-3xl pointer-events-none" />
        <div className="text-center space-y-4 relative z-10">
          <div className="w-12 h-12 border-4 border-brand-500 border-t-transparent rounded-full animate-spin mx-auto" />
          <p className="text-sm font-semibold text-slate-600 dark:text-slate-300">
            Initializing PI Pascals Attendance System...
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen flex flex-col bg-slate-50 text-slate-900 dark:bg-navy-950 dark:text-slate-100 transition-colors relative">
      {/* Live Animated Background Layer */}
      <div className="fixed inset-0 overflow-hidden pointer-events-none z-0">
        <div className="ambient-orb-1 absolute -top-48 -left-48 w-[32rem] h-[32rem] rounded-full bg-gradient-to-br from-indigo-600/20 via-blue-700/15 to-transparent blur-3xl" />
        <div className="ambient-orb-2 absolute top-1/4 -right-48 w-[36rem] h-[36rem] rounded-full bg-gradient-to-bl from-amber-500/12 via-indigo-500/15 to-transparent blur-3xl" />
        <div className="ambient-orb-3 absolute -bottom-48 left-1/3 w-[30rem] h-[30rem] rounded-full bg-gradient-to-tr from-purple-700/15 via-blue-600/12 to-transparent blur-3xl" />
        <div className="absolute inset-0 bg-grid-pattern opacity-60" />
      </div>

      <Navbar darkMode={darkMode} setDarkMode={setDarkMode} />

      <main className="flex-1 max-w-7xl w-full mx-auto px-4 sm:px-6 lg:px-8 py-6 relative z-10">
        {!user ? (
          <LoginModal />
        ) : (
          <>
            {role === 'ADMIN' && <AdminDashboard />}
            {role === 'TEACHER' && <TeacherDashboard />}
            {role === 'STUDENT' && <StudentDashboard />}
          </>
        )}
      </main>

      {/* Footer */}
      <footer className="border-t border-slate-200/80 dark:border-navy-800/80 bg-white/90 dark:bg-navy-950/90 backdrop-blur-md py-6 text-center text-xs text-slate-500 relative z-10">
        <div className="max-w-7xl mx-auto px-4 flex flex-col sm:flex-row items-center justify-between gap-3">
          <div className="flex items-center gap-2">
            <ShieldCheck className="w-4 h-4 text-brand-600" />
            <span className="font-bold text-slate-800 dark:text-slate-200">
              PI Pascals Attendance System
            </span>
            <span className="text-slate-400">| PI Pascals Institute PVT LTD</span>
          </div>
          <p className="text-[11px] text-slate-500 dark:text-slate-400">
            Dual-Confirmation Attendance Portal • All rights reserved
          </p>
        </div>
      </footer>
    </div>
  );
};

export function App() {
  const [darkMode, setDarkMode] = useState<boolean>(() => {
    return localStorage.getItem('theme') === 'dark';
  });

  useEffect(() => {
    if (darkMode) {
      document.documentElement.classList.add('dark');
      localStorage.setItem('theme', 'dark');
    } else {
      document.documentElement.classList.remove('dark');
      localStorage.setItem('theme', 'light');
    }
  }, [darkMode]);

  return (
    <AuthProvider>
      <ToastProvider>
        <DashboardContent darkMode={darkMode} setDarkMode={setDarkMode} />
      </ToastProvider>
    </AuthProvider>
  );
}

export default App;
