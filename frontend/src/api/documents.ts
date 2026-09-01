import { apiRequest, apiRequestWithoutResponse } from "./client";
import type { DocumentResponse, DocumentTextResponse } from "./types";

export function listDocuments(token: string): Promise<DocumentResponse[]> {
  return apiRequest<DocumentResponse[]>("/documents", { token });
}

export function uploadDocument(token: string, file: File): Promise<DocumentResponse> {
  const formData = new FormData();
  formData.append("file", file);
  return apiRequest<DocumentResponse>("/documents", {
    method: "POST",
    body: formData,
    token,
  });
}

export function getDocumentText(token: string, documentId: number): Promise<DocumentTextResponse> {
  return apiRequest<DocumentTextResponse>(`/documents/${documentId}/text`, { token });
}

export function deleteDocument(token: string, documentId: number): Promise<void> {
  return apiRequestWithoutResponse(`/documents/${documentId}`, { method: "DELETE", token });
}