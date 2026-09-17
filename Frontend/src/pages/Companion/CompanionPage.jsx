import {
  useEffect,
  useState,
} from "react";

import {
  BookOpen,
  Check,
  Copy,
  FileText,
  Lightbulb,
  Mic,
  Paperclip,
  Pencil,
  Plus,
  Send,
  Sparkles,
  ThumbsDown,
  ThumbsUp,
  Trash2,
  X,
} from "lucide-react";

import AppShell from "../../components/layout/AppShell.jsx";
import { useAuth } from "../../contexts/AuthContext.jsx";

import {
  createChat,
  deleteChat,
  getChatMessages,
  getChats,
  renameChat,
  sendChatMessage,
} from "../../services/chatService.js";

import "./companion.css";

/*
 * Errors that mean the authentication session
 * is no longer valid.
 */
const AUTH_ERROR_CODES = new Set([
  "AUTHENTICATION_REQUIRED",
  "TOKEN_INVALID",
  "TOKEN_EXPIRED",
  "TOKEN_REVOKED",
]);

const suggestedPrompts = [
  {
    icon: BookOpen,
    text: "Explain backpropagation in simple terms",
  },
  {
    icon: FileText,
    text: "Summarise my Machine Learning lecture notes",
  },
  {
    icon: Lightbulb,
    text: "Create 5 practice questions for my Physics exam",
  },
];

function CompanionPage() {
  const {
    accessToken,
    logout,
  } = useAuth();

  const [message, setMessage] =
    useState("");

  const [
    conversations,
    setConversations,
  ] = useState([]);

  const [
    selectedChatId,
    setSelectedChatId,
  ] = useState(null);

  const [messages, setMessages] =
    useState([]);

  const [
    isLoadingChats,
    setIsLoadingChats,
  ] = useState(false);

  const [
    isLoadingMessages,
    setIsLoadingMessages,
  ] = useState(false);

  const [
    isCreatingChat,
    setIsCreatingChat,
  ] = useState(false);

  const [
    isSending,
    setIsSending,
  ] = useState(false);

  /*
   * Rename state.
   */
  const [
    editingChatId,
    setEditingChatId,
  ] = useState(null);

  const [
    editingTitle,
    setEditingTitle,
  ] = useState("");

  const [
    renamingChatId,
    setRenamingChatId,
  ] = useState(null);

  /*
   * Delete state.
   */
  const [
    deletingChatId,
    setDeletingChatId,
  ] = useState(null);

  const [error, setError] =
    useState("");

  /*
   * Clear an invalid session.
   *
   * ProtectedRoute will take care of returning
   * the user to the authentication flow.
   */
  async function clearInvalidSession() {
    try {
      await logout();
    } catch {
      /*
       * AuthContext clears local authentication
       * state in its finally block.
       */
    }
  }

  /*
   * Load all chats owned by the current student.
   */
  useEffect(() => {
    if (!accessToken) {
      return;
    }

    let cancelled = false;

    async function loadChats() {
      try {
        setIsLoadingChats(true);
        setError("");

        const result =
          await getChats(accessToken);

        if (cancelled) {
          return;
        }

        const chatItems =
          result?.items ?? [];

        setConversations(chatItems);

        /*
         * Keep the currently selected chat if
         * it still exists.
         *
         * Otherwise open the first available chat.
         */
        setSelectedChatId(
          (currentChatId) => {
            const stillExists =
              chatItems.some(
                (chat) =>
                  chat.id ===
                  currentChatId,
              );

            if (stillExists) {
              return currentChatId;
            }

            return (
              chatItems[0]?.id ??
              null
            );
          },
        );
      } catch (err) {
        if (cancelled) {
          return;
        }

        console.error(
          "Unable to load chats:",
          err.code,
        );

        if (
          AUTH_ERROR_CODES.has(
            err.code,
          )
        ) {
          await clearInvalidSession();
          return;
        }

        setError(
          "Chats are currently unavailable. Please try again.",
        );
      } finally {
        if (!cancelled) {
          setIsLoadingChats(false);
        }
      }
    }

    void loadChats();

    return () => {
      cancelled = true;
    };
  }, [accessToken]);

  /*
   * Load messages whenever another conversation
   * is selected from the sidebar.
   */
  useEffect(() => {
    if (
      !accessToken ||
      !selectedChatId
    ) {
      setMessages([]);
      return;
    }

    let cancelled = false;

    async function loadMessages() {
      try {
        setIsLoadingMessages(true);
        setError("");

        const result =
          await getChatMessages(
            accessToken,
            selectedChatId,
          );

        if (cancelled) {
          return;
        }

        setMessages(
          result?.items ?? [],
        );
      } catch (err) {
        if (cancelled) {
          return;
        }

        console.error(
          "Unable to load chat messages:",
          err.code,
        );

        if (
          AUTH_ERROR_CODES.has(
            err.code,
          )
        ) {
          await clearInvalidSession();
          return;
        }

        /*
         * CHAT_NOT_FOUND can happen if the chat
         * was removed somewhere else.
         *
         * Remove stale UI state without making
         * assumptions about who owned the chat.
         */
        if (
          err.code ===
          "CHAT_NOT_FOUND"
        ) {
          setConversations(
            (current) =>
              current.filter(
                (chat) =>
                  chat.id !==
                  selectedChatId,
              ),
          );

          setSelectedChatId(null);
          setMessages([]);

          setError(
            "This conversation is no longer available.",
          );

          return;
        }

        setError(
          "Unable to load this conversation.",
        );
      } finally {
        if (!cancelled) {
          setIsLoadingMessages(
            false,
          );
        }
      }
    }

    void loadMessages();

    return () => {
      cancelled = true;
    };
  }, [
    accessToken,
    selectedChatId,
  ]);

  /*
   * Create a new backend conversation.
   */
  async function handleNewConversation() {
    if (
      !accessToken ||
      isCreatingChat
    ) {
      return;
    }

    try {
      setIsCreatingChat(true);
      setError("");

      const newChat =
        await createChat(
          accessToken,
        );

      setConversations(
        (current) => [
          newChat,
          ...current,
        ],
      );

      setSelectedChatId(
        newChat.id,
      );

      setMessages([]);
      setMessage("");

      /*
       * Close any active rename editor.
       */
      setEditingChatId(null);
      setEditingTitle("");
    } catch (err) {
      console.error(
        "Unable to create chat:",
        err.code,
      );

      if (
        AUTH_ERROR_CODES.has(
          err.code,
        )
      ) {
        await clearInvalidSession();
        return;
      }

      setError(
        "Unable to create a conversation. Please try again.",
      );
    } finally {
      setIsCreatingChat(false);
    }
  }

  /*
   * Open an existing conversation.
   */
  function handleSelectConversation(
    chatId,
  ) {
    setSelectedChatId(chatId);

    setMessage("");
    setError("");
  }

  /*
   * Begin editing a chat title.
   */
  function startRename(
    conversation,
  ) {
    setEditingChatId(
      conversation.id,
    );

    setEditingTitle(
      conversation.title ||
        "New chat",
    );

    setError("");
  }

  /*
   * Cancel the rename without changing
   * anything in the backend.
   */
  function cancelRename() {
    setEditingChatId(null);
    setEditingTitle("");
  }

  /*
   * Save the new title using:
   *
   * PATCH /api/v1/chats/{chat_id}
   */
  async function handleRenameChat(
    event,
    chatId,
  ) {
    event.preventDefault();

    const newTitle =
      editingTitle.trim();

    if (
      !newTitle ||
      !accessToken ||
      renamingChatId
    ) {
      return;
    }

    try {
      setRenamingChatId(chatId);
      setError("");

      const updatedChat =
        await renameChat(
          accessToken,
          chatId,
          newTitle,
        );

      /*
       * Update the sidebar immediately after
       * the backend confirms the rename.
       */
      setConversations(
        (current) =>
          current.map((chat) =>
            chat.id === chatId
              ? {
                  ...chat,
                  ...updatedChat,
                  title:
                    updatedChat
                      ?.title ||
                    newTitle,
                }
              : chat,
          ),
      );

      setEditingChatId(null);
      setEditingTitle("");
    } catch (err) {
      console.error(
        "Unable to rename chat:",
        err.code,
      );

      if (
        AUTH_ERROR_CODES.has(
          err.code,
        )
      ) {
        await clearInvalidSession();
        return;
      }

      if (
        err.code ===
        "CHAT_NOT_FOUND"
      ) {
        setConversations(
          (current) =>
            current.filter(
              (chat) =>
                chat.id !==
                chatId,
            ),
        );

        setEditingChatId(null);

        setError(
          "This conversation is no longer available.",
        );

        return;
      }

      setError(
        "Unable to rename this conversation.",
      );
    } finally {
      setRenamingChatId(null);
    }
  }

  /*
   * Delete a chat using:
   *
   * DELETE /api/v1/chats/{chat_id}
   *
   * The user must confirm before anything
   * is removed.
   */
  async function handleDeleteChat(
    conversation,
  ) {
    const confirmed =
      window.confirm(
        `Delete "${conversation.title || "New chat"}"? This cannot be undone.`,
      );

    if (
      !confirmed ||
      !accessToken
    ) {
      return;
    }

    try {
      setDeletingChatId(
        conversation.id,
      );

      setError("");

      await deleteChat(
        accessToken,
        conversation.id,
      );

      /*
       * Determine which chats remain after
       * this one is removed.
       */
      const remainingChats =
        conversations.filter(
          (chat) =>
            chat.id !==
            conversation.id,
        );

      setConversations(
        remainingChats,
      );

      /*
       * If the deleted chat was currently open,
       * automatically open another conversation.
       *
       * If none remain, return to the empty
       * AI Assistant welcome screen.
       */
      if (
        selectedChatId ===
        conversation.id
      ) {
        const nextChatId =
          remainingChats[0]
            ?.id ?? null;

        setSelectedChatId(
          nextChatId,
        );

        if (!nextChatId) {
          setMessages([]);
        }
      }

      if (
        editingChatId ===
        conversation.id
      ) {
        cancelRename();
      }
    } catch (err) {
      console.error(
        "Unable to delete chat:",
        err.code,
      );

      if (
        AUTH_ERROR_CODES.has(
          err.code,
        )
      ) {
        await clearInvalidSession();
        return;
      }

      if (
        err.code ===
        "CHAT_NOT_FOUND"
      ) {
        const remainingChats =
          conversations.filter(
            (chat) =>
              chat.id !==
              conversation.id,
          );

        setConversations(
          remainingChats,
        );

        if (
          selectedChatId ===
          conversation.id
        ) {
          setSelectedChatId(
            remainingChats[0]
              ?.id ?? null,
          );

          setMessages([]);
        }

        return;
      }

      setError(
        "Unable to delete this conversation.",
      );
    } finally {
      setDeletingChatId(null);
    }
  }

  /*
   * Send a message to the real backend.
   */
  async function handleSubmit(
    event,
  ) {
    event.preventDefault();

    const content =
      message.trim();

    if (
      !content ||
      isSending ||
      !accessToken
    ) {
      return;
    }

    try {
      setIsSending(true);
      setError("");

      let chatId =
        selectedChatId;

      /*
       * Automatically create a conversation
       * if the student sends a question while
       * no chat exists yet.
       */
      if (!chatId) {
        const newChat =
          await createChat(
            accessToken,
          );

        setConversations(
          (current) => [
            newChat,
            ...current,
          ],
        );

        setSelectedChatId(
          newChat.id,
        );

        chatId =
          newChat.id;
      }

      const result =
        await sendChatMessage(
          accessToken,
          chatId,
          content,
        );

      /*
       * The backend currently returns both:
       *
       * - the student's message
       * - the completed AI response
       */
      if (
        result?.user_message &&
        result?.assistant_message
      ) {
        setMessages(
          (current) => [
            ...current,
            result.user_message,
            result.assistant_message,
          ],
        );
      }

      setMessage("");
    } catch (err) {
      console.error(
        "Unable to send message:",
        err.code,
      );

      if (
        AUTH_ERROR_CODES.has(
          err.code,
        )
      ) {
        await clearInvalidSession();
        return;
      }

      if (
        err.code ===
        "NO_PROCESSED_NOTES"
      ) {
        setError(
          "Upload and process at least one note before asking the AI a question.",
        );
      } else if (
        err.code ===
        "RATE_LIMIT_EXCEEDED"
      ) {
        setError(
          "Too many requests. Please wait and try again.",
        );
      } else if (
        err.code ===
        "CHAT_NOT_FOUND"
      ) {
        setConversations(
          (current) =>
            current.filter(
              (chat) =>
                chat.id !==
                selectedChatId,
            ),
        );

        setSelectedChatId(null);
        setMessages([]);

        setError(
          "This conversation could not be found.",
        );
      } else if (
        err.code ===
        "VALIDATION_ERROR"
      ) {
        setError(
          "Please check your message and try again.",
        );
      } else if (
        err.code ===
        "ANSWER_GENERATION_FAILED"
      ) {
        setError(
          "The AI could not generate an answer. Please try again.",
        );
      } else {
        setError(
          "Unable to send your message. Please try again.",
        );
      }
    } finally {
      setIsSending(false);
    }
  }

  function handleSuggestedPrompt(
    prompt,
  ) {
    setMessage(prompt);
  }

  /*
   * Format message time for the chat UI.
   */
  function formatMessageTime(
    createdAt,
  ) {
    if (!createdAt) {
      return "";
    }

    const date =
      new Date(createdAt);

    return date.toLocaleTimeString(
      [],
      {
        hour: "2-digit",
        minute: "2-digit",
      },
    );
  }

  return (
    <AppShell>
      <div className="companion-layout">

        {/* Conversation sidebar */}

        <aside className="conversation-sidebar">
          <div className="conversation-new-wrapper">
            <button
              type="button"
              className="new-conversation-button"
              onClick={
                handleNewConversation
              }
              disabled={
                isCreatingChat
              }
            >
              <Plus size={18} />

              {isCreatingChat
                ? "Creating..."
                : "New Conversation"}
            </button>
          </div>

          <div className="conversation-list">
            <div className="conversation-section">
              <p className="conversation-group-title">
                CONVERSATIONS
              </p>

              {isLoadingChats && (
                <p className="conversation-status">
                  Loading conversations...
                </p>
              )}

              {!isLoadingChats &&
                conversations.length ===
                  0 && (
                  <p className="conversation-status">
                    No conversations yet
                  </p>
                )}

              {conversations.map(
                (conversation) => {
                  const isEditing =
                    editingChatId ===
                    conversation.id;

                  const isSelected =
                    selectedChatId ===
                    conversation.id;

                  return (
                    <div
                      key={
                        conversation.id
                      }
                      className={`conversation-row ${
                        isSelected
                          ? "active"
                          : ""
                      }`}
                    >
                      {isEditing ? (
                        /*
                         * Inline rename form.
                         */
                        <form
                          className="conversation-rename-form"
                          onSubmit={(
                            event,
                          ) =>
                            handleRenameChat(
                              event,
                              conversation.id,
                            )
                          }
                        >
                          <input
                            type="text"
                            value={
                              editingTitle
                            }
                            onChange={(
                              event,
                            ) =>
                              setEditingTitle(
                                event.target
                                  .value,
                              )
                            }
                            autoFocus
                            aria-label="Conversation title"
                          />

                          <button
                            type="submit"
                            className="conversation-action-button"
                            title="Save name"
                            aria-label="Save conversation name"
                            disabled={
                              renamingChatId ===
                                conversation.id ||
                              !editingTitle.trim()
                            }
                          >
                            <Check
                              size={
                                14
                              }
                            />
                          </button>

                          <button
                            type="button"
                            className="conversation-action-button"
                            onClick={
                              cancelRename
                            }
                            title="Cancel rename"
                            aria-label="Cancel rename"
                          >
                            <X
                              size={
                                14
                              }
                            />
                          </button>
                        </form>
                      ) : (
                        <>
                          <button
                            type="button"
                            className="conversation-title-button"
                            onClick={() =>
                              handleSelectConversation(
                                conversation.id,
                              )
                            }
                          >
                            {conversation.title ||
                              "New chat"}
                          </button>

                          <div className="conversation-actions">
                            <button
                              type="button"
                              className="conversation-action-button"
                              onClick={() =>
                                startRename(
                                  conversation,
                                )
                              }
                              title="Rename conversation"
                              aria-label={`Rename ${conversation.title || "conversation"}`}
                            >
                              <Pencil
                                size={
                                  14
                                }
                              />
                            </button>

                            <button
                              type="button"
                              className="conversation-action-button conversation-delete-button"
                              onClick={() =>
                                handleDeleteChat(
                                  conversation,
                                )
                              }
                              disabled={
                                deletingChatId ===
                                conversation.id
                              }
                              title="Delete conversation"
                              aria-label={`Delete ${conversation.title || "conversation"}`}
                            >
                              <Trash2
                                size={
                                  14
                                }
                              />
                            </button>
                          </div>
                        </>
                      )}
                    </div>
                  );
                },
              )}
            </div>
          </div>
        </aside>

        {/* Main AI chat */}

        <section className="chat-section">
          <header className="chat-header">
            <div className="chat-header-icon">
              <Sparkles
                size={20}
              />
            </div>

            <div>
              <h1>
                AI Study Assistant
              </h1>

              <p>
                Ask questions about
                your uploaded study
                materials
              </p>
            </div>
          </header>

          <div className="chat-content">

            {/* Empty/welcome state */}

            {messages.length ===
                0 &&
              !isLoadingMessages && (
                <>
                  <div className="assistant-message-row">
                    <div className="assistant-avatar">
                      <Sparkles
                        size={20}
                      />
                    </div>

                    <div>
                      <div className="assistant-message">
                        <p>
                          Hi! I&apos;m
                          your AI study
                          assistant.
                        </p>

                        <p>
                          I can help you
                          understand your
                          uploaded lecture
                          notes and study
                          materials.
                        </p>

                        <p>
                          What would you
                          like to study
                          today?
                        </p>
                      </div>
                    </div>
                  </div>

                  <div className="suggested-prompts">
                    <p>
                      Try a suggested
                      prompt:
                    </p>

                    {suggestedPrompts.map(
                      ({
                        icon: Icon,
                        text,
                      }) => (
                        <button
                          type="button"
                          className="suggested-prompt"
                          key={text}
                          onClick={() =>
                            handleSuggestedPrompt(
                              text,
                            )
                          }
                        >
                          <span>
                            <Icon
                              size={
                                18
                              }
                            />
                          </span>

                          {text}
                        </button>
                      ),
                    )}
                  </div>
                </>
              )}

            {/* Message loading state */}

            {isLoadingMessages && (
              <div className="chat-loading">
                Loading messages...
              </div>
            )}

            {/* Real chat messages */}

            {!isLoadingMessages &&
              messages.map(
                (chatMessage) => {
                  const isUser =
                    chatMessage.role ===
                    "user";

                  return (
                    <div
                      key={
                        chatMessage.id
                      }
                      className={
                        isUser
                          ? "user-message-row"
                          : "assistant-message-row"
                      }
                    >
                      {!isUser && (
                        <div className="assistant-avatar">
                          <Sparkles
                            size={
                              20
                            }
                          />
                        </div>
                      )}

                      <div>
                        <div
                          className={
                            isUser
                              ? "user-message"
                              : "assistant-message"
                          }
                        >
                          <p>
                            {
                              chatMessage.content
                            }
                          </p>

                          {chatMessage
                            .sources
                            ?.length >
                            0 && (
                            <div className="message-sources">
                              <strong>
                                Sources
                              </strong>

                              {chatMessage.sources.map(
                                (
                                  source,
                                ) => (
                                  <span
                                    key={
                                      source.chunk_id
                                    }
                                  >
                                    {
                                      source.note_title
                                    }

                                    {source.page
                                      ? ` — page ${source.page}`
                                      : ""}
                                  </span>
                                ),
                              )}
                            </div>
                          )}
                        </div>

                        <div className="message-meta">
                          <span>
                            {formatMessageTime(
                              chatMessage.created_at,
                            )}
                          </span>

                          {!isUser && (
                            <>
                              <button
                                type="button"
                                aria-label="Copy message"
                                onClick={() =>
                                  navigator.clipboard.writeText(
                                    chatMessage.content,
                                  )
                                }
                              >
                                <Copy
                                  size={
                                    13
                                  }
                                />
                              </button>

                              <button
                                type="button"
                                aria-label="Like message"
                              >
                                <ThumbsUp
                                  size={
                                    13
                                  }
                                />
                              </button>

                              <button
                                type="button"
                                aria-label="Dislike message"
                              >
                                <ThumbsDown
                                  size={
                                    13
                                  }
                                />
                              </button>
                            </>
                          )}
                        </div>
                      </div>
                    </div>
                  );
                },
              )}
          </div>

          {/* Chat input */}

          <div className="chat-input-area">
            {error && (
              <div className="chat-error">
                {error}
              </div>
            )}

            <form
              className="chat-input-form"
              onSubmit={
                handleSubmit
              }
            >
              <div className="chat-input-box">
                <input
                  type="text"
                  value={message}
                  onChange={(
                    event,
                  ) =>
                    setMessage(
                      event.target
                        .value,
                    )
                  }
                  placeholder="Ask a question about your study materials..."
                  disabled={
                    isSending
                  }
                />

                <button
                  type="button"
                  className="chat-tool-button"
                  aria-label="Attach file"
                >
                  <Paperclip
                    size={18}
                  />
                </button>

                <button
                  type="button"
                  className="chat-tool-button"
                  aria-label="Voice input"
                >
                  <Mic size={18} />
                </button>
              </div>

              <button
                type="submit"
                className="chat-send-button"
                aria-label="Send message"
                disabled={
                  isSending ||
                  !message.trim()
                }
              >
                <Send size={20} />
              </button>
            </form>

            <p className="chat-disclaimer">
              AI can make mistakes.
              Always verify important
              information with your
              course materials.
            </p>
          </div>
        </section>
      </div>
    </AppShell>
  );
}

export default CompanionPage;