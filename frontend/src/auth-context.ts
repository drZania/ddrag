import { createContext } from "react";

import type { Credentials, PublicUser } from "./api/types";

export interface AuthContextValue {
  isLoading: boolean;
  token: string | null;
  user: PublicUser | null;
  login: (credentials: Credentials) => Promise<void>;
  register: (credentials: Credentials) => Promise<void>;
  logout: () => void;
}

export const AuthContext = createContext<AuthContextValue | null>(null);