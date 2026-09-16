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
  uploadNote,
} from "../../services/noteService.js";

import "./uploadNotes.css";

function UploadNotesPage() {
  const fileInputRef = useRef(null);

  const { accessToken } = useAuth();

  const [selectedFile, setSelectedFile] = useState(null);
  const [title, setTitle] = useState("");

  const [isDragging, setIsDragging] = useState(false);
  const [isUploading, setIsUploading] = useState(false);
  const [isLoadingNotes, setIsLoadingNotes] = useState(false);

  const [error, setError] = useState("");
  const [successMessage, setSuccessMessage] = useState("");

  const [recentUploads, setRecentUploads] = useState([]);

  /*
   * Load recent notes from the backend.
   */
  useEffect(() => {
    if (!accessToken) {
      return;
    }

    async function loadNotes() {
      try {
        setIsLoadingNotes(true);

        const result = await getNotes(accessToken, {
          page: 1,
          pageSize: 5,
        });

        setRecentUploads(result?.items ?? []);
      } catch (err) {
        console.error(
          "Unable to load notes:",
          err.code,
        );
      } finally {
        setIsLoadingNotes(false);
      }
    }

    loadNotes();
  }, [accessToken]);

  function validateAndSelectFile(file) {
    if (!file) {
      return;
    }

    const fileName = file.name.toLowerCase();

    const isPdf =
      file.type === "application/pdf" ||
      fileName.endsWith(".pdf");

    if (!isPdf) {
      setError(
        "Only PDF files are supported during this sprint.",
      );

      setSelectedFile(null);
      setSuccessMessage("");

      return;
    }

    if (file.size === 0) {
      setError("The selected PDF is empty.");
      setSelectedFile(null);

      return;
    }

    setError("");
    setSuccessMessage("");
    setSelectedFile(file);

    /*
     * Use filename as a convenient default title.
     */
    if (!title.trim()) {
      setTitle(
        file.name.replace(/\.pdf$/i, ""),
      );
    }
  }

  function handleFileChange(event) {
    const file = event.target.files?.[0];

    validateAndSelectFile(file);
  }

  function handleDragOver(event) {
    event.preventDefault();

    setIsDragging(true);
  }

  function handleDragLeave(event) {
    event.preventDefault();

    setIsDragging(false);
  }

  function handleDrop(event) {
    event.preventDefault();

    setIsDragging(false);

    const file =
      event.dataTransfer.files?.[0];

    validateAndSelectFile(file);
  }

  function handleRemoveFile() {
    setSelectedFile(null);
    setTitle("");
    setError("");
    setSuccessMessage("");

    if (fileInputRef.current) {
      fileInputRef.current.value = "";
    }
  }

  async function handleUpload() {
    if (!selectedFile) {
      setError("Please select a PDF file first.");
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

      const uploadedNote = await uploadNote(
        accessToken,
        {
          file: selectedFile,
          title,
        },
      );

      setSuccessMessage(
        "Your PDF was uploaded successfully and is now being processed.",
      );

      setRecentUploads((current) => [
        uploadedNote,
        ...current,
      ]);

      setSelectedFile(null);
      setTitle("");

      if (fileInputRef.current) {
        fileInputRef.current.value = "";
      }
    } catch (err) {
      console.error(
        "Unable to upload note:",
        err.code,
      );

      if (err.code === "FILE_TOO_LARGE") {
        setError(
          "This PDF is larger than the allowed upload limit.",
        );
      } else if (
        err.code === "UNSUPPORTED_FILE_TYPE"
      ) {
        setError(
          "Only PDF files are supported.",
        );
      } else if (
        err.code === "AUTHENTICATION_REQUIRED"
      ) {
        setError(
          "Your session has expired. Please sign in again.",
        );
      } else if (
        err.code === "VALIDATION_ERROR"
      ) {
        setError(
          "The PDF could not be uploaded. Please check the file and try again.",
        );
      } else {
        setError(
          "Unable to upload the PDF. The notes backend may not be available yet.",
        );
      }
    } finally {
      setIsUploading(false);
    }
  }

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

  function formatDate(dateValue) {
    if (!dateValue) {
      return "";
    }

    const date = new Date(dateValue);

    return date.toLocaleDateString([], {
      day: "numeric",
      month: "short",
      year: "numeric",
    });
  }

  function formatStatus(status) {
    if (!status) {
      return "Queued";
    }

    return (
      status.charAt(0).toUpperCase() +
      status.slice(1)
    );
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
              Upload your lecture notes so Smart
              Peer Companion can process them and
              use them when answering your study
              questions.
            </p>
          </div>
        </section>

        <div className="upload-layout">
          <div className="upload-main-column">

            {/* Title */}

            <section className="upload-card">
              <div className="upload-section-heading">
                <h2>Note Details</h2>

                <p>
                  Give your study material a title.
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
                  onChange={(event) =>
                    setTitle(event.target.value)
                  }
                />
              </div>
            </section>

            {/* File upload */}

            <section className="upload-card">
              <div className="upload-section-heading">
                <h2>Upload PDF</h2>

                <p>
                  Drag and drop your lecture notes
                  below or choose a PDF from your
                  computer.
                </p>
              </div>

              <div
                className={`drop-zone ${
                  isDragging
                    ? "dragging"
                    : ""
                }`}
                onDragOver={handleDragOver}
                onDragLeave={handleDragLeave}
                onDrop={handleDrop}
              >
                <div className="drop-zone-icon">
                  <Upload size={28} />
                </div>

                <h3>
                  Drag & drop your PDF here
                </h3>

                <p>
                  PDF files are supported during
                  this sprint.
                </p>

                <span>or</span>

                <button
                  type="button"
                  className="browse-button"
                  onClick={() =>
                    fileInputRef.current?.click()
                  }
                >
                  Browse Files
                </button>

                <input
                  ref={fileInputRef}
                  type="file"
                  accept=".pdf,application/pdf"
                  onChange={handleFileChange}
                  hidden
                />
              </div>

              {selectedFile && (
                <div className="selected-file">
                  <div className="selected-file-icon">
                    <FileText size={20} />
                  </div>

                  <div className="selected-file-info">
                    <strong>
                      {selectedFile.name}
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
                    onClick={handleRemoveFile}
                    aria-label="Remove selected file"
                  >
                    <X size={18} />
                  </button>
                </div>
              )}

              {error && (
                <p className="upload-error">
                  {error}
                </p>
              )}

              {successMessage && (
                <div className="upload-success">
                  <CheckCircle2 size={17} />

                  <span>
                    {successMessage}
                  </span>
                </div>
              )}

              <button
                type="button"
                className="upload-submit-button"
                onClick={handleUpload}
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

            {/* Recent uploads */}

            <section className="upload-card recent-uploads-card">
              <div className="upload-section-heading">
                <h2>Recent Uploads</h2>

                <p>
                  Your latest uploaded learning
                  materials.
                </p>
              </div>

              {isLoadingNotes && (
                <p className="upload-empty-state">
                  Loading notes...
                </p>
              )}

              {!isLoadingNotes &&
                recentUploads.length === 0 && (
                  <p className="upload-empty-state">
                    No notes uploaded yet.
                  </p>
                )}

              {!isLoadingNotes &&
                recentUploads.length > 0 && (
                  <div className="recent-upload-list">
                    {recentUploads.map(
                      (note) => (
                        <div
                          className="recent-upload-item"
                          key={note.id}
                        >
                          <div className="recent-upload-file-icon">
                            <FileText
                              size={19}
                            />
                          </div>

                          <div className="recent-upload-info">
                            <strong>
                              {note.title ||
                                note.file_name}
                            </strong>

                            <span>
                              {note.file_name}

                              {note.created_at &&
                                ` · ${formatDate(
                                  note.created_at,
                                )}`}
                            </span>
                          </div>

                          <div
                            className={`upload-status ${
                              note.status ===
                              "ready"
                                ? "processed"
                                : "processing"
                            }`}
                          >
                            {formatStatus(
                              note.status,
                            )}

                            {typeof note.processing_progress ===
                              "number" &&
                              note.status !==
                                "ready" &&
                              ` ${note.processing_progress}%`}
                          </div>
                        </div>
                      ),
                    )}
                  </div>
                )}
            </section>
          </div>

          {/* Right side */}

          <aside className="upload-side-column">
            <section className="upload-info-card">
              <div className="info-card-heading">
                <Lightbulb size={20} />

                <h3>Upload Tips</h3>
              </div>

              <ul>
                <li>
                  Only PDF files are supported
                  during this sprint.
                </li>

                <li>
                  Use clear, text-based lecture
                  notes where possible.
                </li>

                <li>
                  Make sure the PDF is not empty.
                </li>

                <li>
                  Processing may take some time
                  after upload.
                </li>
              </ul>
            </section>

            <section className="upload-info-card">
              <div className="info-card-heading">
                <BrainCircuit size={20} />

                <h3>
                  What happens after upload
                </h3>
              </div>

              <div className="generated-feature">
                <CheckCircle2 size={18} />

                <div>
                  <strong>
                    Text Extraction
                  </strong>

                  <span>
                    SPC extracts text from the
                    uploaded PDF.
                  </span>
                </div>
              </div>

              <div className="generated-feature">
                <CheckCircle2 size={18} />

                <div>
                  <strong>
                    Document Chunking
                  </strong>

                  <span>
                    Content is divided into
                    searchable sections.
                  </span>
                </div>
              </div>

              <div className="generated-feature">
                <CheckCircle2 size={18} />

                <div>
                  <strong>
                    AI Embeddings
                  </strong>

                  <span>
                    Your notes become available
                    for grounded AI questions.
                  </span>
                </div>
              </div>
            </section>

            <section className="upload-pro-tip">
              <strong>Pro tip</strong>

              <p>
                Wait until a note reaches Ready
                status before asking the AI
                questions about its content.
              </p>
            </section>
          </aside>
        </div>
      </div>
    </AppShell>
  );
}

export default UploadNotesPage;