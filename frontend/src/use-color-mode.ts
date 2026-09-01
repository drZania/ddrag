import { useContext } from "react";

import { ColorModeContext, type ColorModeContextValue } from "./color-mode-context";

export function useColorMode(): ColorModeContextValue {
  const value = useContext(ColorModeContext);
  if (!value) {
    throw new Error("useColorMode must be used within ColorModeProvider");
  }
  return value;
}