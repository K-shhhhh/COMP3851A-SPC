import {
  useEffect,
  useLayoutEffect,
  useMemo,
  useRef,
  useState,
} from "react";

import {
  groupByTopic,
  layoutConnections,
  layoutMindMap,
  topicOf,
} from "./mindMapLayout.js";

/*
 * Smart Peer Companion
 * Knowledge Graph mind map
 *
 * A NotebookLM style mind map: the document on the left, its topics in the
 * middle, and each topic's concepts to the right when it is expanded.
 *
 *  * Click a topic to open or close it, click a concept to read about it.
 *  * Related concepts are joined by curved arcs. Selecting a concept draws
 *    its connections (and opens the topics at the other end); "Show all
 *    connections" draws every arc at once.
 *  * Zoom with the buttons, Ctrl/Cmd + scroll, or a trackpad pinch. Drag the
 *    background to move around.
 *
 * Every colour and text style lives in knowledgeGraph.css so dark mode works.
 */

/* Small documents open fully expanded; big ones start collapsed and tidy. */
const AUTO_EXPAND_MAX_CONCEPTS = 12;

const MIN_ZOOM = 0.3;
const MAX_ZOOM = 2;
const ZOOM_STEP = 1.2;
const INITIAL_MIN_ZOOM = 0.8;
const MAX_LABELLED_ARCS = 12;

/* Arc colours: one per concept that connections point TO, so everything that
   points at the same concept (for example all subjects with a Credit grade)
   shares a colour. */
const ARC_COLORS = [
  "#e4572e",
  "#2e86ab",
  "#3bb273",
  "#9b5de5",
  "#f2a541",
  "#e83f6f",
  "#1b998b",
  "#7b6d8d",
  "#c1666b",
  "#4f6d7a",
];

const TOPIC_COLORS = [
  "#7047eb",
  "#2f9e8f",
  "#e0883a",
  "#d9507a",
  "#3b82c4",
  "#8a9a2b",
  "#a05cc8",
  "#c4574a",
];

/** Topic to colour, in order of first appearance so colours stay stable. */
export function buildTopicColors(nodes) {
  const colors = new Map();
  for (const node of nodes) {
    const topic = topicOf(node);
    if (!colors.has(topic)) {
      colors.set(topic, TOPIC_COLORS[colors.size % TOPIC_COLORS.length]);
    }
  }
  return colors;
}

/** Shorten text so it fits a box of the given width. */
function fit(text, boxWidth, reserved = 0, charWidth = 7.4) {
  const maxChars = Math.max(6, Math.floor((boxWidth - 28 - reserved) / charWidth));
  if (text.length <= maxChars) {
    return text;
  }
  return `${text.slice(0, maxChars - 1).trimEnd()}…`;
}

function clampZoom(value) {
  return Math.min(MAX_ZOOM, Math.max(MIN_ZOOM, Math.round(value * 100) / 100));
}

function KnowledgeGraphView({
  graph,
  documentTitle,
  selectedNodeId,
  onSelectNode,
}) {
  const nodes = graph.nodes;
  const edges = graph.edges;

  const groups = useMemo(() => groupByTopic(nodes), [nodes]);
  const topicColors = useMemo(() => buildTopicColors(nodes), [nodes]);

  const [expanded, setExpanded] = useState(() => {
    const open = new Set();
    if (nodes.length <= AUTO_EXPAND_MAX_CONCEPTS) {
      for (const group of groups) {
        open.add(group.topic);
      }
    }
    return open;
  });

  const [showAll, setShowAll] = useState(
    nodes.length <= AUTO_EXPAND_MAX_CONCEPTS,
  );
  const [zoom, setZoom] = useState(1);

  const scrollRef = useRef(null);
  const zoomRef = useRef(1);
  const zoomByRef = useRef(null);
  const anchorRef = useRef(null);
  const dragRef = useRef(null);
  const suppressClickRef = useRef(false);

  zoomRef.current = zoom;

  const nodeById = useMemo(() => {
    const map = new Map();
    for (const node of nodes) {
      map.set(node.id, node);
    }
    return map;
  }, [nodes]);

  // Selecting a concept opens its topic AND the topics of everything it is
  // connected to, so both ends of every connection are visible.
  useEffect(() => {
    if (selectedNodeId === null) {
      return;
    }
    const node = nodeById.get(selectedNodeId);
    if (!node) {
      return;
    }

    const topicsToOpen = new Set();
    topicsToOpen.add(topicOf(node));
    for (const edge of edges) {
      let otherId = null;
      if (edge.source_node_id === selectedNodeId) {
        otherId = edge.target_node_id;
      } else if (edge.target_node_id === selectedNodeId) {
        otherId = edge.source_node_id;
      }
      if (otherId !== null) {
        const other = nodeById.get(otherId);
        if (other) {
          topicsToOpen.add(topicOf(other));
        }
      }
    }

    setExpanded((current) => {
      let changed = false;
      const next = new Set(current);
      for (const topic of topicsToOpen) {
        if (!next.has(topic)) {
          next.add(topic);
          changed = true;
        }
      }
      return changed ? next : current;
    });
  }, [selectedNodeId, nodeById, edges]);

  const layout = useMemo(
    () => layoutMindMap(groups, expanded),
    [groups, expanded],
  );

  const arcs = useMemo(
    () => layoutConnections(layout, edges, { selectedNodeId, showAll }),
    [layout, edges, selectedNodeId, showAll],
  );

  const arcColors = useMemo(() => {
    const colors = new Map();
    for (const edge of edges) {
      if (!colors.has(edge.target_node_id)) {
        colors.set(
          edge.target_node_id,
          ARC_COLORS[colors.size % ARC_COLORS.length],
        );
      }
    }
    return colors;
  }, [edges]);

  // Concepts directly related to the selected one, from the graph's edges.
  const relatedIds = useMemo(() => {
    const ids = new Set();
    if (selectedNodeId === null) {
      return ids;
    }
    for (const edge of edges) {
      if (edge.source_node_id === selectedNodeId) {
        ids.add(edge.target_node_id);
      }
      if (edge.target_node_id === selectedNodeId) {
        ids.add(edge.source_node_id);
      }
    }
    return ids;
  }, [edges, selectedNodeId]);

  const { root, topics, concepts, links } = layout;

  const selectedNode =
    selectedNodeId !== null ? nodeById.get(selectedNodeId) : null;
  let selectedTopicIndex = -1;
  if (selectedNode) {
    const selectedTopic = topicOf(selectedNode);
    selectedTopicIndex = topics.findIndex((t) => t.topic === selectedTopic);
  }

  /* ---------------------------------------------------------------
     ZOOM
     --------------------------------------------------------------- */

  /*
   * Change the zoom while keeping the point under `anchor` (a position
   * inside the scroll area) where it is, so zooming feels natural.
   */
  function zoomTo(nextZoom, anchor) {
    const next = clampZoom(nextZoom);
    const current = zoomRef.current;
    const container = scrollRef.current;

    if (next === current) {
      anchorRef.current = null;
      return;
    }

    if (container && anchor) {
      anchorRef.current = {
        contentX: (container.scrollLeft + anchor.x) / current,
        contentY: (container.scrollTop + anchor.y) / current,
        viewX: anchor.x,
        viewY: anchor.y,
      };
    }
    setZoom(next);
  }

  zoomByRef.current = (factor, anchor) => {
    zoomTo(zoomRef.current * factor, anchor);
  };

  function viewportCentre() {
    const container = scrollRef.current;
    if (!container) {
      return null;
    }
    return { x: container.clientWidth / 2, y: container.clientHeight / 2 };
  }

  // After the new size is on screen, restore the anchored scroll position.
  useLayoutEffect(() => {
    const anchor = anchorRef.current;
    const container = scrollRef.current;
    if (!anchor || !container) {
      return;
    }
    container.scrollLeft = anchor.contentX * zoom - anchor.viewX;
    container.scrollTop = anchor.contentY * zoom - anchor.viewY;
    anchorRef.current = null;
  }, [zoom]);

  function fitToWidth() {
    const container = scrollRef.current;
    if (!container || container.clientWidth === 0) {
      return;
    }
    anchorRef.current = null;
    setZoom(clampZoom(Math.min(1, (container.clientWidth - 8) / layout.width)));
    container.scrollLeft = 0;
    container.scrollTop = 0;
  }

  // A wide map starts zoomed out just enough to fit (never below 80%).
  useEffect(() => {
    const container = scrollRef.current;
    if (!container || container.clientWidth === 0) {
      return;
    }
    const available = container.clientWidth - 8;
    if (layout.width > available) {
      setZoom(clampZoom(Math.max(INITIAL_MIN_ZOOM, available / layout.width)));
    }
    // Only on first display of this graph.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Ctrl/Cmd + scroll (and a trackpad pinch, which browsers report the same
  // way) zooms. This needs a non-passive listener so the page itself does not
  // zoom; plain scrolling still just moves around.
  useEffect(() => {
    const container = scrollRef.current;
    if (!container) {
      return undefined;
    }

    function handleWheel(event) {
      if (!event.ctrlKey && !event.metaKey) {
        return;
      }
      event.preventDefault();
      const rect = container.getBoundingClientRect();
      zoomByRef.current(Math.exp(-event.deltaY * 0.01), {
        x: event.clientX - rect.left,
        y: event.clientY - rect.top,
      });
    }

    container.addEventListener("wheel", handleWheel, { passive: false });
    return () => container.removeEventListener("wheel", handleWheel);
  }, []);

  /* ---------------------------------------------------------------
     DRAG TO PAN
     --------------------------------------------------------------- */

  function handlePointerDown(event) {
    if (event.button !== 0) {
      return;
    }
    if (event.target.closest && event.target.closest(".kg-mm-topic, .kg-mm-concept")) {
      return;
    }
    const container = scrollRef.current;
    dragRef.current = {
      startX: event.clientX,
      startY: event.clientY,
      scrollLeft: container.scrollLeft,
      scrollTop: container.scrollTop,
      moved: false,
    };
  }

  function handlePointerMove(event) {
    const drag = dragRef.current;
    if (!drag) {
      return;
    }
    const dx = event.clientX - drag.startX;
    const dy = event.clientY - drag.startY;
    if (!drag.moved && Math.abs(dx) + Math.abs(dy) > 4) {
      drag.moved = true;
      // Keep receiving the drag even if the pointer leaves the map. This is
      // done only now, not on press, because a captured pointer sends its
      // click to the capturing element and a plain click must reach the map.
      if (event.currentTarget.setPointerCapture) {
        event.currentTarget.setPointerCapture(event.pointerId);
      }
    }
    if (drag.moved) {
      scrollRef.current.scrollLeft = drag.scrollLeft - dx;
      scrollRef.current.scrollTop = drag.scrollTop - dy;
    }
  }

  function handlePointerEnd(event) {
    const drag = dragRef.current;
    dragRef.current = null;
    if (drag && drag.moved) {
      // The click that ends a drag must not count as "click on the background".
      suppressClickRef.current = true;
      setTimeout(() => {
        suppressClickRef.current = false;
      }, 0);
    }
    if (event.currentTarget.releasePointerCapture) {
      event.currentTarget.releasePointerCapture(event.pointerId);
    }
  }

  /* ---------------------------------------------------------------
     OPEN / CLOSE
     --------------------------------------------------------------- */

  function toggleTopic(topic) {
    setExpanded((current) => {
      const next = new Set(current);
      if (next.has(topic)) {
        next.delete(topic);
      } else {
        next.add(topic);
      }
      return next;
    });
  }

  function expandAll() {
    const all = new Set();
    for (const group of groups) {
      all.add(group.topic);
    }
    setExpanded(all);
  }

  function collapseAll() {
    setExpanded(new Set());
    onSelectNode(null);
  }

  function toggleShowAll() {
    if (!showAll) {
      expandAll();
    }
    setShowAll(!showAll);
  }

  function activateOnKey(event, action) {
    if (event.key === "Enter" || event.key === " ") {
      event.preventDefault();
      action();
    }
  }

  const zoomPercent = Math.round(zoom * 100);
  const showArcLabels = arcs.length <= MAX_LABELLED_ARCS;

  return (
    <div className="kg-mm">
      <div className="kg-mm-toolbar">
        <span className="kg-mm-summary">
          {nodes.length} concepts in {groups.length}{" "}
          {groups.length === 1 ? "topic" : "topics"}
        </span>

        <div className="kg-mm-actions">
          <div className="kg-mm-zoom" role="group" aria-label="Zoom">
            <button
              type="button"
              aria-label="Zoom out"
              onClick={() => zoomTo(zoom / ZOOM_STEP, viewportCentre())}
            >
              −
            </button>

            <button
              type="button"
              className="kg-mm-zoom-level"
              aria-label="Reset zoom to 100%"
              onClick={() => zoomTo(1, viewportCentre())}
            >
              {zoomPercent}%
            </button>

            <button
              type="button"
              aria-label="Zoom in"
              onClick={() => zoomTo(zoom * ZOOM_STEP, viewportCentre())}
            >
              +
            </button>

            <button
              type="button"
              aria-label="Fit to width"
              onClick={fitToWidth}
            >
              Fit
            </button>
          </div>

          <button
            type="button"
            className={showAll ? "kg-mm-toggle-on" : ""}
            aria-pressed={showAll}
            onClick={toggleShowAll}
          >
            Show all connections
          </button>

          <button type="button" onClick={expandAll}>
            Expand all
          </button>

          <button type="button" onClick={collapseAll}>
            Collapse all
          </button>
        </div>
      </div>

      <div
        className="kg-mm-scroll"
        ref={scrollRef}
        onPointerDown={handlePointerDown}
        onPointerMove={handlePointerMove}
        onPointerUp={handlePointerEnd}
        onPointerCancel={handlePointerEnd}
      >
        <svg
          className="kg-mm-svg"
          width={layout.width * zoom}
          height={layout.height * zoom}
          viewBox={`0 0 ${layout.width} ${layout.height}`}
          role="group"
          aria-label="Mind map of the selected document"
          onClick={() => {
            if (!suppressClickRef.current) {
              onSelectNode(null);
            }
          }}
        >
          <defs>
            <marker
              id="kg-mm-arrow-active"
              viewBox="0 0 10 10"
              refX="9"
              refY="5"
              markerWidth="6"
              markerHeight="6"
              orient="auto"
            >
              <path d="M 0 0 L 10 5 L 0 10 z" className="kg-mm-arrow-active" />
            </marker>
          </defs>

          {links.map((link) => {
            const active =
              (link.kind === "topic" && link.topicIndex === selectedTopicIndex) ||
              (link.kind === "concept" && link.nodeId === selectedNodeId);

            return (
              <path
                key={link.key}
                className={`kg-mm-link ${active ? "kg-mm-link-active" : ""}`}
                d={link.path}
              />
            );
          })}

          {/* CONNECTIONS between related concepts */}
          {arcs.map((arc) => {
            const source = nodeById.get(arc.sourceId);
            const target = nodeById.get(arc.targetId);
            const color = arcColors.get(arc.targetId);
            const dimmed = selectedNodeId !== null && !arc.active;
            const className = [
              "kg-mm-arc",
              arc.active ? "kg-mm-arc-active" : "",
              dimmed ? "kg-mm-arc-dim" : "",
            ].join(" ").trim();
            const description =
              source && target
                ? `${source.title} ${arc.label || "relates to"} ${target.title}`
                : arc.label;

            return (
              <g key={arc.key}>
                <path
                  className={className}
                  d={arc.path}
                  stroke={color}
                  markerEnd={arc.active ? "url(#kg-mm-arrow-active)" : undefined}
                />

                {!arc.active && (
                  <circle
                    className={`kg-mm-arc-dot ${dimmed ? "kg-mm-arc-dim" : ""}`}
                    cx={arc.endX}
                    cy={arc.endY}
                    r={4.5}
                    fill={color}
                  />
                )}

                {arc.label && (arc.active || showArcLabels) && (
                  <text
                    className="kg-mm-arc-label"
                    x={arc.labelX}
                    y={arc.labelY}
                    dominantBaseline="central"
                  >
                    {arc.label.length > 22
                      ? `${arc.label.slice(0, 21)}…`
                      : arc.label}
                  </text>
                )}

                <title>{description}</title>
              </g>
            );
          })}

          {/* DOCUMENT (root) */}
          <g className="kg-mm-root">
            <rect
              x={root.x}
              y={root.y}
              width={root.w}
              height={root.h}
              rx={root.h / 2}
            />
            <text
              x={root.x + 16}
              y={root.centerY}
              dominantBaseline="central"
            >
              {fit(documentTitle || "Document", root.w)}
            </text>
            <title>{documentTitle || "Document"}</title>
          </g>

          {/* TOPICS */}
          {topics.map((topic) => {
            const color = topicColors.get(topic.topic);

            return (
              <g
                key={`topic-${topic.topic}`}
                className="kg-mm-topic"
                role="button"
                tabIndex={0}
                aria-expanded={topic.expanded}
                aria-label={`${topic.topic}, ${topic.count} concepts`}
                onClick={(event) => {
                  event.stopPropagation();
                  toggleTopic(topic.topic);
                }}
                onKeyDown={(event) =>
                  activateOnKey(event, () => toggleTopic(topic.topic))
                }
              >
                <rect
                  x={topic.x}
                  y={topic.y}
                  width={topic.w}
                  height={topic.h}
                  rx={topic.h / 2}
                  fill={color}
                />
                <text
                  x={topic.x + 16}
                  y={topic.centerY}
                  dominantBaseline="central"
                >
                  {fit(topic.topic, topic.w, 26)}
                </text>

                <circle
                  className="kg-mm-badge"
                  cx={topic.x + topic.w}
                  cy={topic.centerY}
                  r={12}
                  stroke={color}
                />
                <text
                  className="kg-mm-badge-text"
                  x={topic.x + topic.w}
                  y={topic.centerY}
                  textAnchor="middle"
                  dominantBaseline="central"
                >
                  {topic.expanded ? "−" : topic.count}
                </text>
                <title>{topic.topic}</title>
              </g>
            );
          })}

          {/* CONCEPTS */}
          {concepts.map((concept) => {
            const node = concept.node;
            const color = topicColors.get(concept.topic);
            const isSelected = node.id === selectedNodeId;
            const isRelated = relatedIds.has(node.id);
            const className = [
              "kg-mm-concept",
              isSelected ? "kg-mm-concept-selected" : "",
              isRelated ? "kg-mm-concept-related" : "",
            ].join(" ").trim();
            const description = (node.description || "").trim();

            return (
              <g
                key={`concept-${node.id}`}
                className={className}
                role="button"
                tabIndex={0}
                aria-pressed={isSelected}
                aria-label={`${node.title}. ${description ? `${description}. ` : ""}Topic ${concept.topic}.`}
                onClick={(event) => {
                  event.stopPropagation();
                  onSelectNode(isSelected ? null : node.id);
                }}
                onKeyDown={(event) =>
                  activateOnKey(event, () => onSelectNode(node.id))
                }
              >
                <rect
                  x={concept.x}
                  y={concept.y}
                  width={concept.w}
                  height={concept.h}
                  rx={12}
                  fill={color}
                  fillOpacity={0.16}
                  stroke={color}
                />
                <text
                  x={concept.x + 14}
                  y={description ? concept.y + 19 : concept.centerY}
                  dominantBaseline="central"
                >
                  {fit(node.title, concept.w)}
                </text>
                {description && (
                  <text
                    className="kg-mm-concept-sub"
                    x={concept.x + 14}
                    y={concept.y + 37}
                    dominantBaseline="central"
                  >
                    {fit(description, concept.w, 0, 6.3)}
                  </text>
                )}
                <title>{description ? `${node.title}\n${description}` : node.title}</title>
              </g>
            );
          })}
        </svg>
      </div>

      <p className="kg-mm-hint">
        Click a topic to open or close it. Select a concept to see what it
        connects to. Hold Ctrl or Cmd and scroll, or pinch, to zoom, and drag
        the background to move around.
      </p>
    </div>
  );
}

export default KnowledgeGraphView;
