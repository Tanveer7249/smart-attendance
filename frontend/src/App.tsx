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
      <div className="flex items-center justify-center min-h-screen bg-slate-50 dark:bg-navy-950">
        <div className="text-center space-y-4">
          <div className="w-12 h-12 border-4 border-brand-500 border-t-transparent rounded-full animate-spin mx-auto" />
          <p className="text-sm font-semibold text-slate-600 dark:text-slate-300">
            Initializing Smart Attendance Dual-Confirmation System...
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen flex flex-col bg-slate-50 text-slate-900 dark:bg-navy-950 dark:text-slate-100 transition-colors">
      <Navbar darkMode={darkMode} setDarkMode={setDarkMode} />

      <main className="flex-1 max-w-7xl w-full mx-auto px-4 sm:px-6 lg:px-8 py-6">
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
      <footer className="border-t border-slate-200/80 dark:border-navy-800/80 bg-white dark:bg-navy-950 py-6 text-center text-xs text-slate-500">
        <div className="max-w-7xl mx-auto px-4 flex flex-col sm:flex-row items-center justify-between gap-3">
          <div className="flex items-center gap-2">
            <ShieldCheck className="w-4 h-4 text-brand-600" />
            <span className="font-semibold text-slate-700 dark:text-slate-300">
              Smart Attendance Management System
            </span>
            <span className="text-slate-400">| Strict Dual-Confirmation Architecture</span>
          </div>
          <p className="text-[11px] text-slate-400">
            Attendance recorded as PRESENT only when confirmed by BOTH student and authorized teacher.
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
