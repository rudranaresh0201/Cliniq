/**
 * ClinIQ 2.0 — DeepDive API client
 *
 * Endpoint: POST /api/v2/cases/{case_id}/labs/upload
 * All interfaces mirror the exact JSON returned by lab_ingestion.py +
 * cbc_interpreter.py / generic_interpret.  Do not invent fields here.
 */

// ---------------------------------------------------------------------------
// Interfaces derived from live backend source
// ---------------------------------------------------------------------------

/** One abnormal lab value — produced by flag_abnormals() in cbc_interpreter.py */
export interface AbnormalFlag {
  marker: string;
  value: string;                          // stored as string by the interpreter
  reference_range?: string;               // e.g. "12.0 - 17.5"
  direction: 'low' | 'high';
  severity: 'critical' | 'moderate' | 'mild';
  interpretation: string;                 // e.g. "Haemoglobin is LOW at 11.2"
}

/** One matched clinical pattern — produced by detect_patterns() in cbc_interpreter.py */
export interface PatternDetected {
  pattern: string;
  confidence: number;                     // 0–1 float (confidence_base × match_ratio)
  india_common?: boolean;
  note?: string;
  criteria_matched?: number;
  criteria_total?: number;
}

/** Follow-up test recommendation from Groq synthesis */
export interface FollowUpTest {
  test: string;
  reason: string;
  priority: 'immediate' | '48h' | 'week';
}

/** interpretation field — the full DeepDive output object */
export interface DeepDiveInterpretation {
  report_type: string;
  parsed_values: Record<string, number | string>;
  values_count: number;
  abnormal_flags: AbnormalFlag[];
  abnormal_count: number;
  patterns_detected: PatternDetected[];
  primary_pattern: string | null;
  risk_level: 'low' | 'moderate' | 'high' | 'critical';
  risk_reason: string;
  immediate_actions: string[];
  follow_up_tests: FollowUpTest[];
  clinical_summary: string;
  primary_finding: string;
  india_context: string;
  patient_explanation: string;
  monitoring_needed: boolean;
  ocr_confidence?: number;
  extraction_error?: string;
  error?: string;
}

/** Top-level response from POST /api/v2/cases/{case_id}/labs/upload */
export interface LabUploadResponse {
  report_id: string;
  case_id: string;
  filename: string;
  report_type: string;                    // "CBC" | "LFT" | "RFT" | "ECG" | "Xray" | "generic"
  raw_text: string;
  confidence_score: number;              // OCR confidence 0–1
  extracted_values: Record<string, number | string>;
  interpretation: DeepDiveInterpretation;
  critical_flags: AbnormalFlag[];
  abnormal_count: number;
  timeline_event_id: string | null;
  extraction_error: string | null;
}

// ---------------------------------------------------------------------------
// Upload function
// ---------------------------------------------------------------------------

const BASE_URL = (import.meta.env.VITE_API_URL as string | undefined) ?? '';

export async function uploadLabReport(
  file: File,
  caseId: string,
): Promise<LabUploadResponse> {
  const form = new FormData();
  form.append('file', file);

  const uploadUrl = `${BASE_URL}/api/v2/cases/${encodeURIComponent(caseId)}/labs/upload`;
  const res = await fetch(uploadUrl, { method: 'POST', body: form });

  if (!res.ok) {
    const body = await res.json().catch(() => ({ detail: `HTTP ${res.status}` }));
    throw new Error(
      typeof body.detail === 'string' ? body.detail : `Upload failed (${res.status})`,
    );
  }

  return res.json() as Promise<LabUploadResponse>;
}
