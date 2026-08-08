export interface RequestRow {
  id: number | string;
  request_id?: string | null;
  status_code: number | null;
  model: string | null;
  path?: string;
  stream?: boolean;
  timestamp_utc: string | null;
  input_tokens: number | null;
  output_tokens: number | null;
  cache_read_tokens: number | null;
  cache_write_tokens: number | null;
  cost_usd: number | null;
  ttfb_s: number | null;
  total_s: number | null;
  stop_reason: string | null;
  error_body?: string | null;
}

export interface RequestsResponse {
  rows: RequestRow[];
  page: number;
  total_pages: number;
  total: number;
  models: string[];
}

export interface RequestDetailResponse {
  row: RequestRow;
  request_body: string | null;
  response_body: string | null;
  original_request_body: string | null;
}

export interface CostsSummary {
  request_count: number;
  total_cost: number;
  total_input_tokens: number;
  total_output_tokens: number;
}

export interface CostSeries {
  labels: string[];
  cost: number[];
  count: number[];
}

export interface ModelCost {
  model: string | null;
  request_count: number;
  total_input_tokens: number;
  total_output_tokens: number;
  total_cost: number;
}

export interface FolderCost {
  full_path: string;
  folder: string;
  request_count: number;
  input_tokens: number;
  output_tokens: number;
  cost: number;
}

export interface CostsResponse {
  summary: CostsSummary;
  series: CostSeries;
  by_model: ModelCost[];
  by_folder: FolderCost[];
}

export type DiffRowType = "same" | "add" | "remove";

export interface DiffRow {
  type: DiffRowType;
  text: string;
}
