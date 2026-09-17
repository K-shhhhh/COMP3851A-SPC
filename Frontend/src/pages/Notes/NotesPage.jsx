import {
  useEffect,
  useRef,
  useState,
} from "react";

import {
  AlertCircle,
  Eye,
  FileText,
  LoaderCircle,
  Trash2,
  X,
} from "lucide-react";

import AppShell from "../../components/layout/AppShell.jsx";
import { useAuth } from "../../contexts/AuthContext.jsx";

import {
  deleteNote,
  getNote,
  getNotes,
  getNoteStatus,
} from "../../services/noteService.js";

import "./notes.css";

/*
 * Notes with these statuses are still being processed.
 * We keep polling them until the backend returns "ready" or "failed".
 */
const ACTIVE_STATUSES = new Set([
  "queued",
  "processing",
]);

/*
 * Any of these errors means the current login session
 * is no longer valid.
 */
const AUTH_ERROR_CODES = new Set([
  "AUTHENTICATION_REQUIRED",
  "TOKEN_INVALID",
  "TOKEN_EXPIRED",
  "TOKEN_REVOKED",
]);

function NotesPage() {
  const {
    accessToken,
    logout,
  } = useAuth();

  const [notes, setNotes] = useState([]);

  const [isLoading, setIsLoading] = useState(true);

  /*
   * General page-level error.
   */
  const [error, setError] = useState("");

  /*
   * Errors caused by actions such as deleting or opening a note.
   */
  const [actionError, setActionError] = useState("");

  /*
   * Tracks which note is currently being deleted.
   * This lets us disable only that note's delete button.
   */
  const [deletingNoteId, setDeletingNoteId] = useState(null);

  /*
   * Tracks which note is currently loading its full details.
   */
  const [loadingDetailsId, setLoadingDetailsId] = useState(null);

  /*
   * Full metadata returned by GET /notes/{note_id}.
   */
  const [selectedNote, setSelectedNote] = useState(null);

  /*
   * Store one polling timer per note.
   *
   * A Map prevents us from accidentally starting multiple
   * timers for the same note.
   */
  const pollingTimersRef = useRef(new Map());

  /*
   * Clear a single note's polling timer.
   */
  function stopPolling(noteId) {
    const timerId =
      pollingTimersRef.current.get(noteId);

    if (timerId) {
      window.clearTimeout(timerId);
    }

    pollingTimersRef.current.delete(noteId);
  }

  /*
   * Clear every active polling timer.
   *
   * Used when leaving the page or when authentication expires.
   */
  function stopAllPolling() {
    pollingTimersRef.current.forEach(
      (timerId) => {
        window.clearTimeout(timerId);
      },
    );

    pollingTimersRef.current.clear();
  }

  /*
   * Update one note in the Notes list.
   *
   * If the same note is currently open in the details modal,
   * update that copy too so both parts of the UI stay in sync.
   */
  function updateNote(noteId, updates) {
    setNotes((currentNotes) =>
      currentNotes.map((note) =>
        note.id === noteId
          ? {
              ...note,
              ...updates,
            }
          : note,
      ),
    );

    setSelectedNote((currentNote) => {
      if (!currentNote) {
        return currentNote;
      }

      if (currentNote.id !== noteId) {
        return currentNote;
      }

      return {
        ...currentNote,
        ...updates,
      };
    });
  }

  /*
   * Remove a note from local UI state.
   *
   * This is used after a successful DELETE and when the backend
   * reports NOTE_NOT_FOUND for stale data.
   */
  function removeNoteFromUi(noteId) {
    stopPolling(noteId);

    setNotes((currentNotes) =>
      currentNotes.filter(
        (note) => note.id !== noteId,
      ),
    );

    setSelectedNote((currentNote) =>
      currentNote?.id === noteId
        ? null
        : currentNote,
    );
  }

  /*
   * Clear the local login session when the backend tells us
   * the access token is no longer valid.
   *
   * logout() clears sessionStorage even if its backend request fails.
   */
  async function clearInvalidSession() {
    stopAllPolling();

    try {
      await logout();
    } catch {
      /*
       * AuthContext clears local auth state in its finally block,
       * so there is nothing else we need to do here.
       */
    }
  }

  /*
   * Schedule the next processing-status request.
   *
   * setTimeout is used instead of setInterval so a slow request
   * cannot overlap with another request for the same note.
   */
  function schedulePolling(noteId) {
    if (!accessToken) {
      return;
    }

    /*
     * Never create two timers for one note.
     */
    if (
      pollingTimersRef.current.has(noteId)
    ) {
      return;
    }

    const timerId = window.setTimeout(
      () => {
        /*
         * This timer has fired, so remove it before
         * making the request.
         */
        pollingTimersRef.current.delete(
          noteId,
        );

        void pollNoteStatus(noteId);
      },
      2500,
    );

    pollingTimersRef.current.set(
      noteId,
      timerId,
    );
  }

  /*
   * Ask the backend for the latest processing state.
   *
   * Important:
   * - list response uses processing_progress
   * - status response uses progress
   *
   * We explicitly map progress -> processing_progress here.
   */
  async function pollNoteStatus(noteId) {
    if (!accessToken) {
      return;
    }

    try {
      const result =
        await getNoteStatus(
          accessToken,
          noteId,
        );

      const updates = {
        status: result.status,
        processing_progress:
          result.progress,
        processing_message:
          result.message,
        processing_error:
          result.error,
        updated_at:
          result.updated_at,
      };

      updateNote(noteId, updates);

      /*
       * Continue polling only while processing is active.
       */
      if (
        ACTIVE_STATUSES.has(
          result.status,
        )
      ) {
        schedulePolling(noteId);
      }
    } catch (err) {
      /*
       * Authentication errors mean the session must be cleared.
       */
      if (
        AUTH_ERROR_CODES.has(err.code)
      ) {
        await clearInvalidSession();
        return;
      }

      /*
       * NOTE_NOT_FOUND can happen when this page has stale data.
       * Remove it from the UI without making assumptions about ownership.
       */
      if (err.code === "NOTE_NOT_FOUND") {
        removeNoteFromUi(noteId);
        return;
      }

      /*
       * Temporary/network polling failures should not immediately
       * kill processing. Try again on the next polling cycle.
       */
      schedulePolling(noteId);
    }
  }

  /*
   * Load My Notes from the real backend when the page opens.
   */
  useEffect(() => {
    let cancelled = false;

    async function loadNotes() {
      if (!accessToken) {
        setIsLoading(false);
        return;
      }

      try {
        setIsLoading(true);
        setError("");

        const result = await getNotes(
          accessToken,
          {
            page: 1,
            pageSize: 20,
          },
        );

        if (cancelled) {
          return;
        }

        const loadedNotes =
          result?.items ?? [];

        setNotes(loadedNotes);

        /*
         * Start one polling timer for every queued/processing note.
         */
        loadedNotes.forEach((note) => {
          if (
            ACTIVE_STATUSES.has(
              note.status,
            )
          ) {
            schedulePolling(note.id);
          }
        });
      } catch (err) {
        if (cancelled) {
          return;
        }

        if (
          AUTH_ERROR_CODES.has(err.code)
        ) {
          await clearInvalidSession();
          return;
        }

        setError(
          "Unable to load your notes. Please try again.",
        );
      } finally {
        if (!cancelled) {
          setIsLoading(false);
        }
      }
    }

    void loadNotes();

    /*
     * When the page unmounts, stop every timer.
     * This prevents background requests after leaving My Notes.
     */
    return () => {
      cancelled = true;
      stopAllPolling();
    };
  }, [accessToken]);

  /*
   * Load the full metadata for one note.
   *
   * The Notes list only contains compact metadata.
   * GET /notes/{id} gives us file size and content type too.
   */
  async function handleViewDetails(note) {
    if (!accessToken) {
      return;
    }

    try {
      setActionError("");
      setLoadingDetailsId(note.id);

      const detail = await getNote(
        accessToken,
        note.id,
      );

      /*
       * Preserve any processing error/message we already received
       * from status polling because the detail endpoint only returns
       * public note metadata.
       */
      setSelectedNote({
        ...detail,
        processing_error:
          note.processing_error ?? null,
        processing_message:
          note.processing_message ?? "",
      });
    } catch (err) {
      if (
        AUTH_ERROR_CODES.has(err.code)
      ) {
        await clearInvalidSession();
        return;
      }

      if (err.code === "NOTE_NOT_FOUND") {
        removeNoteFromUi(note.id);

        setActionError(
          "This note is no longer available.",
        );

        return;
      }

      setActionError(
        "Unable to load the note details. Please try again.",
      );
    } finally {
      setLoadingDetailsId(null);
    }
  }

  /*
   * Delete a note from the backend first.
   *
   * The UI removes the note only after DELETE succeeds.
   */
  async function handleDelete(note) {
    const confirmed = window.confirm(
      `Delete "${note.title}"? This cannot be undone.`,
    );

    if (!confirmed) {
      return;
    }

    if (!accessToken) {
      return;
    }

    try {
      setActionError("");
      setDeletingNoteId(note.id);

      await deleteNote(
        accessToken,
        note.id,
      );

      /*
       * DELETE returns 204 No Content.
       * Once it succeeds, remove the item locally.
       */
      removeNoteFromUi(note.id);
    } catch (err) {
      if (
        AUTH_ERROR_CODES.has(err.code)
      ) {
        await clearInvalidSession();
        return;
      }

      if (err.code === "NOTE_NOT_FOUND") {
        removeNoteFromUi(note.id);

        setActionError(
          "This note is no longer available.",
        );

        return;
      }

      setActionError(
        "Unable to delete this note. Please try again.",
      );
    } finally {
      setDeletingNoteId(null);
    }
  }

  /*
   * Friendly display name for processing states.
   */
  function formatStatus(status) {
    switch (status) {
      case "queued":
        return "Queued";

      case "processing":
        return "Processing";

      case "ready":
        return "Ready";

      case "failed":
        return "Failed";

      default:
        return "Unknown";
    }
  }

  /*
   * Processing message displayed beneath each note.
   *
   * Krish's current pipeline starts at 1% and then jumps to 100%.
   * Showing "Processing…" at 1% avoids making the page look frozen.
   */
  function getProcessingText(note) {
    const progress =
      note.processing_progress ?? 0;

    if (note.status === "queued") {
      return "Waiting to start processing";
    }

    if (note.status === "processing") {
      if (progress <= 1) {
        return "Processing…";
      }

      return `Processing… ${progress}%`;
    }

    if (note.status === "ready") {
      return "Ready for AI questions";
    }

    if (note.status === "failed") {
      return (
        note.processing_error?.message ||
        "The document could not be processed."
      );
    }

    return "";
  }

  /*
   * Format backend timestamps for display.
   */
  function formatDate(dateValue) {
    if (!dateValue) {
      return "—";
    }

    const date = new Date(dateValue);

    return date.toLocaleString([], {
      day: "numeric",
      month: "short",
      year: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });
  }

  /*
   * Convert file size from bytes into a readable value.
   */
  function formatFileSize(bytes) {
    if (
      bytes === null ||
      bytes === undefined
    ) {
      return "—";
    }

    if (bytes < 1024) {
      return `${bytes} B`;
    }

    if (bytes < 1024 * 1024) {
      return `${(
        bytes / 1024
      ).toFixed(1)} KB`;
    }

    return `${(
      bytes /
      1024 /
      1024
    ).toFixed(2)} MB`;
  }

  return (
    <AppShell>
      <section className="notes-page">
        <div className="notes-page-header">
          <div>
            <h1>My Notes</h1>

            <p>
              View and manage the notes
              you&apos;ve uploaded.
            </p>
          </div>
        </div>

        {error && (
          <div
            className="notes-alert notes-alert-error"
            role="alert"
          >
            <AlertCircle size={18} />
            <span>{error}</span>
          </div>
        )}

        {actionError && (
          <div
            className="notes-alert notes-alert-error"
            role="alert"
          >
            <AlertCircle size={18} />
            <span>{actionError}</span>
          </div>
        )}

        {isLoading ? (
          <div className="notes-state-card">
            <LoaderCircle
              className="notes-spinner"
              size={24}
            />

            <p>Loading your notes…</p>
          </div>
        ) : notes.length === 0 ? (
          <div className="notes-state-card">
            <FileText size={32} />

            <h2>No notes yet</h2>

            <p>
              Upload a PDF and it will
              appear here.
            </p>
          </div>
        ) : (
          <div className="notes-list">
            {notes.map((note) => {
              const progress =
                note.processing_progress ??
                0;

              const isActive =
                ACTIVE_STATUSES.has(
                  note.status,
                );

              const isIndeterminate =
                note.status ===
                  "processing" &&
                progress <= 1;

              return (
                <article
                  className="notes-card"
                  key={note.id}
                >
                  <div className="notes-card-icon">
                    <FileText size={24} />
                  </div>

                  <div className="notes-card-main">
                    <div className="notes-card-heading">
                      <div>
                        <h2>
                          {note.title}
                        </h2>

                        <p className="notes-file-name">
                          {note.file_name}
                        </p>
                      </div>

                      <span
                        className={`notes-status notes-status-${note.status}`}
                      >
                        {formatStatus(
                          note.status,
                        )}
                      </span>
                    </div>

                    <div className="notes-processing-row">
                      {isActive && (
                        <LoaderCircle
                          className="notes-spinner"
                          size={16}
                        />
                      )}

                      <span>
                        {getProcessingText(
                          note,
                        )}
                      </span>
                    </div>

                    {isActive && (
                      <div
                        className={`notes-progress-track ${
                          isIndeterminate
                            ? "notes-progress-indeterminate"
                            : ""
                        }`}
                        aria-label="Document processing progress"
                      >
                        {!isIndeterminate && (
                          <span
                            className="notes-progress-value"
                            style={{
                              width: `${Math.min(
                                100,
                                Math.max(
                                  0,
                                  progress,
                                ),
                              )}%`,
                            }}
                          />
                        )}
                      </div>
                    )}

                    {note.status ===
                      "failed" && (
                      <div className="notes-failure">
                        <AlertCircle
                          size={16}
                        />

                        <span>
                          {getProcessingText(
                            note,
                          )}
                        </span>
                      </div>
                    )}

                    <p className="notes-date">
                      Uploaded{" "}
                      {formatDate(
                        note.created_at,
                      )}
                    </p>
                  </div>

                  <div className="notes-card-actions">
                    <button
                      type="button"
                      className="notes-button notes-button-secondary"
                      onClick={() =>
                        handleViewDetails(
                          note,
                        )
                      }
                      disabled={
                        loadingDetailsId ===
                        note.id
                      }
                    >
                      {loadingDetailsId ===
                      note.id ? (
                        <LoaderCircle
                          className="notes-spinner"
                          size={16}
                        />
                      ) : (
                        <Eye size={16} />
                      )}

                      <span>
                        View Details
                      </span>
                    </button>

                    <button
                      type="button"
                      className="notes-button notes-button-danger"
                      onClick={() =>
                        handleDelete(note)
                      }
                      disabled={
                        deletingNoteId ===
                        note.id
                      }
                    >
                      {deletingNoteId ===
                      note.id ? (
                        <LoaderCircle
                          className="notes-spinner"
                          size={16}
                        />
                      ) : (
                        <Trash2
                          size={16}
                        />
                      )}

                      <span>
                        {deletingNoteId ===
                        note.id
                          ? "Deleting…"
                          : "Delete"}
                      </span>
                    </button>
                  </div>
                </article>
              );
            })}
          </div>
        )}
      </section>

      {selectedNote && (
        <div
          className="notes-modal-backdrop"
          role="presentation"
          onMouseDown={(event) => {
            if (
              event.target ===
              event.currentTarget
            ) {
              setSelectedNote(null);
            }
          }}
        >
          <div
            className="notes-modal"
            role="dialog"
            aria-modal="true"
            aria-labelledby="note-details-title"
          >
            <div className="notes-modal-header">
              <div>
                <p className="notes-modal-eyebrow">
                  Note Details
                </p>

                <h2 id="note-details-title">
                  {selectedNote.title}
                </h2>
              </div>

              <button
                type="button"
                className="notes-modal-close"
                aria-label="Close note details"
                onClick={() =>
                  setSelectedNote(null)
                }
              >
                <X size={20} />
              </button>
            </div>

            <div className="notes-details-grid">
              <div>
                <span>File name</span>
                <strong>
                  {selectedNote.file_name}
                </strong>
              </div>

              <div>
                <span>File type</span>
                <strong>
                  {selectedNote.content_type ||
                    "—"}
                </strong>
              </div>

              <div>
                <span>File size</span>
                <strong>
                  {formatFileSize(
                    selectedNote.file_size,
                  )}
                </strong>
              </div>

              <div>
                <span>Status</span>
                <strong>
                  {formatStatus(
                    selectedNote.status,
                  )}
                </strong>
              </div>

              <div>
                <span>Uploaded</span>
                <strong>
                  {formatDate(
                    selectedNote.created_at,
                  )}
                </strong>
              </div>

              <div>
                <span>Last updated</span>
                <strong>
                  {formatDate(
                    selectedNote.updated_at,
                  )}
                </strong>
              </div>
            </div>

            {selectedNote.status ===
              "processing" && (
              <div className="notes-modal-message">
                <LoaderCircle
                  className="notes-spinner"
                  size={18}
                />

                <span>
                  {getProcessingText(
                    selectedNote,
                  )}
                </span>
              </div>
            )}

            {selectedNote.status ===
              "failed" && (
              <div className="notes-modal-message notes-modal-message-error">
                <AlertCircle size={18} />

                <span>
                  {getProcessingText(
                    selectedNote,
                  )}
                </span>
              </div>
            )}

            <div className="notes-modal-actions">
              <button
                type="button"
                className="notes-button notes-button-secondary"
                onClick={() =>
                  setSelectedNote(null)
                }
              >
                Close
              </button>

              <button
                type="button"
                className="notes-button notes-button-danger"
                onClick={() =>
                  handleDelete(
                    selectedNote,
                  )
                }
                disabled={
                  deletingNoteId ===
                  selectedNote.id
                }
              >
                <Trash2 size={16} />

                <span>
                  Delete Note
                </span>
              </button>
            </div>
          </div>
        </div>
      )}
    </AppShell>
  );
}

export default NotesPage;