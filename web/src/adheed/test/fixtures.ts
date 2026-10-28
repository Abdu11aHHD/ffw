import type {
  AppConfig, Appointment, FollowUp, HealthProfile, HomeData, NotificationList,
  Profile, ReportDetail, ReportSummary, SukkarState, VisitPrep, WellnessData,
} from '../lib/types';

export const profile: Profile = {
  id: 'u1', pseudo_id: 'SP-DEMO01', role: 'patient',
  target_profile: 'general_adult_t1_t2',
  target_profile_label_ar: 'بالغ مصاب بالسكري من النوع الأول أو الثاني (أهداف عامة)',
  display_name: 'سارة الأحمد (حساب تجريبي)',
  health_record_number: 'SP-0000-0000-DEMO', is_synthetic: true,
};

export const config: AppConfig = {
  demo_mode: true, supabase_configured: false, gemini_configured: false,
  environment: 'demo', max_upload_bytes: 15728640,
  accepted_mime_types: ['application/pdf'], setup_notes_ar: ['لم تُضبط بيانات Supabase.'],
};

export const reportSummary: ReportSummary = {
  id: 'r1', status: 'ready', status_label_ar: 'التقرير جاهز',
  created_at: '2026-10-27T08:00:00Z', file_name: 'report.pdf', file_size_bytes: 23858,
  page_count: 1, format_id: 'omnipod_discover_agp_summary_v1', format_verified: true,
  device_label: 'Omnipod 5 & Dexcom G7',
  period: { status: 'found', start: '2026-10-13', end: '2026-10-26', days: 14,
    source_label: '13/10/2026–26/10/2026', note_ar: null, page: 1 },
  outcome: 'review_suggested', outcome_title_ar: 'يحتاج إلى مراجعة مختص',
  data_sufficient: true, error_ar: null, provenance: 'synthetic',
};

export const reportDetail: ReportDetail = {
  ...reportSummary,
  glucose_unit: 'mg/dL',
  report_period: reportSummary.period,
  metrics_period: reportSummary.period,
  data_quality: {
    days_of_data: 14, coverage_percent: 88,
    coverage_source: 'نسبة اتصال الحساس كما طُبعت في التقرير', sufficient: true, reasons_ar: [],
  },
  warnings_ar: ['يحتوي ملف PDF على ملخصات مطبوعة فقط؛ لم يُعِد التطبيق بناء القراءات التفصيلية.'],
  extraction: {
    format_id: 'omnipod_discover_agp_summary_v1', format_verified: true, glucose_unit: 'mg/dL',
    report_period: reportSummary.period!, metrics_period: reportSummary.period!,
    fields: [
      {
        key: 'mean_glucose', label_ar: 'متوسط السكر', extracted_value: 168, corrected_value: null,
        ai_value: null, effective_value: 168, unit: 'mg/dL', extraction_status: 'found',
        extraction_status_label_ar: 'تم العثور عليه', validation: 'valid',
        validation_label_ar: 'اجتاز التحقق', method: 'local_text',
        method_label_ar: 'قراءة نص الملف في الخادم', source_page: 1,
        source_label: 'Average Glucose', source_text: 'Average Glucose / 168 mg/dL',
        messages_ar: [], marked_unavailable: false, confirmed: true, verification: 'verified',
        eligible_for_bulk_confirm: true,
      },
      {
        key: 'time_very_low', label_ar: 'منخفض جدًا (أقل من 54)', extracted_value: 1.4,
        corrected_value: null, ai_value: null, effective_value: 1.4, unit: '%',
        extraction_status: 'found', extraction_status_label_ar: 'تم العثور عليه',
        validation: 'valid', validation_label_ar: 'اجتاز التحقق', method: 'local_text',
        method_label_ar: 'قراءة نص الملف في الخادم', source_page: 1,
        source_label: 'Very Low (<54 mg/dL)', source_text: '1.4% Very Low', messages_ar: [],
        marked_unavailable: false, confirmed: true, verification: 'verified',
        eligible_for_bulk_confirm: true,
      },
    ],
    checks: [
      { id: 'band_sum', passed: true, message_ar: 'مجموع نطاقات السكر الخمسة 100% (متسق).', involved: [] },
      { id: 'gmi_mean', passed: true, message_ar: 'قيمة GMI تتسق مع متوسط السكر.', involved: [] },
    ],
    warnings_ar: [], sensor_label: 'نسبة اتصال الحساس', limited_data_notice: false,
    device_label: 'Omnipod 5 & Dexcom G7', report_days_label: 14, ai_used: false,
    found_count: 12, page_count: 1,
  },
  verified_metrics: [
    { key: 'mean_glucose', label_ar: 'متوسط السكر', value: 168, unit: 'mg/dL',
      origin: 'extracted_from_report', origin_label_ar: 'مستخرج من التقرير', status: 'verified',
      status_label_ar: 'موثّق', source_label: 'Average Glucose', source_page: 1,
      original_extracted_value: null, note: null },
  ],
  analysis: {
    rules_version: '2026.10-demo.1', outcome: 'review_suggested',
    outcome_title_ar: 'يحتاج إلى مراجعة مختص',
    outcome_explanation_ar: 'انطبقت قاعدة مُعدّة على بيانات موثّقة. هذا ليس تشخيصًا.',
    results: [], reasons_ar: ['منخفض جدًا 1.4% لا يستوفي الهدف المرجعي العام (أقل من 1%).'],
    limitations_ar: [], evaluated_at: '2026-10-27T08:00:05Z',
  },
  ai_summary: {
    text: 'القيم الموثّقة:\n• متوسط السكر: 168 mg/dL', source: 'local_template',
    source_label_ar: 'نص من قالب محلي (دون ذكاء اصطناعي)',
    fallback_reason_ar: 'لم يُضبط مفتاح خدمة الذكاء الاصطناعي على الخادم.',
  },
  has_stored_file: false,
};

export const homeData: HomeData = {
  profile, demo_mode: true, greeting_ar: 'مرحبًا', unread_notifications: 2,
  next_appointment: null,
  sukkar_plus: {
    state: 'ready', title_ar: 'التقرير جاهز للمراجعة',
    body_ar: 'اطّلع على المؤشرات ومصادرها، وجهّز أسئلتك للموعد.',
    steps: [
      { key: 'upload', label_ar: 'رفع التقرير', done: true },
      { key: 'process', label_ar: 'قراءة المؤشرات', done: true },
      { key: 'prepare', label_ar: 'الاستعداد للموعد', done: true },
      { key: 'followup', label_ar: 'طلب متابعة', done: false },
      { key: 'appointment', label_ar: 'موعد تجريبي', done: false },
    ],
    reports_count: 1, latest_report: reportSummary,
  },
  shortcuts: [
    { key: 'sukkar_plus', label_ar: 'سكر بلس', subtitle_ar: 'رحلتك مع السكر، بطريقة أسهل',
      route: '/sukkar', icon: 'glucose' },
    { key: 'appointments', label_ar: 'مواعيدي', subtitle_ar: 'القادمة والسابقة',
      route: '/appointments', icon: 'calendar' },
  ],
};

export const healthProfile: HealthProfile = {
  profile,
  targets: {
    profile: 'general_adult_t1_t2',
    profile_label_ar: 'بالغ مصاب بالسكري من النوع الأول أو الثاني (أهداف عامة)',
    notes_ar: ['أهداف مرجعية عامة.'],
    items: [{ metric: 'time_in_range', label_ar: 'الوقت ضمن النطاق (70–180)',
      text_ar: 'أكثر من 70%', source_ref: 'Battelino 2019 Table 3' }],
  },
  sukkar_plus: {
    reports_count: 1, latest_report: reportSummary, open_followups: 0, appointments: 1,
    data_sufficiency_rule_ar: 'تُعدّ البيانات كافية عند 14 يومًا على الأقل وتغطية حساس لا تقل عن 70%.',
  },
  metric_catalogue: [],
  report_statuses_ar: { ready: 'التقرير جاهز' },
};

export const sukkarState: SukkarState = {
  journey: homeData.sukkar_plus,
  recent_reports: [reportSummary], reports_total: 1, followups: [], open_followups: 0,
  demo_mode: true,
  how_it_works: [
    { step: 1, title_ar: 'ارفع تقريرك', body_ar: 'ملف PDF نصي.' },
    { step: 2, title_ar: 'نقرأ المطبوع فقط', body_ar: 'مع مصدر كل قيمة.' },
    { step: 3, title_ar: 'نتحقق قبل أن نعرض', body_ar: 'فحوص حسابية.' },
    { step: 4, title_ar: 'تجهّز لموعدك', body_ar: 'ملخص وأسئلة.' },
    { step: 5, title_ar: 'تطلب مراجعة عند الحاجة', body_ar: 'طلب تجريبي.' },
  ],
  limits_ar: ['لا يتصل سكر بلس بمنصة صحتي الرسمية.'],
};

export const emptySukkarState: SukkarState = {
  ...sukkarState,
  journey: { state: 'no_report', title_ar: 'لم ترفع تقريرًا بعد',
    body_ar: 'ابدأ برفع تقرير السكر لنرتّبه معك خطوة بخطوة.',
    steps: sukkarState.journey.steps.map((s) => ({ ...s, done: false })),
    reports_count: 0, latest_report: null },
  recent_reports: [], reports_total: 0,
};

export const notifications: NotificationList = {
  items: [
    { id: 'n1', kind: 'report_ready', channel: 'personal', title_ar: 'تقريرك جاهز',
      body_ar: 'انتهت معالجة تقرير السكر الذي رفعته.', sender_ar: 'سكر بلس',
      created_at: '2026-10-27T08:00:00Z', read: false, read_at: null, link: '/sukkar/reports/r1' },
    { id: 'n2', kind: 'general', channel: 'general', title_ar: 'عن سكر بلس',
      body_ar: 'نموذج أولي مستقل.', sender_ar: 'سكر بلس',
      created_at: '2026-10-20T08:00:00Z', read: true, read_at: '2026-10-21T08:00:00Z', link: null },
  ],
  unread_total: 1, personal_count: 1, personal_unread: 1, general_count: 1, general_unread: 0,
};

export const appointments: { upcoming: Appointment[]; past: Appointment[]; prototype_note_ar: string } = {
  upcoming: [], past: [], prototype_note_ar: 'جميع المواعيد هنا مواعيد تجريبية. لم يُحجز أي موعد حقيقي.',
};

export const visitPrep: VisitPrep = {
  generated_at: '2026-10-27T09:00:00Z', is_synthetic: true, report_id: 'r1',
  period_ar: '13 أكتوبر إلى 26 أكتوبر 2026', period_days: 14,
  metrics: [{ label_ar: 'الوقت ضمن النطاق (70–180)', value_ar: '65.5%',
    note_ar: 'مستخرج من التقرير', source_ar: 'Time in Range (70-180 mg/dL) — صفحة 1' }],
  patterns_ar: [], limitations_ar: [], missing_ar: [],
  questions_ar: ['هل الأهداف المرجعية العامة مناسبة لي؟'],
  comparison: { comparable: false, reason_ar: 'لا يوجد تقريران بفترات معروفة للمقارنة.',
    previous_period_ar: null, current_period_ar: null, previous_days: null, current_days: null,
    deltas: [], caveats_ar: [], method_version: 'cgm_periods.v1' },
  outcome: reportDetail.analysis, target_notes_ar: [], appointment: null, followups: [],
  disclaimer_ar: 'هذا الملخص تعليمي. لا يتضمن تشخيصًا أو توصيات علاجية.',
};

export const wellness: WellnessData = {
  topics: [{ id: 'time_in_range', icon: 'range', title_ar: 'ما معنى الوقت ضمن النطاق؟',
    summary_ar: 'النسبة التي بقي فيها السكر بين 70 و180.',
    body_ar: ['يقيس الوقت ضمن النطاق نسبة القراءات بين 70 و180.'],
    source_ref: 'Battelino 2019' }],
  linked_report: reportSummary,
  disclaimer_ar: 'محتوى تعليمي عام. لا يتضمن تشخيصًا.',
};

export const followup: FollowUp = {
  id: 'f1', pseudo_ref: 'REQ-ABC123', trigger: 'rule', trigger_label_ar: 'قاعدة مُعدّة مسبقًا',
  rule_ids: ['TBR54-TARGET'], rules_version: '2026.10-demo.1',
  reason_ar: 'أرغب في مراجعة تقريري قبل الموعد.',
  shared_snapshot: { period: '13 أكتوبر إلى 26 أكتوبر 2026',
    items: { 'الوقت ضمن النطاق (70–180)': '65.5%' }, quality_notes: [] },
  status: 'awaiting_review', status_label_ar: 'بانتظار المراجعة', decision: null,
  decision_label_ar: null, patient_message_ar: null,
  created_at: '2026-10-27T10:00:00Z', updated_at: '2026-10-27T10:00:00Z',
  provenance: 'synthetic', report_id: 'r1', appointment_id: null,
  history: [{ from_status: null, from_label_ar: null, to_status: 'draft', to_label_ar: 'مسودة',
    at: '2026-10-27T10:00:00Z', actor_role: 'patient', note_ar: null }],
  notes: [], appointment: null,
};
