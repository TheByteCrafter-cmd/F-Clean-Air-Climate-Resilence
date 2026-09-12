import { ApiStatusResponse, ErrorResponse, HealthResponse } from '../types/api';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

export class ApiError extends Error {
  public code: string;
  public details?: unknown;

  constructor(code: string, message: string, details?: unknown) {
    super(message);
    this.name = 'ApiError';
    this.code = code;
    this.details = details;
  }
}

async function request<T>(endpoint: string, options?: RequestInit): Promise<T> {
  const url = `${API_BASE_URL}${endpoint}`;
  const response = await fetch(url, {
    headers: {
      'Content-Type': 'application/json',
      ...options?.headers,
    },
    ...options,
  });

  if (!response.ok) {
    let errorCode = `HTTP_${response.status}`;
    let errorMessage = response.statusText || 'API Request Failed';
    let errorDetails: unknown = undefined;

    try {
      const errorPayload: ErrorResponse = await response.json();
      if (errorPayload.error) {
        errorCode = errorPayload.error.code;
        errorMessage = errorPayload.error.message;
        errorDetails = errorPayload.error.details;
      }
    } catch {
      // Non-JSON error body fallback
    }

    throw new ApiError(errorCode, errorMessage, errorDetails);
  }

  return response.json();
}

export const apiClient = {
  getHealth: (): Promise<HealthResponse> => request<HealthResponse>('/api/health'),
  getV1Status: (): Promise<ApiStatusResponse> => request<ApiStatusResponse>('/api/v1/status'),
};
