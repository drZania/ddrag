import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter, Route, Routes } from "react-router-dom";

import { App } from "./App";
import { AuthProvider } from "./auth-provider";
import { ColorModeProvider } from "./color-mode";
import "./styles.css";
import { ChakraProvider } from "@chakra-ui/react";
import { system } from "./theme";

const root = document.getElementById("root");

if (!root) {
  throw new Error("Application root was not found");
}

createRoot(root).render(
  <StrictMode>
    <ChakraProvider value={system}>
      <ColorModeProvider>
        <AuthProvider>
          <BrowserRouter>
            <Routes>
              <Route path="/" element={<App />} />
            </Routes>
          </BrowserRouter>
        </AuthProvider>
      </ColorModeProvider>
    </ChakraProvider>
  </StrictMode>,
);