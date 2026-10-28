import { useState, type ReactNode } from 'react';
import { Link, Route, Routes, useLocation } from 'react-router-dom';
import type { DiabetesJourneyHostProps } from '../components/diabetes-integration/types';
import { api, ApiError } from './lib/api';
import { useSession } from './lib/session';
import { Button, Card, ErrorState, Notice, Spinner } from './components/ui';
import SukkarHome from './sukkar/SukkarHome';
import SukkarUpload from './sukkar/SukkarUpload';
import SukkarReports from './sukkar/SukkarReports';
import SukkarReportDetail from './sukkar/SukkarReportDetail';
import SukkarVisitPrep from './sukkar/SukkarVisitPrep';
import SukkarHowItWorks from './sukkar/SukkarHowItWorks';
import { SukkarFollowupDetail, SukkarFollowupList, SukkarFollowupNew } from './sukkar/SukkarFollowups';
import { ReviewerDashboard, ReviewerRequest } from './reviewer/ReviewerApp';

/** Authentication is independent of the team's fictional profile switcher. */
export function BackendBoundary({children, role='patient'}: {children: ReactNode; role?: 'patient' | 'reviewer'}) {
  const {config, profile, loading, error, retry, signIn, signOut, demoMode} = useSession();
  const [token,setToken] = useState('');
  const [busy,setBusy] = useState(false);
  const [failure,setFailure] = useState<string | null>(null);
  async function login(demo: boolean) {
    setBusy(true); setFailure(null);
    try {
      let value = token.trim();
      if (demo) {
        const session = await api.demoSession();
        value = role === 'reviewer' ? session.reviewer_token : session.patient_token;
      }
      await signIn(value);
    } catch (e) {setFailure(e instanceof ApiError ? e.messageAr : 'تعذّر تسجيل الدخول.');}
    finally {setBusy(false);}
  }
  let content;
  if (loading) content = <div className="p-8 text-center"><Spinner size={28} /></div>;
  else if (error) content = <div className="p-4"><ErrorState message={error.messageAr} onRetry={retry} /></div>;
  else if (!profile || profile.role !== role) content = <div className="space-y-4 p-4">
    <Card className="p-5 space-y-4">
      <h2 className="text-[21px] font-bold">{role === 'reviewer' ? 'دخول المراجع' : 'أهلًا بك في عضيد'}</h2>
      <p className="text-[14px] text-ink-2">{role === 'reviewer' ? 'راجع الطلبات والملخصات قبل تسجيل القرار.' : 'خلّنا نرتّب تقريرك ونجهّز أسئلتك لموعدك.'}</p>
      {demoMode ? <>
        <Notice tone="warn" title="وضع تجريبي">بيانات اصطناعية في ذاكرة الخادم، تُحذف عند إعادة تشغيله. استخدم تقرير التجربة ولا ترفع معلومات صحية حقيقية.</Notice>
        <Button full loading={busy} onClick={() => void login(true)}>{role === 'reviewer' ? 'الدخول كمراجع تجريبي' : 'الدخول كمريض تجريبي'}</Button>
      </> : <>
        <label className="block text-[14px]" htmlFor="adheed-access-token">رمز جلسة Supabase Auth</label>
        <input id="adheed-access-token" type="password" autoComplete="off" className="w-full rounded-xl border border-line p-3" value={token} onChange={e => setToken(e.target.value)} />
        <Button full disabled={!token.trim()} loading={busy} onClick={() => void login(false)}>تسجيل الدخول</Button>
      </>}
      {failure && <p role="alert" className="text-danger">{failure}</p>}
    </Card>
  </div>;
  else content = <>
    {demoMode && <div className="adh-demo" role="note">وضع العرض — بيانات تجريبية، والمواعيد محاكاة فقط</div>}
    {children}
    <div className="adh-tools">
      <span>{profile.display_name}</span>
      <button type="button" onClick={signOut}>إنهاء الجلسة</button>
      <Link to={role === 'reviewer' ? '/my-profile/diabetes-journey' : '/reviewer'}>{role === 'reviewer' ? 'العودة إلى عضيد' : 'لوحة المراجع'}</Link>
    </div>
    {config && <details className="px-4 pb-4 text-[12px] text-ink-3"><summary>حالة الاتصال والخدمات</summary>
      <p>التخزين: {config.supabase_configured ? 'Supabase' : 'تجريبي داخل الذاكرة'} · التحليل: {config.ai_configured ? `${config.ai_provider} · ${config.ai_model}` : 'قواعد وقوالب Python — الذكاء الاصطناعي غير مفعّل'}</p>
    </details>}
  </>;
  return <div id="adheed-feature" className="adh-root" dir="rtl" lang="ar">{content}</div>;
}

export function AdheedFeature(_props: DiabetesJourneyHostProps) {
  return <BackendBoundary><Routes>
    <Route index element={<SukkarHome />} />
    <Route path="upload" element={<SukkarUpload />} />
    <Route path="reports" element={<SukkarReports />} />
    <Route path="reports/:id" element={<SukkarReportDetail />} />
    <Route path="visit-prep" element={<SukkarVisitPrep />} />
    <Route path="visit-prep/:reportId" element={<SukkarVisitPrep />} />
    <Route path="followups" element={<SukkarFollowupList />} />
    <Route path="followups/new" element={<SukkarFollowupNew />} />
    <Route path="followups/:id" element={<SukkarFollowupDetail />} />
    <Route path="how-it-works" element={<SukkarHowItWorks />} />
    <Route path="*" element={<p className="p-5">الصفحة غير موجودة. <Link to="/my-profile/diabetes-journey">العودة إلى عضيد</Link></p>} />
  </Routes></BackendBoundary>;
}

export function ReviewerPage() {
  const {pathname} = useLocation();
  return <BackendBoundary role="reviewer">{pathname === '/reviewer' ? <ReviewerDashboard /> : <ReviewerRequest />}</BackendBoundary>;
}
