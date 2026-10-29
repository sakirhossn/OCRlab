import {
  DocumentUploadResponse,
  JobStatusResponse,
  StructuredResultContract,
  UsageStatsResponse,
} from './types';

export interface ClientOptions {
  apiKey?: string;
  baseUrl?: string;
}

export class UnlimitedOCRClient {
  private apiKey: string;
  private baseUrl: string;

  constructor(options: ClientOptions = {}) {
    this.apiKey = options.apiKey || (typeof process !== 'undefined' ? process.env.UNLIMITED_OCR_API_KEY || '' : '');
    if (!this.apiKey) {
      throw new Error('API key must be provided or set via UNLIMITED_OCR_API_KEY environment variable.');
    }
    this.baseUrl = (options.baseUrl || 'https://api.ocrlab.cloud/v1').replace(/\/+$/, '');
  }

  private async request<T>(path: string, init: RequestInit = {}): Promise<T> {
    const headers = new Headers(init.headers);
    headers.set('Authorization', `Bearer ${this.apiKey}`);
    headers.set('User-Agent', 'UnlimitedOCR-TypeScriptSDK/1.0');

    const url = `${this.baseUrl}${path}`;
    const response = await fetch(url, { ...init, headers });

    if (!response.ok) {
      const errText = await response.text();
      throw new Error(`API Error [${response.status}]: ${errText}`);
    }

    const contentType = response.headers.get('content-type') || '';
    if (contentType.includes('application/json')) {
      return (await response.json()) as T;
    }
    return (await response.text()) as unknown as T;
  }

  /**
   * Uploads a document (PDF, PNG, JPEG) and queues an async OCR job.
   */
  async uploadDocument(
    file: Blob | Buffer | Uint8Array,
    filename = 'document.pdf',
    mode: 'auto' | 'native_only' | 'ocr_only' | 'hybrid' = 'auto',
    idempotencyKey?: string,
  ): Promise<DocumentUploadResponse> {
    const formData = new FormData();
    const blob = file instanceof Blob ? file : new Blob([file]);
    formData.append('file', blob, filename);
    formData.append('mode', mode);

    const headers: Record<string, string> = {};
    if (idempotencyKey) {
      headers['Idempotency-Key'] = idempotencyKey;
    }

    return this.request<DocumentUploadResponse>('/documents', {
      method: 'POST',
      body: formData,
      headers,
    });
  }

  /**
   * Retrieves the current processing state and progress.
   */
  async getJobStatus(jobId: string): Promise<JobStatusResponse> {
    return this.request<JobStatusResponse>(`/jobs/${jobId}`);
  }

  /**
   * Polls until the job reaches succeeded or failed state.
   */
  async waitForCompletion(
    jobId: string,
    pollIntervalMs = 1500,
    timeoutMs = 60000,
  ): Promise<JobStatusResponse> {
    const start = Date.now();
    while (Date.now() - start < timeoutMs) {
      const status = await this.getJobStatus(jobId);
      if (status.status === 'succeeded' || status.status === 'failed' || status.status === 'cancelled') {
        return status;
      }
      await new Promise((r) => setTimeout(r, pollIntervalMs));
    }
    throw new Error(`Job ${jobId} timed out after ${timeoutMs}ms`);
  }

  /**
   * Retrieves structured result adhering to versioned schema 1.0.
   */
  async getResultJSON(jobId: string): Promise<StructuredResultContract> {
    return this.request<StructuredResultContract>(`/jobs/${jobId}/result?format=json`);
  }

  /**
   * Retrieves extracted Markdown layout.
   */
  async getResultMarkdown(jobId: string): Promise<string> {
    return this.request<string>(`/jobs/${jobId}/result?format=markdown`);
  }

  /**
   * Retrieves extracted plain text.
   */
  async getResultText(jobId: string): Promise<string> {
    return this.request<string>(`/jobs/${jobId}/result?format=text`);
  }

  /**
   * Retrieves tenant quota statistics.
   */
  async getUsage(): Promise<UsageStatsResponse> {
    return this.request<UsageStatsResponse>('/usage');
  }
}
