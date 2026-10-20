import {
  createContext,
  useContext,
  useEffect,
  useMemo,
  useState,
} from "react";

import {
  getCurrentUser,
  login as loginRequest,
  logout as logoutRequest,
  register as registerRequest,
} from "../services/authService.js";

import {
  rememberSessionExpired,
  tokenHasExpired,
} from "../utils/sessionNotice.js";

const AuthContext = createContext(null);

const TOKEN_KEY = "spc_access_token";
const USER_KEY = "spc_user";

export function AuthProvider({ children }) {
  const [accessToken, setAccessToken] = useState(() =>
    sessionStorage.getItem(TOKEN_KEY),
  );

  const [user, setUser] = useState(() => {
    const storedUser = sessionStorage.getItem(USER_KEY);

    if (!storedUser) {
      return null;
    }

    try {
      return JSON.parse(storedUser);
    } catch {
      return null;
    }
  });

  const [isLoading, setIsLoading] = useState(true);

  const isAuthenticated = Boolean(accessToken && user);

  useEffect(() => {
    async function restoreSession() {
      if (!accessToken) {
        setUser(null);
        setIsLoading(false);
        return;
      }

      try {
        const currentUser = await getCurrentUser(accessToken);

        setUser(currentUser);
        sessionStorage.setItem(USER_KEY, JSON.stringify(currentUser));
      } catch {
        if (tokenHasExpired(accessToken)) {
          rememberSessionExpired();
        }

        sessionStorage.removeItem(TOKEN_KEY);
        sessionStorage.removeItem(USER_KEY);

        setAccessToken(null);
        setUser(null);
      } finally {
        setIsLoading(false);
      }
    }

    restoreSession();
  }, [accessToken]);

  async function register({ fullName, email, password }) {
    return registerRequest({
      fullName,
      email,
      password,
    });
  }

  async function login({ email, password }) {
    const result = await loginRequest({
      email,
      password,
    });

    const token = result.access_token;
    const safeUser = result.user;

    sessionStorage.setItem(TOKEN_KEY, token);
    sessionStorage.setItem(USER_KEY, JSON.stringify(safeUser));

    setAccessToken(token);
    setUser(safeUser);

    return result;
  }

  async function logout() {
    // Pages call logout() when the API says the token is no longer valid.
    // If the token has simply run out, remember that so the login page can
    // explain it instead of looking like a random logout.
    const sessionRanOut =
      Boolean(accessToken) && tokenHasExpired(accessToken);

    try {
      if (accessToken) {
        await logoutRequest(accessToken);
      }
    } finally {
      if (sessionRanOut) {
        rememberSessionExpired();
      }

      sessionStorage.removeItem(TOKEN_KEY);
      sessionStorage.removeItem(USER_KEY);

      setAccessToken(null);
      setUser(null);
    }
  }

  async function refreshCurrentUser() {
    if (!accessToken) {
      return null;
    }

    const currentUser = await getCurrentUser(accessToken);

    setUser(currentUser);
    sessionStorage.setItem(USER_KEY, JSON.stringify(currentUser));

    return currentUser;
  }

  const value = useMemo(
    () => ({
      user,
      accessToken,
      isAuthenticated,
      isLoading,
      register,
      login,
      logout,
      refreshCurrentUser,
    }),
    [user, accessToken, isAuthenticated, isLoading],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const context = useContext(AuthContext);

  if (!context) {
    throw new Error("useAuth must be used inside AuthProvider");
  }

  return context;
}