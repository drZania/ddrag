import {
  Box,
  Button,
  Card,
  Dialog,
  Flex,
  Heading,
  IconButton,
  Input,
  Menu,
  Spinner,
  Text,
  Textarea,
  VStack,
} from "@chakra-ui/react";
import { Check, Copy, Edit3, Menu as MenuIcon, MoreHorizontal, Plus, Send, Trash2, X } from "lucide-react";
import { useEffect, useEffectEvent, useState, type FormEvent } from "react";

import {
  applicationInformationPrompts,
  getApplicationInformation,
  type ApplicationInformation,
} from "./application-information";
import { createChatSession, deleteChatSession, listChatMessages, listChatSessions, renameChatSession, submitQuestion } from "./api/chat";
import { ApiError, isUnauthorized } from "./api/client";
import type { ChatMessageResponse, ChatQuestionResponse, ChatSessionResponse } from "./api/types";
import { useAuth } from "./use-auth";
import { WorkspaceNavigation } from "./WorkspaceNavigation";

interface ChatWorkspaceProps {
  onOpenDocuments: () => void;
}

function errorMessage(error: unknown, fallback: string): string {
  return error instanceof ApiError ? error.message : fallback;
}

function SourceList({ response }: { response: ChatQuestionResponse }) {
  if (!response.context_available) {
    return <Text mt="3" color="muted" fontSize="sm">No retrieved context was available for this answer.</Text>;
  }

  if (response.sources.length === 0) {
    return <Text mt="3" color="muted" fontSize="sm">No source metadata was returned for this answer.</Text>;
  }

  return (
    <Box as="section" aria-label="Answer sources" mt="4" pt="4" borderTopWidth="1px" borderColor="border">
      <Text as="h3" mb="2" color="muted" fontSize="sm" fontWeight="700">Sources</Text>
      <VStack align="stretch" gap="2">
        {response.sources.map((source) => (
          <Box key={source.citation_id} px="3" py="2" bg="background" borderLeftWidth="2px" borderColor="primary" overflowWrap="anywhere">
            <Text fontSize="sm" fontWeight="600">[{source.citation_id}] Document {source.document_id}</Text>
            <Text mt="1" color="muted" fontSize="xs">
              Chunk {source.chunk_id} · Order {source.chunk_order} · Distance {source.distance.toFixed(4)}
            </Text>
          </Box>
        ))}
      </VStack>
    </Box>
  );
}

function ApplicationInformationPanel({ onChoosePrompt }: { onChoosePrompt: (prompt: string) => void }) {
  return (
    <Box px="4" py="4" borderWidth="1px" borderColor="border" bg="surface">
      <Text color="secondary" fontSize="xs" fontWeight="700" textTransform="uppercase" letterSpacing="0.08em">About DDRAG</Text>
      <Text mt="2" fontWeight="600">Document-grounded answers, with clear sources</Text>
      <Text mt="1" color="muted" fontSize="sm">Ask about an uploaded document, or choose a question about the application.</Text>
      <Flex mt="3" wrap="wrap" gap="2">
        {applicationInformationPrompts.map((prompt) => <Button key={prompt} size="sm" variant="outline" onClick={() => onChoosePrompt(prompt)}>{prompt}</Button>)}
      </Flex>
    </Box>
  );
}

function ApplicationInformationExchange({ information }: { information: ApplicationInformation }) {
  return (
    <VStack align="stretch" gap="3">
      <Flex justify="end"><Card.Root maxW={{ base: "100%", md: "82%" }} bg="teal.700" color="white" borderColor="teal.700"><Card.Body px="4" py="3"><Text whiteSpace="pre-wrap" overflowWrap="anywhere">{information.question}</Text></Card.Body></Card.Root></Flex>
      <Box maxW={{ base: "100%", md: "82%" }} px="4" py="3" borderLeftWidth="3px" borderColor="secondary" bg="surface" overflowWrap="anywhere">
        <Text color="secondary" fontSize="xs" fontWeight="700" textTransform="uppercase" letterSpacing="0.08em">Application information</Text>
        <Text mt="2" whiteSpace="pre-wrap">{information.answer}</Text>
      </Box>
    </VStack>
  );
}

function CopyAnswerButton({ content }: { content: string }) {
  const [status, setStatus] = useState<"idle" | "copied" | "error">("idle");

  async function copyAnswer() {
    try {
      await navigator.clipboard.writeText(content);
      setStatus("copied");
    } catch {
      setStatus("error");
    }
  }

  return (
    <Flex mt="3" align="center" gap="2">
      <Button size="sm" variant="ghost" onClick={() => void copyAnswer()} aria-label="Copy answer">
        {status === "copied" ? <Check size={16} /> : <Copy size={16} />} {status === "copied" ? "Copied" : "Copy"}
      </Button>
      {status === "error" && <Text color="error" fontSize="xs" role="alert">Unable to copy this answer.</Text>}
    </Flex>
  );
}

function ChatActions({ session, onRename, onDelete }: { session: ChatSessionResponse; onRename: () => void; onDelete: () => void }) {
  return (
    <Menu.Root positioning={{ placement: "bottom-end" }}>
      <Menu.Trigger asChild>
        <IconButton aria-label={`Actions for chat ${session.id}`} title="Chat actions" size="sm" variant="ghost"><MoreHorizontal size={18} /></IconButton>
      </Menu.Trigger>
      <Menu.Positioner>
        <Menu.Content>
          <Menu.Item value="rename" onClick={onRename}><Edit3 size={16} /> Rename chat</Menu.Item>
          <Menu.Item value="delete" color="error" onClick={onDelete}><Trash2 size={16} /> Delete chat</Menu.Item>
        </Menu.Content>
      </Menu.Positioner>
    </Menu.Root>
  );
}

function RenameChatDialog({ session, title, error, isSaving, onChange, onClose, onSave }: { session: ChatSessionResponse | null; title: string; error: string | null; isSaving: boolean; onChange: (value: string) => void; onClose: () => void; onSave: () => void }) {
  const isInvalid = !title.trim() || title.length > 120;
  return (
    <Dialog.Root open={session !== null} onOpenChange={(details) => !details.open && !isSaving && onClose()} placement="center">
      <Dialog.Backdrop />
      <Dialog.Positioner px={{ base: "1rem", md: "2rem" }}>
        <Dialog.Content maxW="28rem" bg="surface" borderColor="border">
          <Dialog.Header><Dialog.Title fontFamily="heading" fontWeight="500">Rename chat</Dialog.Title></Dialog.Header>
          <Dialog.Body><Text asChild display="block" mb="1.5" fontSize="sm" fontWeight="600"><label htmlFor="chat-title">Chat name</label></Text><Input id="chat-title" value={title} maxLength={120} disabled={isSaving} onChange={(event) => onChange(event.target.value)} aria-invalid={Boolean(error) || isInvalid} aria-describedby={error ? "rename-error" : undefined} autoFocus />{error && <Text id="rename-error" mt="3" color="error" fontSize="sm" role="alert">{error}</Text>}</Dialog.Body>
          <Dialog.Footer><Button variant="outline" disabled={isSaving} onClick={onClose}>Cancel</Button><Button colorPalette="teal" loading={isSaving} disabled={isSaving || isInvalid} onClick={onSave}>Save</Button></Dialog.Footer>
        </Dialog.Content>
      </Dialog.Positioner>
    </Dialog.Root>
  );
}

function DeleteChatDialog({ session, isDeleting, error, onClose, onConfirm }: { session: ChatSessionResponse | null; isDeleting: boolean; error: string | null; onClose: () => void; onConfirm: () => void }) {
  return (
    <Dialog.Root open={session !== null} onOpenChange={(details) => !details.open && !isDeleting && onClose()} placement="center">
      <Dialog.Backdrop />
      <Dialog.Positioner px={{ base: "1rem", md: "2rem" }}>
        <Dialog.Content maxW="28rem" bg="surface" borderColor="border">
          <Dialog.Header><Dialog.Title fontFamily="heading" fontWeight="500">Delete chat?</Dialog.Title></Dialog.Header>
          <Dialog.Body><Text>Delete Chat {session?.id} and its messages?</Text><Text mt="3" color="muted" fontSize="sm">This permanently removes the conversation and its source history. This action cannot be undone.</Text>{error && <Text mt="3" color="error" fontSize="sm" role="alert">{error}</Text>}</Dialog.Body>
          <Dialog.Footer><Button variant="outline" disabled={isDeleting} onClick={onClose}>Cancel</Button><Button colorPalette="red" loading={isDeleting} disabled={isDeleting} onClick={onConfirm}><Trash2 size={17} /> Delete</Button></Dialog.Footer>
        </Dialog.Content>
      </Dialog.Positioner>
    </Dialog.Root>
  );
}

function ChatSessionList({ sessions, selectedSessionId, isLoading, onSelect, onRename, onDelete }: { sessions: ChatSessionResponse[]; selectedSessionId: number | null; isLoading: boolean; onSelect: (sessionId: number) => void; onRename: (session: ChatSessionResponse) => void; onDelete: (session: ChatSessionResponse) => void }) {
  if (isLoading) return <Flex gap="2" align="center" color="muted" fontSize="sm" role="status"><Spinner size="sm" /> Loading chats</Flex>;
  if (sessions.length === 0) return <Text color="muted" fontSize="sm">Start a chat to ask about your documents.</Text>;
  return <Box flex="1" minH="0" overflowY="auto"><VStack align="stretch" gap="1">
    {sessions.map((session) => <Flex key={session.id} align="center" borderRadius="l2" bg={session.id === selectedSessionId ? "teal.subtle" : undefined}><Button flex="1" minW="0" variant="ghost" colorPalette={session.id === selectedSessionId ? "teal" : "gray"} justifyContent="start" h="auto" minH="3.5rem" px="3" py="2" onClick={() => onSelect(session.id)}><Box minW="0" textAlign="start"><Text fontSize="sm" fontWeight="600" truncate>{session.title}</Text><Text mt="0.5" color="muted" fontSize="xs">Created {new Date(session.created_at).toLocaleDateString()}</Text></Box></Button><ChatActions session={session} onRename={() => onRename(session)} onDelete={() => onDelete(session)} /></Flex>)}
  </VStack></Box>;
}

function MobileChatSidebar({ open, onClose, onOpenDocuments, sessions, selectedSessionId, isLoadingSessions, onCreateSession, onSelectSession, onRename, onDelete }: { open: boolean; onClose: () => void; onOpenDocuments: () => void; sessions: ChatSessionResponse[]; selectedSessionId: number | null; isLoadingSessions: boolean; onCreateSession: () => void; onSelectSession: (sessionId: number) => void; onRename: (session: ChatSessionResponse) => void; onDelete: (session: ChatSessionResponse) => void }) {
  return <Dialog.Root open={open} onOpenChange={(details) => !details.open && onClose()}><Dialog.Backdrop /><Dialog.Positioner justifyContent="flex-start"><Dialog.Content h="100dvh" maxW="19rem" borderRadius="0" bg="surface" borderColor="border"><Dialog.Header><Flex align="center" justify="space-between"><Dialog.Title fontFamily="heading" fontWeight="500">DDRAG</Dialog.Title><Dialog.CloseTrigger asChild><IconButton aria-label="Close chat sidebar" title="Close chat sidebar" variant="ghost"><X size={18} /></IconButton></Dialog.CloseTrigger></Flex></Dialog.Header><Dialog.Body display="flex" flexDirection="column" minH="0" px="0"><Box px="1.5rem" pb="4"><WorkspaceNavigation activeWorkspace="chat" onSelect={(workspace) => { onClose(); if (workspace === "documents") onOpenDocuments(); }} /></Box><Flex flex="1" minH="0" direction="column" borderTopWidth="1px" borderColor="border" px="1.5rem" pt="4"><Flex justify="space-between" align="center" mb="3"><Box><Text fontWeight="700">Chats</Text><Text color="muted" fontSize="xs">Your conversations</Text></Box><IconButton aria-label="New chat" title="New chat" size="sm" variant="ghost" onClick={onCreateSession}><Plus size={18} /></IconButton></Flex><ChatSessionList sessions={sessions} selectedSessionId={selectedSessionId} isLoading={isLoadingSessions} onSelect={(sessionId) => { onSelectSession(sessionId); onClose(); }} onRename={onRename} onDelete={onDelete} /></Flex></Dialog.Body></Dialog.Content></Dialog.Positioner></Dialog.Root>;
}

function Message({ message, response }: { message: ChatMessageResponse; response?: ChatQuestionResponse }) {
  const isUser = message.role === "user";
  return (
    <Flex justify={isUser ? "end" : "start"}>
      <Card.Root maxW={{ base: "100%", md: "82%" }} bg={isUser ? "teal.700" : "surface"} color={isUser ? "white" : "text"} borderColor={isUser ? "teal.700" : "border"}>
        <Card.Body gap="0" px="4" py="3">
          <Text whiteSpace="pre-wrap" overflowWrap="anywhere">{message.content}</Text>
          {!isUser && response && <SourceList response={response} />}
          {!isUser && <CopyAnswerButton content={message.content} />}
        </Card.Body>
      </Card.Root>
    </Flex>
  );
}

export function ChatWorkspace({ onOpenDocuments }: ChatWorkspaceProps) {
  const { logout, token } = useAuth();
  const [sessions, setSessions] = useState<ChatSessionResponse[]>([]);
  const [selectedSessionId, setSelectedSessionId] = useState<number | null>(null);
  const [messages, setMessages] = useState<ChatMessageResponse[]>([]);
  const [responsesByMessageId, setResponsesByMessageId] = useState<Record<number, ChatQuestionResponse>>({});
  const [applicationInformation, setApplicationInformation] = useState<ApplicationInformation | null>(null);
  const [question, setQuestion] = useState("");
  const [isLoadingSessions, setIsLoadingSessions] = useState(true);
  const [isLoadingMessages, setIsLoadingMessages] = useState(true);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [sessionPendingDeletion, setSessionPendingDeletion] = useState<ChatSessionResponse | null>(null);
  const [isDeletingSession, setIsDeletingSession] = useState(false);
  const [deleteError, setDeleteError] = useState<string | null>(null);
  const [sessionPendingRename, setSessionPendingRename] = useState<ChatSessionResponse | null>(null);
  const [renameTitle, setRenameTitle] = useState("");
  const [isRenamingSession, setIsRenamingSession] = useState(false);
  const [renameError, setRenameError] = useState<string | null>(null);
  const [isSidebarOpen, setIsSidebarOpen] = useState(false);
  const handleUnauthorized = useEffectEvent(logout);

  async function selectSession(sessionId: number) {
    if (!token) return;
    setSelectedSessionId(sessionId);
    setIsLoadingMessages(true);
    setError(null);
    setApplicationInformation(null);
    try {
      const loadedMessages = await listChatMessages(token, sessionId);
      setMessages(loadedMessages);
      setResponsesByMessageId({});
    } catch (requestError) {
      if (isUnauthorized(requestError)) logout();
      else setError(errorMessage(requestError, "Unable to load this chat."));
    } finally {
      setIsLoadingMessages(false);
    }
  }

  useEffect(() => {
    if (!token) return;
    void listChatSessions(token)
      .then((loadedSessions) => {
        setSessions(loadedSessions);
        const initialSession = loadedSessions[0];
        if (!initialSession) {
          setIsLoadingMessages(false);
          return;
        }
        setSelectedSessionId(initialSession.id);
        setApplicationInformation(null);
        void listChatMessages(token, initialSession.id)
          .then((loadedMessages) => {
            setMessages(loadedMessages);
            setResponsesByMessageId({});
          })
          .catch((requestError: unknown) => {
            if (isUnauthorized(requestError)) handleUnauthorized();
            else setError(errorMessage(requestError, "Unable to load this chat."));
          })
          .finally(() => setIsLoadingMessages(false));
      })
      .catch((requestError: unknown) => {
        if (isUnauthorized(requestError)) handleUnauthorized();
        else setError(errorMessage(requestError, "Unable to load chats. Check that the backend is running."));
      })
      .finally(() => setIsLoadingSessions(false));
  }, [token]);

  async function createSession() {
    if (!token) return;
    setError(null);
    try {
      const session = await createChatSession(token);
      setSessions((currentSessions) => [session, ...currentSessions.filter((currentSession) => currentSession.id !== session.id)]);
      await selectSession(session.id);
    } catch (requestError) {
      if (isUnauthorized(requestError)) logout();
      else setError(errorMessage(requestError, "Unable to create a chat."));
    }
  }

  async function confirmDeleteSession() {
    if (!token || !sessionPendingDeletion) return;
    const session = sessionPendingDeletion;
    setIsDeletingSession(true);
    setDeleteError(null);
    try {
      await deleteChatSession(token, session.id);
      setSessions((currentSessions) => currentSessions.filter((currentSession) => currentSession.id !== session.id));
      if (selectedSessionId === session.id) {
        setSelectedSessionId(null);
        setMessages([]);
        setResponsesByMessageId({});
        setApplicationInformation(null);
        setQuestion("");
      }
      setSessionPendingDeletion(null);
      setSuccess(`Chat ${session.id} was deleted.`);
    } catch (requestError) {
      if (isUnauthorized(requestError)) logout();
      else setDeleteError(errorMessage(requestError, "Unable to delete this chat."));
    } finally {
      setIsDeletingSession(false);
    }
  }

  async function confirmRenameSession() {
    if (!token || !sessionPendingRename || !renameTitle.trim()) return;
    const session = sessionPendingRename;
    setIsRenamingSession(true);
    setRenameError(null);
    try {
      const renamedSession = await renameChatSession(token, session.id, renameTitle.trim());
      setSessions((currentSessions) => currentSessions.map((currentSession) => currentSession.id === renamedSession.id ? renamedSession : currentSession));
      setSessionPendingRename(null);
      setSuccess(`Chat renamed to ${renamedSession.title}.`);
    } catch (requestError) {
      if (isUnauthorized(requestError)) logout();
      else setRenameError(errorMessage(requestError, "Unable to rename this chat."));
    } finally {
      setIsRenamingSession(false);
    }
  }

  async function sendQuestion(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!token || selectedSessionId === null || !question.trim()) return;
    const submittedQuestion = question.trim();
    setQuestion("");
    setIsSubmitting(true);
    setError(null);
    const localInformation = getApplicationInformation(submittedQuestion);
    if (localInformation) {
      setApplicationInformation(localInformation);
      setIsSubmitting(false);
      return;
    }
    setApplicationInformation(null);
    try {
      const response = await submitQuestion(token, selectedSessionId, submittedQuestion);
      const [updatedMessages, updatedSessions] = await Promise.all([
        listChatMessages(token, selectedSessionId),
        listChatSessions(token),
      ]);
      setMessages(updatedMessages);
      setSessions(updatedSessions);
      setResponsesByMessageId((currentResponses) => ({
        ...currentResponses,
        [response.assistant_message_id]: response,
      }));
    } catch (requestError) {
      if (isUnauthorized(requestError)) logout();
      else {
        setError(errorMessage(requestError, "Unable to answer that question."));
        void listChatMessages(token, selectedSessionId).then(setMessages).catch(() => undefined);
      }
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <Flex flex="1" minH="0" direction={{ base: "column", lg: "row" }}>
      <Box display={{ base: "none", lg: "block" }}><WorkspaceNavigation activeWorkspace="chat" onSelect={(workspace) => workspace === "documents" && onOpenDocuments()} /></Box>

      <Flex flex="1" minW="0" minH="0" direction={{ base: "column", lg: "row" }}>
        <Box display={{ base: "none", lg: "flex" }} w="16rem" flexShrink="0" px="1.5rem" py="1.5rem" borderRightWidth="1px" borderColor="border" bg="surface" flexDirection="column">
          <Flex justify="space-between" align="center" mb="3"><Box><Text fontWeight="700">Chats</Text><Text color="muted" fontSize="xs">Your conversations</Text></Box><IconButton aria-label="New chat" title="New chat" size="sm" variant="ghost" onClick={createSession}><Plus size={18} /></IconButton></Flex>
          <ChatSessionList sessions={sessions} selectedSessionId={selectedSessionId} isLoading={isLoadingSessions} onSelect={(sessionId) => void selectSession(sessionId)} onRename={(session) => { setRenameError(null); setRenameTitle(session.title); setSessionPendingRename(session); }} onDelete={(session) => { setDeleteError(null); setSessionPendingDeletion(session); }} />
        </Box>

        <Flex as="main" flex="1" minW="0" minH="0" direction="column" px={{ base: "1.25rem", md: "3rem" }} py={{ base: "1.5rem", md: "2rem" }}>
          <Flex display={{ base: "flex", lg: "none" }} flexShrink="0" align="center" gap="3" mb="3" pb="3" borderBottomWidth="1px" borderColor="border"><IconButton aria-label="Open chat sidebar" title="Open chat sidebar" variant="ghost" onClick={() => setIsSidebarOpen(true)}><MenuIcon size={19} /></IconButton><Text minW="0" fontWeight="600" truncate>{selectedSessionId === null ? "Chats" : sessions.find((session) => session.id === selectedSessionId)?.title ?? "Untitled chat"}</Text></Flex>
          <Box display={{ base: "none", lg: "block" }} flexShrink="0" mb="4"><Text color="secondary" fontSize="sm" fontWeight="700" textTransform="uppercase" letterSpacing="0.08em">Conversation</Text><Heading mt="2" fontFamily="heading" fontSize="3xl" fontWeight="500">{selectedSessionId === null ? "Ask your documents" : sessions.find((session) => session.id === selectedSessionId)?.title ?? "Untitled chat"}</Heading></Box>
          {error && <Box id="chat-error" mb="4" px="3" py="2" borderLeftWidth="3px" borderColor="error" bg="surface" role="alert"><Text color="error" fontSize="sm">{error}</Text></Box>}
          {success && <Box mb="4" px="3" py="2" borderLeftWidth="3px" borderColor="success" bg="surface" aria-live="polite"><Text color="success" fontSize="sm">{success}</Text></Box>}
          {selectedSessionId === null ? <Flex flex="1" align="center" justify="center" minH="16rem" direction="column" gap="3" textAlign="center"><Text fontWeight="600">Choose a conversation to begin</Text><Text color="muted" fontSize="sm">Create a chat to ask questions grounded in your uploaded documents.</Text><Button colorPalette="teal" onClick={createSession}><Plus size={18} /> New chat</Button></Flex> : <>
            <VStack flex="1" minH="0" overflowY="auto" align="stretch" justify={messages.length === 0 && !isLoadingMessages ? "center" : "start"} gap="4" pr="1">
              {isLoadingMessages ? <Flex align="center" justify="center" minH="12rem" gap="3" color="muted" role="status"><Spinner size="sm" /> Loading conversation</Flex> : messages.length === 0 ? <ApplicationInformationPanel onChoosePrompt={setQuestion} /> : messages.map((message) => <Message key={message.id} message={message} response={responsesByMessageId[message.id]} />)}
              {applicationInformation && <ApplicationInformationExchange information={applicationInformation} />}
              {isSubmitting && <Flex align="center" gap="3" color="muted" role="status"><Spinner size="sm" /> Finding an answer in your documents</Flex>}
            </VStack>
            <Box asChild mt="6"><form onSubmit={sendQuestion}><Flex direction={{ base: "column", sm: "row" }} gap="3"><Textarea aria-label="Question" aria-describedby={error ? "chat-error" : undefined} aria-invalid={Boolean(error)} value={question} onChange={(event) => setQuestion(event.target.value)} placeholder="Ask a question about your documents" disabled={isSubmitting} resize="vertical" minH="5rem" /><Button type="submit" alignSelf={{ base: "stretch", sm: "end" }} colorPalette="teal" loading={isSubmitting} disabled={isSubmitting || !question.trim()}><Send size={18} /> Send</Button></Flex></form></Box>
          </>}
        </Flex>
      </Flex>
      <DeleteChatDialog session={sessionPendingDeletion} isDeleting={isDeletingSession} error={deleteError} onClose={() => setSessionPendingDeletion(null)} onConfirm={() => void confirmDeleteSession()} />
      <RenameChatDialog session={sessionPendingRename} title={renameTitle} error={renameError} isSaving={isRenamingSession} onChange={setRenameTitle} onClose={() => setSessionPendingRename(null)} onSave={() => void confirmRenameSession()} />
      <MobileChatSidebar open={isSidebarOpen} onClose={() => setIsSidebarOpen(false)} onOpenDocuments={onOpenDocuments} sessions={sessions} selectedSessionId={selectedSessionId} isLoadingSessions={isLoadingSessions} onCreateSession={() => { void createSession(); setIsSidebarOpen(false); }} onSelectSession={(sessionId) => void selectSession(sessionId)} onRename={(session) => { setRenameError(null); setRenameTitle(session.title); setSessionPendingRename(session); }} onDelete={(session) => { setDeleteError(null); setSessionPendingDeletion(session); }} />
    </Flex>
  );
}