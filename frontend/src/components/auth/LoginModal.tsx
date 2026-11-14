import React, { useState } from 'react';
import { useAuth } from '../../context/AuthContext';
import { useToast } from '../../context/ToastContext';
import { Shield, UserCheck, GraduationCap, LogIn, CheckCircle2, Key, Info } from 'lucide-react';

export const LoginModal: React.FC<{ isOpen?: boolean; onClose?: () => void }> = () => {
  const { login } = useAuth();
  const toast = useToast();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [loading, setLoading] = useState(false);
  const [activeRoleTab, setActiveRoleTab] = useState<'ADMIN' | 'TEACHER' | 'STUDENT'>('ADMIN');

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    try {
      await login(email, password);
      toast.success('Signed in successfully');
    } catch (err: any) {
      toast.error('Login Failed', err.message);
    } finally {
      setLoading(false);
    }
  };

  const fillAdminCredentials = () => {
    setEmail('admin@smartattendance.edu');
    setPassword('Admin@123');
    setActiveRoleTab('ADMIN');
    toast.info('Initial Admin credentials loaded');
  };

  return (
    <div className="flex items-center justify-center min-h-[75vh] p-4">
      <div className="bg-white dark:bg-navy-900 rounded-3xl border border-slate-200 dark:border-navy-800 max-w-md w-full p-8 shadow-2xl space-y-6">
        {/* Header */}
        <div className="text-center space-y-1">
          <div className="w-12 h-12 rounded-2xl bg-gradient-to-tr from-brand-600 to-indigo-500 text-white flex items-center justify-center mx-auto shadow-lg shadow-brand-500/30">
            <CheckCircle2 className="w-7 h-7" />
          </div>
          <h2 className="text-2xl font-bold text-slate-900 dark:text-white pt-2">Sign In to SmartAttend</h2>
          <p className="text-xs text-slate-500">Dual-Confirmation Attendance Portal</p>
        </div>

        {/* Role Tab Selector */}
        <div className="flex bg-slate-100 dark:bg-navy-800 p-1 rounded-xl text-xs font-semibold">
          <button
            type="button"
            onClick={() => {
              setActiveRoleTab('ADMIN');
              setEmail('admin@smartattendance.edu');
              setPassword('Admin@123');
            }}
            className={`flex-1 py-2 rounded-lg flex items-center justify-center gap-1.5 transition-all ${
              activeRoleTab === 'ADMIN' ? 'bg-white dark:bg-navy-900 text-rose-600 shadow-sm' : 'text-slate-500'
            }`}
          >
            <Shield className="w-3.5 h-3.5" />
            Admin
          </button>
          <button
            type="button"
            onClick={() => {
              setActiveRoleTab('TEACHER');
              setEmail('');
              setPassword('');
            }}
            className={`flex-1 py-2 rounded-lg flex items-center justify-center gap-1.5 transition-all ${
              activeRoleTab === 'TEACHER' ? 'bg-white dark:bg-navy-900 text-brand-600 shadow-sm' : 'text-slate-500'
            }`}
          >
            <UserCheck className="w-3.5 h-3.5" />
            Teacher
          </button>
          <button
            type="button"
            onClick={() => {
              setActiveRoleTab('STUDENT');
              setEmail('');
              setPassword('');
            }}
            className={`flex-1 py-2 rounded-lg flex items-center justify-center gap-1.5 transition-all ${
              activeRoleTab === 'STUDENT' ? 'bg-white dark:bg-navy-900 text-emerald-600 shadow-sm' : 'text-slate-500'
            }`}
          >
            <GraduationCap className="w-3.5 h-3.5" />
            Student
          </button>
        </div>

        {/* Helpful Info Note */}
        <div className="p-3 rounded-xl bg-slate-50 dark:bg-navy-800/60 border border-slate-200/60 dark:border-navy-700/60 flex items-start gap-2.5 text-[11px] text-slate-600 dark:text-slate-400">
          <Info className="w-4 h-4 text-brand-500 shrink-0 mt-0.5" />
          <p>
            {activeRoleTab === 'ADMIN' && (
              <span>System Administrator can create teacher accounts, student accounts, and assign students to teachers.</span>
            )}
            {activeRoleTab === 'TEACHER' && (
              <span>Teacher accounts are created by the Admin. Use the email and password provided by your Administrator.</span>
            )}
            {activeRoleTab === 'STUDENT' && (
              <span>Student accounts are created by the Admin. Use the email/ID and password provided by your Administrator.</span>
            )}
          </p>
        </div>

        {/* Login Form */}
        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-xs font-semibold text-slate-700 dark:text-slate-300 mb-1">
              Email / Account ID
            </label>
            <input
              type="email"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder={
                activeRoleTab === 'ADMIN'
                  ? 'admin@smartattendance.edu'
                  : activeRoleTab === 'TEACHER'
                  ? 'teacher@school.edu'
                  : 'student@school.edu'
              }
              className="w-full text-xs px-3.5 py-2.5 rounded-xl bg-slate-50 dark:bg-navy-800 border border-slate-200 dark:border-navy-700 text-slate-900 dark:text-white focus:outline-none focus:ring-2 focus:ring-brand-500"
            />
          </div>

          <div>
            <label className="block text-xs font-semibold text-slate-700 dark:text-slate-300 mb-1">
              Password
            </label>
            <input
              type="password"
              required
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="••••••••"
              className="w-full text-xs px-3.5 py-2.5 rounded-xl bg-slate-50 dark:bg-navy-800 border border-slate-200 dark:border-navy-700 text-slate-900 dark:text-white focus:outline-none focus:ring-2 focus:ring-brand-500"
            />
          </div>

          <button
            type="submit"
            disabled={loading}
            className="w-full py-2.5 rounded-xl text-xs font-bold bg-brand-600 hover:bg-brand-500 text-white shadow-lg shadow-brand-500/20 transition-all flex items-center justify-center gap-2 mt-2"
          >
            <LogIn className="w-4 h-4" />
            {loading ? 'Authenticating...' : `Sign In as ${activeRoleTab}`}
          </button>
        </form>

        {/* Quick initial admin button */}
        {activeRoleTab === 'ADMIN' && (
          <div className="pt-2 text-center">
            <button
              type="button"
              onClick={fillAdminCredentials}
              className="text-xs text-brand-600 hover:text-brand-700 dark:text-brand-400 font-semibold underline flex items-center justify-center gap-1 mx-auto"
            >
              <Key className="w-3.5 h-3.5" />
              Fill Initial Admin Credentials (Admin@123)
            </button>
          </div>
        )}
      </div>
    </div>
  );
};
