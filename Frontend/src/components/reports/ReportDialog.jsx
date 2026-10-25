import { useEffect, useState } from "react";
import {
  AlertCircle,
  CheckCircle2,
  Flag,
  LoaderCircle,
  X,
} from "lucide-react";

import { createReport } from "../../services/reportService.js";

import "./reportDialog.css";

const CATEGORIES = [
  ["harassment_bullying", "Harassment or bullying"],
  ["hate_discrimination", "Hate or discrimination"],
  ["spam_scam", "Spam or scam"],
  ["inappropriate_content", "Inappropriate content"],
  ["academic_misconduct", "Academic misconduct"],
  ["privacy_violation", "Privacy violation"],
  ["impersonation", "Impersonation"],
  ["dangerous_content", "Dangerous content"],
  ["other", "Other"],
];

const MAX_EVIDENCE = 3;
const MAX_EVIDENCE_BYTES = 5 * 1024 * 1024;
const ALLOWED_TYPES = new Set([
  "image/png",
  "image/jpeg",
]);

function reportError(error) {
  const messages = {
    AUTHENTICATION_REQUIRED:
      "Please sign in again before submitting a report.",
    REPORT_PERMISSION_DENIED:
      "You do not have permission to report this item.",
    REPORT_TARGET_NOT_FOUND:
      "This item is no longer available.",
    DUPLICATE_REPORT:
      "You have already submitted a report for this item.",
    INVALID_REPORT_EVIDENCE:
      "One or more evidence images are invalid.",
    PERSISTENCE_NOT_CONFIGURED:
      "Reporting is temporarily unavailable while the server database is being configured.",
  };

  return (
    messages[error?.code] ||
    error?.message ||
    "Unable to submit the report. Please try again."
  );
}

export default function ReportDialog({
  accessToken,
  target,
  onClose,
}) {
  const [category, setCategory] =
    useState("inappropriate_content");

  const [description, setDescription] =
    useState("");

  const [
    includeLimitedContext,
    setIncludeLimitedContext,
  ] = useState(false);

  const [evidence, setEvidence] =
    useState([]);

  const [saving, setSaving] =
    useState(false);

  const [error, setError] =
    useState("");

  const [submitted, setSubmitted] =
    useState(false);

  useEffect(() => {
    function handleKeyDown(event) {
      if (
        event.key === "Escape" &&
        !saving
      ) {
        onClose();
      }
    }

    window.addEventListener(
      "keydown",
      handleKeyDown,
    );

    return () => {
      window.removeEventListener(
        "keydown",
        handleKeyDown,
      );
    };
  }, [onClose, saving]);

  function chooseEvidence(event) {
    const files =
      Array.from(
        event.target.files || [],
      );

    event.target.value = "";

    if (files.length > MAX_EVIDENCE) {
      setError(
        "You can attach a maximum of three evidence images.",
      );
      return;
    }

    const invalid = files.find(
      (file) =>
        !ALLOWED_TYPES.has(file.type) ||
        file.size > MAX_EVIDENCE_BYTES,
    );

    if (invalid) {
      setError(
        "Evidence must be PNG or JPEG and no larger than 5 MB per image.",
      );
      return;
    }

    setError("");
    setEvidence(files);
  }

  async function submit(event) {
    event.preventDefault();

    const trimmed =
      description.trim();

    if (
      trimmed.length < 10 ||
      trimmed.length > 2000
    ) {
      setError(
        "Please enter a description between 10 and 2000 characters.",
      );
      return;
    }

    setSaving(true);
    setError("");

    try {
      await createReport(
        accessToken,
        {
          targetType:
            target.type,
          targetId:
            target.id,
          category,
          description:
            trimmed,
          includeLimitedContext:
            target.type === "message"
              ? includeLimitedContext
              : false,
          evidence,
        },
      );

      setSubmitted(true);
    } catch (requestError) {
      setError(
        reportError(
          requestError,
        ),
      );
    } finally {
      setSaving(false);
    }
  }

  return (
    <div
      className="report-dialog-backdrop"
      onMouseDown={(event) => {
        if (
          event.target === event.currentTarget &&
          !saving
        ) {
          onClose();
        }
      }}
    >
      <section
        className="report-dialog"
        role="dialog"
        aria-modal="true"
        aria-labelledby="report-dialog-title"
      >
        <div className="report-dialog-header">
          <div>
            <span className="report-dialog-eyebrow">
              Report
            </span>
            <h2 id="report-dialog-title">
              <Flag size={20} />
              Report {target.label || target.type}
            </h2>
          </div>

          <button
            type="button"
            onClick={onClose}
            disabled={saving}
            aria-label="Close report dialog"
          >
            <X size={20} />
          </button>
        </div>

        {submitted ? (
          <div className="report-dialog-success">
            <CheckCircle2 size={30} />
            <h3>Report submitted</h3>
            <p>
              Your report has been sent for review.
              You can track it from My Reports.
            </p>
            <button
              type="button"
              className="report-primary"
              onClick={onClose}
            >
              Done
            </button>
          </div>
        ) : (
          <form
            className="report-dialog-form"
            onSubmit={submit}
          >
            <label>
              Category
              <select
                value={category}
                onChange={(event) =>
                  setCategory(
                    event.target.value,
                  )
                }
                disabled={saving}
              >
                {CATEGORIES.map(
                  ([value, label]) => (
                    <option
                      value={value}
                      key={value}
                    >
                      {label}
                    </option>
                  ),
                )}
              </select>
            </label>

            <label>
              What happened?
              <textarea
                rows={5}
                minLength={10}
                maxLength={2000}
                value={description}
                onChange={(event) =>
                  setDescription(
                    event.target.value,
                  )
                }
                placeholder="Describe the issue..."
                disabled={saving}
                required
              />
              <small>
                {description.length}/2000
              </small>
            </label>

            {target.type === "message" && (
              <label className="report-context-check">
                <input
                  type="checkbox"
                  checked={
                    includeLimitedContext
                  }
                  onChange={(event) =>
                    setIncludeLimitedContext(
                      event.target.checked,
                    )
                  }
                  disabled={saving}
                />
                <span>
                  Include a small amount of nearby
                  conversation for context
                </span>
              </label>
            )}

            <label>
              Evidence images (optional)
              <input
                type="file"
                accept="image/png,image/jpeg"
                multiple
                onChange={chooseEvidence}
                disabled={saving}
              />
              <small>
                Up to 3 PNG/JPEG images, 5 MB each.
              </small>
            </label>

            {evidence.length > 0 && (
              <div className="report-evidence-list">
                {evidence.map(
                  (file) => (
                    <span key={`${file.name}-${file.size}`}>
                      {file.name}
                    </span>
                  ),
                )}
              </div>
            )}

            {error && (
              <div
                className="report-dialog-error"
                role="alert"
              >
                <AlertCircle size={17} />
                {error}
              </div>
            )}

            <div className="report-dialog-actions">
              <button
                type="button"
                className="report-secondary"
                onClick={onClose}
                disabled={saving}
              >
                Cancel
              </button>

              <button
                type="submit"
                className="report-primary"
                disabled={saving}
              >
                {saving && (
                  <LoaderCircle
                    className="report-spin"
                    size={16}
                  />
                )}
                {saving
                  ? "Submitting..."
                  : "Submit report"}
              </button>
            </div>
          </form>
        )}
      </section>
    </div>
  );
}
