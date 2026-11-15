import React, { useState, useEffect, useRef } from 'react';
import { api } from '../../services/api';
import {
  StudentDashboardStats, AttendanceRecord, ClassSession,
  SubjectAttendanceSummary
} from '../../types';
import { useToast } from '../../context/ToastContext';
import { Html5Qrcode } from 'html5-qrcode';
import {
  CheckCircle2, AlertTriangle, QrCode,
  Calendar, Check, ArrowRight, RefreshCw,
  Camera, TrendingUp, Calculator, ShieldCheck, Key
} from 'lucide-react';

export const StudentDashboard: React.FC = () => {
  const toast = useToast();
  const [stats, setStats] = useState<StudentDashboardStats | null>(null);
  const [loading, setLoading] = useState(true);

  // Active session submission modal
  const [selectedSession, setSelectedSession] = useState<ClassSession | null>(null);
  const [submissionPin, setSubmissionPin] = useState('');
  const [submissionToken, setSubmissionToken] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [submissionResult, setSubmissionResult] = useState<AttendanceRecord | null>(null);
  const [scanMode, setScanMode] = useState<'PIN' | 'QR'>('PIN');
  const [gpsLocation, setGpsLocation] = useState<{ lat: number; lng: number } | null>(null);

  // QR scanner states
  const [cameraActive, setCameraActive] = useState(false);
  const [cameraError, setCameraError] = useState<string | null>(null);
  const qrScannerRef = useRef<Html5Qrcode | null>(null);

  // Leave Modal
  const [showLeaveModal, setShowLeaveModal] = useState(false);
  const [leaveForm, setLeaveForm] = useState({
    start_date: new Date().toISOString().split('T')[0],
    end_date: new Date().toISOString().split('T')[0],
    reason: '',
  });

  // Dispute Modal
  const [disputeRecord, setDisputeRecord] = useState<AttendanceRecord | null>(null);
  const [disputeReason, setDisputeReason] = useState('');

  const loadData = async () => {
    try {
      setLoading(true);
      const data = await api.getStudentDashboard();
      setStats(data);
    } catch (e: any) {
      toast.error('Failed to load student data', e.message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();

    if (navigator.geolocation) {
      navigator.geolocation.getCurrentPosition(
        (pos) => setGpsLocation({ lat: pos.coords.latitude, lng: pos.coords.longitude }),
        () => console.log('Location not permitted or unavailable')
      );
    }
  }, []);

  // HTML5 QR Scanner initialization
  useEffect(() => {
    if (selectedSession && scanMode === 'QR') {
      setCameraError(null);
      setCameraActive(true);
      const regionId = 'html5-qr-reader-region';

      const timer = setTimeout(() => {
        try {
          const scanner = new Html5Qrcode(regionId);
          qrScannerRef.current = scanner;

          scanner
            .start(
              { facingMode: 'environment' },
              {
                fps: 10,
                qrbox: { width: 220, height: 220 },
              },
              (decodedText) => {
                handleQrPayload(decodedText);
                stopScanner();
              },
              () => {} // frame parse pass
            )
            .catch((err) => {
              console.warn('Environment camera failed, trying user camera:', err);
              scanner
                .start(
                  { facingMode: 'user' },
                  {
                    fps: 10,
                    qrbox: { width: 220, height: 220 },
                  },
                  (decodedText) => {
                    handleQrPayload(decodedText);
                    stopScanner();
                  },
                  () => {}
                )
                .catch((e: any) => {
                  console.error('Camera error:', e);
                  setCameraError('Camera access unavailable or blocked. Please type the 6-digit PIN (Ask from Teacher).');
                  setCameraActive(false);
                });
            });
        } catch (e: any) {
          setCameraError(e.message || 'Camera scanner error');
          setCameraActive(false);
        }
      }, 150);

      return () => {
        clearTimeout(timer);
        stopScanner();
      };
    } else {
      stopScanner();
    }
  }, [selectedSession?.id, scanMode]);

  const stopScanner = () => {
    if (qrScannerRef.current) {
      if (qrScannerRef.current.isScanning) {
        qrScannerRef.current.stop().catch(console.error);
      }
      qrScannerRef.current = null;
    }
    setCameraActive(false);
  };

  const handleQrPayload = (payloadStr: string) => {
    try {
      const parsed = JSON.parse(payloadStr);
      if (parsed.token) setSubmissionToken(parsed.token);
      if (parsed.pin) setSubmissionPin(parsed.pin);
      toast.success('QR Code Captured!', 'Attendance token successfully scanned.');
    } catch {
      setSubmissionPin(payloadStr);
      toast.success('QR Code Scanned!', 'Code captured from screen.');
    }
  };

  const handleOpenAttendanceModal = (session: ClassSession) => {
    setSelectedSession(session);
    // Secret PIN is NOT prefilled!
    setSubmissionPin('');
    setSubmissionToken('');
    setSubmissionResult(null);
    setScanMode('PIN');
  };

  const handleSubmitAttendance = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedSession) return;

    if (!submissionPin.trim() && !submissionToken.trim()) {
      toast.warning('Please enter the 6-digit PIN (Ask from Teacher) or scan QR code');
      return;
    }

    try {
      setSubmitting(true);
      const result = await api.studentMarkPresent({
        session_id: selectedSession.id,
        pin: submissionPin.trim() || undefined,
        token: submissionToken.trim() || undefined,
        latitude: gpsLocation?.lat,
        longitude: gpsLocation?.lng,
        device_info: `${navigator.platform} - ${navigator.userAgent.slice(0, 35)}`,
      });

      setSubmissionResult(result);
      stopScanner();
      toast.success(
        'Step 1 Confirmed: Attendance Marked!',
        'Awaiting teacher verification in classroom for official PRESENT status.'
      );
      loadData();
    } catch (err: any) {
      toast.error('Attendance Submission Failed', err.message);
    } finally {
      setSubmitting(false);
    }
  };

  const handleApplyLeave = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      await api.submitLeave(leaveForm);
      toast.success('Leave application submitted for faculty review');
      setShowLeaveModal(false);
      setLeaveForm({
        start_date: new Date().toISOString().split('T')[0],
        end_date: new Date().toISOString().split('T')[0],
        reason: '',
      });
      loadData();
    } catch (err: any) {
      toast.error('Failed to submit leave', err.message);
    }
  };

  const handleRaiseDispute = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!disputeRecord) return;
    try {
      await api.submitDispute(disputeRecord.id, disputeReason);
      toast.success('Dispute ticket raised', 'Administrator and faculty will review your attendance.');
      setDisputeRecord(null);
      setDisputeReason('');
      loadData();
    } catch (err: any) {
      toast.error('Failed to submit dispute', err.message);
    }
  };

  const calculatePrediction = (attended: number, total: number, target: number = 75) => {
    if (total === 0) return { status: 'safe', count: 0, text: 'No classes conducted yet.' };

    const currentPct = (attended / total) * 100;
    if (currentPct < target) {
      const needed = Math.ceil((0.75 * total - attended) / 0.25);
      return {
        status: 'risk',
        count: Math.max(needed, 1),
        text: `Must attend next ${Math.max(needed, 1)} consecutive classes to reach 75.0%`
      };
    } else {
      const canMiss = Math.floor((attended - 0.75 * total) / 0.75);
      return {
        status: 'safe',
        count: canMiss,
        text: canMiss > 0 ? `Can safely miss at most ${canMiss} class${canMiss > 1 ? 'es' : ''} while maintaining >75%` : 'On track! Keep attending to maintain safe margin.'
      };
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-[60vh]">
        <div className="text-center space-y-3">
          <div className="w-10 h-10 border-4 border-emerald-500 border-t-transparent rounded-full animate-spin mx-auto" />
          <p className="text-sm font-medium text-slate-500">Loading Student Portal...</p>
        </div>
      </div>
    );
  }

  const isAtRisk = stats ? stats.is_at_risk : false;
  const overallPrediction = stats ? calculatePrediction(stats.present_count + stats.late_count, stats.total_classes) : null;

  return (
    <div className="space-y-6 pb-12">
      {/* Welcome Hero Card */}
      <div className="bg-gradient-to-r from-navy-950 via-[#0B132B] to-navy-900 p-6 rounded-2xl text-white shadow-2xl shadow-navy-950/30 border border-slate-700/50 backdrop-blur-md flex flex-col md:flex-row items-start md:items-center justify-between gap-6">
        <div>
          <div className="flex items-center gap-2">
            <span className="text-xs font-bold uppercase tracking-wider text-amber-400">Student Portal • PI Pascals Institute PVT LTD</span>
          </div>
          <h1 className="text-2xl font-extrabold tracking-tight mt-1">{stats?.student_name}</h1>
          <p className="text-xs text-slate-300 mt-0.5 font-medium">PI Pascals Attendance System</p>
          <div className="mt-2 flex items-center gap-1.5 flex-wrap">
            <span className="text-[11px] text-slate-400">Assigned Faculty Mentors:</span>
            {stats?.assigned_teachers && stats.assigned_teachers.length > 0 ? (
              stats.assigned_teachers.map((tName, i) => (
                <span key={i} className="px-2 py-0.5 rounded-md bg-emerald-500/20 text-emerald-300 border border-emerald-500/30 text-[10px] font-semibold">
                  {tName}
                </span>
              ))
            ) : (
              <span className="text-[10px] text-slate-400 italic">Faculty will be assigned by Administrator</span>
            )}
          </div>
        </div>

        {/* Big Overall Attendance Gauge */}
        <div className="flex items-center gap-4 bg-white/10 dark:bg-navy-900/60 p-4 rounded-2xl border border-white/10 backdrop-blur-md">
          <div className="text-right">
            <span className="text-[11px] font-semibold text-slate-300 block">Overall Verified Attendance</span>
            <span className={`text-3xl font-extrabold tracking-tight ${isAtRisk ? 'text-rose-400' : 'text-emerald-400'}`}>
              {stats?.overall_percentage}%
            </span>
            <span className="text-[10px] text-slate-400 block mt-0.5">
              {stats?.present_count} Present | {stats?.late_count} Late | {stats?.absent_count} Absent
            </span>
          </div>

          <div className={`w-14 h-14 rounded-2xl flex items-center justify-center font-bold text-lg shadow-inner ${
            isAtRisk ? 'bg-rose-500/20 text-rose-300 border border-rose-500/40' : 'bg-emerald-500/20 text-emerald-300 border border-emerald-500/40'
          }`}>
            {stats?.overall_percentage}%
          </div>
        </div>
      </div>

      {/* ATTENDANCE PREDICTION & FORECAST BANNER */}
      {overallPrediction && (
        <div className={`p-4 rounded-2xl border flex items-center justify-between gap-4 transition-all ${
          overallPrediction.status === 'risk'
            ? 'bg-rose-50 dark:bg-rose-950/40 border-rose-200 dark:border-rose-900 text-rose-900 dark:text-rose-200'
            : 'bg-emerald-50 dark:bg-emerald-950/40 border-emerald-200 dark:border-emerald-900 text-emerald-900 dark:text-emerald-200'
        }`}>
          <div className="flex items-center gap-3">
            <div className={`p-2.5 rounded-xl ${
              overallPrediction.status === 'risk' ? 'bg-rose-500 text-white' : 'bg-emerald-600 text-white'
            }`}>
              <Calculator className="w-5 h-5" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <span className="text-xs font-bold uppercase tracking-wider">
                  Attendance Forecast &amp; Eligibility Predictor
                </span>
                <span className="text-[10px] font-semibold px-2 py-0.5 rounded bg-black/10">
                  Target: 75.0%
                </span>
              </div>
              <p className="text-xs font-medium mt-0.5 leading-relaxed">
                {overallPrediction.text}
              </p>
            </div>
          </div>

          <button
            onClick={() => setShowLeaveModal(true)}
            className="hidden sm:flex items-center gap-1.5 px-3 py-1.5 rounded-xl text-xs font-semibold bg-white dark:bg-navy-900 text-slate-800 dark:text-slate-200 border border-slate-200 dark:border-navy-700 shadow-sm"
          >
            <Calendar className="w-3.5 h-3.5" />
            Apply Leave
          </button>
        </div>
      )}

      {/* ACTIVE SESSIONS BANNER (Classes specifically scheduled for this student) */}
      {stats?.active_sessions && stats.active_sessions.length > 0 && (
        <div className="bg-gradient-to-r from-emerald-600 via-teal-600 to-emerald-700 text-white p-5 rounded-2xl shadow-xl shadow-emerald-950/20 space-y-3 animate-slide-up">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <span className="w-3 h-3 rounded-full bg-white animate-ping" />
              <h2 className="text-base font-bold">Class In Session: Attendance Window Open!</h2>
            </div>
            <span className="text-xs font-bold uppercase tracking-wider bg-white/20 px-2.5 py-0.5 rounded-full">
              Live Now
            </span>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            {stats.active_sessions.map((sess) => (
              <div
                key={sess.id}
                className="bg-white/10 backdrop-blur-md p-4 rounded-xl border border-white/20 flex items-center justify-between gap-4"
              >
                <div>
                  <h3 className="font-bold text-sm">{sess.title}</h3>
                  <p className="text-xs text-emerald-100 mt-0.5">
                    Course: <span className="font-semibold">{sess.subject_name}</span> | Faculty: {sess.teacher_name}
                  </p>
                  <p className="text-[11px] text-emerald-200 font-mono mt-0.5">
                    Started at {sess.start_time} | Late threshold: {sess.late_threshold_minutes} min
                  </p>
                </div>

                <button
                  onClick={() => handleOpenAttendanceModal(sess)}
                  className="px-4 py-2.5 rounded-xl text-xs font-bold bg-white text-emerald-800 hover:bg-emerald-50 transition-colors shadow-lg shadow-black/10 flex items-center gap-1.5 shrink-0"
                >
                  <QrCode className="w-4 h-4" />
                  Mark Attendance
                </button>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* SUBJECT-WISE ATTENDANCE BREAKDOWN */}
      <div className="bg-white dark:bg-navy-900 rounded-2xl border border-slate-200/80 dark:border-navy-800 p-5 shadow-sm space-y-4">
        <div className="flex items-center justify-between">
          <div>
            <h3 className="text-sm font-bold text-slate-900 dark:text-white">Course Attendance Breakdown</h3>
            <p className="text-xs text-slate-500">Official dual-confirmed attendance by subject.</p>
          </div>
        </div>

        {stats?.subject_breakdown.length === 0 ? (
          <p className="text-xs text-slate-400 py-6 text-center">No class records yet.</p>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {stats?.subject_breakdown.map((sb) => (
              <div
                key={sb.subject_id}
                className="p-4 rounded-xl border border-slate-200/80 dark:border-navy-700/80 bg-slate-50/50 dark:bg-navy-800/40 space-y-2"
              >
                <div className="flex items-center justify-between">
                  <h4 className="font-bold text-xs text-slate-900 dark:text-white">{sb.subject_name}</h4>
                  <span className={`text-xs font-extrabold ${sb.is_at_risk ? 'text-rose-500' : 'text-emerald-600'}`}>
                    {sb.percentage}%
                  </span>
                </div>
                <div className="w-full bg-slate-200 dark:bg-navy-700 h-2 rounded-full overflow-hidden">
                  <div
                    className={`h-full ${sb.is_at_risk ? 'bg-rose-500' : 'bg-emerald-500'}`}
                    style={{ width: `${Math.min(sb.percentage, 100)}%` }}
                  />
                </div>
                <p className="text-[10px] text-slate-400">
                  {sb.attended_classes} of {sb.total_classes} classes attended
                </p>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* RECENT ATTENDANCE HISTORY TABLE */}
      <div className="bg-white dark:bg-navy-900 rounded-2xl border border-slate-200/80 dark:border-navy-800 p-5 shadow-sm space-y-4">
        <div className="flex items-center justify-between">
          <div>
            <h3 className="text-sm font-bold text-slate-900 dark:text-white">Recent Attendance Logs</h3>
            <p className="text-xs text-slate-500">Dual-confirmed records with timestamps.</p>
          </div>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-xs text-left">
            <thead className="bg-slate-50 dark:bg-navy-800 text-slate-700 dark:text-slate-300 uppercase font-semibold">
              <tr>
                <th className="py-2.5 px-3">Session</th>
                <th className="py-2.5 px-3">Course</th>
                <th className="py-2.5 px-3">Date</th>
                <th className="py-2.5 px-3">Student Confirmed</th>
                <th className="py-2.5 px-3">Teacher Confirmed</th>
                <th className="py-2.5 px-3">Final Status</th>
                <th className="py-2.5 px-3 text-right">Dispute</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100 dark:divide-navy-800">
              {stats?.recent_records.map((r) => (
                <tr key={r.id} className="hover:bg-slate-50/50 dark:hover:bg-navy-800/40">
                  <td className="py-2.5 px-3 font-semibold text-slate-900 dark:text-white">{r.session_title}</td>
                  <td className="py-2.5 px-3 text-slate-600 dark:text-slate-400">{r.subject_name}</td>
                  <td className="py-2.5 px-3 font-mono">{r.session_date}</td>
                  <td className="py-2.5 px-3">
                    {r.student_confirmation ? (
                      <span className="text-emerald-600 font-semibold flex items-center gap-1">
                        <Check className="w-3.5 h-3.5" /> Yes
                      </span>
                    ) : (
                      <span className="text-slate-400">No</span>
                    )}
                  </td>
                  <td className="py-2.5 px-3">
                    {r.teacher_confirmation ? (
                      <span className="text-emerald-600 font-semibold flex items-center gap-1">
                        <Check className="w-3.5 h-3.5" /> Yes
                      </span>
                    ) : (
                      <span className="text-amber-600">Pending</span>
                    )}
                  </td>
                  <td className="py-2.5 px-3">
                    <span className={`px-2 py-0.5 rounded text-[10px] font-bold ${
                      r.status === 'PRESENT' ? 'bg-emerald-100 text-emerald-700' :
                      r.status === 'LATE' ? 'bg-indigo-100 text-indigo-700' :
                      r.status === 'STUDENT_MARKED' ? 'bg-amber-100 text-amber-700' :
                      'bg-slate-100 text-slate-600'
                    }`}>
                      {r.status}
                    </span>
                  </td>
                  <td className="py-2.5 px-3 text-right">
                    {r.status === 'ABSENT' && (
                      <button
                        onClick={() => setDisputeRecord(r)}
                        className="text-[11px] font-semibold text-brand-600 hover:underline"
                      >
                        Report Issue
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* ATTENDANCE SUBMISSION MODAL WITH HTML5 WEBCAM SCANNER & HIDDEN PIN */}
      {selectedSession && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-navy-950/70 backdrop-blur-sm animate-fade-in">
          <div className="bg-white dark:bg-navy-900 rounded-3xl border border-slate-200 dark:border-navy-800 max-w-md w-full p-6 shadow-2xl space-y-5">
            <div className="flex items-center justify-between border-b border-slate-100 dark:border-navy-800 pb-3">
              <div>
                <span className="text-[11px] font-mono font-bold text-brand-600 uppercase">
                  Class Verification
                </span>
                <h3 className="text-base font-bold text-slate-900 dark:text-white">
                  {selectedSession.title}
                </h3>
              </div>
              <button
                onClick={() => {
                  stopScanner();
                  setSelectedSession(null);
                }}
                className="text-slate-400 hover:text-slate-600 text-xs font-semibold"
              >
                Close
              </button>
            </div>

            {/* DUAL CONFIRMATION STEP INDICATOR */}
            <div className="bg-slate-50 dark:bg-navy-800/80 p-3.5 rounded-2xl border border-slate-200/80 dark:border-navy-700 space-y-2">
              <span className="text-[10px] font-bold uppercase tracking-wider text-slate-500 block">
                Dual Confirmation Protocol
              </span>

              <div className="flex items-center justify-between text-xs">
                {/* Step 1 */}
                <div className="flex items-center gap-2">
                  <div className={`w-5 h-5 rounded-full flex items-center justify-center font-bold text-[10px] ${
                    submissionResult?.student_confirmation
                      ? 'bg-emerald-500 text-white'
                      : 'bg-brand-600 text-white animate-pulse'
                  }`}>
                    {submissionResult?.student_confirmation ? '✓' : '1'}
                  </div>
                  <span className={`font-semibold ${submissionResult?.student_confirmation ? 'text-emerald-600' : 'text-slate-900 dark:text-white'}`}>
                    Student Marks
                  </span>
                </div>

                <ArrowRight className="w-4 h-4 text-slate-400" />

                {/* Step 2 */}
                <div className="flex items-center gap-2">
                  <div className={`w-5 h-5 rounded-full flex items-center justify-center font-bold text-[10px] ${
                    submissionResult?.teacher_confirmation
                      ? 'bg-emerald-500 text-white'
                      : 'bg-slate-200 text-slate-600 dark:bg-navy-700 dark:text-slate-400'
                  }`}>
                    {submissionResult?.teacher_confirmation ? '✓' : '2'}
                  </div>
                  <span className={`font-semibold ${submissionResult?.teacher_confirmation ? 'text-emerald-600' : 'text-slate-500'}`}>
                    Teacher Confirms
                  </span>
                </div>
              </div>
            </div>

            {submissionResult ? (
              /* Success State */
              <div className="text-center py-4 space-y-3">
                <div className="w-14 h-14 bg-emerald-100 text-emerald-600 rounded-full flex items-center justify-center mx-auto">
                  <CheckCircle2 className="w-8 h-8" />
                </div>
                <h4 className="text-base font-bold text-slate-900 dark:text-white">
                  Step 1 Completed Successfully!
                </h4>
                <p className="text-xs text-slate-600 dark:text-slate-400 max-w-xs mx-auto leading-relaxed">
                  Your confirmation has been sent to <strong>{selectedSession.teacher_name}</strong>'s live console. As soon as the professor verifies your physical presence in class, your status will become <strong>PRESENT</strong>.
                </p>
                <div className="pt-2">
                  <button
                    onClick={() => setSelectedSession(null)}
                    className="w-full py-2.5 rounded-xl text-xs font-bold bg-brand-600 hover:bg-brand-500 text-white"
                  >
                    Done
                  </button>
                </div>
              </div>
            ) : (
              /* Form State */
              <form onSubmit={handleSubmitAttendance} className="space-y-4">
                {/* Input Mode Toggle */}
                <div className="flex bg-slate-100 dark:bg-navy-800 p-1 rounded-xl text-xs font-semibold">
                  <button
                    type="button"
                    onClick={() => {
                      stopScanner();
                      setScanMode('PIN');
                    }}
                    className={`flex-1 py-1.5 rounded-lg transition-all ${
                      scanMode === 'PIN' ? 'bg-white dark:bg-navy-900 text-brand-600 shadow-sm' : 'text-slate-500'
                    }`}
                  >
                    Enter 6-Digit PIN
                  </button>
                  <button
                    type="button"
                    onClick={() => setScanMode('QR')}
                    className={`flex-1 py-1.5 rounded-lg transition-all ${
                      scanMode === 'QR' ? 'bg-white dark:bg-navy-900 text-brand-600 shadow-sm' : 'text-slate-500'
                    }`}
                  >
                    Live Camera QR Scanner
                  </button>
                </div>

                {scanMode === 'PIN' ? (
                  <div className="space-y-2">
                    <label className="block text-xs font-semibold text-slate-700 dark:text-slate-300">
                      Attendance PIN (Ask from Teacher)
                    </label>

                    <input
                      required
                      type="text"
                      maxLength={6}
                      value={submissionPin}
                      onChange={(e) => setSubmissionPin(e.target.value)}
                      placeholder="Ask from Teacher"
                      className="w-full text-center text-2xl font-bold font-mono tracking-widest py-3 rounded-xl bg-slate-50 dark:bg-navy-800 border border-slate-200 dark:border-navy-700 text-brand-600 focus:outline-none focus:ring-2 focus:ring-brand-500"
                    />

                    <div className="p-3 rounded-xl bg-brand-50 dark:bg-brand-950/40 border border-brand-200 dark:border-brand-900/40 flex items-start gap-2 text-xs text-brand-800 dark:text-brand-300">
                      <Key className="w-4 h-4 shrink-0 mt-0.5" />
                      <p>
                        The 6-digit attendance code is kept confidential by your teacher. Please ask your teacher in class to obtain this code.
                      </p>
                    </div>
                  </div>
                ) : (
                  <div className="space-y-3">
                    <label className="block text-xs font-semibold text-slate-700 dark:text-slate-300 text-center">
                      Point Camera at Teacher's Classroom QR Code
                    </label>

                    <div className="relative rounded-2xl overflow-hidden border-2 border-brand-500/80 bg-black">
                      <div id="html5-qr-reader-region" className="w-full min-h-[220px]" />
                    </div>

                    {cameraError && (
                      <p className="text-xs text-rose-500 text-center font-medium">
                        {cameraError}
                      </p>
                    )}

                    {submissionToken && (
                      <div className="p-2.5 rounded-xl bg-emerald-50 text-emerald-800 text-xs flex items-center justify-center gap-1.5 font-bold">
                        <Check className="w-4 h-4" /> QR Code Scanned &amp; Loaded!
                      </div>
                    )}
                  </div>
                )}

                <button
                  type="submit"
                  disabled={submitting}
                  className="w-full py-3 rounded-xl text-xs font-bold bg-brand-600 hover:bg-brand-500 text-white shadow-lg shadow-brand-500/20 transition-all flex items-center justify-center gap-2"
                >
                  {submitting ? (
                    <>
                      <div className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" />
                      Verifying with Server...
                    </>
                  ) : (
                    'Confirm My Attendance (Step 1)'
                  )}
                </button>
              </form>
            )}
          </div>
        </div>
      )}

      {/* LEAVE APPLICATION MODAL */}
      {showLeaveModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-navy-950/60 backdrop-blur-sm animate-fade-in">
          <div className="bg-white dark:bg-navy-900 rounded-2xl border border-slate-200 dark:border-navy-800 max-w-md w-full p-6 shadow-2xl space-y-4">
            <h3 className="text-base font-bold text-slate-900 dark:text-white">Apply for Leave of Absence</h3>
            <form onSubmit={handleApplyLeave} className="space-y-3">
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-semibold text-slate-700 dark:text-slate-300 mb-1">Start Date</label>
                  <input
                    required
                    type="date"
                    value={leaveForm.start_date}
                    onChange={(e) => setLeaveForm({ ...leaveForm, start_date: e.target.value })}
                    className="w-full text-xs px-3 py-2 rounded-xl bg-slate-50 dark:bg-navy-800 border border-slate-200 dark:border-navy-700 font-mono"
                  />
                </div>
                <div>
                  <label className="block text-xs font-semibold text-slate-700 dark:text-slate-300 mb-1">End Date</label>
                  <input
                    required
                    type="date"
                    value={leaveForm.end_date}
                    onChange={(e) => setLeaveForm({ ...leaveForm, end_date: e.target.value })}
                    className="w-full text-xs px-3 py-2 rounded-xl bg-slate-50 dark:bg-navy-800 border border-slate-200 dark:border-navy-700 font-mono"
                  />
                </div>
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-700 dark:text-slate-300 mb-1">Reason for Leave</label>
                <textarea
                  required
                  rows={3}
                  value={leaveForm.reason}
                  onChange={(e) => setLeaveForm({ ...leaveForm, reason: e.target.value })}
                  placeholder="Medical reason, institutional competition, or emergency..."
                  className="w-full text-xs p-3 rounded-xl bg-slate-50 dark:bg-navy-800 border border-slate-200 dark:border-navy-700"
                />
              </div>

              <div className="flex items-center justify-end gap-2 pt-2">
                <button
                  type="button"
                  onClick={() => setShowLeaveModal(false)}
                  className="px-4 py-2 rounded-xl text-xs font-semibold text-slate-600 dark:text-slate-400 hover:bg-slate-100 dark:hover:bg-navy-800"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="px-4 py-2 rounded-xl text-xs font-semibold bg-brand-600 hover:bg-brand-500 text-white"
                >
                  Submit Application
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* DISPUTE MODAL */}
      {disputeRecord && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-navy-950/60 backdrop-blur-sm animate-fade-in">
          <div className="bg-white dark:bg-navy-900 rounded-2xl border border-slate-200 dark:border-navy-800 max-w-md w-full p-6 shadow-2xl space-y-4">
            <h3 className="text-base font-bold text-slate-900 dark:text-white">Report Attendance Issue</h3>
            <p className="text-xs text-slate-500">
              Session: <strong>{disputeRecord.session_title}</strong> ({disputeRecord.session_date})
            </p>

            <form onSubmit={handleRaiseDispute} className="space-y-3">
              <div>
                <label className="block text-xs font-semibold text-slate-700 dark:text-slate-300 mb-1">Detailed Explanation</label>
                <textarea
                  required
                  rows={3}
                  value={disputeReason}
                  onChange={(e) => setDisputeReason(e.target.value)}
                  placeholder="Explain why you were present (e.g. proxy scan error, camera glitch, verified by faculty)..."
                  className="w-full text-xs p-3 rounded-xl bg-slate-50 dark:bg-navy-800 border border-slate-200 dark:border-navy-700"
                />
              </div>

              <div className="flex items-center justify-end gap-2 pt-2">
                <button
                  type="button"
                  onClick={() => setDisputeRecord(null)}
                  className="px-4 py-2 rounded-xl text-xs font-semibold text-slate-600 dark:text-slate-400 hover:bg-slate-100 dark:hover:bg-navy-800"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="px-4 py-2 rounded-xl text-xs font-semibold bg-brand-600 hover:bg-brand-500 text-white"
                >
                  Submit Dispute Ticket
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};
