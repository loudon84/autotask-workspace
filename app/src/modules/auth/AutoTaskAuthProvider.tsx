import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
} from "react";
import { logout as authLogout, getAuthState } from "@/actions/auth";
import { clearAllWebSessions } from "@/actions/web-workspace";
import { setUnauthorizedHandler } from "@/services/api-client";
import { getApiMode } from "@/services/endpoint-config";
import { AutoTaskLoginScreen } from "./AutoTaskLoginScreen";
import type { PublicAuthState } from "./auth.types";
import { BootstrapScreen } from "./components/BootstrapScreen";

interface AuthContextValue {
  authState: PublicAuthState;
  logout: () => Promise<void>;
  refresh: () => Promise<void>;
}

const AuthContext = createContext<AuthContextValue | null>(null);

const MOCK_AUTH_STATE: PublicAuthState = {
  status: "authenticated",
  user: {
    id: "mock-user",
    email: "demo@autotask.local",
    displayName: "Mock 用户",
  },
};

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) {
    throw new Error("useAuth must be used within AutoTaskAuthProvider");
  }
  return ctx;
}

interface AutoTaskAuthProviderProps {
  children: React.ReactNode;
}

export function AutoTaskAuthProvider({ children }: AutoTaskAuthProviderProps) {
  const isMockMode = getApiMode() === "mock";
  const [authState, setAuthState] = useState<PublicAuthState>({
    status: "loading",
  });

  const refresh = useCallback(async () => {
    if (isMockMode) {
      setAuthState(MOCK_AUTH_STATE);
      return;
    }
    const state = await getAuthState();
    setAuthState(state);
  }, [isMockMode]);

  const logout = useCallback(async () => {
    if (isMockMode) {
      setAuthState(MOCK_AUTH_STATE);
      return;
    }
    try {
      await clearAllWebSessions();
    } catch {
      // ignore cleanup errors during logout
    }
    const state = await authLogout();
    setAuthState(state);
  }, [isMockMode]);

  useEffect(() => {
    refresh().catch(() => {
      setAuthState({ status: "unauthenticated" });
    });
  }, [refresh]);

  useEffect(() => {
    if (!isMockMode) {
      setUnauthorizedHandler(() => {
        setAuthState({ status: "unauthenticated" });
      });
    }
  }, [isMockMode]);

  const value = useMemo(
    () => ({ authState, logout, refresh }),
    [authState, logout, refresh]
  );

  if (authState.status === "loading") {
    return <BootstrapScreen />;
  }

  if (!isMockMode && authState.status === "unauthenticated") {
    return (
      <AuthContext.Provider value={value}>
        <AutoTaskLoginScreen onLoginSuccess={refresh} />
      </AuthContext.Provider>
    );
  }

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}
