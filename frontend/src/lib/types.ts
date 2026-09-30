export interface User {
  id: string;
  email: string;
  name: string;
  picture: string;
}

export interface ColumnMapping {
  id: string;
  order_index: number;
  source_column: string;
  suggested_column: string;
  target_column: string;
  semantic_type: string;
  suggested_type: string;
  target_type: string;
  nullable: boolean;
  primary_key_candidate: boolean;
  foreign_key_candidate: boolean;
  include: boolean;
  confidence: number;
  source: "AI_SUGGESTED" | "USER_MODIFIED";
}

export interface TimelineEvent {
  timestamp: string | null;
  event: string;
}

export interface EntityRef {
  type: string;
  id: string;
}

export interface Visualization {
  type: "bar" | "line" | "pie" | "kpi" | "table" | "none";
  x_field: string | null;
  y_field: string | null;
  series_field: string | null;
  title: string | null;
}

export interface QueryResponse {
  session_id: string;
  answer: string;
  intent: "analytics" | "entity_investigation" | "clarification" | "error";
  entity: EntityRef | null;
  result: Record<string, unknown>[];
  timeline: TimelineEvent[];
  summary: Record<string, unknown> | null;
  visualization: Visualization | null;
  sql: string | null;
  agents_consulted: string[];
  agent_log: string[];
  missing_info: string[];
}

export interface DemoSeedResult {
  name: string;
  status: string;
  error: string | null;
}

export interface DomainColumn extends ColumnMapping {
  is_new_column: boolean;
}

export interface DomainResult {
  domain_id: string;
  agent_key: string;
  agent_label: string;
  table_name: string;
  is_new_table: boolean;
  agent_note: string | null;
  data_quality_issues: string[];
  ambiguous_fields: string[];
  columns: DomainColumn[];
}

export interface AnalyzeResponse {
  dataset_id: string;
  domains: DomainResult[];
  agent_log: string[];
}

export interface ConfirmedDomain {
  agent_key: string;
  agent_label: string;
  table_name: string;
  status: string;
  row_count: number;
}

export interface ConfirmResponse {
  dataset_id: string;
  domains: ConfirmedDomain[];
  agent_log: string[];
}

export interface DatasetSummary {
  id: string;
  name: string;
  status: string;
  row_count: number;
  error_message: string;
}

export interface ReadyDomain {
  agent_key: string;
  agent_label: string;
  table_name: string;
  row_count: number;
}

export interface DatasetListResponse {
  datasets: DatasetSummary[];
  domains: ReadyDomain[];
}

export interface ChatTurn {
  id: string;
  role: "user" | "assistant";
  question?: string;
  response?: QueryResponse;
  pending?: boolean;
  error?: string;
}
