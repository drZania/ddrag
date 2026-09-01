export class ApiError extends Error {
  constructor(
    public readonly status: number,
    message: string,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

interface ApiErrorResponse {
  detail?: string;
}

interface ApiRequestOptions extends Omit<RequestInit, "body" | "headers"> {
  body?: BodyInit | null;
  headers?: HeadersInit;
  token?: string;
}

const apiBaseUrl = (import.meta.env.VITE_API_BASE_URL ?? "").replace(/\/$/, "");

export async function apiRequest<T>(path: string, options: ApiRequestOptions = {}): Promise<T> {
  const { token, headers, ...requestOptions } = options;
  const response = await fetch(`${apiBaseUrl}${path}`, {
    ...requestOptions,
    headers: {
      ...headers,
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
  });

  if (!response.ok) {
    const error = (await response.json().catch(() => ({}))) as ApiErrorResponse;
    throw new ApiError(response.status, error.detail ?? "Request failed");
  }

  return (await response.json()) as T;
}

export async function apiRequestWithoutResponse(path: string, options: ApiRequestOptions = {}): Promise<void> {
  const { token, headers, ...requestOptions } = options;
  const response = await fetch(`${apiBaseUrl}${path}`, {
    ...requestOptions,
    headers: {
      ...headers,
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
  });

  if (!response.ok) {
    const error = (await response.json().catch(() => ({}))) as ApiErrorResponse;
    throw new ApiError(response.status, error.detail ?? "Request failed");
  }
}

export function isUnauthorized(error: unknown): boolean {
  return error instanceof ApiError && error.status === 401;
}