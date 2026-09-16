import { useEffect, useState } from "react";
import {
  BookOpen,
  Copy,
  FileText,
  Lightbulb,
  Mic,
  Paperclip,
  Plus,
  Send,
  Sparkles,
  ThumbsDown,
  ThumbsUp,
} from "lucide-react";

import AppShell from "../../components/layout/AppShell.jsx";
import { useAuth } from "../../contexts/AuthContext.jsx";

import {
  createChat,
  getChats,
  getChatMessages,
  sendChatMessage,
} from "../../services/chatService.js";

import "./companion.css";

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
  const { accessToken } = useAuth();

  const [message, setMessage] = useState("");

  const [conversations, setConversations] = useState([]);
  const [selectedChatId, setSelectedChatId] = useState(null);

  const [messages, setMessages] = useState([]);

  const [isLoadingChats, setIsLoadingChats] = useState(false);
  const [isLoadingMessages, setIsLoadingMessages] =
    useState(false);

  const [isCreatingChat, setIsCreatingChat] = useState(false);
  const [isSending, setIsSending] = useState(false);

  const [error, setError] = useState("");

  /*
   * Load the authenticated user's chats.
   */
  useEffect(() => {
    if (!accessToken) {
      return;
    }

    async function loadChats() {
      try {
        setIsLoadingChats(true);
        setError("");

        const result = await getChats(accessToken);

        const chatItems = result?.items ?? [];

        setConversations(chatItems);

        if (chatItems.length > 0) {
          setSelectedChatId(chatItems[0].id);
        }
      } catch (err) {
        console.error("Unable to load chats:", err.code);

        setError(
          "Chats are currently unavailable. The backend chat service may not be running yet.",
        );
      } finally {
        setIsLoadingChats(false);
      }
    }

    loadChats();
  }, [accessToken]);

  /*
   * Load messages whenever the selected chat changes.
   */
  useEffect(() => {
    if (!accessToken || !selectedChatId) {
      setMessages([]);
      return;
    }

    async function loadMessages() {
      try {
        setIsLoadingMessages(true);
        setError("");

        const result = await getChatMessages(
          accessToken,
          selectedChatId,
        );

        setMessages(result?.items ?? []);
      } catch (err) {
        console.error(
          "Unable to load chat messages:",
          err.code,
        );

        setError("Unable to load this conversation.");
      } finally {
        setIsLoadingMessages(false);
      }
    }

    loadMessages();
  }, [accessToken, selectedChatId]);

  /*
   * Create a real chat through the backend.
   */
  async function handleNewConversation() {
    if (!accessToken || isCreatingChat) {
      return;
    }

    try {
      setIsCreatingChat(true);
      setError("");

      const newChat = await createChat(accessToken);

      setConversations((current) => [
        newChat,
        ...current,
      ]);

      setSelectedChatId(newChat.id);
      setMessages([]);
      setMessage("");
    } catch (err) {
      console.error("Unable to create chat:", err.code);

      setError(
        "Unable to create a conversation. The chat backend endpoint may not be available yet.",
      );
    } finally {
      setIsCreatingChat(false);
    }
  }

  /*
   * Open an existing conversation.
   */
  function handleSelectConversation(chatId) {
    setSelectedChatId(chatId);
    setMessage("");
    setError("");
  }

  /*
   * Send a message to the real backend.
   */
  async function handleSubmit(event) {
    event.preventDefault();

    const content = message.trim();

    if (!content || isSending || !accessToken) {
      return;
    }

    try {
      setIsSending(true);
      setError("");

      let chatId = selectedChatId;

      /*
       * If the user has no chat yet, automatically
       * create one before sending the first question.
       */
      if (!chatId) {
        const newChat = await createChat(accessToken);

        setConversations((current) => [
          newChat,
          ...current,
        ]);

        setSelectedChatId(newChat.id);

        chatId = newChat.id;
      }

      const result = await sendChatMessage(
        accessToken,
        chatId,
        content,
      );

      /*
       * Backend immediately returns the user's message.
       * The AI response will later arrive through WebSocket.
       */
      if (result?.message) {
        setMessages((current) => [
          ...current,
          result.message,
        ]);
      }

      setMessage("");
    } catch (err) {
      console.error("Unable to send message:", err.code);

      if (err.code === "NO_PROCESSED_NOTES") {
        setError(
          "Upload and process at least one note before asking the AI a question.",
        );
      } else if (err.code === "RATE_LIMIT_EXCEEDED") {
        setError(
          "Too many requests. Please wait and try again.",
        );
      } else if (err.code === "CHAT_NOT_FOUND") {
        setError(
          "This conversation could not be found.",
        );
      } else if (err.code === "VALIDATION_ERROR") {
        setError(
          "Please check your message and try again.",
        );
      } else {
        setError(
          "Unable to send your message. The chat backend may not be available yet.",
        );
      }
    } finally {
      setIsSending(false);
    }
  }

  function handleSuggestedPrompt(prompt) {
    setMessage(prompt);
  }

  function formatMessageTime(createdAt) {
    if (!createdAt) {
      return "";
    }

    const date = new Date(createdAt);

    return date.toLocaleTimeString([], {
      hour: "2-digit",
      minute: "2-digit",
    });
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
              onClick={handleNewConversation}
              disabled={isCreatingChat}
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
                conversations.length === 0 && (
                  <p className="conversation-status">
                    No conversations yet
                  </p>
                )}

              {conversations.map((conversation) => (
                <button
                  key={conversation.id}
                  type="button"
                  className={`conversation-item ${
                    selectedChatId === conversation.id
                      ? "active"
                      : ""
                  }`}
                  onClick={() =>
                    handleSelectConversation(
                      conversation.id,
                    )
                  }
                >
                  {conversation.title || "New chat"}
                </button>
              ))}
            </div>
          </div>
        </aside>

        {/* Main chat */}

        <section className="chat-section">

          <header className="chat-header">
            <div className="chat-header-icon">
              <Sparkles size={20} />
            </div>

            <div>
              <h1>AI Study Assistant</h1>

              <p>
                Ask questions about your uploaded study
                materials
              </p>
            </div>
          </header>

          <div className="chat-content">

            {/* Welcome message */}

            {messages.length === 0 &&
              !isLoadingMessages && (
                <>
                  <div className="assistant-message-row">
                    <div className="assistant-avatar">
                      <Sparkles size={20} />
                    </div>

                    <div>
                      <div className="assistant-message">
                        <p>
                          Hi! I&apos;m your AI study
                          assistant.
                        </p>

                        <p>
                          I can help you understand your
                          uploaded lecture notes and study
                          materials.
                        </p>

                        <p>
                          What would you like to study today?
                        </p>
                      </div>
                    </div>
                  </div>

                  <div className="suggested-prompts">
                    <p>Try a suggested prompt:</p>

                    {suggestedPrompts.map(
                      ({ icon: Icon, text }) => (
                        <button
                          type="button"
                          className="suggested-prompt"
                          key={text}
                          onClick={() =>
                            handleSuggestedPrompt(text)
                          }
                        >
                          <span>
                            <Icon size={18} />
                          </span>

                          {text}
                        </button>
                      ),
                    )}
                  </div>
                </>
              )}

            {/* Loading */}

            {isLoadingMessages && (
              <div className="chat-loading">
                Loading messages...
              </div>
            )}

            {/* Real messages */}

            {!isLoadingMessages &&
              messages.map((chatMessage) => {
                const isUser =
                  chatMessage.role === "user";

                return (
                  <div
                    key={chatMessage.id}
                    className={
                      isUser
                        ? "user-message-row"
                        : "assistant-message-row"
                    }
                  >
                    {!isUser && (
                      <div className="assistant-avatar">
                        <Sparkles size={20} />
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
                        <p>{chatMessage.content}</p>

                        {chatMessage.sources?.length >
                          0 && (
                          <div className="message-sources">
                            <strong>Sources</strong>

                            {chatMessage.sources.map(
                              (source) => (
                                <span
                                  key={
                                    source.chunk_id
                                  }
                                >
                                  {source.note_title}

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
                              <Copy size={13} />
                            </button>

                            <button
                              type="button"
                              aria-label="Like message"
                            >
                              <ThumbsUp size={13} />
                            </button>

                            <button
                              type="button"
                              aria-label="Dislike message"
                            >
                              <ThumbsDown size={13} />
                            </button>
                          </>
                        )}
                      </div>
                    </div>
                  </div>
                );
              })}
          </div>

          {/* Input */}

          <div className="chat-input-area">

            {error && (
              <div className="chat-error">
                {error}
              </div>
            )}

            <form
              className="chat-input-form"
              onSubmit={handleSubmit}
            >
              <div className="chat-input-box">
                <input
                  type="text"
                  value={message}
                  onChange={(event) =>
                    setMessage(event.target.value)
                  }
                  placeholder="Ask a question about your study materials..."
                  disabled={isSending}
                />

                <button
                  type="button"
                  className="chat-tool-button"
                  aria-label="Attach file"
                >
                  <Paperclip size={18} />
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
                  isSending || !message.trim()
                }
              >
                <Send size={20} />
              </button>
            </form>

            <p className="chat-disclaimer">
              AI can make mistakes. Always verify important
              information with your course materials.
            </p>
          </div>
        </section>
      </div>
    </AppShell>
  );
}

export default CompanionPage;