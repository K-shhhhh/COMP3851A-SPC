import {
  useEffect,
  useMemo,
  useState,
} from "react";

import {
  ArrowLeft,
  FileText,
} from "lucide-react";

import {
  useNavigate,
  useParams,
  useSearchParams,
} from "react-router-dom";

import { useAuth } from "../../contexts/AuthContext.jsx";
import { getNotePdf } from "../../services/noteService.js";

import "./pdfViewer.css";

const AUTH_ERROR_CODES = new Set([
  "AUTHENTICATION_REQUIRED",
  "TOKEN_INVALID",
  "TOKEN_EXPIRED",
  "TOKEN_REVOKED",
  "SESSION_REQUIRED",
  "SESSION_EXPIRED",
]);

function PdfViewerPage() {
  const navigate = useNavigate();
  const { noteId } = useParams();
  const [searchParams] = useSearchParams();
  const { accessToken, logout } = useAuth();

  const [pdfUrl, setPdfUrl] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const page = useMemo(
    () =>
      Math.max(
        1,
        Number(searchParams.get("page")) || 1,
      ),
    [searchParams],
  );

  const title =
    searchParams.get("title") ||
    "Cited source";

  useEffect(() => {
    if (!accessToken || !noteId) {
      return undefined;
    }

    let cancelled = false;
    let objectUrl = "";

    async function loadPdf() {
      setLoading(true);
      setError("");

      try {
        const blob = await getNotePdf(
          accessToken,
          noteId,
        );

        if (cancelled) {
          return;
        }

        objectUrl = URL.createObjectURL(blob);
        setPdfUrl(objectUrl);
      } catch (err) {
        if (cancelled) {
          return;
        }

        console.error(
          "Unable to open cited PDF:",
          err.code,
        );

        if (AUTH_ERROR_CODES.has(err.code)) {
          await logout();
          return;
        }

        if (err.code === "NOTE_NOT_FOUND") {
          setError(
            "This cited PDF is no longer available or you do not have access to it.",
          );
        } else {
          setError(
            "Unable to open this cited PDF right now.",
          );
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    }

    void loadPdf();

    return () => {
      cancelled = true;

      if (objectUrl) {
        URL.revokeObjectURL(objectUrl);
      }
    };
  }, [
    accessToken,
    logout,
    noteId,
  ]);

  return (
    <main className="pdf-viewer-page">
      <header className="pdf-viewer-toolbar">
        <button
          type="button"
          className="pdf-viewer-back"
          onClick={() => navigate(-1)}
        >
          <ArrowLeft size={17} />
          Back
        </button>

        <div className="pdf-viewer-title">
          <FileText size={18} />

          <span>
            <strong>{title}</strong>
            <small>Opening cited page {page}</small>
          </span>
        </div>
      </header>

      <section className="pdf-viewer-content">
        {loading && (
          <div className="pdf-viewer-state">
            Loading cited PDF...
          </div>
        )}

        {!loading && error && (
          <div className="pdf-viewer-state pdf-viewer-error">
            {error}
          </div>
        )}

        {!loading && !error && pdfUrl && (
          <iframe
            className="pdf-viewer-frame"
            title={`${title} — page ${page}`}
            src={`${pdfUrl}#page=${page}`}
          />
        )}
      </section>
    </main>
  );
}

export default PdfViewerPage;
