import {
  Badge,
  Box,
  Button,
  Card,
  Dialog,
  Flex,
  Heading,
  IconButton,
  Input,
  Link,
  Menu,
  Spinner,
  Text,
  VStack,
} from "@chakra-ui/react";
import { Eye, FileUp, LogOut, Moon, MoreHorizontal, Sun, Trash2 } from "lucide-react";
import { Link as RouterLink } from "react-router-dom";
import { useEffect, useEffectEvent, useState, type ChangeEvent, type FormEvent } from "react";

import { ChatWorkspace } from "./ChatWorkspace";
import { ApiError, isUnauthorized } from "./api/client";
import { deleteDocument, getDocumentText, listDocuments, uploadDocument } from "./api/documents";
import type { DocumentResponse, DocumentTextResponse } from "./api/types";
import { useColorMode } from "./use-color-mode";
import { useAuth } from "./use-auth";
import { WorkspaceNavigation } from "./WorkspaceNavigation";

function errorMessage(error: unknown, fallback: string): string {
  return error instanceof ApiError ? error.message : fallback;
}

function DocumentStatus({ status }: { status: string }) {
  const colorPalette = status === "ready" ? "green" : status === "failed" ? "red" : "orange";
  return (
    <Badge colorPalette={colorPalette} variant="subtle" textTransform="capitalize">
      {status}
    </Badge>
  );
}

function DocumentActions({ document, onView, onDelete }: { document: DocumentResponse; onView: () => void; onDelete: () => void }) {
  return (
    <Menu.Root positioning={{ placement: "bottom-end" }}>
      <Menu.Trigger asChild>
        <IconButton aria-label={`Actions for ${document.original_filename}`} title="Document actions" size="sm" variant="ghost"><MoreHorizontal size={18} /></IconButton>
      </Menu.Trigger>
      <Menu.Positioner>
        <Menu.Content>
          <Menu.Item value="view" onClick={onView}><Eye size={16} /> View document</Menu.Item>
          <Menu.Item value="delete" color="error" onClick={onDelete}><Trash2 size={16} /> Delete document</Menu.Item>
        </Menu.Content>
      </Menu.Positioner>
    </Menu.Root>
  );
}

function DocumentTextDialog({ document, content, error, isLoading, onClose }: { document: DocumentResponse | null; content: DocumentTextResponse | null; error: string | null; isLoading: boolean; onClose: () => void }) {
  return (
    <Dialog.Root open={document !== null} onOpenChange={(details) => !details.open && onClose()} placement="center">
      <Dialog.Backdrop />
      <Dialog.Positioner px={{ base: "1rem", md: "2rem" }}>
        <Dialog.Content maxW="48rem" maxH={{ base: "calc(100dvh - 2rem)", md: "42rem" }} bg="surface" borderColor="border">
          <Dialog.Header><Dialog.Title fontFamily="heading" fontWeight="500" overflowWrap="anywhere">{document?.original_filename ?? "Document"}</Dialog.Title></Dialog.Header>
          <Dialog.Body overflowY="auto">
            {isLoading ? <Flex minH="12rem" align="center" justify="center" gap="3" color="muted" role="status"><Spinner size="sm" /> Loading extracted text</Flex> : error ? <Text color="error" role="alert">{error}</Text> : content?.extracted_text ? <Text whiteSpace="pre-wrap" overflowWrap="anywhere" fontSize="sm" lineHeight="tall">{content.extracted_text}</Text> : <Box py="6"><Text fontWeight="600">No extracted text is available</Text><Text mt="1" color="muted" fontSize="sm">{content?.extraction_error ?? "This document does not contain text DDRAG can display."}</Text></Box>}
          </Dialog.Body>
          <Dialog.Footer><Button variant="outline" onClick={onClose}>Close</Button></Dialog.Footer>
        </Dialog.Content>
      </Dialog.Positioner>
    </Dialog.Root>
  );
}

function DeleteDocumentDialog({ document, isDeleting, error, onClose, onConfirm }: { document: DocumentResponse | null; isDeleting: boolean; error: string | null; onClose: () => void; onConfirm: () => void }) {
  return (
    <Dialog.Root open={document !== null} onOpenChange={(details) => !details.open && !isDeleting && onClose()} placement="center">
      <Dialog.Backdrop />
      <Dialog.Positioner px={{ base: "1rem", md: "2rem" }}>
        <Dialog.Content maxW="28rem" bg="surface" borderColor="border">
          <Dialog.Header><Dialog.Title fontFamily="heading" fontWeight="500">Delete document?</Dialog.Title></Dialog.Header>
          <Dialog.Body><Text>Delete <Text as="span" fontWeight="700" overflowWrap="anywhere">{document?.original_filename}</Text> from your library?</Text><Text mt="3" color="muted" fontSize="sm">This removes the stored document and its processed content. This action cannot be undone.</Text>{error && <Text mt="3" color="error" fontSize="sm" role="alert">{error}</Text>}</Dialog.Body>
          <Dialog.Footer><Button variant="outline" disabled={isDeleting} onClick={onClose}>Cancel</Button><Button colorPalette="red" loading={isDeleting} disabled={isDeleting} onClick={onConfirm}><Trash2 size={17} /> Delete</Button></Dialog.Footer>
        </Dialog.Content>
      </Dialog.Positioner>
    </Dialog.Root>
  );
}

function AuthScreen() {
  const { login, register } = useAuth();
  const [mode, setMode] = useState<"login" | "register">("login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    setIsSubmitting(true);
    try {
      await (mode === "login" ? login({ email, password }) : register({ email, password }));
    } catch (requestError) {
      setError(errorMessage(requestError, "Unable to reach DDRAG. Check that the backend is running."));
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <Flex flex="1" align="center" justify="center" px="1.25rem" py={{ base: "3rem", md: "5rem" }}>
      <Card.Root w="full" maxW="26rem" borderColor="border" bg="surface" boxShadow="sm">
        <Card.Body gap="6">
          <VStack align="start" gap="2">
            <Text color="secondary" fontSize="sm" fontWeight="700" textTransform="uppercase" letterSpacing="0.08em">
              Document-grounded answers
            </Text>
            <Heading fontFamily="heading" fontSize="3xl" fontWeight="500">
              {mode === "login" ? "Welcome back" : "Create your workspace"}
            </Heading>
            <Text color="muted">{mode === "login" ? "Sign in to manage your documents." : "Start with an account for your documents."}</Text>
          </VStack>

          <form onSubmit={submit}>
            <VStack align="stretch" gap="4">
              <Box>
                <Text asChild display="block" mb="1.5" fontSize="sm" fontWeight="600"><label htmlFor="email">Email address</label></Text>
                <Input id="email" type="email" autoComplete="email" value={email} onChange={(event) => setEmail(event.target.value)} aria-invalid={Boolean(error)} aria-describedby={error ? "auth-error" : undefined} required />
              </Box>
              <Box>
                <Text asChild display="block" mb="1.5" fontSize="sm" fontWeight="600"><label htmlFor="password">Password</label></Text>
                <Input
                  id="password"
                  type="password"
                  autoComplete={mode === "login" ? "current-password" : "new-password"}
                  value={password}
                  onChange={(event) => setPassword(event.target.value)}
                  minLength={8}
                  aria-invalid={Boolean(error)}
                  aria-describedby={error ? "auth-error" : undefined}
                  required
                />
              </Box>
              {error && <Text id="auth-error" color="error" fontSize="sm" role="alert">{error}</Text>}
              <Button type="submit" colorPalette="teal" loading={isSubmitting} disabled={isSubmitting}>
                {mode === "login" ? "Sign in" : "Create account"}
              </Button>
            </VStack>
          </form>

          <Text color="muted" fontSize="sm">
            {mode === "login" ? "New to DDRAG?" : "Already have an account?"}{" "}
            <Button
              variant="plain"
              color="primary"
              size="sm"
              onClick={() => {
                setMode((currentMode) => (currentMode === "login" ? "register" : "login"));
                setError(null);
              }}
            >
              {mode === "login" ? "Create an account" : "Sign in"}
            </Button>
          </Text>
        </Card.Body>
      </Card.Root>
    </Flex>
  );
}

function DocumentWorkspace({ onOpenChat }: { onOpenChat: () => void }) {
  const { logout, token, user } = useAuth();
  const [documents, setDocuments] = useState<DocumentResponse[]>([]);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isUploading, setIsUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [viewedDocument, setViewedDocument] = useState<DocumentResponse | null>(null);
  const [documentText, setDocumentText] = useState<DocumentTextResponse | null>(null);
  const [documentTextError, setDocumentTextError] = useState<string | null>(null);
  const [isLoadingDocumentText, setIsLoadingDocumentText] = useState(false);
  const [documentPendingDeletion, setDocumentPendingDeletion] = useState<DocumentResponse | null>(null);
  const [isDeletingDocument, setIsDeletingDocument] = useState(false);
  const [deleteError, setDeleteError] = useState<string | null>(null);
  const handleUnauthorized = useEffectEvent(logout);

  useEffect(() => {
    if (!token) return;

    void listDocuments(token)
      .then(setDocuments)
      .catch((requestError: unknown) => {
        if (isUnauthorized(requestError)) handleUnauthorized();
        else setError(errorMessage(requestError, "Unable to load documents. Check that the backend is running."));
      })
      .finally(() => setIsLoading(false));
  }, [token]);

  function selectFile(event: ChangeEvent<HTMLInputElement>) {
    setSelectedFile(event.target.files?.[0] ?? null);
    setError(null);
    setSuccess(null);
  }

  async function submitUpload(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!token || !selectedFile) return;
    const form = event.currentTarget;
    setIsUploading(true);
    setError(null);
    setSuccess(null);
    try {
      const document = await uploadDocument(token, selectedFile);
      setDocuments((currentDocuments) => [document, ...currentDocuments]);
      setSuccess(`${document.original_filename} finished processing with status ${document.status}.`);
      setSelectedFile(null);
      const input = form.elements.namedItem("document") as HTMLInputElement;
      input.value = "";
    } catch (requestError) {
      if (isUnauthorized(requestError)) logout();
      else setError(errorMessage(requestError, "Unable to upload the document. Check that the backend is running."));
    } finally {
      setIsUploading(false);
    }
  }

  async function viewDocument(document: DocumentResponse) {
    if (!token) return;
    setViewedDocument(document);
    setDocumentText(null);
    setDocumentTextError(null);
    setIsLoadingDocumentText(true);
    try {
      setDocumentText(await getDocumentText(token, document.id));
    } catch (requestError) {
      if (isUnauthorized(requestError)) logout();
      else setDocumentTextError(errorMessage(requestError, "Unable to load the extracted text."));
    } finally {
      setIsLoadingDocumentText(false);
    }
  }

  async function confirmDeleteDocument() {
    if (!token || !documentPendingDeletion) return;
    const document = documentPendingDeletion;
    setIsDeletingDocument(true);
    setDeleteError(null);
    try {
      await deleteDocument(token, document.id);
      setDocuments((currentDocuments) => currentDocuments.filter((currentDocument) => currentDocument.id !== document.id));
      setDocumentPendingDeletion(null);
      setSuccess(`${document.original_filename} was deleted.`);
    } catch (requestError) {
      if (isUnauthorized(requestError)) logout();
      else setDeleteError(errorMessage(requestError, "Unable to delete this document."));
    } finally {
      setIsDeletingDocument(false);
    }
  }

  return (
    <Flex flex="1" direction={{ base: "column", md: "row" }}>
      <WorkspaceNavigation activeWorkspace="documents" onSelect={(workspace) => workspace === "chat" && onOpenChat()} />

      <Box as="main" flex="1" minW="0" px={{ base: "1.25rem", md: "3rem" }} py={{ base: "2.5rem", md: "4rem" }}>
        <VStack align="stretch" gap="8" maxW="52rem">
          <Box>
            <Text color="secondary" fontSize="sm" fontWeight="700" textTransform="uppercase" letterSpacing="0.08em">Workspace</Text>
            <Heading mt="2" fontFamily="heading" fontSize={{ base: "3xl", md: "4xl" }} fontWeight="500">Your documents</Heading>
            <Text mt="2" color="muted" overflowWrap="anywhere">Signed in as {user?.email}</Text>
          </Box>

          <Card.Root borderColor="border" bg="surface" boxShadow="xs">
            <Card.Body>
              <form onSubmit={submitUpload}>
                <Flex direction={{ base: "column", sm: "row" }} align={{ base: "stretch", sm: "end" }} gap="3">
                  <Box flex="1">
                    <Text asChild display="block" mb="1.5" fontSize="sm" fontWeight="600"><label htmlFor="document">Add a document</label></Text>
                    <Input
                      id="document"
                      name="document"
                      type="file"
                      accept=".pdf,.txt,.md,.docx,text/plain,text/markdown,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                      onChange={selectFile}
                      disabled={isUploading}
                      aria-describedby="document-help document-feedback"
                      required
                    />
                  </Box>
                  <Button type="submit" colorPalette="teal" loading={isUploading} disabled={!selectedFile || isUploading}>
                    <FileUp size={18} /> Upload
                  </Button>
                </Flex>
              </form>
              <Text id="document-help" mt="3" color="muted" fontSize="sm">PDF, TXT, Markdown, or DOCX. Maximum 10 MB.</Text>
              <Box id="document-feedback" mt="3" aria-live="polite" aria-atomic="true">
                {isUploading && <Text color="muted" fontSize="sm">Uploading and processing your document. This may take a moment.</Text>}
                {success && <Text color="success" fontSize="sm">{success}</Text>}
                {error && <Text color="error" fontSize="sm" role="alert">{error}</Text>}
              </Box>
            </Card.Body>
          </Card.Root>

          <Box>
            <Flex align="baseline" justify="space-between" gap="4">
              <Heading fontFamily="heading" fontSize="2xl" fontWeight="500">Library</Heading>
              {!isLoading && <Text color="muted" fontSize="sm">{documents.length} {documents.length === 1 ? "document" : "documents"}</Text>}
            </Flex>
            {isLoading ? (
              <Flex minH="8rem" align="center" gap="3" color="muted" role="status"><Spinner size="sm" /> Loading documents</Flex>
            ) : documents.length === 0 ? (
              <Box mt="4" px="4" py="6" borderWidth="1px" borderColor="border" bg="surface"><Text fontWeight="600">Your library is empty</Text><Text mt="1" color="muted" fontSize="sm">Upload a document to make it available for grounded answers.</Text></Box>
            ) : (
              <VStack mt="4" align="stretch" gap="0" borderTopWidth="1px" borderColor="border">
                {documents.map((document) => (
                  <Flex key={document.id} align={{ base: "start", sm: "center" }} justify="space-between" gap="4" px={{ base: "0", sm: "2" }} py="4" borderBottomWidth="1px" borderColor="border" _hover={{ bg: "surface" }}>
                    <Box minW="0">
                      <Text fontWeight="600" overflowWrap="anywhere">{document.original_filename}</Text>
                      <Text mt="1" color="muted" fontSize="sm">
                        {(document.file_size_bytes / 1024).toFixed(1)} KB · {new Date(document.created_at).toLocaleDateString()}
                      </Text>
                    </Box>
                    <Flex align="center" gap="2" flexShrink="0">
                      <DocumentStatus status={document.status} />
                      <DocumentActions document={document} onView={() => void viewDocument(document)} onDelete={() => { setDeleteError(null); setDocumentPendingDeletion(document); }} />
                    </Flex>
                  </Flex>
                ))}
              </VStack>
            )}
          </Box>
        </VStack>
      </Box>
      <DocumentTextDialog document={viewedDocument} content={documentText} error={documentTextError} isLoading={isLoadingDocumentText} onClose={() => setViewedDocument(null)} />
      <DeleteDocumentDialog document={documentPendingDeletion} isDeleting={isDeletingDocument} error={deleteError} onClose={() => setDocumentPendingDeletion(null)} onConfirm={() => void confirmDeleteDocument()} />
    </Flex>
  );
}

export function App() {
  const { colorMode, toggleColorMode } = useColorMode();
  const { isLoading, logout, user } = useAuth();
  const [activeWorkspace, setActiveWorkspace] = useState<"documents" | "chat">("documents");
  const nextMode = colorMode === "light" ? "dark" : "light";

  return (
    <Flex h="100dvh" direction="column" bg="background" overflow="hidden">
      <Flex
        as="header"
        align="center"
        justify="space-between"
        minH="4.5rem"
        px={{ base: "1.25rem", md: "2.5rem" }}
        borderBottomWidth="1px"
        borderColor="border"
        bg="surface"
      >
        <Link asChild color="text" _hover={{ color: "primary" }}>
          <RouterLink to="/" aria-label="DDRAG workspace">
            <Heading fontFamily="heading" fontSize="xl" fontWeight="600">
              DDRAG
            </Heading>
          </RouterLink>
        </Link>
        <Flex align="center" gap="1">
          {user && <IconButton aria-label="Sign out" title="Sign out" variant="ghost" color="muted" onClick={logout}><LogOut size={18} /></IconButton>}
          <IconButton aria-label={`Switch to ${nextMode} mode`} title={`Switch to ${nextMode} mode`} variant="ghost" color="muted" onClick={toggleColorMode}>
            {colorMode === "light" ? <Moon size={18} /> : <Sun size={18} />}
          </IconButton>
        </Flex>
      </Flex>

      {isLoading ? <Flex flex="1" minH="0" align="center" justify="center" gap="3" color="muted" role="status"><Spinner size="sm" /> Restoring your session</Flex> : user ? activeWorkspace === "documents" ? <DocumentWorkspace onOpenChat={() => setActiveWorkspace("chat")} /> : <ChatWorkspace onOpenDocuments={() => setActiveWorkspace("documents")} /> : <AuthScreen />}
    </Flex>
  );
}