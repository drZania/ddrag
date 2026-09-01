import { apiRequest } from "./client";
import type { Credentials, PublicUser, TokenResponse } from "./types";

export function register(credentials: Credentials): Promise<PublicUser> {
  return apiRequest<PublicUser>("/auth/register", {
    method: "POST",
    body: JSON.stringify(credentials),
    headers: { "Content-Type": "application/json" },
  });
}

export function login(credentials: Credentials): Promise<TokenResponse> {
  return apiRequest<TokenResponse>("/auth/login", {
    method: "POST",
    body: JSON.stringify(credentials),
    headers: { "Content-Type": "application/json" },
  });
}

export function getCurrentUser(token: string): Promise<PublicUser> {
  return apiRequest<PublicUser>("/auth/me", { token });
}