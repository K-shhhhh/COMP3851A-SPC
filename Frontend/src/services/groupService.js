import { integrationConfig } from "../config/integration.js";
import { apiRequest } from "./apiClient.js";
import { createWebSocketTicket } from "./authService.js";

/*
 * =========================================================
 * QUERY HELPER
 * =========================================================
 */

function buildQuery(params) {
  const searchParams = new URLSearchParams();

  Object.entries(params).forEach(([key, value]) => {
    if (
      value !== undefined &&
      value !== null &&
      value !== ""
    ) {
      searchParams.set(key, String(value));
    }
  });

  const query = searchParams.toString();

  return query ? `?${query}` : "";
}

/*
 * =========================================================
 * STUDY GROUPS
 * =========================================================
 */

/**
 * Discover active public groups.
 *
 * GET /study-groups/discover
 */
export function discoverPublicGroups(
  accessToken,
  {
    page = 1,
    pageSize = 20,
    search = "",
  } = {},
) {
  const query = buildQuery({
    page,
    page_size: pageSize,
    search,
  });

  return apiRequest(
    `/study-groups/discover${query}`,
    {
      method: "GET",
      accessToken,
    },
  );
}

/**
 * Get groups that the current user owns
 * or has joined.
 *
 * GET /study-groups/mine
 *
 * Supported filters:
 * all
 * public
 * private
 * owned
 */
export function getMyGroups(
  accessToken,
  {
    filter = "all",
    page = 1,
    pageSize = 20,
  } = {},
) {
  const query = buildQuery({
    filter,
    page,
    page_size: pageSize,
  });

  return apiRequest(
    `/study-groups/mine${query}`,
    {
      method: "GET",
      accessToken,
    },
  );
}

/**
 * Create a study group.
 *
 * POST /study-groups
 */
export function createStudyGroup(
  accessToken,
  payload,
) {
  return apiRequest("/study-groups", {
    method: "POST",
    accessToken,
    body: JSON.stringify(payload),
  });
}

/**
 * Get one study group.
 *
 * GET /study-groups/{groupId}
 */
export function getStudyGroup(
  accessToken,
  groupId,
) {
  return apiRequest(
    `/study-groups/${groupId}`,
    {
      method: "GET",
      accessToken,
    },
  );
}

/**
 * Update a study group.
 *
 * PUT /study-groups/{groupId}
 *
 * Backend expects all editable fields.
 */
export function updateStudyGroup(
  accessToken,
  groupId,
  payload,
) {
  return apiRequest(
    `/study-groups/${groupId}`,
    {
      method: "PUT",
      accessToken,
      body: JSON.stringify(payload),
    },
  );
}

/**
 * Delete a study group.
 *
 * DELETE /study-groups/{groupId}
 */
export function deleteStudyGroup(
  accessToken,
  groupId,
) {
  return apiRequest(
    `/study-groups/${groupId}`,
    {
      method: "DELETE",
      accessToken,
    },
  );
}

/**
 * Join a public group.
 *
 * POST /study-groups/{groupId}/join
 */
export function joinStudyGroup(
  accessToken,
  groupId,
) {
  return apiRequest(
    `/study-groups/${groupId}/join`,
    {
      method: "POST",
      accessToken,
    },
  );
}

/*
 * =========================================================
 * MEMBERS
 * =========================================================
 */

/**
 * Get group members.
 *
 * GET /study-groups/{groupId}/members
 */
export function getStudyGroupMembers(
  accessToken,
  groupId,
  {
    page = 1,
    pageSize = 20,
  } = {},
) {
  const query = buildQuery({
    page,
    page_size: pageSize,
  });

  return apiRequest(
    `/study-groups/${groupId}/members${query}`,
    {
      method: "GET",
      accessToken,
    },
  );
}

/**
 * Add a registered student to a group by email.
 *
 * Mainly used for private groups.
 *
 * POST /study-groups/{groupId}/members
 */
export function addStudyGroupMember(
  accessToken,
  groupId,
  email,
) {
  return apiRequest(
    `/study-groups/${groupId}/members`,
    {
      method: "POST",
      accessToken,
      body: JSON.stringify({
        email,
      }),
    },
  );
}

/**
 * Remove an ordinary member.
 *
 * DELETE /study-groups/{groupId}/members/{userId}
 */
export function removeStudyGroupMember(
  accessToken,
  groupId,
  userId,
) {
  return apiRequest(
    `/study-groups/${groupId}/members/${userId}`,
    {
      method: "DELETE",
      accessToken,
    },
  );
}

/**
 * Leave a study group.
 *
 * DELETE /study-groups/{groupId}/members/me
 */
export function leaveStudyGroup(
  accessToken,
  groupId,
) {
  return apiRequest(
    `/study-groups/${groupId}/members/me`,
    {
      method: "DELETE",
      accessToken,
    },
  );
}

/*
 * =========================================================
 * CHANNELS
 * =========================================================
 */

/**
 * Get group channels.
 *
 * GET /study-groups/{groupId}/channels
 */
export function getStudyGroupChannels(
  accessToken,
  groupId,
  {
    page = 1,
    pageSize = 20,
  } = {},
) {
  const query = buildQuery({
    page,
    page_size: pageSize,
  });

  return apiRequest(
    `/study-groups/${groupId}/channels${query}`,
    {
      method: "GET",
      accessToken,
    },
  );
}

/**
 * Create a group channel.
 *
 * POST /study-groups/{groupId}/channels
 *
 * payload:
 * {
 *   name,
 *   description
 * }
 */
export function createStudyGroupChannel(
  accessToken,
  groupId,
  payload,
) {
  return apiRequest(
    `/study-groups/${groupId}/channels`,
    {
      method: "POST",
      accessToken,
      body: JSON.stringify(payload),
    },
  );
}

/**
 * Get one channel.
 *
 * GET /study-groups/{groupId}/channels/{channelId}
 */
export function getStudyGroupChannel(
  accessToken,
  groupId,
  channelId,
) {
  return apiRequest(
    `/study-groups/${groupId}/channels/${channelId}`,
    {
      method: "GET",
      accessToken,
    },
  );
}

/**
 * Update channel.
 *
 * PUT /study-groups/{groupId}/channels/{channelId}
 */
export function updateStudyGroupChannel(
  accessToken,
  groupId,
  channelId,
  payload,
) {
  return apiRequest(
    `/study-groups/${groupId}/channels/${channelId}`,
    {
      method: "PUT",
      accessToken,
      body: JSON.stringify(payload),
    },
  );
}

/**
 * Delete channel.
 *
 * DELETE /study-groups/{groupId}/channels/{channelId}
 */
export function deleteStudyGroupChannel(
  accessToken,
  groupId,
  channelId,
) {
  return apiRequest(
    `/study-groups/${groupId}/channels/${channelId}`,
    {
      method: "DELETE",
      accessToken,
    },
  );
}

/*
 * =========================================================
 * GROUP MESSAGES
 * =========================================================
 */

/**
 * Get messages from a channel.
 *
 * GET
 * /study-groups/{groupId}/channels/{channelId}/messages
 */
export function getGroupMessages(
  accessToken,
  groupId,
  channelId,
  {
    page = 1,
    pageSize = 50,
  } = {},
) {
  const query = buildQuery({
    page,
    page_size: pageSize,
  });

  return apiRequest(
    `/study-groups/${groupId}/channels/${channelId}/messages${query}`,
    {
      method: "GET",
      accessToken,
    },
  );
}

/**
 * Create a channel message.
 *
 * POST
 * /study-groups/{groupId}/channels/{channelId}/messages
 *
 * Normal message:
 * {
 *   content,
 *   mentioned_user_ids: []
 * }
 *
 * AI message:
 * {
 *   content,
 *   mentioned_user_ids: [],
 *   ai_mode,
 *   response_format
 * }
 */
export function createGroupMessage(
  accessToken,
  groupId,
  channelId,
  {
    content,
    mentionedUserIds = [],
    aiMode = null,
    responseFormat = null,
  },
) {
  const body = {
    content,
    mentioned_user_ids:
      mentionedUserIds,
  };

  /*
   * Do not send AI fields for an ordinary
   * human message.
   */
  if (aiMode) {
    body.ai_mode = aiMode;

    if (responseFormat) {
      body.response_format =
        responseFormat;
    }
  }

  return apiRequest(
    `/study-groups/${groupId}/channels/${channelId}/messages`,
    {
      method: "POST",
      accessToken,
      body: JSON.stringify(body),
    },
  );
}

/**
 * Get one message.
 *
 * GET
 * /study-groups/{groupId}/channels/{channelId}/messages/{messageId}
 */
export function getGroupMessage(
  accessToken,
  groupId,
  channelId,
  messageId,
) {
  return apiRequest(
    `/study-groups/${groupId}/channels/${channelId}/messages/${messageId}`,
    {
      method: "GET",
      accessToken,
    },
  );
}

/**
 * Update a message.
 *
 * PUT
 * /study-groups/{groupId}/channels/{channelId}/messages/{messageId}
 *
 * AI-invoking messages should not be edited.
 */
export function updateGroupMessage(
  accessToken,
  groupId,
  channelId,
  messageId,
  content,
  mentionedUserIds = [],
) {
  return apiRequest(
    `/study-groups/${groupId}/channels/${channelId}/messages/${messageId}`,
    {
      method: "PUT",
      accessToken,
      body: JSON.stringify({
        content,
        mentioned_user_ids:
          mentionedUserIds,
      }),
    },
  );
}

/**
 * Delete a message.
 *
 * DELETE
 * /study-groups/{groupId}/channels/{channelId}/messages/{messageId}
 */
export function deleteGroupMessage(
  accessToken,
  groupId,
  channelId,
  messageId,
) {
  return apiRequest(
    `/study-groups/${groupId}/channels/${channelId}/messages/${messageId}`,
    {
      method: "DELETE",
      accessToken,
    },
  );
}

/*
 * =========================================================
 * REAL-TIME CHANNEL WEBSOCKET
 * =========================================================
 */

/**
 * Connect to a Study Group channel WebSocket.
 *
 * A fresh short-lived WebSocket ticket is requested
 * before every connection.
 *
 * JWT access token is NEVER placed in the WebSocket URL.
 */
export async function connectStudyGroupChannel(
  accessToken,
  groupId,
  channelId,
  handlers = {},
) {
  /*
   * createWebSocketTicket already exists in authService.js.
   * Do not declare another function with that name here.
   */
  const ticketResponse =
    await createWebSocketTicket(
      accessToken,
    );

  const ticket =
    ticketResponse.ticket;

  if (!ticket) {
    throw new Error(
      "WebSocket ticket was not returned by the server.",
    );
  }

  const baseUrl =
    integrationConfig.webSocketBaseUrl;

  const url =
    `${baseUrl}` +
    `/ws/study-groups/${encodeURIComponent(
      groupId,
    )}` +
    `/channels/${encodeURIComponent(
      channelId,
    )}` +
    `?ticket=${encodeURIComponent(
      ticket,
    )}`;

  const socket =
    new WebSocket(url);

  let active = true;

  /*
   * Connection opened.
   */
  socket.addEventListener(
    "open",
    () => {
      if (!active) return;

      handlers.onOpen?.();
    },
  );

  /*
   * Message/event received.
   */
  socket.addEventListener(
    "message",
    (event) => {
      if (!active) return;

      try {
        const data =
          JSON.parse(event.data);

        handlers.onMessage?.(
          data,
        );
      } catch (error) {
        handlers.onError?.(
          error,
        );
      }
    },
  );

  /*
   * WebSocket error.
   */
  socket.addEventListener(
    "error",
    (event) => {
      if (!active) return;

      handlers.onError?.(
        event,
      );
    },
  );

  /*
   * Connection closed.
   */
  socket.addEventListener(
    "close",
    (event) => {
      if (!active) return;

      handlers.onClose?.(
        event,
      );
    },
  );

  /*
   * Return cleanup function.
   *
   * GroupStudyPage calls this when the user changes
   * channel/group or when the component unmounts.
   */
  return () => {
    active = false;

    if (
      socket.readyState ===
        WebSocket.OPEN ||
      socket.readyState ===
        WebSocket.CONNECTING
    ) {
      socket.close(
        1000,
        "Component unsubscribed",
      );
    }
  };
}