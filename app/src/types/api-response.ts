export interface ApiResponseEnvelope<T> {
  code: number;
  data: T;
  error_code?: number | string | null;
  message?: string | null;
}

export function unwrapApiResponse<T>(response: unknown): T {
  const envelope = response as ApiResponseEnvelope<T>;
  if (
    envelope &&
    typeof envelope === "object" &&
    "data" in envelope &&
    "code" in envelope
  ) {
    return envelope.data;
  }
  return response as T;
}
