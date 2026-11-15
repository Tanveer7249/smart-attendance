import React, { useState, useEffect } from 'react';
import { api } from '../../services/api';
import {
  TeacherDashboardStats, ClassSession, AttendanceRecord,
  Subject, AttendanceStatus
} from '../../types';
import { useToast } from '../../context/ToastContext';
import { useAuth } from '../../context/AuthContext';
import { QRCodeSVG } from 'qrcode.react';
import {
  Play, StopCircle, RefreshCw, CheckCircle2, XCircle, Clock,
  Users, Layers, Plus, Calendar, AlertCircle, Copy, Shield,
  Eye, CheckCheck, UserCheck, Search, BookOpen, ChevronDown
} from 'lucide-react';

export const TeacherDashboard: React.FC = () => {
  const toast = useToast();
  const { user } = useAuth();
  const [stats, setStats] = useState<TeacherDashboardStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState<'classes' | 'students'>('classes');

  // Active / selected live session
  const [liveSession, setLiveSession] = useState<ClassSession | null>(null);
  const [attendees, setAttendees] = useState<AttendanceRecord[]>([]);
  const [qrToken, setQrToken] = useState<string>('');
  const [qrSecondsLeft, setQrSecondsLeft] = useState<number>(30);
  const [loadingAttendees, setLoadingAttendees] = useState(false);

  // Student list search
  const [assignedStudentSearch, setAssignedStudentSearch] = useState('');

  // New Class Modal
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [courses, setCourses] = useState<Subject[]>([]);
  const [selectedStudentIds, setSelectedStudentIds] = useState<number[]>([]);
  const [newClassForm, setNewClassForm] = useState({
    title: '',
    subject_id: 0,
    session_date: new Date().toISOString().split('T')[0],
    start_time: '09:00',
    duration_minutes: 60,
    late_threshold_minutes: 15,
    require_gps: false,
  });

  // Manual Correction Modal
  const [correctionModalRecord, setCorrectionModalRecord] = useState<AttendanceRecord | null>(null);
  const [correctionStatus, setCorrectionStatus] = useState<AttendanceStatus>('PRESENT');
  const [correctionReason, setCorrectionReason] = useState<string>('');

  // Rejection Reason Modal
  const [rejectModalRecord, setRejectModalRecord] = useState<AttendanceRecord | null>(null);
  const [rejectionReason, setRejectionReason] = useState<string>('Student not physically present in class');

  const loadDashboard = async () => {
    try {
      setLoading(true);
      const data = await api.getTeacherDashboard();
      setStats(data);

      const subjects = await api.getSubjects(data.teacher_id);
      setCourses(subjects);

      if (subjects.length > 0 && newClassForm.subject_id === 0) {
        setNewClassForm((prev) => ({
          ...prev,
          subject_id: subjects[0].id,
          title: `${subjects[0].name} Lecture`,
        }));
      }

      if (data.active_session) {
        setLiveSession(data.active_session);
        await loadAttendees(data.active_session.id);
      }
    } catch (e: any) {
      toast.error('Failed to load teacher dashboard', e.message);
    } finally {
      setLoading(false);
    }
  };

  const loadAttendees = async (sessionId: number) => {
    try {
      setLoadingAttendees(true);
      const list = await api.getSessionAttendees(sessionId);
      setAttendees(list);
    } catch (e: any) {
      console.error(e);
    } finally {
      setLoadingAttendees(false);
    }
  };

  useEffect(() => {
    loadDashboard();
  }, []);

  // WebSocket / Live Feed for active session
  useEffect(() => {
    if (!liveSession || liveSession.status !== 'ACTIVE') return;

    // Refresh QR token immediately on load
    api.refreshQrToken(liveSession.id).then((res) => {
      setQrToken(res.token);
      setQrSecondsLeft(30);
    }).catch(console.error);

    // Refresh QR token every 30s
    const qrInterval = setInterval(async () => {
      try {
        const res = await api.refreshQrToken(liveSession.id);
        setQrToken(res.token);
        setQrSecondsLeft(30);
      } catch (err) {
        console.error('QR token refresh error:', err);
      }
    }, 30000);

    // Countdown timer for ring
    const countdownInterval = setInterval(() => {
      setQrSecondsLeft((prev) => (prev > 1 ? prev - 1 : 30));
    }, 1000);

    // Poll attendees every 3s
    const pollInterval = setInterval(() => {
      loadAttendees(liveSession.id);
    }, 3000);

    // Connect WebSocket
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${protocol}//${window.location.host}/ws/attendance/${liveSession.id}`;
    let socket: WebSocket | null = null;
    try {
      socket = new WebSocket(wsUrl);
      socket.onmessage = (event) => {
        try {
          const msg = JSON.parse(event.data);
          if (msg.type === 'STUDENT_SUBMISSION') {
            toast.info(`New submission: ${msg.student_name} marked attendance!`);
            loadAttendees(liveSession.id);
          } else if (msg.type === 'TEACHER_CONFIRMED' || msg.type === 'SESSION_CLOSED') {
            loadAttendees(liveSession.id);
          }
        } catch (e) {
          console.error(e);
        }
      };
    } catch (e) {
      console.warn('WS connect fallback to polling:', e);
    }

    return () => {
      clearInterval(qrInterval);
      clearInterval(countdownInterval);
      clearInterval(pollInterval);
      if (socket) socket.close();
    };
  }, [liveSession?.id, liveSession?.status]);

  const handleStartClass = async (sessionId: number) => {
    try {
      const updated = await api.startClass(sessionId);
      setLiveSession(updated);
      toast.success('Class session started!', 'Dynamic QR code and attendance PIN are now live.');
      loadDashboard();
    } catch (e: any) {
      toast.error('Failed to start class', e.message);
    }
  };

  const handleCloseSession = async () => {
    if (!liveSession) return;
    if (!confirm('Are you sure you want to finalize and close this attendance session? Unconfirmed students will be marked ABSENT.')) {
      return;
    }
    try {
      const closed = await api.closeSession(liveSession.id);
      setLiveSession(closed);
      toast.success('Session finalized and closed!', 'All unconfirmed attendance finalized as ABSENT.');
      loadDashboard();
      loadAttendees(closed.id);
    } catch (e: any) {
      toast.error('Failed to close session', e.message);
    }
  };

  const handleConfirmSingle = async (rec: AttendanceRecord, asStatus: AttendanceStatus = 'PRESENT') => {
    if (!liveSession) return;
    try {
      await api.teacherConfirmStudents(liveSession.id, [rec.id], asStatus);
      toast.success(
        `Verified: ${rec.student_name}`,
        `Dual confirmation satisfied! Status marked as ${asStatus}.`
      );
      loadAttendees(liveSession.id);
    } catch (e: any) {
      toast.error('Confirmation failed', e.message);
    }
  };

  const handleBulkConfirmMarked = async () => {
    if (!liveSession) return;
    const markedIds = attendees
      .filter((a) => a.student_confirmation && !a.teacher_confirmation && a.id > 0)
      .map((a) => a.id);

    if (markedIds.length === 0) {
      toast.info('No pending submissions waiting for confirmation.');
      return;
    }

    try {
      await api.teacherConfirmStudents(liveSession.id, markedIds, 'PRESENT');
      toast.success(`Dual-confirmed ${markedIds.length} student submissions!`);
      loadAttendees(liveSession.id);
    } catch (e: any) {
      toast.error('Bulk confirmation failed', e.message);
    }
  };

  const handleConfirmReject = async () => {
    if (!liveSession || !rejectModalRecord) return;
    try {
      await api.teacherRejectStudent(liveSession.id, rejectModalRecord.id, rejectionReason);
      toast.warning(`Submission rejected for ${rejectModalRecord.student_name}`);
      setRejectModalRecord(null);
      loadAttendees(liveSession.id);
    } catch (e: any) {
      toast.error('Rejection failed', e.message);
    }
  };

  const handleManualCorrection = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!correctionModalRecord) return;
    try {
      await api.manualAttendanceCorrection(
        correctionModalRecord.id,
        correctionStatus,
        correctionReason
      );
      toast.success('Attendance corrected', 'Audit trail updated successfully.');
      setCorrectionModalRecord(null);
      setCorrectionReason('');
      if (liveSession) loadAttendees(liveSession.id);
    } catch (e: any) {
      toast.error('Manual correction failed', e.message);
    }
  };

  const handleCreateClass = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newClassForm.subject_id) {
      toast.warning('Please select a course');
      return;
    }
    if (selectedStudentIds.length === 0) {
      toast.warning('Please select at least one student for this class session');
      return;
    }

    try {
      const payload: any = {
        title: newClassForm.title,
        subject_id: newClassForm.subject_id,
        session_date: newClassForm.session_date,
        start_time: newClassForm.start_time,
        duration_minutes: newClassForm.duration_minutes,
        late_threshold_minutes: newClassForm.late_threshold_minutes,
        require_gps: newClassForm.require_gps,
        student_ids: selectedStudentIds,
      };

      const created = await api.createClass(payload);
      toast.success('Class session scheduled specifically for selected student(s)!');
      setShowCreateModal(false);
      setSelectedStudentIds([]);
      loadDashboard();
      if (!liveSession) {
        setLiveSession(created);
      }
    } catch (e: any) {
      toast.error('Failed to create class', e.message);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-[60vh]">
        <div className="text-center space-y-3">
          <div className="w-10 h-10 border-4 border-brand-500 border-t-transparent rounded-full animate-spin mx-auto" />
          <p className="text-sm font-medium text-slate-500">Loading Faculty Console...</p>
        </div>
      </div>
    );
  }

  // Calculate live session counters
  const totalEnrolled = attendees.length;
  const markedByStudentCount = attendees.filter((a) => a.student_confirmation).length;
  const confirmedPresentCount = attendees.filter((a) => a.status === 'PRESENT').length;
  const lateCount = attendees.filter((a) => a.status === 'LATE').length;
  const pendingTeacherCount = attendees.filter((a) => a.student_confirmation && !a.teacher_confirmation).length;
  const notMarkedCount = attendees.filter((a) => !a.student_confirmation && a.status === 'NOT_MARKED').length;

  const assignedStudents = stats?.assigned_students || [];
  const filteredAssignedStudents = assignedStudents.filter((s) => {
    if (!assignedStudentSearch) return true;
    const q = assignedStudentSearch.toLowerCase();
    return (
      s.full_name.toLowerCase().includes(q) ||
      s.email.toLowerCase().includes(q)
    );
  });

  return (
    <div className="space-y-6 pb-12">
      {/* Top Welcome & Actions Header */}
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 bg-gradient-to-r from-navy-950 via-[#0B132B] to-navy-900 p-6 rounded-2xl text-white shadow-2xl shadow-navy-950/30 border border-slate-700/50 backdrop-blur-md">
        <div>
          <span className="text-xs font-bold uppercase tracking-wider text-amber-400">Faculty Dashboard • PI Pascals Institute PVT LTD</span>
          <h1 className="text-2xl font-extrabold tracking-tight mt-0.5">Welcome, {stats?.teacher_name || user?.full_name || 'Faculty Member'}</h1>
          <p className="text-xs text-slate-300 mt-1 font-medium">
            Department of {stats?.department || user?.teacher_profile?.department || 'Academics'} • PI Pascals Attendance System
          </p>
        </div>

        <div className="flex items-center gap-3">
          <button
            onClick={() => {
              if (courses.length > 0 && newClassForm.subject_id === 0) {
                setNewClassForm((prev) => ({
                  ...prev,
                  subject_id: courses[0].id,
                  title: `${courses[0].name} Lecture`,
                }));
              }
              setShowCreateModal(true);
            }}
            className="flex items-center gap-2 px-4 py-2.5 rounded-xl text-xs font-bold bg-brand-600 hover:bg-brand-500 text-white shadow-lg shadow-brand-500/20 transition-all"
          >
            <Plus className="w-4 h-4" />
            Schedule Class Session
          </button>
        </div>
      </div>

      {/* Tab Switcher */}
      <div className="flex items-center gap-2 border-b border-slate-200 dark:border-navy-800 pb-2">
        <button
          onClick={() => setActiveTab('classes')}
          className={`flex items-center gap-2 px-4 py-2 rounded-xl text-xs font-bold transition-all ${
            activeTab === 'classes'
              ? 'bg-brand-600 text-white shadow-md shadow-brand-500/20'
              : 'text-slate-600 dark:text-slate-400 hover:bg-slate-100 dark:hover:bg-navy-800'
          }`}
        >
          <Layers className="w-4 h-4" />
          Classes &amp; Live Attendance
          {liveSession && liveSession.status === 'ACTIVE' && (
            <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse ml-1" />
          )}
        </button>

        <button
          onClick={() => setActiveTab('students')}
          className={`flex items-center gap-2 px-4 py-2 rounded-xl text-xs font-bold transition-all ${
            activeTab === 'students'
              ? 'bg-brand-600 text-white shadow-md shadow-brand-500/20'
              : 'text-slate-600 dark:text-slate-400 hover:bg-slate-100 dark:hover:bg-navy-800'
          }`}
        >
          <UserCheck className="w-4 h-4" />
          My Assigned Students ({assignedStudents.length})
        </button>
      </div>

      {/* TAB 1: CLASSES & LIVE ROOM */}
      {activeTab === 'classes' && (
        <div className="space-y-6">
          {/* LIVE CLASS ATTENDANCE ENGINE ROOM */}
          {liveSession && liveSession.status === 'ACTIVE' && (
            <div className="bg-white dark:bg-navy-900 rounded-2xl border-2 border-brand-500/80 p-6 shadow-2xl space-y-6 animate-fade-in relative overflow-hidden">
              <div className="absolute top-0 right-0 bg-brand-600 text-white text-[11px] font-bold px-4 py-1 rounded-bl-xl uppercase tracking-wider flex items-center gap-1.5 shadow-sm">
                <span className="w-2 h-2 rounded-full bg-emerald-400 animate-ping" />
                Live Classroom Attendance Active
              </div>

              {/* Session Header */}
              <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-4 pt-2">
                <div>
                  <span className="text-xs font-semibold px-2 py-0.5 rounded bg-brand-50 text-brand-700 dark:bg-brand-950 dark:text-brand-300 font-mono">
                    {liveSession.subject_code} - {liveSession.subject_name}
                  </span>
                  <h2 className="text-xl font-bold text-slate-900 dark:text-white mt-1">
                    {liveSession.title}
                  </h2>
                  <p className="text-xs text-slate-500 mt-0.5">
                    Date: <span className="font-mono">{liveSession.session_date}</span> |
                    Started: <span className="font-mono">{liveSession.start_time}</span> |
                    Late Threshold: {liveSession.late_threshold_minutes} mins
                  </p>
                </div>

                <div className="flex items-center gap-2">
                  <button
                    onClick={handleBulkConfirmMarked}
                    disabled={pendingTeacherCount === 0}
                    className={`flex items-center gap-1.5 px-4 py-2 rounded-xl text-xs font-bold transition-all shadow-md ${
                      pendingTeacherCount > 0
                        ? 'bg-emerald-600 hover:bg-emerald-500 text-white shadow-emerald-500/20'
                        : 'bg-slate-100 text-slate-400 dark:bg-navy-800 dark:text-slate-600 cursor-not-allowed'
                    }`}
                  >
                    <CheckCheck className="w-4 h-4" />
                    Confirm All Marked ({pendingTeacherCount})
                  </button>

                  <button
                    onClick={handleCloseSession}
                    className="flex items-center gap-1.5 px-4 py-2 rounded-xl text-xs font-bold bg-rose-600 hover:bg-rose-500 text-white shadow-md shadow-rose-500/20"
                  >
                    <StopCircle className="w-4 h-4" />
                    Finalize &amp; End Class
                  </button>
                </div>
              </div>

              {/* Live Dual Confirmation Panel */}
              <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 items-stretch">
                {/* Dynamic QR Code & PIN Display */}
                <div className="lg:col-span-1 bg-gradient-to-b from-slate-50 to-brand-50/40 dark:from-navy-800/80 dark:to-brand-950/20 p-5 rounded-2xl border border-brand-200 dark:border-brand-900/40 flex flex-col items-center justify-center text-center">
                  <div className="flex items-center justify-between w-full mb-3 px-2">
                    <span className="text-xs font-bold uppercase tracking-wider text-brand-700 dark:text-brand-300">
                      Dynamic QR Code
                    </span>
                    <span className="text-[11px] font-mono px-2 py-0.5 rounded-full bg-brand-100 text-brand-800 dark:bg-brand-900 dark:text-brand-200">
                      Refreshes in {qrSecondsLeft}s
                    </span>
                  </div>

                  {/* QR Container */}
                  <div className="bg-white p-4 rounded-2xl shadow-xl border border-slate-200 dark:border-navy-700 relative">
                    {qrToken ? (
                      <QRCodeSVG
                        value={JSON.stringify({
                          session_id: liveSession.id,
                          token: qrToken,
                          pin: liveSession.attendance_pin,
                        })}
                        size={190}
                        level="H"
                        includeMargin={false}
                      />
                    ) : (
                      <div className="w-[190px] h-[190px] flex items-center justify-center">
                        <RefreshCw className="w-8 h-8 animate-spin text-brand-500" />
                      </div>
                    )}
                  </div>

                  {/* Temporary 6-digit PIN */}
                  <div className="mt-4 w-full bg-white dark:bg-navy-900 p-3 rounded-xl border border-slate-200 dark:border-navy-700">
                    <span className="text-[11px] font-semibold text-slate-500 uppercase tracking-wider block">
                      Teacher Secret Attendance PIN
                    </span>
                    <span className="text-3xl font-extrabold tracking-widest text-brand-600 dark:text-brand-400 font-mono mt-0.5 block">
                      {liveSession.attendance_pin}
                    </span>
                    <span className="text-[10px] text-slate-400">
                      Hidden from student portal. Provide to present students in class.
                    </span>
                  </div>
                </div>

                {/* Attendance Status Dashboard Counters */}
                <div className="lg:col-span-2 flex flex-col justify-between space-y-4">
                  <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
                    <div className="bg-slate-50 dark:bg-navy-800/80 p-3.5 rounded-xl border border-slate-200/80 dark:border-navy-700">
                      <span className="text-[11px] font-semibold text-slate-500">Students In Session</span>
                      <p className="text-2xl font-bold text-slate-900 dark:text-white mt-1">{totalEnrolled}</p>
                      <p className="text-[10px] text-slate-400">Rostered for this class</p>
                    </div>

                    <div className="bg-brand-50/50 dark:bg-brand-950/20 p-3.5 rounded-xl border border-brand-200 dark:border-brand-900/40">
                      <span className="text-[11px] font-semibold text-brand-700 dark:text-brand-300">Student Marked</span>
                      <p className="text-2xl font-bold text-brand-600 dark:text-brand-400 mt-1">{markedByStudentCount}</p>
                      <p className="text-[10px] text-brand-600/70">Step 1: Submitted PIN/QR</p>
                    </div>

                    <div className="bg-emerald-50/50 dark:bg-emerald-950/20 p-3.5 rounded-xl border border-emerald-200 dark:border-emerald-900/40">
                      <span className="text-[11px] font-semibold text-emerald-700 dark:text-emerald-300">Dual-Confirmed</span>
                      <p className="text-2xl font-bold text-emerald-600 dark:text-emerald-400 mt-1">{confirmedPresentCount}</p>
                      <p className="text-[10px] text-emerald-600/70">Official PRESENT</p>
                    </div>

                    <div className="bg-amber-50/50 dark:bg-amber-950/20 p-3.5 rounded-xl border border-amber-200 dark:border-amber-900/40">
                      <span className="text-[11px] font-semibold text-amber-700 dark:text-amber-300">Awaiting Your Confirm</span>
                      <p className="text-2xl font-bold text-amber-600 dark:text-amber-400 mt-1">{pendingTeacherCount}</p>
                      <p className="text-[10px] text-amber-600/70">Needs physical verification</p>
                    </div>

                    <div className="bg-indigo-50/50 dark:bg-indigo-950/20 p-3.5 rounded-xl border border-indigo-200 dark:border-indigo-900/40">
                      <span className="text-[11px] font-semibold text-indigo-700 dark:text-indigo-300">Late Marked</span>
                      <p className="text-2xl font-bold text-indigo-600 dark:text-indigo-400 mt-1">{lateCount}</p>
                      <p className="text-[10px] text-indigo-600/70">&gt; {liveSession.late_threshold_minutes} min late</p>
                    </div>

                    <div className="bg-slate-100 dark:bg-navy-950 p-3.5 rounded-xl border border-slate-200 dark:border-navy-800">
                      <span className="text-[11px] font-semibold text-slate-500">Unresolved / Absent</span>
                      <p className="text-2xl font-bold text-slate-600 dark:text-slate-400 mt-1">{notMarkedCount}</p>
                      <p className="text-[10px] text-slate-400">Marked ABSENT at close</p>
                    </div>
                  </div>

                  {/* Dual Confirmation Protocol Explainer Strip */}
                  <div className="bg-brand-50/60 dark:bg-brand-950/40 border border-brand-200/80 dark:border-brand-900/50 p-3.5 rounded-xl text-xs flex items-center gap-3">
                    <Shield className="w-5 h-5 text-brand-600 shrink-0" />
                    <p className="text-slate-700 dark:text-slate-300 leading-relaxed text-[11px]">
                      <strong>Dual-Confirmation Enforcement:</strong> Students who scan the QR or type the PIN enter the <em>STUDENT_MARKED</em> state. Official <strong>PRESENT</strong> status is awarded only after you confirm their physical presence.
                    </p>
                  </div>
                </div>
              </div>

              {/* Student Verification Table */}
              <div className="border border-slate-200 dark:border-navy-800 rounded-xl overflow-hidden">
                <div className="p-3 bg-slate-50 dark:bg-navy-800/80 border-b border-slate-200 dark:border-navy-800 flex items-center justify-between">
                  <span className="text-xs font-bold text-slate-900 dark:text-white uppercase tracking-wider">
                    Selected Students Verification Feed ({attendees.length})
                  </span>
                  <button
                    onClick={() => loadAttendees(liveSession.id)}
                    className="flex items-center gap-1 text-[11px] font-semibold text-brand-600 hover:text-brand-700 dark:text-brand-400"
                  >
                    <RefreshCw className={`w-3.5 h-3.5 ${loadingAttendees ? 'animate-spin' : ''}`} />
                    Refresh Feed
                  </button>
                </div>

                <div className="overflow-x-auto max-h-96 overflow-y-auto">
                  <table className="w-full text-xs text-left">
                    <thead className="bg-slate-100 dark:bg-navy-900 text-slate-600 dark:text-slate-400 font-semibold sticky top-0 z-10">
                      <tr>
                        <th className="py-2.5 px-3">Student Name</th>
                        <th className="py-2.5 px-3">Student Marked</th>
                        <th className="py-2.5 px-3">Teacher Confirmed</th>
                        <th className="py-2.5 px-3">Final Status</th>
                        <th className="py-2.5 px-3 text-right">Verification Actions</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-100 dark:divide-navy-800">
                      {attendees.map((rec) => {
                        const isPending = rec.student_confirmation && !rec.teacher_confirmation;
                        const isPresent = rec.status === 'PRESENT';

                        return (
                          <tr
                            key={rec.student_id}
                            className={`transition-colors ${
                              isPending
                                ? 'bg-amber-50/40 dark:bg-amber-950/10'
                                : isPresent
                                ? 'bg-emerald-50/20 dark:bg-emerald-950/10'
                                : 'hover:bg-slate-50/50 dark:hover:bg-navy-800/40'
                            }`}
                          >
                            <td className="py-2.5 px-3 font-semibold text-slate-900 dark:text-white flex items-center gap-2">
                              <div className="w-6 h-6 rounded-full bg-slate-200 dark:bg-navy-700 flex items-center justify-center font-bold text-[10px]">
                                {rec.student_name ? rec.student_name.charAt(0) : 'S'}
                              </div>
                              <div>
                                <span>{rec.student_name}</span>
                                {rec.student_device && (
                                  <p className="text-[10px] text-slate-400 font-normal truncate max-w-[150px]">
                                    {rec.student_device}
                                  </p>
                                )}
                              </div>
                            </td>

                            <td className="py-2.5 px-3">
                              {rec.student_confirmation ? (
                                <span className="flex items-center gap-1 text-emerald-600 dark:text-emerald-400 font-semibold text-[11px]">
                                  <CheckCircle2 className="w-3.5 h-3.5" />
                                  Confirmed
                                  <span className="text-[10px] text-slate-400 font-normal">
                                    ({rec.student_confirmed_at ? new Date(rec.student_confirmed_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) : 'now'})
                                  </span>
                                </span>
                              ) : (
                                <span className="text-slate-400 text-[11px]">Not yet submitted</span>
                              )}
                            </td>

                            <td className="py-2.5 px-3">
                              {rec.teacher_confirmation ? (
                                <span className="flex items-center gap-1 text-emerald-600 dark:text-emerald-400 font-semibold text-[11px]">
                                  <CheckCircle2 className="w-3.5 h-3.5" />
                                  Confirmed
                                </span>
                              ) : (
                                <span className="text-amber-600 dark:text-amber-400 font-medium text-[11px]">
                                  Pending Review
                                </span>
                              )}
                            </td>

                            <td className="py-2.5 px-3">
                              <span
                                className={`px-2 py-0.5 rounded text-[10px] font-bold ${
                                  rec.status === 'PRESENT'
                                    ? 'bg-emerald-100 text-emerald-700 dark:bg-emerald-950 dark:text-emerald-300'
                                    : rec.status === 'LATE'
                                    ? 'bg-indigo-100 text-indigo-700 dark:bg-indigo-950 dark:text-indigo-300'
                                    : rec.status === 'STUDENT_MARKED'
                                    ? 'bg-amber-100 text-amber-700 dark:bg-amber-950 dark:text-amber-300 animate-pulse'
                                    : rec.status === 'REJECTED'
                                    ? 'bg-rose-100 text-rose-700 dark:bg-rose-950 dark:text-rose-300'
                                    : 'bg-slate-100 text-slate-600 dark:bg-navy-800 dark:text-slate-400'
                                }`}
                              >
                                {rec.status}
                              </span>
                            </td>

                            <td className="py-2.5 px-3 text-right">
                              <div className="flex items-center justify-end gap-1.5">
                                {rec.id > 0 && !rec.teacher_confirmation && (
                                  <>
                                    <button
                                      onClick={() => handleConfirmSingle(rec, 'PRESENT')}
                                      className="px-2.5 py-1 rounded-lg text-[11px] font-bold bg-emerald-600 hover:bg-emerald-500 text-white shadow-sm"
                                      title="Verify in classroom and mark PRESENT"
                                    >
                                      Confirm Present
                                    </button>
                                    <button
                                      onClick={() => handleConfirmSingle(rec, 'LATE')}
                                      className="px-2.5 py-1 rounded-lg text-[11px] font-semibold bg-amber-600 hover:bg-amber-500 text-white"
                                      title="Mark as Late arrival"
                                    >
                                      Late
                                    </button>
                                    <button
                                      onClick={() => setRejectModalRecord(rec)}
                                      className="px-2.5 py-1 rounded-lg text-[11px] font-semibold bg-rose-600 hover:bg-rose-500 text-white"
                                      title="Reject student claim"
                                    >
                                      Reject
                                    </button>
                                  </>
                                )}

                                {rec.id > 0 && rec.teacher_confirmation && (
                                  <button
                                    onClick={() => {
                                      setCorrectionModalRecord(rec);
                                      setCorrectionStatus(rec.status);
                                    }}
                                    className="text-[11px] font-medium text-slate-500 hover:text-brand-600 dark:hover:text-brand-400 underline"
                                  >
                                    Edit / Correction
                                  </button>
                                )}
                              </div>
                            </td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              </div>
            </div>
          )}

          {/* SCHEDULED & UPCOMING CLASSES */}
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            {/* Scheduled Classes List */}
            <div className="lg:col-span-2 bg-white dark:bg-navy-900 rounded-2xl border border-slate-200/80 dark:border-navy-800 p-5 shadow-sm space-y-4">
              <div className="flex items-center justify-between">
                <div>
                  <h3 className="text-sm font-bold text-slate-900 dark:text-white">Scheduled Classes</h3>
                  <p className="text-xs text-slate-500">Initiate live attendance sessions for your selected students.</p>
                </div>
              </div>

              <div className="space-y-3">
                {stats?.upcoming_classes.length === 0 ? (
                  <div className="p-8 text-center text-xs text-slate-400 border border-dashed border-slate-200 dark:border-navy-700 rounded-xl space-y-2">
                    <p>No upcoming classes scheduled.</p>
                    <button
                      onClick={() => setShowCreateModal(true)}
                      className="px-3 py-1.5 rounded-lg text-xs font-semibold bg-brand-600 hover:bg-brand-500 text-white"
                    >
                      Schedule Your First Class
                    </button>
                  </div>
                ) : (
                  stats?.upcoming_classes.map((c) => {
                    const isThisActive = liveSession?.id === c.id && c.status === 'ACTIVE';

                    return (
                      <div
                        key={c.id}
                        className={`p-4 rounded-xl border transition-all flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3 ${
                          isThisActive
                            ? 'bg-brand-50/40 border-brand-300 dark:bg-brand-950/20 dark:border-brand-900'
                            : 'bg-slate-50/80 dark:bg-navy-800/60 border-slate-200/70 dark:border-navy-700/60'
                        }`}
                      >
                        <div>
                          <div className="flex items-center gap-2">
                            <span className="font-semibold text-xs text-slate-900 dark:text-white">{c.title}</span>
                            <span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-brand-100 text-brand-800 dark:bg-brand-950 dark:text-brand-300">
                              {c.subject_code || c.subject_name}
                            </span>
                          </div>
                          <p className="text-[11px] text-slate-500 mt-0.5">
                            Course: <span className="font-medium text-slate-700 dark:text-slate-300">{c.subject_name}</span> |
                            Date: <span className="font-mono">{c.session_date} {c.start_time}</span>
                          </p>
                        </div>

                        <div className="flex items-center gap-2">
                          {c.status === 'SCHEDULED' && (
                            <button
                              onClick={() => handleStartClass(c.id)}
                              className="flex items-center gap-1.5 px-3.5 py-1.5 rounded-lg text-xs font-bold bg-emerald-600 hover:bg-emerald-500 text-white shadow-sm"
                            >
                              <Play className="w-3.5 h-3.5 fill-current" />
                              Start Class Session
                            </button>
                          )}

                          {c.status === 'ACTIVE' && (
                            <button
                              onClick={() => {
                                setLiveSession(c);
                                loadAttendees(c.id);
                              }}
                              className="flex items-center gap-1.5 px-3.5 py-1.5 rounded-lg text-xs font-bold bg-brand-600 text-white shadow-sm"
                            >
                              <Eye className="w-3.5 h-3.5" />
                              Open Live Room
                            </button>
                          )}
                        </div>
                      </div>
                    );
                  })
                )}
              </div>
            </div>

            {/* Teaching Load & Quick Stats */}
            <div className="bg-white dark:bg-navy-900 rounded-2xl border border-slate-200/80 dark:border-navy-800 p-5 shadow-sm space-y-4">
              <h3 className="text-sm font-bold text-slate-900 dark:text-white">Teaching Load &amp; Allocation</h3>

              <div className="space-y-3">
                <div
                  onClick={() => setActiveTab('students')}
                  className="p-3.5 rounded-xl bg-brand-50/50 dark:bg-brand-950/20 border border-brand-200 dark:border-brand-900/40 flex items-center justify-between cursor-pointer hover:bg-brand-50 transition-colors"
                >
                  <div>
                    <span className="text-xs font-semibold text-brand-800 dark:text-brand-300">Admin-Assigned Students</span>
                    <p className="text-[10px] text-slate-500">Students under your supervision</p>
                  </div>
                  <span className="text-lg font-bold text-brand-600 dark:text-brand-400">
                    {stats?.assigned_students_count || 0}
                  </span>
                </div>

                <div className="p-3.5 rounded-xl bg-slate-50 dark:bg-navy-800/60 border border-slate-200/60 dark:border-navy-700/60 flex items-center justify-between">
                  <span className="text-xs text-slate-600 dark:text-slate-400">Available Courses</span>
                  <span className="text-sm font-bold text-slate-900 dark:text-white">{courses.length}</span>
                </div>

                <div className="p-3.5 rounded-xl bg-emerald-50 dark:bg-emerald-950/20 border border-emerald-200 dark:border-emerald-900/40 flex items-center justify-between">
                  <span className="text-xs font-semibold text-emerald-800 dark:text-emerald-300">Average Student Turnout</span>
                  <span className="text-base font-extrabold text-emerald-600 dark:text-emerald-400">
                    {stats?.average_attendance_percentage}%
                  </span>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* TAB 2: MY ASSIGNED STUDENTS */}
      {activeTab === 'students' && (
        <div className="bg-white dark:bg-navy-900 rounded-2xl border border-slate-200/80 dark:border-navy-800 p-5 shadow-sm space-y-4">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
            <div>
              <h2 className="text-base font-bold text-slate-900 dark:text-white">
                Admin-Assigned Students Roster ({assignedStudents.length})
              </h2>
              <p className="text-xs text-slate-500">
                These students have been assigned to you by the Administrator. When scheduling a class, select which of these students to include.
              </p>
            </div>

            <div className="relative w-full sm:w-64">
              <Search className="w-3.5 h-3.5 absolute left-3 top-2.5 text-slate-400" />
              <input
                type="text"
                placeholder="Search assigned students..."
                value={assignedStudentSearch}
                onChange={(e) => setAssignedStudentSearch(e.target.value)}
                className="w-full text-xs pl-8 pr-3 py-1.5 rounded-xl bg-slate-50 dark:bg-navy-800 border border-slate-200 dark:border-navy-700"
              />
            </div>
          </div>

          {assignedStudents.length === 0 ? (
            <div className="p-10 text-center space-y-2 border border-dashed border-slate-200 dark:border-navy-700 rounded-2xl">
              <UserCheck className="w-10 h-10 text-slate-400 mx-auto" />
              <p className="text-sm font-semibold text-slate-700 dark:text-slate-300">No Students Assigned Yet</p>
              <p className="text-xs text-slate-500 max-w-md mx-auto">
                The System Administrator assigns students to your account in the Admin Operations Center. Once assigned, you can select them to schedule classes.
              </p>
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-xs text-left">
                <thead className="bg-slate-50 dark:bg-navy-800 text-slate-700 dark:text-slate-300 uppercase font-semibold">
                  <tr>
                    <th className="py-2.5 px-3">Student Name</th>
                    <th className="py-2.5 px-3">Email Address (Login ID)</th>
                    <th className="py-2.5 px-3">Assigned On</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100 dark:divide-navy-800">
                  {filteredAssignedStudents.map((s) => (
                    <tr key={s.assignment_id} className="hover:bg-slate-50/50 dark:hover:bg-navy-800/40">
                      <td className="py-3 px-3 font-semibold text-slate-900 dark:text-white flex items-center gap-2">
                        <div className="w-6 h-6 rounded-full bg-brand-100 text-brand-700 font-bold flex items-center justify-center text-[10px]">
                          {s.full_name.charAt(0)}
                        </div>
                        {s.full_name}
                      </td>
                      <td className="py-3 px-3 text-slate-500 font-mono">{s.email}</td>
                      <td className="py-3 px-3 text-slate-400 font-mono text-[11px]">
                        {new Date(s.assigned_at).toLocaleDateString()}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}

      {/* CREATE CLASS MODAL (with Course Dropdown & Student Selection) */}
      {showCreateModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-navy-950/60 backdrop-blur-sm animate-fade-in">
          <div className="bg-white dark:bg-navy-900 rounded-3xl border border-slate-200 dark:border-navy-800 max-w-lg w-full p-6 shadow-2xl space-y-4 max-h-[90vh] overflow-y-auto">
            <div className="flex items-center justify-between border-b border-slate-100 dark:border-navy-800 pb-3">
              <div>
                <h3 className="text-base font-bold text-slate-900 dark:text-white">Schedule Class Session</h3>
                <p className="text-xs text-slate-500">
                  Select course and pick specific students who can attend.
                </p>
              </div>
              <button
                onClick={() => setShowCreateModal(false)}
                className="text-slate-400 hover:text-slate-600 dark:hover:text-white text-sm font-bold"
              >
                ✕
              </button>
            </div>

            {assignedStudents.length === 0 ? (
              <div className="p-4 rounded-xl bg-amber-50 dark:bg-amber-950/40 border border-amber-200 dark:border-amber-900/40 text-xs text-amber-800 dark:text-amber-300 space-y-2">
                <p className="font-bold flex items-center gap-1.5">
                  <AlertCircle className="w-4 h-4 shrink-0" />
                  No Students Assigned to You Yet
                </p>
                <p>
                  The Administrator must assign students to your account before you can schedule a class for them. Please request your Admin to assign students in the Admin Operations Center.
                </p>
              </div>
            ) : (
              <form onSubmit={handleCreateClass} className="space-y-3.5">
                {/* 1. Course Selection Dropdown */}
                <div>
                  <label className="block text-xs font-semibold text-slate-700 dark:text-slate-300 mb-1">
                    1. Select Course
                  </label>
                  {courses.length === 0 ? (
                    <p className="text-xs text-rose-500 italic">
                      No courses available. Ask Admin to create courses.
                    </p>
                  ) : (
                    <select
                      required
                      value={newClassForm.subject_id}
                      onChange={(e) => {
                        const sid = Number(e.target.value);
                        const found = courses.find((c) => c.id === sid);
                        setNewClassForm({
                          ...newClassForm,
                          subject_id: sid,
                          title: found ? `${found.name} Session` : newClassForm.title,
                        });
                      }}
                      className="w-full text-xs px-3 py-2 rounded-xl bg-slate-50 dark:bg-navy-800 border border-slate-200 dark:border-navy-700 font-semibold"
                    >
                      <option value="">-- Choose Course --</option>
                      {courses.map((c) => (
                        <option key={c.id} value={c.id}>
                          {c.name} ({c.code})
                        </option>
                      ))}
                    </select>
                  )}
                </div>

                {/* 2. Student Selection Dropdown / Checkbox Picker */}
                <div>
                  <div className="flex items-center justify-between mb-1">
                    <label className="text-xs font-semibold text-slate-700 dark:text-slate-300">
                      2. Select Specific Student(s) for this Class
                    </label>
                    <button
                      type="button"
                      onClick={() => {
                        if (selectedStudentIds.length === assignedStudents.length) {
                          setSelectedStudentIds([]);
                        } else {
                          setSelectedStudentIds(assignedStudents.map((s) => s.student_id));
                        }
                      }}
                      className="text-[11px] font-semibold text-brand-600 hover:underline"
                    >
                      {selectedStudentIds.length === assignedStudents.length
                        ? 'Deselect All'
                        : 'Select All'}
                    </button>
                  </div>

                  <div className="border border-slate-200 dark:border-navy-700 rounded-xl max-h-40 overflow-y-auto p-2 space-y-1.5 bg-slate-50/50 dark:bg-navy-800/40">
                    {assignedStudents.map((s) => {
                      const isSelected = selectedStudentIds.includes(s.student_id);
                      return (
                        <label
                          key={s.student_id}
                          className={`p-2 rounded-lg border text-xs flex items-center justify-between cursor-pointer transition-colors ${
                            isSelected
                              ? 'bg-brand-100/60 dark:bg-brand-950/60 border-brand-400 font-semibold'
                              : 'bg-white dark:bg-navy-900 border-slate-200 dark:border-navy-700 hover:bg-slate-50'
                          }`}
                        >
                          <div className="flex items-center gap-2">
                            <input
                              type="checkbox"
                              checked={isSelected}
                              onChange={(e) => {
                                if (e.target.checked) {
                                  setSelectedStudentIds((prev) => [...prev, s.student_id]);
                                } else {
                                  setSelectedStudentIds((prev) =>
                                    prev.filter((id) => id !== s.student_id)
                                  );
                                }
                              }}
                              className="rounded text-brand-600"
                            />
                            <span>{s.full_name}</span>
                          </div>
                          <span className="text-[10px] text-slate-400 font-mono">{s.email}</span>
                        </label>
                      );
                    })}
                  </div>
                  <p className="text-[10px] text-slate-400 mt-1">
                    * This specific class will only appear in the portals of the {selectedStudentIds.length} student(s) selected above.
                  </p>
                </div>

                {/* 3. Class Title */}
                <div>
                  <label className="block text-xs font-semibold text-slate-700 dark:text-slate-300 mb-1">
                    Class Title / Topic
                  </label>
                  <input
                    required
                    type="text"
                    value={newClassForm.title}
                    onChange={(e) => setNewClassForm({ ...newClassForm, title: e.target.value })}
                    className="w-full text-xs px-3 py-2 rounded-xl bg-slate-50 dark:bg-navy-800 border border-slate-200 dark:border-navy-700"
                    placeholder="e.g. Mathematics - Probability &amp; Statistics"
                  />
                </div>

                {/* 4. Date, Time & Duration */}
                <div className="grid grid-cols-3 gap-3">
                  <div>
                    <label className="block text-xs font-semibold text-slate-700 dark:text-slate-300 mb-1">Date</label>
                    <input
                      required
                      type="date"
                      value={newClassForm.session_date}
                      onChange={(e) => setNewClassForm({ ...newClassForm, session_date: e.target.value })}
                      className="w-full text-xs px-3 py-2 rounded-xl bg-slate-50 dark:bg-navy-800 border border-slate-200 dark:border-navy-700 font-mono"
                    />
                  </div>

                  <div>
                    <label className="block text-xs font-semibold text-slate-700 dark:text-slate-300 mb-1">Start Time</label>
                    <input
                      required
                      type="time"
                      value={newClassForm.start_time}
                      onChange={(e) => setNewClassForm({ ...newClassForm, start_time: e.target.value })}
                      className="w-full text-xs px-3 py-2 rounded-xl bg-slate-50 dark:bg-navy-800 border border-slate-200 dark:border-navy-700 font-mono"
                    />
                  </div>

                  <div>
                    <label className="block text-xs font-semibold text-slate-700 dark:text-slate-300 mb-1">Duration (min)</label>
                    <input
                      required
                      type="number"
                      min="15"
                      max="180"
                      value={newClassForm.duration_minutes}
                      onChange={(e) => setNewClassForm({ ...newClassForm, duration_minutes: parseInt(e.target.value) })}
                      className="w-full text-xs px-3 py-2 rounded-xl bg-slate-50 dark:bg-navy-800 border border-slate-200 dark:border-navy-700"
                    />
                  </div>
                </div>

                <div className="flex items-center justify-end gap-2 pt-3 border-t border-slate-100 dark:border-navy-800">
                  <button
                    type="button"
                    onClick={() => setShowCreateModal(false)}
                    className="px-4 py-2 rounded-xl text-xs font-semibold text-slate-600 dark:text-slate-400 hover:bg-slate-100 dark:hover:bg-navy-800"
                  >
                    Cancel
                  </button>
                  <button
                    type="submit"
                    disabled={selectedStudentIds.length === 0}
                    className={`px-4 py-2 rounded-xl text-xs font-bold text-white shadow-md transition-all ${
                      selectedStudentIds.length > 0
                        ? 'bg-brand-600 hover:bg-brand-500 shadow-brand-500/20'
                        : 'bg-slate-300 dark:bg-navy-700 cursor-not-allowed opacity-60'
                    }`}
                  >
                    Schedule for Selected ({selectedStudentIds.length}) Student(s)
                  </button>
                </div>
              </form>
            )}
          </div>
        </div>
      )}

      {/* REJECT SUBMISSION MODAL */}
      {rejectModalRecord && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-navy-950/60 backdrop-blur-sm animate-fade-in">
          <div className="bg-white dark:bg-navy-900 rounded-2xl border border-slate-200 dark:border-navy-800 max-w-md w-full p-6 shadow-2xl space-y-4">
            <h3 className="text-base font-bold text-rose-600 flex items-center gap-2">
              <XCircle className="w-5 h-5" />
              Reject Attendance Submission
            </h3>
            <p className="text-xs text-slate-600 dark:text-slate-400">
              Rejecting attendance for <strong>{rejectModalRecord.student_name}</strong>. Please specify the verification failure reason:
            </p>

            <textarea
              rows={3}
              value={rejectionReason}
              onChange={(e) => setRejectionReason(e.target.value)}
              className="w-full text-xs p-3 rounded-xl bg-slate-50 dark:bg-navy-800 border border-slate-200 dark:border-navy-700"
              placeholder="e.g. Student not present in classroom, proxy scan attempt."
            />

            <div className="flex items-center justify-end gap-2 pt-2">
              <button
                type="button"
                onClick={() => setRejectModalRecord(null)}
                className="px-4 py-2 rounded-xl text-xs font-semibold text-slate-600 dark:text-slate-400 hover:bg-slate-100 dark:hover:bg-navy-800"
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={handleConfirmReject}
                className="px-4 py-2 rounded-xl text-xs font-semibold bg-rose-600 hover:bg-rose-500 text-white"
              >
                Confirm Rejection
              </button>
            </div>
          </div>
        </div>
      )}

      {/* MANUAL CORRECTION MODAL */}
      {correctionModalRecord && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-navy-950/60 backdrop-blur-sm animate-fade-in">
          <div className="bg-white dark:bg-navy-900 rounded-2xl border border-slate-200 dark:border-navy-800 max-w-md w-full p-6 shadow-2xl space-y-4">
            <h3 className="text-base font-bold text-slate-900 dark:text-white">Manual Attendance Adjustment</h3>
            <p className="text-xs text-slate-500">
              Modifying attendance for <strong>{correctionModalRecord.student_name}</strong>. An immutable audit log entry will be created.
            </p>

            <form onSubmit={handleManualCorrection} className="space-y-3">
              <div>
                <label className="block text-xs font-semibold text-slate-700 dark:text-slate-300 mb-1">New Attendance Status</label>
                <select
                  value={correctionStatus}
                  onChange={(e) => setCorrectionStatus(e.target.value as any)}
                  className="w-full text-xs px-3 py-2 rounded-xl bg-slate-50 dark:bg-navy-800 border border-slate-200 dark:border-navy-700"
                >
                  <option value="PRESENT">PRESENT</option>
                  <option value="LATE">LATE</option>
                  <option value="ABSENT">ABSENT</option>
                </select>
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-700 dark:text-slate-300 mb-1">Mandatory Audit Reason</label>
                <textarea
                  required
                  rows={3}
                  value={correctionReason}
                  onChange={(e) => setCorrectionReason(e.target.value)}
                  className="w-full text-xs p-3 rounded-xl bg-slate-50 dark:bg-navy-800 border border-slate-200 dark:border-navy-700"
                  placeholder="e.g. Student confirmed physical presence by professor."
                />
              </div>

              <div className="flex items-center justify-end gap-2 pt-2">
                <button
                  type="button"
                  onClick={() => setCorrectionModalRecord(null)}
                  className="px-4 py-2 rounded-xl text-xs font-semibold text-slate-600 dark:text-slate-400 hover:bg-slate-100 dark:hover:bg-navy-800"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="px-4 py-2 rounded-xl text-xs font-semibold bg-brand-600 hover:bg-brand-500 text-white"
                >
                  Save &amp; Log Audit
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};
