import {useNavigate} from 'react-router-dom';
import {useLanguage} from '../../i18n';
import type {Appointment} from '../../types';
import {Button,Dialog} from '../ui';

/** The shell never fabricates an appointment or silently changes backend state. */
export function AppointmentDetailsDialog({appointment,onClose}:{appointment:Appointment|null;onClose:()=>void}) {
 const {l,formatDateTime}=useLanguage();
 const navigate=useNavigate();
 return <Dialog open={!!appointment} onClose={onClose} title="تفاصيل الموعد التجريبي"
   actions={<Button block onClick={()=>{if(appointment)navigate(`/appointments/${appointment.id}`);onClose();}}>فتح التفاصيل</Button>}>
   {appointment && <><p>{l(appointment.clinic)}</p><p>{l(appointment.facility)}</p><p>{formatDateTime(appointment.dateTime)}</p><p className="form__note">محاكاة داخل النموذج الأولي — لا يوجد حجز لدى منشأة صحية.</p></>}
 </Dialog>;
}
export function BookAppointmentDialog({open,onClose}:{open:boolean;onClose:()=>void}) {
 const navigate=useNavigate();
 return <Dialog open={open} onClose={onClose} title="المواعيد في النموذج التجريبي"
   actions={<Button block onClick={()=>{navigate('/my-profile');onClose();}}>الذهاب إلى ملفي</Button>}>
   <p>تُنشأ المواعيد التجريبية من Python بعد مراجعة طلب المتابعة والموافقة عليه. افتح عضيد من ملفي، وراجع تقريرك ثم أرسل طلب متابعة.</p>
   <p className="form__note">لا يُحجز أي موعد حقيقي من هذا النموذج.</p>
 </Dialog>;
}
