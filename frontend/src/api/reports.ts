import api from './client';

export type ReportKind = 'sandbox' | 'repurposing' | 'toxicity' | 'deg' | 'ddi' | 'bioactivity' | 'denovo' | 'admet' | 'dti_gnn';
export type ReportStyle = 'scientific' | 'executive';
export type ReportModel = 'gemini-2.5-flash' | 'gemini-2.5-pro';

export interface GenerateReportRequest {
  kind:    ReportKind;
  payload: unknown;
  style?:  ReportStyle;
  model?:  ReportModel;
}

export interface GeneratedReport {
  report_id:       string;
  kind:            ReportKind;
  style:           ReportStyle;
  model:           string;
  title:           string;
  report_markdown: string;
  created_at:      string;
}

export interface ReportListItem {
  report_id:  string;
  kind:       ReportKind;
  style:      ReportStyle;
  model:      string;
  title:      string;
  created_at: string;
}

export const reportsApi = {
  generate: (body: GenerateReportRequest) =>
    api.post<GeneratedReport>('/reports/generate/', body),

  list: () =>
    api.get<{ reports: ReportListItem[] }>('/reports/'),

  get: (reportId: string) =>
    api.get<GeneratedReport>(`/reports/${reportId}/`),

  remove: (reportId: string) =>
    api.delete<{ deleted: number }>(`/reports/${reportId}/`),
};
