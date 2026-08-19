import { createContext, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { api, ApiError } from "../lib/api";
import type { AuthResponse } from "../lib/types";

const AUTH_KEY = ["auth"] as const;

interface AuthContextValue {
  data: AuthResponse | null;
  loading: boolean;
  isAuthenticated: boolean;
  orgId: string | null;
  role: string | null;
  login: (email: string, password: string) => Promise<AuthResponse>;
  register: (input: {
    email: string;
    password: string;
    full_name: string;
    org_name: string;
  }) => Promise<AuthResponse>;
  logout: () => Promise<void>;
  switchOrg: (orgId: string) => Promise<AuthResponse>;
  refresh: () => Promise<void>;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const queryClient = useQueryClient();
  const [forcedNull, setForcedNull] = useState(false);

  const query = useQuery({
    queryKey: [...AUTH_KEY],
    queryFn: () => api<AuthResponse>("/api/auth/me"),
    retry: false,
    staleTime: 45_000,
    refetchOnWindowFocus: true,
    enabled: !forcedNull,
  });

  // A 401 anywhere in the app invalidates the session.
  useEffect(() => {
    const onUnauthorized = () => {
      setForcedNull(true);
      queryClient.setQueryData([...AUTH_KEY], null);
      queryClient.clear();
    };
    window.addEventListener("auth:unauthorized", onUnauthorized);
    return () => window.removeEventListener("auth:unauthorized", onUnauthorized);
  }, [queryClient]);

  const data = forcedNull ? null : (query.data ?? null);

  const value = useMemo<AuthContextValue>(() => {
    const apply = (resp: AuthResponse) => {
      setForcedNull(false);
      queryClient.setQueryData([...AUTH_KEY], resp);
      queryClient.invalidateQueries();
      return resp;
    };

    return {
      data,
      loading: query.isLoading,
      isAuthenticated: Boolean(data),
      orgId: data?.orgs[0]?.id ?? null,
      role: data?.orgs[0]?.role ?? null,
      login: async (email, password) => apply(await api<AuthResponse>("/api/auth/login", { method: "POST", body: { email, password } })),
      register: async (input) =>
        apply(
          await api<AuthResponse>("/api/auth/register", {
            method: "POST",
            body: {
              email: input.email,
              password: input.password,
              full_name: input.full_name,
              org_name: input.org_name,
            },
          }),
        ),
      logout: async () => {
        try {
          await api("/api/auth/logout", { method: "POST" });
        } catch (err) {
          if (!(err instanceof ApiError && err.status === 401)) {
            // logout is best-effort; still clear local state
          }
        }
        setForcedNull(true);
        queryClient.clear();
      },
      switchOrg: async (orgId) =>
        apply(await api<AuthResponse>("/api/auth/switch-org", { method: "POST", body: { org_id: orgId } })),
      refresh: async () => {
        try {
          const resp = await api<AuthResponse>("/api/auth/me");
          apply(resp);
        } catch {
          setForcedNull(true);
        }
      },
    };
  }, [data, query.isLoading, queryClient]);

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}
