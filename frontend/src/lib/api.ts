import { API_URL, CHAT_URL, MAX_UPLOAD_BYTES } from "../config";
import type { ExtractResult, PlanRequest, PlanResponse } from "./types";

/** An error the UI can explain. `code` matches the backend error codes, plus a few client ones. */
export class ApiError extends Error {
  code: string;
  status: number;
  constructor(code: string, message: string, status = 0) {
    super(message);
    this.code = code;
    this.status = status;
  }
}

async function request<T>(base: string, path: string, init?: RequestInit, timeoutMs = 60_000): Promise<T> {
  const ctrl = new AbortController();
  const timer = setTimeout(() => ctrl.abort(), timeoutMs);
  let res: Response;
  try {
    res = await fetch(base + path, {
      ...init,
      headers: { "content-type": "application/json", ...init?.headers },
      signal: init?.signal ?? ctrl.signal,
    });
  } catch (e) {
    if ((e as Error).name === "AbortError") throw new ApiError("TIMEOUT", "The request took too long.");
    throw new ApiError("NETWORK", "Couldn't reach the server. Check your internet connection.");
  } finally {
    clearTimeout(timer);
  }
  let body: unknown = null;
  try {
    body = await res.json();
  } catch {
    // non-JSON (e.g. a gateway error page)
  }
  if (!res.ok) {
    const b = (body ?? {}) as { error?: string; message?: string };
    throw new ApiError(b.error || `HTTP_${res.status}`, b.message || "Something went wrong.", res.status);
  }
  return body as T;
}

const post = <T>(path: string, data: unknown, base = API_URL, timeoutMs?: number) =>
  request<T>(base, path, { method: "POST", body: JSON.stringify(data) }, timeoutMs);

const ALLOWED = ["image/jpeg", "image/png", "image/webp", "application/pdf"];

/** Checks the file before upload so common problems get a clear message without a round trip. */
export function checkFile(file: File): ApiError | null {
  const name = file.name.toLowerCase();
  if (file.type === "image/heic" || file.type === "image/heif" || name.endsWith(".heic") || name.endsWith(".heif"))
    return new ApiError("HEIC_NOT_SUPPORTED", "HEIC");
  if (!ALLOWED.includes(file.type)) return new ApiError("UNSUPPORTED_TYPE", "type");
  if (file.size > MAX_UPLOAD_BYTES) return new ApiError("FILE_TOO_LARGE", "size");
  if (file.size === 0) return new ApiError("UNSUPPORTED_TYPE", "empty");
  return null;
}

interface UploadUrl {
  uploadUrl: string;
  fields: Record<string, string>;
  key: string;
}

/** Presigned POST to S3. The file has to be the last form field. */
export async function uploadBill(file: File): Promise<string> {
  const bad = checkFile(file);
  if (bad) throw bad;
  const up = await post<UploadUrl>("/upload-url", { contentType: file.type, size: file.size });
  const form = new FormData();
  for (const [k, v] of Object.entries(up.fields)) form.append(k, v);
  form.append("file", file);
  let res: Response;
  try {
    res = await fetch(up.uploadUrl, { method: "POST", body: form });
  } catch {
    throw new ApiError("NETWORK", "Upload failed. Check your internet connection.");
  }
  if (!res.ok) {
    const text = await res.text().catch(() => "");
    if (text.includes("EntityTooLarge")) throw new ApiError("FILE_TOO_LARGE", "size", res.status);
    throw new ApiError("UPLOAD_FAILED", "Upload failed.", res.status);
  }
  return up.key;
}

export const extractBill = (key: string) => post<ExtractResult>("/extract", { key }, API_URL, 65_000);

export const createPlan = (req: PlanRequest) => post<PlanResponse>("/plan", req);

export const getPlan = (id: string) => request<PlanResponse>(API_URL, `/plan/${encodeURIComponent(id)}`);

export const speak = (text: string, lang: string) =>
  post<{ audio: string; contentType: string }>("/speak", { text, lang });

export interface ChatReply {
  reply: string;
  sessionId: string;
}

export const sendChat = (body: { sessionId: string | null; planId: string; message: string; lang: string }) =>
  post<ChatReply>("/chat", body, CHAT_URL, 60_000);
