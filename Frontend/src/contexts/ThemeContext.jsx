import {
  createContext,
  useContext,
  useEffect,
  useState,
} from "react";

const ThemeContext =
  createContext(null);

const THEME_STORAGE_KEY =
  "spc_theme";

function getInitialTheme() {
  try {
    const savedTheme =
      localStorage.getItem(
        THEME_STORAGE_KEY,
      );

    if (
      savedTheme === "light" ||
      savedTheme === "dark"
    ) {
      return savedTheme;
    }
  } catch {
    // Fall back to light mode.
  }

  return "light";
}

export function ThemeProvider({
  children,
}) {
  const [theme, setTheme] =
    useState(getInitialTheme);

  useEffect(() => {
    document.documentElement.setAttribute(
      "data-theme",
      theme,
    );

    try {
      localStorage.setItem(
        THEME_STORAGE_KEY,
        theme,
      );
    } catch {
      // Theme still works even
      // without localStorage.
    }
  }, [theme]);

  function toggleTheme() {
    setTheme((currentTheme) =>
      currentTheme === "light"
        ? "dark"
        : "light",
    );
  }

  return (
    <ThemeContext.Provider
      value={{
        theme,
        setTheme,
        toggleTheme,
      }}
    >
      {children}
    </ThemeContext.Provider>
  );
}

export function useTheme() {
  const context =
    useContext(ThemeContext);

  if (!context) {
    throw new Error(
      "useTheme must be used inside ThemeProvider",
    );
  }

  return context;
}