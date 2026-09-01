import { Box, Button, VStack } from "@chakra-ui/react";
import { Files, MessageSquare } from "lucide-react";

type Workspace = "documents" | "chat";

interface WorkspaceNavigationProps {
  activeWorkspace: Workspace;
  onSelect: (workspace: Workspace) => void;
}

export function WorkspaceNavigation({ activeWorkspace, onSelect }: WorkspaceNavigationProps) {
  return (
    <Box
      as="nav"
      aria-label="Primary navigation"
      w={{ base: "100%", md: "14rem" }}
      px={{ base: "1.25rem", md: "1.5rem" }}
      py={{ base: "1rem", md: "1.5rem" }}
      borderBottomWidth={{ base: "1px", md: "0" }}
      borderRightWidth={{ base: "0", md: "1px" }}
      borderColor="border"
      bg="surface"
    >
      <VStack align="stretch" gap="1">
        <Button
          variant={activeWorkspace === "documents" ? "subtle" : "ghost"}
          colorPalette={activeWorkspace === "documents" ? "teal" : "gray"}
          justifyContent="start"
          onClick={() => onSelect("documents")}
        >
          <Files size={17} /> Documents
        </Button>
        <Button
          variant={activeWorkspace === "chat" ? "subtle" : "ghost"}
          colorPalette={activeWorkspace === "chat" ? "teal" : "gray"}
          justifyContent="start"
          onClick={() => onSelect("chat")}
        >
          <MessageSquare size={17} /> Chats
        </Button>
      </VStack>
    </Box>
  );
}
