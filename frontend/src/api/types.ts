export interface Credentials {
  email: string;
  password: string;
}

export interface PublicUser {
  id: number;
  email: string;
  created_at: string;
}

export interface TokenResponse {
  access_token: string;
  token_type: string;
}

export interface DocumentResponse {
  id: number;
  user_id: number;
  original_filename: string;
  storage_path: string;
  content_type: string;
  file_size_bytes: number;
  sha256_digest: string;
  status: string;
  created_at: string;
}

export interface DocumentTextResponse {
  id: number;
  status: string;
  extracted_text: string | null;
  extraction_error: string | null;
}

export interface ChatSessionResponse {
  id: number;
  title: string;
  created_at: string;
}

export interface ChatMessageResponse {
  id: number;
  role: "user" | "assistant";
  content: string;
  created_at: string;
}

export interface QuerySourceResponse {
  citation_id: number;
  document_id: number;
  chunk_id: number;
  chunk_order: number;
  distance: number;
}

export interface ChatQuestionResponse {
  query_id: number;
  assistant_message_id: number;
  answer: string;
  context_available: boolean;
  sources: QuerySourceResponse[];
  citation_validation: Record<string, unknown>;
}