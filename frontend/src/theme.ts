import { createSystem, defaultConfig, defineConfig } from "@chakra-ui/react";

const config = defineConfig({
  globalCss: {
    "html, body, #root": {
      minHeight: "100%",
    },
    body: {
      margin: "0",
      bg: "background",
      color: "text",
      fontFamily: "body",
    },
  },
  theme: {
    semanticTokens: {
      colors: {
        background: {
          value: { _light: "{colors.gray.50}", _dark: "{colors.gray.950}" },
        },
        surface: {
          value: { _light: "{colors.white}", _dark: "{colors.gray.900}" },
        },
        text: {
          value: { _light: "{colors.gray.950}", _dark: "{colors.gray.50}" },
        },
        muted: {
          value: { _light: "{colors.gray.600}", _dark: "{colors.gray.400}" },
        },
        primary: {
          value: { _light: "{colors.teal.700}", _dark: "{colors.teal.300}" },
        },
        secondary: {
          value: { _light: "{colors.orange.700}", _dark: "{colors.orange.300}" },
        },
        border: {
          value: { _light: "{colors.gray.200}", _dark: "{colors.gray.700}" },
        },
        success: {
          value: { _light: "{colors.green.700}", _dark: "{colors.green.300}" },
        },
        warning: {
          value: { _light: "{colors.orange.700}", _dark: "{colors.orange.300}" },
        },
        error: {
          value: { _light: "{colors.red.700}", _dark: "{colors.red.300}" },
        },
      },
      fonts: {
        body: {
          value: "ui-sans-serif, system-ui, sans-serif",
        },
        heading: {
          value: "Georgia, 'Times New Roman', serif",
        },
      },
    },
  },
});

export const system = createSystem(defaultConfig, config);