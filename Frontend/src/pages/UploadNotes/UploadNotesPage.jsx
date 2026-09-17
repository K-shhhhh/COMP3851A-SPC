import { useEffect, useRef, useState } from "react";

import {
  BrainCircuit,
  CheckCircle2,
  FileText,
  Lightbulb,
  Upload,
  X,
} from "lucide-react";

import AppShell from "../../components/layout/AppShell.jsx";
import { useAuth } from "../../contexts/AuthContext.jsx";

import {
  getNotes,
  getNoteStatus,
  uploadNote,
} from "../../services/noteService.js";

import "./uploadNotes.css";

/*
 * Notes with these statuses are still being processed.
 *
 * While a note is queued or processing, the frontend
 * periodically asks the backend for its latest status.
 */
const ACTIVE_STATUSES = new Set([
  "queued",
  "processing",
]);

/*
 * These backend error codes mean the user's current
 * authentication session is no longer valid.
 */
const AUTH_ERROR_CODES = new Set([
  "AUTHENTICATION_REQUIRED",
  "TOKEN_INVALID",
  "TOKEN_EXPIRED",
  "TOKEN_REVOKED",
]);

function UploadNotesPage() {
  const fileInputRef = useRef(null);

  /*
   * Store one polling timer per note.
   *
   * Using a Map prevents multiple timers from being
   * created for the same uploaded note.
   */
  const pollingTimersRef = useRef(
    new Map(),
  );

  const {
    accessToken,
    logout,
  } = useAuth();

  const [selectedFile, setSelectedFile] =
    useState(null);

  const [title, setTitle] = useState("");

  const [isDragging, setIsDragging] =
    useState(false);

  const [isUploading, setIsUploading] =
    useState(false);

  const [
    isLoadingNotes,
    setIsLoadingNotes,
  ] = useState(false);

  const [error, setError] = useState("");

  const [
    successMessage,
    setSuccessMessage,
  ] = useState("");

  const [
    recentUploads,
    setRecentUploads,
  ] = useState([]);

  /*
   * Stop the polling timer for one specific note.
   */
  function stopPolling(noteId) {
    const timerId =
      pollingTimersRef.current.get(
        noteId,
      );

    if (timerId) {
      window.clearTimeout(timerId);
    }

    pollingTimersRef.current.delete(
      noteId,
    );
  }

  /*
   * Stop every active polling timer.
   *
   * This is used when:
   * - the user leaves this page
   * - the authentication session expires
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
   * Schedule another status check for a note.
   *
   * We use setTimeout instead of setInterval so
   * a slow backend request cannot overlap with
   * another request for the same note.
   */
  function schedulePolling(noteId) {
    if (!accessToken) {
      return;
    }

    /*
     * Do not create duplicate timers.
     */
    if (
      pollingTimersRef.current.has(
        noteId,
      )
    ) {
      return;
    }

    const timerId =
      window.setTimeout(
        () => {
          /*
           * The timer has now fired,
           * so remove it from the Map.
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
   * Ask the backend for the latest processing
   * state of one uploaded note.
   *
   * Important:
   *
   * GET /notes returns:
   * processing_progress
   *
   * GET /notes/{id}/status returns:
   * progress
   *
   * We therefore map:
   * progress -> processing_progress
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

      /*
       * Update only the note whose status
       * we just received.
       */
      setRecentUploads(
        (currentNotes) =>
          currentNotes.map((note) =>
            note.id === noteId
              ? {
                  ...note,

                  status:
                    result.status,

                  processing_progress:
                    result.progress,

                  processing_message:
                    result.message,

                  processing_error:
                    result.error,

                  updated_at:
                    result.updated_at,
                }
              : note,
          ),
      );

      /*
       * Continue polling only while the
       * document is queued or processing.
       *
       * Once it becomes ready or failed,
       * polling stops automatically.
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
       * If authentication has expired,
       * stop polling and clear the session.
       */
      if (
        AUTH_ERROR_CODES.has(err.code)
      ) {
        stopAllPolling();

        try {
          await logout();
        } catch {
          /*
           * AuthContext clears local session
           * state even if the backend logout
           * request itself fails.
           */
        }

        return;
      }

      /*
       * A note might have been deleted
       * from My Notes or another browser tab.
       *
       * If the backend says it no longer exists,
       * remove the stale item from Recent Uploads.
       */
      if (
        err.code ===
        "NOTE_NOT_FOUND"
      ) {
        stopPolling(noteId);

        setRecentUploads(
          (currentNotes) =>
            currentNotes.filter(
              (note) =>
                note.id !== noteId,
            ),
        );

        return;
      }

      /*
       * Temporary network/backend failures
       * should not permanently stop processing.
       *
       * Try again during the next polling cycle.
       */
      schedulePolling(noteId);
    }
  }

  /*
   * Load the five most recent uploaded notes.
   *
   * Any note that is still queued or processing
   * immediately starts status polling.
   */
  useEffect(() => {
    if (!accessToken) {
      return undefined;
    }

    let cancelled = false;

    async function loadNotes() {
      try {
        setIsLoadingNotes(true);

        const result =
          await getNotes(
            accessToken,
            {
              page: 1,
              pageSize: 5,
            },
          );

        /*
         * Do not update React state if the
         * component has already unmounted.
         */
        if (cancelled) {
          return;
        }

        const loadedNotes =
          result?.items ?? [];

        setRecentUploads(
          loadedNotes,
        );

        /*
         * Start polling every note that
         * has not finished processing yet.
         */
        loadedNotes.forEach(
          (note) => {
            if (
              ACTIVE_STATUSES.has(
                note.status,
              )
            ) {
              schedulePolling(
                note.id,
              );
            }
          },
        );
      } catch (err) {
        if (cancelled) {
          return;
        }

        console.error(
          "Unable to load notes:",
          err.code,
        );

        /*
         * If our authentication token
         * is invalid, clear the session.
         */
        if (
          AUTH_ERROR_CODES.has(
            err.code,
          )
        ) {
          stopAllPolling();

          try {
            await logout();
          } catch {
            /*
             * Local session state is still
             * cleared by AuthContext.
             */
          }
        }
      } finally {
        if (!cancelled) {
          setIsLoadingNotes(false);
        }
      }
    }

    void loadNotes();

    /*
     * Cleanup:
     *
     * Stop all processing timers when the
     * user leaves the Upload Notes page.
     */
    return () => {
      cancelled = true;

      stopAllPolling();
    };
  }, [accessToken]);

  /*
   * Check that the chosen file is a valid PDF
   * before allowing it to be uploaded.
   */
  function validateAndSelectFile(file) {
    if (!file) {
      return;
    }

    const fileName =
      file.name.toLowerCase();

    const isPdf =
      file.type ===
        "application/pdf" ||
      fileName.endsWith(".pdf");

    if (!isPdf) {
      setError(
        "Only PDF files are supported during this sprint.",
      );

      setSelectedFile(null);

      setSuccessMessage("");

      return;
    }

    /*
     * Prevent empty files from being sent
     * to the backend.
     */
    if (file.size === 0) {
      setError(
        "The selected PDF is empty.",
      );

      setSelectedFile(null);

      return;
    }

    setError("");

    setSuccessMessage("");

    setSelectedFile(file);

    /*
     * If the user has not entered a title,
     * use the PDF filename as a convenient
     * default title.
     */
    if (!title.trim()) {
      setTitle(
        file.name.replace(
          /\.pdf$/i,
          "",
        ),
      );
    }
  }

  /*
   * User selected a file using
   * the normal file picker.
   */
  function handleFileChange(event) {
    const file =
      event.target.files?.[0];

    validateAndSelectFile(file);
  }

  /*
   * Allow the browser's drag/drop area
   * to accept the dragged file.
   */
  function handleDragOver(event) {
    event.preventDefault();

    setIsDragging(true);
  }

  /*
   * Remove the visual dragging state
   * when the file leaves the drop area.
   */
  function handleDragLeave(event) {
    event.preventDefault();

    setIsDragging(false);
  }

  /*
   * Handle a PDF dropped directly
   * into the upload area.
   */
  function handleDrop(event) {
    event.preventDefault();

    setIsDragging(false);

    const file =
      event.dataTransfer
        .files?.[0];

    validateAndSelectFile(file);
  }

  /*
   * Remove the currently selected PDF
   * before it has been uploaded.
   */
  function handleRemoveFile() {
    setSelectedFile(null);

    setTitle("");

    setError("");

    setSuccessMessage("");

    if (fileInputRef.current) {
      fileInputRef.current.value =
        "";
    }
  }

  /*
   * Upload the selected PDF using
   * the real Notes API.
   */
  async function handleUpload() {
    if (!selectedFile) {
      setError(
        "Please select a PDF file first.",
      );

      return;
    }

    if (!accessToken) {
      setError(
        "You must be signed in before uploading notes.",
      );

      return;
    }

    try {
      setIsUploading(true);

      setError("");

      setSuccessMessage("");

      const uploadedNote =
        await uploadNote(
          accessToken,
          {
            file: selectedFile,
            title,
          },
        );

      setSuccessMessage(
        "Your PDF was uploaded successfully and is now being processed.",
      );

      /*
       * Add the new note immediately
       * to Recent Uploads.
       *
       * Keep only the five most recent
       * items displayed on this page.
       */
      setRecentUploads(
        (currentNotes) =>
          [
            uploadedNote,
            ...currentNotes,
          ].slice(0, 5),
      );

      /*
       * A successful upload normally returns
       * queued status.
       *
       * Start polling immediately so this
       * page changes to Ready automatically
       * without requiring a refresh.
       */
      if (
        ACTIVE_STATUSES.has(
          uploadedNote.status,
        )
      ) {
        schedulePolling(
          uploadedNote.id,
        );
      }

      /*
       * Clear the upload form after
       * a successful request.
       */
      setSelectedFile(null);

      setTitle("");

      if (fileInputRef.current) {
        fileInputRef.current.value =
          "";
      }
    } catch (err) {
      console.error(
        "Unable to upload note:",
        err.code,
      );

      /*
       * Provide friendly messages for
       * expected backend validation errors.
       */
      if (
        err.code ===
        "FILE_TOO_LARGE"
      ) {
        setError(
          "This PDF is larger than the allowed upload limit.",
        );
      } else if (
        err.code ===
        "UNSUPPORTED_FILE_TYPE"
      ) {
        setError(
          "Only PDF files are supported.",
        );
      } else if (
        err.code ===
          "EMPTY_FILE" ||
        err.code ===
          "INVALID_PDF" ||
        err.code ===
          "INVALID_FILENAME"
      ) {
        setError(
          err.message ||
            "The selected PDF could not be uploaded.",
        );
      } else if (
        AUTH_ERROR_CODES.has(
          err.code,
        )
      ) {
        setError(
          "Your session has expired. Please sign in again.",
        );

        stopAllPolling();

        try {
          await logout();
        } catch {
          /*
           * Local auth state is still
           * cleared by AuthContext.
           */
        }
      } else if (
        err.code ===
        "VALIDATION_ERROR"
      ) {
        setError(
          "The PDF could not be uploaded. Please check the file and try again.",
        );
      } else if (
        err.code ===
          "FILE_STORAGE_UNAVAILABLE" ||
        err.code ===
          "PROCESSING_UNAVAILABLE"
      ) {
        setError(
          "The notes service is temporarily unavailable. Please try again.",
        );
      } else {
        setError(
          "Unable to upload the PDF. Please try again.",
        );
      }
    } finally {
      setIsUploading(false);
    }
  }

  /*
   * Convert a file size in bytes
   * into megabytes for display.
   */
  function formatFileSize(bytes) {
    if (!bytes) {
      return "";
    }

    return `${(
      bytes /
      1024 /
      1024
    ).toFixed(2)} MB`;
  }

  /*
   * Convert the backend timestamp
   * into a readable date.
   */
  function formatDate(dateValue) {
    if (!dateValue) {
      return "";
    }

    const date =
      new Date(dateValue);

    return date.toLocaleDateString(
      [],
      {
        day: "numeric",
        month: "short",
        year: "numeric",
      },
    );
  }

  /*
   * Convert the raw backend status
   * into a readable label.
   */
  function formatStatus(status) {
    if (!status) {
      return "Queued";
    }

    return (
      status
        .charAt(0)
        .toUpperCase() +
      status.slice(1)
    );
  }

  /*
   * Format the processing state shown
   * in Recent Uploads.
   *
   * Krish's current RAG pipeline may stay
   * at 1% while it performs extraction,
   * image captioning, chunking and embeddings.
   *
   * Instead of making it look frozen at 1%,
   * display "Processing…" until the backend
   * reports another percentage or Ready.
   */
  function formatProcessingStatus(
    note,
  ) {
    const progress =
      note.processing_progress ?? 0;

    if (
      note.status === "queued"
    ) {
      return "Queued";
    }

    if (
      note.status ===
      "processing"
    ) {
      if (progress <= 1) {
        return "Processing…";
      }

      return `Processing ${progress}%`;
    }

    if (
      note.status === "ready"
    ) {
      return "Ready";
    }

    if (
      note.status === "failed"
    ) {
      return "Failed";
    }

    return formatStatus(
      note.status,
    );
  }

  /*
   * Choose the existing CSS style
   * used for each processing state.
   */
  function getStatusClass(status) {
    if (status === "ready") {
      return "processed";
    }

    return "processing";
  }

  return (
    <AppShell>
      <div className="upload-page">
        <section className="upload-header">
          <div>
            <p className="upload-eyebrow">
              Notes
            </p>

            <h1>Upload Notes</h1>

            <p>
              Upload your lecture
              notes so Smart Peer
              Companion can process
              them and use them when
              answering your study
              questions.
            </p>
          </div>
        </section>

        <div className="upload-layout">
          <div className="upload-main-column">

            {/* Note title */}

            <section className="upload-card">
              <div className="upload-section-heading">
                <h2>
                  Note Details
                </h2>

                <p>
                  Give your study
                  material a title.
                </p>
              </div>

              <div className="upload-title-field">
                <label htmlFor="note-title">
                  Note title
                </label>

                <input
                  id="note-title"
                  type="text"
                  placeholder="e.g. Week 4 Data Structures"
                  value={title}
                  onChange={(
                    event,
                  ) =>
                    setTitle(
                      event.target
                        .value,
                    )
                  }
                />
              </div>
            </section>

            {/* PDF upload area */}

            <section className="upload-card">
              <div className="upload-section-heading">
                <h2>
                  Upload PDF
                </h2>

                <p>
                  Drag and drop your
                  lecture notes below
                  or choose a PDF from
                  your computer.
                </p>
              </div>

              <div
                className={`drop-zone ${
                  isDragging
                    ? "dragging"
                    : ""
                }`}
                onDragOver={
                  handleDragOver
                }
                onDragLeave={
                  handleDragLeave
                }
                onDrop={
                  handleDrop
                }
              >
                <div className="drop-zone-icon">
                  <Upload
                    size={28}
                  />
                </div>

                <h3>
                  Drag & drop your PDF
                  here
                </h3>

                <p>
                  PDF files are
                  supported during
                  this sprint.
                </p>

                <span>or</span>

                <button
                  type="button"
                  className="browse-button"
                  onClick={() =>
                    fileInputRef
                      .current
                      ?.click()
                  }
                >
                  Browse Files
                </button>

                <input
                  ref={
                    fileInputRef
                  }
                  type="file"
                  accept=".pdf,application/pdf"
                  onChange={
                    handleFileChange
                  }
                  hidden
                />
              </div>

              {/* Selected PDF preview */}

              {selectedFile && (
                <div className="selected-file">
                  <div className="selected-file-icon">
                    <FileText
                      size={20}
                    />
                  </div>

                  <div className="selected-file-info">
                    <strong>
                      {
                        selectedFile.name
                      }
                    </strong>

                    <span>
                      {formatFileSize(
                        selectedFile.size,
                      )}
                    </span>
                  </div>

                  <button
                    type="button"
                    className="remove-file-button"
                    onClick={
                      handleRemoveFile
                    }
                    aria-label="Remove selected file"
                  >
                    <X size={18} />
                  </button>
                </div>
              )}

              {/* Upload error */}

              {error && (
                <p className="upload-error">
                  {error}
                </p>
              )}

              {/* Successful upload message */}

              {successMessage && (
                <div className="upload-success">
                  <CheckCircle2
                    size={17}
                  />

                  <span>
                    {
                      successMessage
                    }
                  </span>
                </div>
              )}

              <button
                type="button"
                className="upload-submit-button"
                onClick={
                  handleUpload
                }
                disabled={
                  !selectedFile ||
                  isUploading
                }
              >
                <Upload size={18} />

                {isUploading
                  ? "Uploading..."
                  : "Upload PDF"}
              </button>
            </section>

            {/* Recent uploaded notes */}

            <section className="upload-card recent-uploads-card">
              <div className="upload-section-heading">
                <h2>
                  Recent Uploads
                </h2>

                <p>
                  Your latest uploaded
                  learning materials.
                </p>
              </div>

              {isLoadingNotes && (
                <p className="upload-empty-state">
                  Loading notes...
                </p>
              )}

              {!isLoadingNotes &&
                recentUploads.length ===
                  0 && (
                  <p className="upload-empty-state">
                    No notes uploaded
                    yet.
                  </p>
                )}

              {!isLoadingNotes &&
                recentUploads.length >
                  0 && (
                  <div className="recent-upload-list">
                    {recentUploads.map(
                      (note) => (
                        <div
                          className="recent-upload-item"
                          key={
                            note.id
                          }
                        >
                          <div className="recent-upload-file-icon">
                            <FileText
                              size={
                                19
                              }
                            />
                          </div>

                          <div className="recent-upload-info">
                            <strong>
                              {note.title ||
                                note.file_name}
                            </strong>

                            <span>
                              {
                                note.file_name
                              }

                              {note.created_at &&
                                ` · ${formatDate(
                                  note.created_at,
                                )}`}
                            </span>
                          </div>

                          {/*
                           * This status updates automatically
                           * because queued/processing notes
                           * are now polled every 2.5 seconds.
                           */}
                          <div
                            className={`upload-status ${getStatusClass(
                              note.status,
                            )}`}
                          >
                            {formatProcessingStatus(
                              note,
                            )}
                          </div>
                        </div>
                      ),
                    )}
                  </div>
                )}
            </section>
          </div>

          {/* Information cards on the right */}

          <aside className="upload-side-column">
            <section className="upload-info-card">
              <div className="info-card-heading">
                <Lightbulb
                  size={20}
                />

                <h3>
                  Upload Tips
                </h3>
              </div>

              <ul>
                <li>
                  Only PDF files are
                  supported during this
                  sprint.
                </li>

                <li>
                  Use clear, text-based
                  lecture notes where
                  possible.
                </li>

                <li>
                  Make sure the PDF is
                  not empty.
                </li>

                <li>
                  Processing may take
                  some time after
                  upload.
                </li>
              </ul>
            </section>

            <section className="upload-info-card">
              <div className="info-card-heading">
                <BrainCircuit
                  size={20}
                />

                <h3>
                  What happens after
                  upload
                </h3>
              </div>

              <div className="generated-feature">
                <CheckCircle2
                  size={18}
                />

                <div>
                  <strong>
                    Text Extraction
                  </strong>

                  <span>
                    SPC extracts text
                    from the uploaded
                    PDF.
                  </span>
                </div>
              </div>

              <div className="generated-feature">
                <CheckCircle2
                  size={18}
                />

                <div>
                  <strong>
                    Document Chunking
                  </strong>

                  <span>
                    Content is divided
                    into searchable
                    sections.
                  </span>
                </div>
              </div>

              <div className="generated-feature">
                <CheckCircle2
                  size={18}
                />

                <div>
                  <strong>
                    AI Embeddings
                  </strong>

                  <span>
                    Your notes become
                    available for
                    grounded AI
                    questions.
                  </span>
                </div>
              </div>
            </section>

            <section className="upload-pro-tip">
              <strong>
                Pro tip
              </strong>

              <p>
                Wait until a note
                reaches Ready status
                before asking the AI
                questions about its
                content.
              </p>
            </section>
          </aside>
        </div>
      </div>
    </AppShell>
  );
}

export default UploadNotesPage;