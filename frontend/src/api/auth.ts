import { apiGet, apiPost } from "./client";

export type UserRole = "administrador" | "supervisor" | "usuario" | "consulta";

export interface UserOut {
  id: number;
  email: string;
  full_name: string;
  role: UserRole;
  is_active: boolean;
}

interface TokenResponse {
  access_token: string;
  token_type: string;
}

export function login(email: string, password: string): Promise<TokenResponse> {
  return apiPost<TokenResponse>("/auth/login", { email, password });
}

export function fetchCurrentUser(): Promise<UserOut> {
  return apiGet<UserOut>("/auth/me");
}
