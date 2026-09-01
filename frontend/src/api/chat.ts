import { apiRequest, apiRequestWithoutResponse } from "./client";
import type { ChatMessageResponse, ChatQuestionResponse, ChatSessionResponse } from "./types";

export function createChatSession(token: string): Promise<ChatSessionResponse> {
  return apiRequest<ChatSessionResponse>("/chat/sessions", { method: "POST", token });
}

export function listChatSessions(token: string): Promise<ChatSessionResponse[]> {
  return apiRequest<ChatSessionResponse[]>("/chat/sessions", { token });
}

export function deleteChatSession(token: string, sessionId: number): Promise<void> {
  return apiRequestWithoutResponse(`/chat/sessions/${sessionId}`, { method: "DELETE", token });
}

export function renameChatSession(token: string, sessionId: number, title: string): Promise<ChatSessionResponse> {
  return apiRequest<ChatSessionResponse>(`/chat/sessions/${sessionId}`, {
    method: "PATCH",
    token,
    body: JSON.stringify({ title }),
    headers: { "Content-Type": "application/json" },
  });
}

export function listChatMessages(token: string, sessionId: number): Promise<ChatMessageResponse[]> {
  return apiRequest<ChatMessageResponse[]>(`/chat/sessions/${sessionId}/messages`, { token });
}

export function submitQuestion(token: string, sessionId: number, question: string): Promise<ChatQuestionResponse> {
  return apiRequest<ChatQuestionResponse>(`/chat/sessions/${sessionId}/questions`, {
    method: "POST",
    token,
    body: JSON.stringify({ question }),
    headers: { "Content-Type": "application/json" },
  });
}