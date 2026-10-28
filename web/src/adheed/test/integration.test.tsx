import {beforeEach,describe,it,expect,vi} from 'vitest';
import {render,screen,fireEvent,waitFor,within} from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import * as fx from './fixtures';
import {api,uploadReport} from '../lib/api';
import App from '../../App';
vi.mock('../lib/api',async () => {
  const real=await vi.importActual<typeof import('../lib/api')>('../lib/api');
  return {...real,api:Object.fromEntries(Object.keys(real.api).map(k => [k,vi.fn()])),uploadReport:vi.fn()};
});
const mock=vi.mocked(api);
const base='/my-profile/diabetes-journey';
function open(path: string) {window.history.replaceState({},'',path);return render(<App />);}
beforeEach(() => {
  vi.clearAllMocks();sessionStorage.clear();localStorage.clear();sessionStorage.setItem('adheed.token','demo-patient');
  mock.config.mockResolvedValue(fx.config);mock.me.mockResolvedValue({profile:fx.profile,role:'patient',demo_mode:true});
  mock.sukkarState.mockResolvedValue(fx.sukkarState);mock.reports.mockResolvedValue({items:[fx.reportSummary],total:1,limit:20,offset:0});
  mock.report.mockResolvedValue(fx.reportDetail);mock.visitPrep.mockResolvedValue(fx.visitPrep);
  mock.appointments.mockResolvedValue({upcoming:[],past:[],prototype_note_ar:'محاكاة'});
  mock.notifications.mockResolvedValue(fx.notifications);
  mock.followups.mockResolvedValue({items:[],total:0});mock.followup.mockResolvedValue(fx.followup);
  mock.createFollowup.mockResolvedValue(fx.followup);
  mock.demoSession.mockResolvedValue({patient_token:'demo-patient',reviewer_token:'demo-reviewer',note_ar:'عرض'});
});
describe('Team shell and Adheed integration',() => {
  it('opens Adheed from the team profile with exactly four navigation destinations',async () => {
    const user=userEvent.setup();open('/my-profile');
    await user.click(screen.getByTestId('diabetes-journey-tile'));
    expect(await screen.findByRole('button',{name:'ابدأ بتقرير السكر'})).toBeInTheDocument();
    const nav=screen.getByRole('navigation');
    expect(within(nav).getAllByRole('link')).toHaveLength(4);
    expect(within(nav).getByRole('link',{name:'ملفي'})).toHaveAttribute('aria-current','page');
    expect(document.querySelector('iframe')).toBeNull();
  });
  it('requests an explicit demo session before any report is loaded',async () => {
    sessionStorage.clear();open(base);
    expect(await screen.findByRole('button',{name:'الدخول كمريض تجريبي'})).toBeInTheDocument();
    expect(mock.sukkarState).not.toHaveBeenCalled();
    await userEvent.click(screen.getByRole('button',{name:'الدخول كمريض تجريبي'}));
    expect(await screen.findByRole('button',{name:'ابدأ بتقرير السكر'})).toBeInTheDocument();
  });
  it('navigates report history and source-backed details inside the same shell',async () => {
    open(`${base}/reports`);
    const report=await screen.findByText('report.pdf');
    await userEvent.click(report);
    expect(await screen.findByText('القيم المستخرجة ومصادرها')).toBeInTheDocument();
    expect(window.location.pathname).toBe(`${base}/reports/r1`);
    expect(screen.getByRole('navigation')).toBeInTheDocument();
  });
  it('rejects non-PDF uploads before calling the upload API',async () => {
    open(`${base}/upload`);await screen.findByText('اختر ملف PDF');
    fireEvent.change(document.querySelector('input[type=file]')!,{target:{files:[new File(['data'],'wrong.txt',{type:'text/plain'})]}});
    expect(await screen.findByText('نوع الملف غير مدعوم. يُقبل ملف PDF فقط.')).toBeInTheDocument();
    expect(uploadReport).not.toHaveBeenCalled();
  });
  it('waits for server processing before offering report results',async () => {
    let finish: (v: {id:string;status:string;status_label_ar:string;error_ar:null;ready:boolean;failed:boolean}) => void=()=>{};
    mock.reportStatus.mockReturnValue(new Promise(resolve => {finish=resolve;}));
    vi.mocked(uploadReport).mockReturnValue({promise:Promise.resolve({report:fx.reportSummary,message_ar:'بدأت المعالجة'}),cancel:vi.fn()});
    open(`${base}/upload`);await screen.findByText('اختر ملف PDF');
    fireEvent.change(document.querySelector('input[type=file]')!,{target:{files:[new File(['%PDF-'],'report.pdf',{type:'application/pdf'})]}});
    await userEvent.click(screen.getByRole('button',{name:'رفع التقرير'}));
    await waitFor(()=>expect(mock.reportStatus).toHaveBeenCalled());
    expect(screen.queryByRole('button',{name:'افتح التقرير'})).not.toBeInTheDocument();
    finish({id:'r1',status:'ready',status_label_ar:'جاهز',error_ar:null,ready:true,failed:false});
    expect(await screen.findByRole('button',{name:'افتح التقرير'})).toBeInTheDocument();
  });
  it('submits the reviewed report and the patient reason to Python',async () => {
    open(`${base}/followups/new?report=r1`);
    const reason=await screen.findByLabelText('لماذا ترغب في المراجعة؟');
    await userEvent.type(reason,'أرغب في مناقشة ملخص التقرير');
    await userEvent.click(screen.getByRole('button',{name:'إرسال الطلب'}));
    await waitFor(()=>expect(mock.createFollowup).toHaveBeenCalledWith({report_id:'r1',reason_ar:'أرغب في مناقشة ملخص التقرير',include_metrics:true}));
  });
  it('does not render a reviewer queue for a patient session',async () => {
    open('/reviewer');
    expect(await screen.findByRole('button',{name:'الدخول كمراجع تجريبي'})).toBeInTheDocument();
    expect(mock.reviewerQueue).not.toHaveBeenCalled();
  });
  it('loads appointments from the backend and keeps the four shell links',async () => {
    open('/appointments');
    await waitFor(()=>expect(mock.appointments).toHaveBeenCalled());
    expect(within(screen.getByRole('navigation')).getAllByRole('link')).toHaveLength(4);
  });
});
