import {
  useEffect,
  useState,
} from "react";

import {
  AlertCircle,
  Eye,
  Flag,
  LoaderCircle,
  X,
} from "lucide-react";

import AppShell from "../../components/layout/AppShell.jsx";
import { useAuth } from "../../contexts/AuthContext.jsx";
import {
  getMyReport,
  getMyReports,
} from "../../services/reportService.js";

import "./reports.css";

const FILTERS = [
  ["", "All"],
  ["submitted", "Submitted"],
  ["under_review", "Under review"],
  ["resolved", "Resolved"],
  ["dismissed", "Dismissed"],
];

function humanize(value) {
  return String(value || "")
    .split("_")
    .filter(Boolean)
    .map(
      (part) =>
        part.charAt(0).toUpperCase() +
        part.slice(1),
    )
    .join(" ");
}

function formatDate(value) {
  if (!value) return "—";

  return new Date(value).toLocaleString(
    [],
    {
      day: "numeric",
      month: "short",
      year: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    },
  );
}

function reportsError(error) {
  if (
    error?.status === 503 ||
    error?.code ===
      "PERSISTENCE_NOT_CONFIGURED"
  ) {
    return (
      "My Reports is temporarily unavailable while " +
      "the server database is being configured."
    );
  }

  if (
    error?.code ===
    "REPORT_NOT_FOUND"
  ) {
    return "This report is no longer available.";
  }

  return (
    error?.message ||
    "Unable to load your reports. Please try again."
  );
}

export default function MyReportsPage() {
  const { accessToken } =
    useAuth();

  const [status, setStatus] =
    useState("");

  const [reports, setReports] =
    useState([]);

  const [nextCursor, setNextCursor] =
    useState(null);

  const [loading, setLoading] =
    useState(true);

  const [loadingMore, setLoadingMore] =
    useState(false);

  const [error, setError] =
    useState("");

  const [selectedReport, setSelectedReport] =
    useState(null);

  const [detailsLoading, setDetailsLoading] =
    useState(false);

  useEffect(() => {
    if (!accessToken) {
      return undefined;
    }

    let cancelled = false;

    async function load() {
      setLoading(true);
      setError("");

      try {
        const result =
          await getMyReports(
            accessToken,
            {
              status,
              limit: 20,
            },
          );

        if (cancelled) return;

        setReports(
          result?.items || [],
        );

        setNextCursor(
          result?.next_cursor ||
          null,
        );
      } catch (requestError) {
        if (!cancelled) {
          setReports([]);
          setNextCursor(null);
          setError(
            reportsError(
              requestError,
            ),
          );
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    }

    void load();

    return () => {
      cancelled = true;
    };
  }, [
    accessToken,
    status,
  ]);

  async function loadMore() {
    if (
      !accessToken ||
      !nextCursor ||
      loadingMore
    ) {
      return;
    }

    setLoadingMore(true);
    setError("");

    try {
      const result =
        await getMyReports(
          accessToken,
          {
            status,
            cursor:
              nextCursor,
            limit: 20,
          },
        );

      setReports(
        (current) => [
          ...current,
          ...(result?.items || []),
        ],
      );

      setNextCursor(
        result?.next_cursor ||
        null,
      );
    } catch (requestError) {
      setError(
        reportsError(
          requestError,
        ),
      );
    } finally {
      setLoadingMore(false);
    }
  }

  async function openDetails(
    report,
  ) {
    if (
      !accessToken ||
      detailsLoading
    ) {
      return;
    }

    setDetailsLoading(true);
    setError("");

    try {
      const detail =
        await getMyReport(
          accessToken,
          report.report_id,
        );

      setSelectedReport(
        detail,
      );
    } catch (requestError) {
      setError(
        reportsError(
          requestError,
        ),
      );
    } finally {
      setDetailsLoading(false);
    }
  }

  return (
    <AppShell>
      <section className="reports-page">
        <header className="reports-heading">
          <div>
            <h1>My Reports</h1>
            <p>
              Track reports you have submitted
              from messages, groups and files.
            </p>
          </div>
        </header>

        <div
          className="reports-filters"
          role="group"
          aria-label="Report status filter"
        >
          {FILTERS.map(
            ([value, label]) => (
              <button
                key={value || "all"}
                type="button"
                className={
                  status === value
                    ? "active"
                    : ""
                }
                onClick={() =>
                  setStatus(value)
                }
              >
                {label}
              </button>
            ),
          )}
        </div>

        {error && (
          <div
            className="reports-alert"
            role="alert"
          >
            <AlertCircle size={18} />
            {error}
          </div>
        )}

        {loading ? (
          <div className="reports-state">
            <LoaderCircle
              className="reports-spin"
              size={24}
            />
            Loading your reports...
          </div>
        ) : reports.length === 0 ? (
          <div className="reports-state reports-empty">
            <Flag size={34} />
            <h2>No reports found</h2>
            <p>
              Reports submitted from a message,
              group or file will appear here.
            </p>
          </div>
        ) : (
          <>
            <div className="reports-list">
              {reports.map(
                (report) => (
                  <article
                    className="report-card"
                    key={
                      report.report_id
                    }
                  >
                    <div className="report-card-main">
                      <div className="report-card-top">
                        <strong>
                          {humanize(
                            report.category,
                          )}
                        </strong>

                        <span
                          className={`report-status report-status-${report.status}`}
                        >
                          {humanize(
                            report.status,
                          )}
                        </span>
                      </div>

                      <div className="report-card-meta">
                        <span>
                          {humanize(
                            report.target_type,
                          )}
                        </span>
                        <span>
                          {formatDate(
                            report.created_at,
                          )}
                        </span>
                      </div>

                      <p>
                        {report.description}
                      </p>
                    </div>

                    <button
                      type="button"
                      className="report-view-button"
                      onClick={() =>
                        openDetails(
                          report,
                        )
                      }
                      disabled={
                        detailsLoading
                      }
                    >
                      <Eye size={16} />
                      View details
                    </button>
                  </article>
                ),
              )}
            </div>

            {nextCursor && (
              <button
                type="button"
                className="reports-load-more"
                onClick={loadMore}
                disabled={loadingMore}
              >
                {loadingMore && (
                  <LoaderCircle
                    className="reports-spin"
                    size={16}
                  />
                )}
                {loadingMore
                  ? "Loading..."
                  : "Load more"}
              </button>
            )}
          </>
        )}
      </section>

      {selectedReport && (
        <div
          className="report-details-backdrop"
          onMouseDown={(event) => {
            if (
              event.target ===
              event.currentTarget
            ) {
              setSelectedReport(
                null,
              );
            }
          }}
        >
          <section
            className="report-details"
            role="dialog"
            aria-modal="true"
            aria-labelledby="report-details-title"
          >
            <div className="report-details-head">
              <div>
                <span>Report details</span>
                <h2 id="report-details-title">
                  {humanize(
                    selectedReport.category,
                  )}
                </h2>
              </div>

              <button
                type="button"
                onClick={() =>
                  setSelectedReport(
                    null,
                  )
                }
                aria-label="Close report details"
              >
                <X size={20} />
              </button>
            </div>

            <dl className="report-details-grid">
              <div>
                <dt>Status</dt>
                <dd>
                  {humanize(
                    selectedReport.status,
                  )}
                </dd>
              </div>
              <div>
                <dt>Target</dt>
                <dd>
                  {humanize(
                    selectedReport.target_type,
                  )}
                </dd>
              </div>
              <div>
                <dt>Submitted</dt>
                <dd>
                  {formatDate(
                    selectedReport.created_at,
                  )}
                </dd>
              </div>
              <div>
                <dt>Last updated</dt>
                <dd>
                  {formatDate(
                    selectedReport.updated_at,
                  )}
                </dd>
              </div>
            </dl>

            <div className="report-details-description">
              <span>Description</span>
              <p>
                {selectedReport.description}
              </p>
            </div>

            {selectedReport.evidence?.length > 0 && (
              <div className="report-details-description">
                <span>Evidence</span>
                <ul>
                  {selectedReport.evidence.map(
                    (item) => (
                      <li key={item.evidence_id}>
                        {item.filename}
                      </li>
                    ),
                  )}
                </ul>
              </div>
            )}

            <div className="report-details-actions">
              <button
                type="button"
                onClick={() =>
                  setSelectedReport(
                    null,
                  )
                }
              >
                Close
              </button>
            </div>
          </section>
        </div>
      )}
    </AppShell>
  );
}
