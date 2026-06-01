export interface AnalyzeRequest {
  query: string;
  age: number | null;
  gender: string;
  medications: string[];
  existing_conditions: string[];
  patient_id?: string;
  state?: string;
}

export interface Condition {
  name: string;
  confidence: number;
  evidence: string[];
}

export interface DrugSafety {
  interactions_found: boolean;
  warnings: string[];
  recommendations: string[];
}

export interface IndiaContextData {
  season: string;
  high_risk_diseases: string[];
  regional_alerts: {
    disease: string;
    severity: string;
    message: string;
    source: string;
  }[];
  epidemiological_note: string;
}

export interface AnalyzeResponse {
  // v1 fields
  triage?: string;
  triage_message?: string;
  conditions?: Condition[];
  immediate_actions?: string[];
  recommended_tests?: string[];
  drug_safety?: DrugSafety;
  red_flags?: string[];
  follow_up_questions?: string[];
  patient_summary?: string;
  disclaimer?: string;
  cached?: boolean;
  error?: string;
  india_context?: IndiaContextData;
  dangerous_differentials?: string[];
  // v2 pipeline fields
  risk_tier?: string;
  risk_flags?: string[];
  synthesis?: string;
  monitoring_plan_created?: boolean;
  monitoring_plan_id?: string | null;
  tasks_created?: number;
  plan_reasoning?: string;
  tools_executed?: string[];
  case_id?: string;
  patient_id?: string;
}
