/**
 * TypeScript type definitions for Unlimited OCR Cloud SDK.
 */

export type BlockType =
  | 'heading'
  | 'paragraph'
  | 'table'
  | 'list'
  | 'formula'
  | 'caption'
  | 'header'
  | 'footer'
  | 'unknown';

export interface DocumentBlock {
  block_id: string;
  type: BlockType;
  reading_order: number;
  text?: string;
  level?: number;
  headers?: string[];
  rows?: any[][];
  items?: string[];
  bbox?: [number, number, number, number];
}

export interface DocumentPage {
  page_number: number;
  width_pts?: number;
  height_pts?: number;
  route?: 'native_vector' | 'ai_ocr';
  blocks: DocumentBlock[];
}

export interface StructuredResultContract {
  schema_version: '1.0';
  document_id: string;
  job_id?: string;
  status: 'succeeded' | 'failed' | 'processing';
  page_count: number;
  engine: string;
  processing_time_seconds?: number;
  pages: DocumentPage[];
}

export interface JobStatusResponse {
  id: string;
  document_id: string;
  status: 'queued' | 'leased' | 'processing' | 'succeeded' | 'failed' | 'cancelled';
  mode: 'auto' | 'native_only' | 'ocr_only' | 'hybrid';
  progress_pct: number;
  retry_count: number;
  error_code?: string;
  error_message?: string;
  created_at: string;
  updated_at: string;
  completed_at?: string;
}

export interface DocumentUploadResponse {
  document_id: string;
  job_id: string;
  status: string;
  filename: string;
  file_size_bytes: number;
  page_count: number;
  mode: string;
  created_at: string;
}

export interface UsageStatsResponse {
  tenant_id: string;
  tenant_name: string;
  tier: string;
  period_month: string;
  monthly_page_quota: number;
  pages_used: number;
  pages_remaining: number;
  quota_percentage_used: number;
  rate_limit_rpm: number;
}
