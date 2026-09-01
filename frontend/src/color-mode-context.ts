import { createContext } from "react";

export type ColorMode = "light" | "dark";

export interface ColorModeContextValue {
  colorMode: ColorMode;
  toggleColorMode: () => void;
}

export const ColorModeContext = createContext<ColorModeContextValue | null>(null);