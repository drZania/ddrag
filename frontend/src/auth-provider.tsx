import { useEffect, useState, type ReactNode } from "react";

import { getCurrentUser, login as loginRequest, register as registerRequest } from "./api/auth";
import type { Credentials, PublicUser } from "./api/types";
import { AuthContext } from "./auth-context";

const TOKEN_STORAGE_KEY = "ddrag-access-token";

export function AuthProvider({ children }: { children: ReactNode }) {
  const [isLoading, setIsLoading] = useState(() => Boolean(window.localStorage.getItem(TOKEN_STORAGE_KEY)));
  const [token, setToken] = useState<string | null>(null);
  const [user, setUser] = useState<PublicUser | null>(null);

  function clearSession() {
    window.localStorage.removeItem(TOKEN_STORAGE_KEY);
    setToken(null);
    setUser(null);
  }

  async function establishSession(accessToken: string) {
    const currentUser = await getCurrentUser(accessToken);
    window.localStorage.setItem(TOKEN_STORAGE_KEY, accessToken);
    setToken(accessToken);
    setUser(currentUser);
  }

  useEffect(() => {
    const storedToken = window.localStorage.getItem(TOKEN_STORAGE_KEY);
    if (!storedToken) return;

    void getCurrentUser(storedToken)
      .then((currentUser) => {
        window.localStorage.setItem(TOKEN_STORAGE_KEY, storedToken);
        setToken(storedToken);
        setUser(currentUser);
      })
      .catch(() => {
        window.localStorage.removeItem(TOKEN_STORAGE_KEY);
        setToken(null);
        setUser(null);
      })
      .finally(() => setIsLoading(false));
  }, []);

  async function login(credentials: Credentials) {
    const response = await loginRequest(credentials);
    await establishSession(response.access_token);
  }

  async function register(credentials: Credentials) {
    await registerRequest(credentials);
    await login(credentials);
  }

  return (
    <AuthContext.Provider value={{ isLoading, token, user, login, register, logout: clearSession }}>
      {children}
    </AuthContext.Provider>
  );
}