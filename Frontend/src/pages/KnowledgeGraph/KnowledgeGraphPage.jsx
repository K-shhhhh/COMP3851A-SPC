import {
  useEffect,
  useMemo,
  useState,
} from "react";

import {
  Link,
  useSearchParams,
} from "react-router-dom";

import {
  AlertCircle,
  BrainCircuit,
  FileText,
  LoaderCircle,
  RefreshCw,
} from "lucide-react";

import AppShell from "../../components/layout/AppShell.jsx";
import KnowledgeGraphView, {
  buildTopicColors,
} from "../../components/knowledgeGraph/KnowledgeGraphView.jsx";
import { useAuth } from "../../contexts/AuthContext.jsx";

import {
  groupByTopic,
  topicOf,
} from "../../components/knowledgeGraph/mindMapLayout.js";

import { getKnowledgeGraph } from "../../services/knowledgeGraphService.js";
import { getNotes } from "../../services/noteService.js";

import "./knowledgeGraph.css";

/*
 * A graph is generated in the background after a document is processed, so
 * the endpoint answers "not ready" for a while. Check again every few
 * seconds, then stop and explain instead of waiting forever.
 */
const GRAPH_RETRY_MS = 4000;
const GRAPH_MAX_ATTEMPTS = 75;

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

function KnowledgeGraphPage() {
  const {
    accessToken,
    logout,
  } = useAuth();

  const [searchParams] = useSearchParams();

  const [notes, setNotes] = useState([]);
  const [isLoadingNotes, setIsLoadingNotes] = useState(true);
  const [notesError, setNotesError] = useState("");

  const [selectedNoteId, setSelectedNoteId] = useState(null);

  /*
   * idle | loading | generating | ready | unavailable | error
   */
  const [graphStatus, setGraphStatus] = useState("idle");
  const [graph, setGraph] = useState(null);
  const [graphError, setGraphError] = useState("");
  const [reloadToken, setReloadToken] = useState(0);

  const [selectedNodeId, setSelectedNodeId] = useState(null);

  async function clearInvalidSession() {
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
   * Load the student's finished documents once.
   */
  useEffect(() => {
    if (!accessToken) {
      return undefined;
    }

    let cancelled = false;

    async function loadNotes() {
      try {
        setIsLoadingNotes(true);
        setNotesError("");

        const result = await getNotes(accessToken, {
          status: "ready",
          page: 1,
          pageSize: 100,
        });

        if (cancelled) {
          return;
        }

        const readyNotes = [];
        for (const note of result?.items ?? []) {
          if (note.status === "ready") {
            readyNotes.push(note);
          }
        }

        setNotes(readyNotes);

        /*
         * Open the document named in ?note=ID when it exists,
         * otherwise the most recent one.
         */
        const requestedId = Number(searchParams.get("note"));
        let chosen = null;
        for (const note of readyNotes) {
          if (note.id === requestedId) {
            chosen = note.id;
          }
        }
        if (chosen === null && readyNotes.length > 0) {
          chosen = readyNotes[0].id;
        }
        setSelectedNoteId(chosen);
      } catch (error) {
        if (cancelled) {
          return;
        }

        if (AUTH_ERROR_CODES.has(error.code)) {
          await clearInvalidSession();
          return;
        }

        setNotesError("Unable to load your notes. Please try again.");
      } finally {
        if (!cancelled) {
          setIsLoadingNotes(false);
        }
      }
    }

    void loadNotes();

    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [accessToken]);

  /*
   * Load the graph for the selected document, checking again while the
   * backend reports it is not ready.
   */
  useEffect(() => {
    if (!accessToken || selectedNoteId === null) {
      return undefined;
    }

    let cancelled = false;
    let timer = null;
    let attempts = 0;

    setGraph(null);
    setSelectedNodeId(null);
    setGraphError("");
    setGraphStatus("loading");

    async function loadGraph() {
      try {
        const result = await getKnowledgeGraph(accessToken, selectedNoteId);

        if (cancelled) {
          return;
        }

        setGraph(result);
        setGraphStatus("ready");
      } catch (error) {
        if (cancelled) {
          return;
        }

        if (AUTH_ERROR_CODES.has(error.code)) {
          await clearInvalidSession();
          return;
        }

        if (error.code === "KNOWLEDGE_GRAPH_NOT_READY") {
          attempts += 1;

          if (attempts >= GRAPH_MAX_ATTEMPTS) {
            setGraphStatus("unavailable");
            return;
          }

          setGraphStatus("generating");
          timer = setTimeout(loadGraph, GRAPH_RETRY_MS);
          return;
        }

        setGraphError(
          error.message || "Unable to load the knowledge graph.",
        );
        setGraphStatus("error");
      }
    }

    void loadGraph();

    return () => {
      cancelled = true;
      if (timer !== null) {
        clearTimeout(timer);
      }
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [accessToken, selectedNoteId, reloadToken]);

  const nodeById = useMemo(() => {
    const map = new Map();
    if (graph) {
      for (const node of graph.nodes) {
        map.set(node.id, node);
      }
    }
    return map;
  }, [graph]);

  const topicColors = useMemo(
    () => (graph ? buildTopicColors(graph.nodes) : new Map()),
    [graph],
  );

  const selectedNode =
    selectedNodeId !== null ? nodeById.get(selectedNodeId) : null;

  let selectedNote = null;
  for (const note of notes) {
    if (note.id === selectedNoteId) {
      selectedNote = note;
    }
  }
  const documentTitle = selectedNote
    ? selectedNote.title || selectedNote.file_name
    : "Document";

  const topicCount = graph ? groupByTopic(graph.nodes).length : 0;

  // Relationships of the selected concept, for the details panel.
  const connections = useMemo(() => {
    const result = [];
    if (!graph || selectedNodeId === null) {
      return result;
    }
    for (const edge of graph.edges) {
      if (edge.source_node_id === selectedNodeId) {
        const other = nodeById.get(edge.target_node_id);
        if (other) {
          result.push({
            key: `out-${edge.id}`,
            direction: "out",
            label: edge.label,
            other,
          });
        }
      } else if (edge.target_node_id === selectedNodeId) {
        const other = nodeById.get(edge.source_node_id);
        if (other) {
          result.push({
            key: `in-${edge.id}`,
            direction: "in",
            label: edge.label,
            other,
          });
        }
      }
    }
    return result;
  }, [graph, nodeById, selectedNodeId]);

  function handleSelectDocument(event) {
    setSelectedNoteId(Number(event.target.value));
  }

  function renderGraphArea() {
    if (graphStatus === "loading") {
      return (
        <div className="kg-state-card">
          <LoaderCircle className="kg-spinner" size={28} />
          <p>Loading the knowledge graph…</p>
        </div>
      );
    }

    if (graphStatus === "generating") {
      return (
        <div className="kg-state-card">
          <LoaderCircle className="kg-spinner" size={28} />
          <h2>Building your knowledge graph</h2>
          <p>
            The graph is still being generated for this document.
            Long documents can take a few minutes. This page checks
            again automatically.
          </p>
        </div>
      );
    }

    if (graphStatus === "unavailable") {
      return (
        <div className="kg-state-card">
          <BrainCircuit size={32} />
          <h2>No graph for this document yet</h2>
          <p>
            It may still be processing, or this document was uploaded
            before graph generation was switched on. Upload it again to
            create a graph.
          </p>
          <button
            type="button"
            className="kg-button"
            onClick={() => setReloadToken((value) => value + 1)}
          >
            <RefreshCw size={16} />
            Check again
          </button>
        </div>
      );
    }

    if (graphStatus === "error") {
      return (
        <div className="kg-state-card">
          <AlertCircle size={32} />
          <h2>Could not load the graph</h2>
          <p>{graphError}</p>
          <button
            type="button"
            className="kg-button"
            onClick={() => setReloadToken((value) => value + 1)}
          >
            <RefreshCw size={16} />
            Try again
          </button>
        </div>
      );
    }

    if (graphStatus === "ready" && graph) {
      return (
        <KnowledgeGraphView
          key={graph.attachment_id}
          graph={graph}
          documentTitle={documentTitle}
          selectedNodeId={selectedNodeId}
          onSelectNode={setSelectedNodeId}
        />
      );
    }

    return null;
  }

  return (
    <AppShell>
      <section className="kg-page">
        <div className="kg-page-header">
          <div>
            <h1>Knowledge Graph</h1>

            <p>
              See the key concepts in a document and how they connect.
            </p>
          </div>

          {notes.length > 0 && (
            <div className="kg-toolbar">
              <label htmlFor="kg-document">Document</label>

              <select
                id="kg-document"
                value={selectedNoteId ?? ""}
                onChange={handleSelectDocument}
              >
                {notes.map((note) => (
                  <option key={note.id} value={note.id}>
                    {note.title || note.file_name}
                  </option>
                ))}
              </select>

              <button
                type="button"
                className="kg-icon-button"
                aria-label="Reload graph"
                onClick={() => setReloadToken((value) => value + 1)}
              >
                <RefreshCw size={16} />
              </button>
            </div>
          )}
        </div>

        {notesError && (
          <div className="kg-alert" role="alert">
            <AlertCircle size={18} />
            <span>{notesError}</span>
          </div>
        )}

        {isLoadingNotes ? (
          <div className="kg-state-card">
            <LoaderCircle className="kg-spinner" size={28} />
            <p>Loading your documents…</p>
          </div>
        ) : notes.length === 0 ? (
          <div className="kg-state-card">
            <FileText size={32} />

            <h2>No finished documents yet</h2>

            <p>
              Upload a PDF and wait until it shows as ready.
              Its knowledge graph will appear here.
            </p>

            <Link to="/notes/upload" className="kg-button">
              Upload notes
            </Link>
          </div>
        ) : (
          <div className="kg-layout">
            <div className="kg-graph-card">{renderGraphArea()}</div>

            <aside className="kg-details" aria-live="polite">
              {selectedNode ? (
                <>
                  <h2>{selectedNode.title}</h2>

                  <span
                    className="kg-topic-chip"
                    style={{
                      backgroundColor:
                        topicColors.get(topicOf(selectedNode)),
                    }}
                  >
                    {topicOf(selectedNode)}
                  </span>

                  <p className="kg-description">
                    {selectedNode.description}
                  </p>

                  {selectedNode.source_chunk_id !== null &&
                    selectedNode.source_chunk_id !== undefined && (
                      <p className="kg-source">
                        Source passage #{selectedNode.source_chunk_id}
                      </p>
                    )}

                  <h3>Connections</h3>

                  {connections.length === 0 ? (
                    <p className="kg-muted">
                      This concept has no connections.
                    </p>
                  ) : (
                    <ul className="kg-connections">
                      {connections.map((connection) => (
                        <li key={connection.key}>
                          <span className="kg-connection-label">
                            {connection.direction === "out"
                              ? `${connection.label || "relates to"} →`
                              : `← ${connection.label || "relates to"}`}
                          </span>

                          <button
                            type="button"
                            onClick={() =>
                              setSelectedNodeId(connection.other.id)
                            }
                          >
                            {connection.other.title}
                          </button>
                        </li>
                      ))}
                    </ul>
                  )}
                </>
              ) : (
                <>
                  <h2>Concept details</h2>

                  {graph ? (
                    <p className="kg-muted">
                      {graph.nodes.length} concepts in {topicCount}{" "}
                      {topicCount === 1 ? "topic" : "topics"}, with{" "}
                      {graph.edges.length} connections between them.
                      Open a topic, then select a concept to read
                      about it.
                    </p>
                  ) : (
                    <p className="kg-muted">
                      Details appear here once the graph is ready.
                    </p>
                  )}
                </>
              )}
            </aside>
          </div>
        )}
      </section>
    </AppShell>
  );
}

export default KnowledgeGraphPage;
