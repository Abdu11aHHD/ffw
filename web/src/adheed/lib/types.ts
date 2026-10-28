/** Types mirroring the FastAPI response models (app/schemas + *.to_json()). */

export type MetricKey =
  | 'mean_glucose' | 'gmi' | 'cv' | 'sd'
  | 'time_very_low' | 'time_low' | 'time_in_range' | 'time_high' | 'time_very_high'
  | 'time_below_range_total' | 'time_above_range_total' | 'sensor_active';

export type ReportStatus = 'processing' | 'needs_review' | 'ready' | 'failed';

export type ReviewOutcome = 'routine_summary' | 'review_suggested' | 'need_more_data' | 'seek_medical_help';

export type FollowUpStatus =
  | 'draft' | 'awaiting_review' | 'under_review' | 'more_info_requested' | 'reviewed' | 'closed';

export type ReviewDecision = 'review_required' | 'data_completion' | 'no_further_action_demo';

export interface ApiErrorBody {
  code: string;
  message_ar: string;
  detail_ar?: string | null;
}

export interface AppConfig {
  demo_mode: boolean;
  supabase_configured: boolean;
  gemini_configured: boolean;
  deepseek_configured?: boolean;
  ai_provider?: string;
  ai_model?: string | null;
  ai_configured?: boolean;
  environment: string;
  max_upload_bytes: number;
  accepted_mime_types: string[];
  setup_notes_ar: string[];
}

export interface Profile {
  id: string;
  pseudo_id: string;
  role: 'patient' | 'reviewer';
  target_profile: string;
  target_profile_label_ar: string;
  display_name: string | null;
  health_record_number: string | null;
  is_synthetic: boolean;
}

export interface PeriodJson {
  status: string;
  start: string | null;
  end: string | null;
  days: number | null;
  source_label: string | null;
  note_ar: string | null;
  page: number | null;
}

export interface ReportSummary {
  id: string;
  status: ReportStatus;
  status_label_ar: string;
  created_at: string;
  file_name: string;
  file_size_bytes: number;
  page_count: number;
  format_id: string | null;
  format_verified: boolean;
  device_label: string | null;
  period: PeriodJson | null;
  outcome: ReviewOutcome | null;
  outcome_title_ar: string | null;
  data_sufficient: boolean | null;
  error_ar: string | null;
  provenance: string;
}

export interface MetricValueJson {
  key: MetricKey;
  label_ar: string;
  value: number | null;
  unit: string;
  origin: string;
  origin_label_ar: string;
  status: string;
  status_label_ar: string;
  source_label: string | null;
  source_page: number | null;
  original_extracted_value: number | null;
  note: string | null;
}

export interface ExtractedFieldJson {
  key: MetricKey;
  label_ar: string;
  extracted_value: number | null;
  corrected_value: number | null;
  ai_value: number | null;
  effective_value: number | null;
  unit: string;
  extraction_status: string;
  extraction_status_label_ar: string;
  validation: string;
  validation_label_ar: string;
  method: string;
  method_label_ar: string;
  source_page: number | null;
  source_label: string | null;
  source_text: string | null;
  messages_ar: string[];
  marked_unavailable: boolean;
  confirmed: boolean;
  verification: string;
  eligible_for_bulk_confirm: boolean;
}

export interface ConsistencyCheckJson {
  id: string;
  passed: boolean | null;
  message_ar: string;
  involved: string[];
}

export interface ExtractionJson {
  format_id: string;
  format_verified: boolean;
  glucose_unit: string;
  report_period: PeriodJson;
  metrics_period: PeriodJson;
  fields: ExtractedFieldJson[];
  checks: ConsistencyCheckJson[];
  warnings_ar: string[];
  sensor_label: string;
  limited_data_notice: boolean;
  device_label: string | null;
  report_days_label: number | null;
  ai_used: boolean;
  found_count: number;
  page_count: number;
}

export interface DataQualityJson {
  days_of_data: number | null;
  coverage_percent: number | null;
  coverage_source: string;
  sufficient: boolean;
  reasons_ar: string[];
}

export interface RuleResultJson {
  rule_id: string;
  rule_version: number;
  rule_title_ar: string;
  status: 'triggered' | 'not_triggered' | 'not_assessable' | 'not_applicable';
  explanation_ar: string;
  evidence: Record<string, string>;
  approval_label_ar: string;
  source_ref: string;
  limitations_ar: string;
}

export interface AnalysisJson {
  rules_version: string;
  outcome: ReviewOutcome;
  outcome_title_ar: string;
  outcome_explanation_ar: string;
  results: RuleResultJson[];
  reasons_ar: string[];
  limitations_ar: string[];
  evaluated_at: string;
}

export interface AiSummaryJson {
  text: string;
  source: 'ai' | 'local_template';
  source_label_ar: string;
  fallback_reason_ar: string | null;
  provider?: string | null;
  model?: string | null;
  observations_ar?: string[];
  questions_ar?: string[];
  limitations_ar?: string[];
}

export interface ReportDetail extends ReportSummary {
  glucose_unit: string;
  report_period: PeriodJson | null;
  metrics_period: PeriodJson | null;
  data_quality: DataQualityJson | null;
  warnings_ar: string[];
  extraction: ExtractionJson | null;
  verified_metrics: MetricValueJson[];
  analysis: AnalysisJson | null;
  ai_summary: AiSummaryJson | null;
  has_stored_file: boolean;
}

export interface SummaryLineJson {
  label_ar: string;
  value_ar: string;
  note_ar: string | null;
  source_ar: string | null;
}

export interface ComparisonJson {
  comparable: boolean;
  reason_ar: string | null;
  previous_period_ar: string | null;
  current_period_ar: string | null;
  previous_days: number | null;
  current_days: number | null;
  deltas: Array<{
    key: MetricKey; label_ar: string; previous: number; current: number;
    delta: number; unit: string; delta_text_ar: string;
  }>;
  caveats_ar: string[];
  method_version: string;
}

export interface VisitPrep {
  generated_at: string;
  is_synthetic: boolean;
  report_id: string | null;
  period_ar: string | null;
  period_days: number | null;
  metrics: SummaryLineJson[];
  patterns_ar: string[];
  limitations_ar: string[];
  missing_ar: string[];
  questions_ar: string[];
  comparison: ComparisonJson | null;
  outcome: AnalysisJson | null;
  target_notes_ar: string[];
  appointment: Appointment | null;
  followups: SummaryLineJson[];
  disclaimer_ar: string;
}

export interface Appointment {
  id: string;
  scheduled_at: string;
  clinic_label: string;
  specialty_ar: string;
  is_simulated: boolean;
  status: string;
  source: string;
  followup_id: string | null;
  report_id: string | null;
  provenance: string;
  simulated_label_ar: string;
  followup?: { pseudo_ref: string; status: string; status_label_ar: string } | null;
  preparation?: VisitPrep;
  prototype_note_ar?: string;
}

export interface FollowUp {
  id: string;
  pseudo_ref: string;
  trigger: string;
  trigger_label_ar: string;
  rule_ids: string[];
  rules_version: string;
  reason_ar: string;
  shared_snapshot: { period: string; items: Record<string, string>; quality_notes: string[] };
  status: FollowUpStatus;
  status_label_ar: string;
  decision: ReviewDecision | null;
  decision_label_ar: string | null;
  patient_message_ar: string | null;
  created_at: string;
  updated_at: string;
  provenance: string;
  report_id: string | null;
  appointment_id: string | null;
  history: Array<{
    from_status: string | null; from_label_ar: string | null;
    to_status: string; to_label_ar: string; at: string;
    actor_role: string; note_ar: string | null;
  }>;
  notes: Array<{ at: string; text_ar: string; author_label: string }>;
  appointment?: Appointment | null;
  report?: Partial<ReportDetail> & { id: string };
}

export interface JourneyStep { key: string; label_ar: string; done: boolean }

export interface Journey {
  state: string;
  title_ar: string;
  body_ar: string;
  steps: JourneyStep[];
  reports_count: number;
  latest_report: ReportSummary | null;
}

export interface HomeData {
  profile: Profile;
  demo_mode: boolean;
  greeting_ar: string;
  unread_notifications: number;
  next_appointment: Appointment | null;
  sukkar_plus: Journey;
  shortcuts: Array<{ key: string; label_ar: string; subtitle_ar: string; route: string; icon: string }>;
}

export interface SukkarState {
  journey: Journey;
  recent_reports: ReportSummary[];
  reports_total: number;
  followups: FollowUp[];
  open_followups: number;
  demo_mode: boolean;
  how_it_works: Array<{ step: number; title_ar: string; body_ar: string }>;
  limits_ar: string[];
}

export interface HealthProfile {
  profile: Profile;
  targets: {
    profile: string;
    profile_label_ar: string;
    notes_ar: string[];
    items: Array<{ metric: string; label_ar: string; text_ar: string; source_ref: string }>;
  };
  sukkar_plus: {
    reports_count: number;
    latest_report: ReportSummary | null;
    open_followups: number;
    appointments: number;
    data_sufficiency_rule_ar: string;
  };
  metric_catalogue: Array<{ key: MetricKey; label_ar: string; short_label_ar: string; is_percent: boolean }>;
  report_statuses_ar: Record<string, string>;
}

export interface NotificationItem {
  id: string;
  kind: string;
  channel: 'personal' | 'general';
  title_ar: string;
  body_ar: string;
  sender_ar: string;
  created_at: string;
  read: boolean;
  read_at: string | null;
  link: string | null;
}

export interface NotificationList {
  items: NotificationItem[];
  unread_total: number;
  personal_count: number;
  personal_unread: number;
  general_count: number;
  general_unread: number;
}

export interface WellnessTopic {
  id: string;
  icon: string;
  title_ar: string;
  summary_ar: string;
  body_ar: string[];
  source_ref: string | null;
  tone?: string;
}

export interface WellnessData {
  topics: WellnessTopic[];
  linked_report: ReportSummary | null;
  disclaimer_ar: string;
}
