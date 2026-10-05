/*
 * Smart Peer Companion
 * Knowledge Graph mind map layout
 *
 * Arranges a document's concepts as a left to right mind map, the way
 * NotebookLM does it:
 *
 *   document  ->  topics  ->  concepts
 *
 * Every concept belongs to one topic. A topic can be collapsed (only the
 * topic box is shown) or expanded (its concepts appear to its right). The
 * layout is a plain deterministic calculation: no randomness, no animation,
 * and it stays tidy at any size, because each concept simply gets its own row.
 */

export const MIND_MAP = {
  PAD: 28,
  ROOT_W: 224,
  TOPIC_W: 240,
  CONCEPT_W: 340,
  NODE_H: 38,
  // Concept boxes show a title and a line of description (for example a grade).
  CONCEPT_H: 52,
  ROW: 62,
  GROUP_GAP: 18,
  COLUMN_GAP: 60,
  // Room to the right of the concept column for connection arcs and labels.
  ARC_SPACE: 170,
};

/** The topic a concept is filed under; empty topics become "General". */
export function topicOf(node) {
  const topic = (node.topic || "").trim();
  return topic || "General";
}

/** Concepts grouped by topic, in order of first appearance. */
export function groupByTopic(nodes) {
  const groups = [];
  const indexByTopic = new Map();

  for (const node of nodes) {
    const topic = topicOf(node);
    if (!indexByTopic.has(topic)) {
      indexByTopic.set(topic, groups.length);
      groups.push({ topic, nodes: [] });
    }
    groups[indexByTopic.get(topic)].nodes.push(node);
  }

  return groups;
}

function curve(x1, y1, x2, y2) {
  const middle = (x1 + x2) / 2;
  return `M ${x1} ${y1} C ${middle} ${y1}, ${middle} ${y2}, ${x2} ${y2}`;
}

/**
 * @param {{topic: string, nodes: object[]}[]} groups from groupByTopic
 * @param {Set<string>} expandedTopics topics whose concepts are shown
 */
export function layoutMindMap(groups, expandedTopics) {
  const {
    PAD, ROOT_W, TOPIC_W, CONCEPT_W, NODE_H, CONCEPT_H, ROW, GROUP_GAP, COLUMN_GAP, ARC_SPACE,
  } = MIND_MAP;

  const rootX = PAD;
  const topicX = rootX + ROOT_W + COLUMN_GAP;
  const conceptX = topicX + TOPIC_W + COLUMN_GAP;

  const topics = [];
  const concepts = [];
  let y = PAD;
  let anyExpanded = false;

  for (let groupIndex = 0; groupIndex < groups.length; groupIndex += 1) {
    const group = groups[groupIndex];
    const expanded = expandedTopics.has(group.topic);
    const visibleCount = expanded ? group.nodes.length : 0;
    const groupHeight = Math.max(1, visibleCount) * ROW;
    const topicCenterY = y + groupHeight / 2;

    topics.push({
      topic: group.topic,
      index: groupIndex,
      count: group.nodes.length,
      expanded,
      x: topicX,
      y: topicCenterY - NODE_H / 2,
      w: TOPIC_W,
      h: NODE_H,
      centerY: topicCenterY,
    });

    if (expanded) {
      anyExpanded = true;
      for (let i = 0; i < group.nodes.length; i += 1) {
        const centerY = y + ROW * (i + 0.5);
        concepts.push({
          node: group.nodes[i],
          topic: group.topic,
          topicIndex: groupIndex,
          x: conceptX,
          y: centerY - CONCEPT_H / 2,
          w: CONCEPT_W,
          h: CONCEPT_H,
          centerY,
        });
      }
    }

    y += groupHeight + GROUP_GAP;
  }

  const contentBottom = groups.length > 0 ? y - GROUP_GAP : PAD + NODE_H;
  const height = contentBottom + PAD;
  const width =
    (anyExpanded ? conceptX + CONCEPT_W + ARC_SPACE : topicX + TOPIC_W) + PAD;

  const rootCenterY = topics.length > 0
    ? (topics[0].centerY + topics[topics.length - 1].centerY) / 2
    : PAD + NODE_H / 2;

  const root = {
    x: rootX,
    y: rootCenterY - NODE_H / 2,
    w: ROOT_W,
    h: NODE_H,
    centerY: rootCenterY,
  };

  const links = [];
  for (const topic of topics) {
    links.push({
      key: `root-${topic.index}`,
      kind: "topic",
      topicIndex: topic.index,
      path: curve(root.x + root.w, root.centerY, topic.x, topic.centerY),
    });
  }
  for (const concept of concepts) {
    const topic = topics[concept.topicIndex];
    links.push({
      key: `topic-${concept.node.id}`,
      kind: "concept",
      topicIndex: concept.topicIndex,
      nodeId: concept.node.id,
      path: curve(topic.x + topic.w, topic.centerY, concept.x, concept.centerY),
    });
  }

  return { width, height, root, topics, concepts, links };
}

/**
 * Curved arcs joining related concepts, drawn to the right of the concept
 * column so they never cross the boxes.
 *
 * An arc is only drawn when BOTH of its concepts are currently visible (their
 * topics are open). By default only the selected concept's connections are
 * drawn; showAll draws every connection.
 */
export function layoutConnections(
  layout,
  edges,
  { selectedNodeId = null, showAll = false } = {},
) {
  const conceptById = new Map();
  for (const concept of layout.concepts) {
    conceptById.set(concept.node.id, concept);
  }

  const existing = new Set();
  for (const edge of edges) {
    existing.add(`${edge.source_node_id}>${edge.target_node_id}`);
  }

  const arcs = [];
  for (const edge of edges) {
    const from = conceptById.get(edge.source_node_id);
    const to = conceptById.get(edge.target_node_id);
    if (!from || !to || from === to) {
      continue;
    }

    const touchesSelection =
      selectedNodeId !== null &&
      (edge.source_node_id === selectedNodeId ||
        edge.target_node_id === selectedNodeId);

    if (!showAll && !touchesSelection) {
      continue;
    }

    const edgeX = from.x + from.w;
    const distance = Math.abs(to.centerY - from.centerY);
    let bulge = Math.min(34 + distance * 0.12, 100);

    // Two edges between the same pair, one each way, must not coincide.
    const hasReverse = existing.has(`${edge.target_node_id}>${edge.source_node_id}`);
    if (hasReverse && edge.source_node_id > edge.target_node_id) {
      bulge += 16;
    }

    arcs.push({
      key: `arc-${edge.id}`,
      edgeId: edge.id,
      sourceId: edge.source_node_id,
      targetId: edge.target_node_id,
      label: edge.label || "",
      active: touchesSelection,
      path:
        `M ${edgeX} ${from.centerY} ` +
        `C ${edgeX + bulge} ${from.centerY}, ${edgeX + bulge} ${to.centerY}, ` +
        `${edgeX + 3} ${to.centerY}`,
      endX: edgeX + 3,
      endY: to.centerY,
      labelX: edgeX + bulge * 0.75 + 6,
      labelY: (from.centerY + to.centerY) / 2,
    });
  }

  return arcs;
}
