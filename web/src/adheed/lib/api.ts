/** Typed API client for the Sukkar Plus FastAPI backend. */

import type {
  AppConfig, Appointment, FollowUp, HealthProfile, HomeData, NotificationList,
  Profile, ReportDetail, ReportSummary, SukkarState, VisitPrep, WellnessData,
} from './types';

const RAW_BASE = (import.meta.env.VITE_API_BASE_URL ?? '').replace(/\/$/, '');
export const API_BASE = `${RAW_BASE}/api/v1`;

const TOKEN_KEY = 'adheed.token';

export function readToken(): string | null {
  try {
    return window.sessionStorage.getItem(TOKEN_KEY);
  } catch {
    return null;
  }
}

export function writeToken(token: string | null): void {
  try {
    if (token) window.sessionStorage.setItem(TOKEN_KEY, token);
    else window.sessionStorage.removeItem(TOKEN_KEY);
  } catch {
    /* private browsing: the session simply does not persist */
  }
}

export class ApiError extends Error {
  readonly status: number;
  readonly code: string;
  readonly messageAr: string;
  readonly detailAr: string | null;

  constructor(status: number, code: string, messageAr: string, detailAr: string | null = null) {
    super(messageAr);
    this.status = status;
    this.code = code;
    this.messageAr = messageAr;
    this.detailAr = detailAr;
  }
}

const NETWORK_MESSAGE =
  'تعذّر الوصول إلى الخادم. تأكد من تشغيل واجهة عضيد البرمجية ثم أعد المحاولة.';

async function toError(res: Response): Promise<ApiError> {
  let code = `http_${res.status}`;
  let messageAr = 'حدث خطأ غير متوقع. حاول مرة أخرى.';
  let detailAr: string | null = null;
  try {
    const body = await res.json();
    const detail = body?.detail;
    if (typeof detail === 'string') {
      messageAr = detail;
    } else if (detail && typeof detail === 'object') {
      code = detail.code ?? code;
      messageAr = detail.message_ar ?? messageAr;
      detailAr = detail.detail_ar ?? null;
    }
  } catch {
    /* non-JSON error body */
  }
  if (res.status === 401) messageAr = 'انتهت الجلسة. سجّل الدخول من جديد.';
  return new ApiError(res.status, code, messageAr, detailAr);
}

interface RequestOptions {
  method?: string;
  body?: unknown;
  signal?: AbortSignal;
  auth?: boolean;
}

async function request<T>(path: string, opts: RequestOptions = {}): Promise<T> {
  const { method = 'GET', body, signal, auth = true } = opts;
  const headers: Record<string, string> = {};
  if (auth) {
    const token = readToken();
    if (token) headers.Authorization = `Bearer ${token}`;
  }
  let payload: BodyInit | undefined;
  if (body instanceof FormData) {
    payload = body;
  } else if (body !== undefined) {
    headers['Content-Type'] = 'application/json';
    payload = JSON.stringify(body);
  }

  let res: Response;
  try {
    res = await fetch(`${API_BASE}${path}`, { method, headers, body: payload, signal });
  } catch (err) {
    if ((err as Error)?.name === 'AbortError') throw err;
    throw new ApiError(0, 'network', NETWORK_MESSAGE);
  }
  if (!res.ok) throw await toError(res);
  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}

/** Upload with real progress. XHR is used because fetch cannot report it. */
export function uploadReport(
  file: File,
  onProgress: (percent: number) => void,
): { promise: Promise<{ report: ReportSummary; message_ar: string }>; cancel: () => void } {
  const xhr = new XMLHttpRequest();
  const promise = new Promise<{ report: ReportSummary; message_ar: string }>((resolve, reject) => {
    const form = new FormData();
    form.append('file', file);
    xhr.open('POST', `${API_BASE}/reports`);
    const token = readToken();
    if (token) xhr.setRequestHeader('Authorization', `Bearer ${token}`);
    xhr.upload.onprogress = (e) => {
      if (e.lengthComputable) onProgress(Math.round((e.loaded / e.total) * 100));
    };
    xhr.onload = () => {
      let parsed: unknown = null;
      try { parsed = JSON.parse(xhr.responseText); } catch { /* ignore */ }
      if (xhr.status >= 200 && xhr.status < 300) {
        resolve(parsed as { report: ReportSummary; message_ar: string });
        return;
      }
      const detail = (parsed as { detail?: { code?: string; message_ar?: string; detail_ar?: string } })?.detail;
      reject(new ApiError(
        xhr.status,
        detail?.code ?? `http_${xhr.status}`,
        detail?.message_ar ?? 'تعذّر رفع الملف. حاول مرة أخرى.',
        detail?.detail_ar ?? null,
      ));
    };
    xhr.onerror = () => reject(new ApiError(0, 'network', NETWORK_MESSAGE));
    xhr.onabort = () => reject(new ApiError(0, 'cancelled', 'أُلغي الرفع.'));
    xhr.send(form);
  });
  return { promise, cancel: () => xhr.abort() };
}

export const api = {
  config: () => request<AppConfig>('/config', { auth: false }),
  demoSession: () => request<{ patient_token: string; reviewer_token: string; note_ar: string }>(
    '/auth/demo-session', { method: 'POST', auth: false }),

  me: () => request<{ profile: Profile; demo_mode: boolean; role: string }>('/me'),
  healthProfile: () => request<HealthProfile>('/me/health-profile'),
  setTargetProfile: (target_profile: string) =>
    request<{ profile: Profile }>('/me/target-profile', { method: 'PATCH', body: { target_profile } }),

  home: () => request<HomeData>('/home'),
  sukkarState: () => request<SukkarState>('/sukkar/state'),

  reports: (limit = 20, offset = 0) =>
    request<{ items: ReportSummary[]; total: number; limit: number; offset: number }>(
      `/reports?limit=${limit}&offset=${offset}`),
  report: (id: string) => request<ReportDetail>(`/reports/${id}`),
  reportStatus: (id: string) => request<{
    id: string; status: string; status_label_ar: string; error_ar: string | null;
    ready: boolean; failed: boolean;
  }>(`/reports/${id}/status`),
  updateFields: (id: string, updates: Array<{
    metric_key: string; corrected_value?: number | null;
    mark_unavailable?: boolean; confirmed?: boolean;
  }>, confirmAllEligible = false) =>
    request<ReportDetail>(`/reports/${id}/fields`, {
      method: 'PATCH', body: { updates, confirm_all_eligible: confirmAllEligible },
    }),

  visitPrep: (reportId?: string) =>
    request<VisitPrep>(reportId ? `/visit-prep/${reportId}` : '/visit-prep'),

  followups: () => request<{ items: FollowUp[]; total: number }>('/followups'),
  followup: (id: string) => request<FollowUp>(`/followups/${id}`),
  createFollowup: (body: { report_id?: string | null; reason_ar: string; include_metrics?: boolean }) =>
    request<FollowUp>('/followups', { method: 'POST', body }),
  withdrawFollowup: (id: string) => request<FollowUp>(`/followups/${id}/withdraw`, { method: 'POST' }),
  closeFollowup: (id: string) => request<FollowUp>(`/followups/${id}/close`, { method: 'POST' }),

  appointments: () => request<{ upcoming: Appointment[]; past: Appointment[]; prototype_note_ar: string }>(
    '/appointments'),
  appointment: (id: string) => request<Appointment>(`/appointments/${id}`),

  notifications: (channel?: 'personal' | 'general') =>
    request<NotificationList>(`/notifications${channel ? `?channel=${channel}` : ''}`),
  readNotification: (id: string) => request<void>(`/notifications/${id}/read`, { method: 'POST' }),
  readAllNotifications: () => request<{ count: number }>('/notifications/read-all', { method: 'POST' }),
  deleteNotifications: (channel?: 'personal' | 'general') =>
    request<{ count: number }>(`/notifications${channel ? `?channel=${channel}` : ''}`, { method: 'DELETE' }),

  wellness: () => request<WellnessData>('/wellness'),

  reviewerQueue: () => request<{ items: FollowUp[]; total: number }>('/reviewer/requests'),
  reviewerRequest: (id: string) => request<FollowUp>(`/reviewer/requests/${id}`),
  reviewerStart: (id: string) => request<FollowUp>(`/reviewer/requests/${id}/start`, { method: 'POST' }),
  reviewerDecide: (id: string, decision: string, note_ar?: string) =>
    request<FollowUp>(`/reviewer/requests/${id}/decide`, { method: 'POST', body: { decision, note_ar } }),
  reviewerNote: (id: string, note_ar: string) =>
    request<FollowUp>(`/reviewer/requests/${id}/notes`, { method: 'POST', body: { note_ar } }),
};
