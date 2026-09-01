import { useEffect, useState, type ReactNode } from "react";

import { ColorModeContext, type ColorMode } from "./color-mode-context";

const STORAGE_KEY = "ddrag-color-mode";

function getInitialColorMode(): ColorMode {
  const storedMode = window.localStorage.getItem(STORAGE_KEY);
  if (storedMode === "light" || storedMode === "dark") {
    return storedMode;
  }

  return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
}

export function ColorModeProvider({ children }: { children: ReactNode }) {
  const [colorMode, setColorMode] = useState<ColorMode>(getInitialColorMode);

  useEffect(() => {
    document.documentElement.dataset.theme = colorMode;
    document.documentElement.classList.toggle("dark", colorMode === "dark");
    window.localStorage.setItem(STORAGE_KEY, colorMode);
  }, [colorMode]);

  return (
    <ColorModeContext.Provider
      value={{
        colorMode,
        toggleColorMode: () => setColorMode((currentMode) => (currentMode === "light" ? "dark" : "light")),
      }}
    >
      {children}
    </ColorModeContext.Provider>
  );
}