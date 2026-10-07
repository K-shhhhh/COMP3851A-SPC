import {
  useCallback,
  useEffect,
  useRef,
  useState,
} from "react";

import {
  AlertTriangle,
  X,
} from "lucide-react";

import "./confirmModal.css";

function ConfirmModal({
  title,
  message,
  confirmLabel = "Confirm",
  cancelLabel = "Cancel",
  tone = "danger",
  onConfirm,
  onCancel,
}) {
  useEffect(() => {
    function handleKeyDown(event) {
      if (event.key === "Escape") {
        onCancel();
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
  }, [onCancel]);

  return (
    <div
      className="confirm-modal-overlay"
      onMouseDown={(event) => {
        if (
          event.target ===
          event.currentTarget
        ) {
          onCancel();
        }
      }}
    >
      <div
        className="confirm-modal"
        role="dialog"
        aria-modal="true"
        aria-labelledby="confirm-modal-title"
        aria-describedby="confirm-modal-message"
      >
        <div className="confirm-modal-header">
          <div
            className={`confirm-modal-icon ${tone}`}
            aria-hidden="true"
          >
            <AlertTriangle size={19} />
          </div>

          <div className="confirm-modal-heading">
            <h2 id="confirm-modal-title">
              {title}
            </h2>

            <p id="confirm-modal-message">
              {message}
            </p>
          </div>

          <button
            type="button"
            className="confirm-modal-close"
            onClick={onCancel}
            aria-label="Close confirmation"
          >
            <X size={18} />
          </button>
        </div>

        <div className="confirm-modal-actions">
          <button
            type="button"
            className="confirm-modal-button secondary"
            onClick={onCancel}
          >
            {cancelLabel}
          </button>

          <button
            type="button"
            className={`confirm-modal-button ${tone}`}
            onClick={onConfirm}
            autoFocus
          >
            {confirmLabel}
          </button>
        </div>
      </div>
    </div>
  );
}

export function useConfirmModal() {
  const [dialog, setDialog] =
    useState(null);

  const resolverRef =
    useRef(null);

  const closeDialog =
    useCallback((result) => {
      const resolve =
        resolverRef.current;

      resolverRef.current =
        null;

      setDialog(null);

      resolve?.(result);
    }, []);

  const requestConfirmation =
    useCallback((options) => {
      return new Promise(
        (resolve) => {
          if (
            resolverRef.current
          ) {
            resolverRef.current(
              false,
            );
          }

          resolverRef.current =
            resolve;

          setDialog({
            title:
              options.title ||
              "Are you sure?",
            message:
              options.message ||
              "Please confirm this action.",
            confirmLabel:
              options.confirmLabel ||
              "Confirm",
            cancelLabel:
              options.cancelLabel ||
              "Cancel",
            tone:
              options.tone ||
              "danger",
          });
        },
      );
    }, []);

  useEffect(() => {
    return () => {
      resolverRef.current?.(
        false,
      );

      resolverRef.current =
        null;
    };
  }, []);

  const confirmModal =
    dialog ? (
      <ConfirmModal
        {...dialog}
        onConfirm={() =>
          closeDialog(true)
        }
        onCancel={() =>
          closeDialog(false)
        }
      />
    ) : null;

  return {
    requestConfirmation,
    confirmModal,
  };
}

export default ConfirmModal;
