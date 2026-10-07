
import {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";

import {
  Bot,
  ChevronLeft,
  ChevronRight,
  Edit3,
  Hash,
  Lock,
  Paperclip,
  Plus,
  Search,
  Send,
  Trash2,
  UserMinus,
  Users,
  X,
} from "lucide-react";

import {
  useSearchParams,
} from "react-router-dom";

import AppShell from "../../components/layout/AppShell.jsx";
import {
  useConfirmModal,
} from "../../components/common/ConfirmModal.jsx";
import { useAuth } from "../../contexts/AuthContext.jsx";
import SimpleMarkdown from "../../components/chat/SimpleMarkdown.jsx";

import {
  addStudyGroupMember,
  connectStudyGroupChannel,
  createGroupMessage,
  createStudyGroup,
  createStudyGroupChannel,
  deleteGroupMessage,
  deleteStudyGroup,
  deleteStudyGroupChannel,
  discoverPublicGroups,
  getGroupMessages,
  getMyGroups,
  getStudyGroupAttachmentStatus,
  getStudyGroupChannels,
  getStudyGroupMembers,
  joinStudyGroup,
  leaveStudyGroup,
  removeStudyGroupMember,
  updateGroupMessage,
  updateStudyGroup,
  updateStudyGroupChannel,
  uploadStudyGroupAttachment,
} from "../../services/groupService.js";

import "./groupStudy.css";
import "./groupStudyPanels.css";

/* =========================================================
   CONSTANTS
   ========================================================= */

const AI_MODES = [
  {
    label: "Companion",
    value: "default",
  },
  {
    label: "Summarizer",
    value: "summarizer",
  },
  {
    label: "QuizMaster",
    value: "quiz",
  },
  {
    label: "Facilitator",
    value: "facilitator",
  },
];


/* =========================================================
   HELPERS
   ========================================================= */


function formatElapsedTime(seconds) {
  const minutes = Math.floor(seconds / 60);
  const remainingSeconds = seconds % 60;

  if (minutes === 0) {
    return `${remainingSeconds}s`;
  }

  return `${minutes}:${String(remainingSeconds).padStart(2, "0")}`;
}

function initials(name = "?") {
  return name
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((part) => part[0])
    .join("")
    .toUpperCase();
}

function timeLabel(value) {
  if (!value) return "";

  return new Date(value).toLocaleTimeString([], {
    hour: "2-digit",
    minute: "2-digit",
  });
}

function apiMessage(error) {
  const messages = {
    STUDY_GROUP_PERMISSION_DENIED:
      "Owner or administrator access is required.",

    PRIVATE_GROUP_INVITATION_REQUIRED:
      "Private groups can only be joined by invitation.",

    STUDY_GROUP_TARGET_USER_NOT_FOUND:
      "No active student was found with that email address.",

    STUDY_GROUP_FULL:
      "This group is full.",

    STUDY_GROUP_CHANNEL_NAME_CONFLICT:
      "A channel with this name already exists.",

    STUDY_GROUP_MENTIONED_USER_NOT_MEMBER:
      "One of the mentioned users is no longer a group member.",

    STUDY_GROUP_NO_READY_CHUNKS:
      "The selected channel does not yet have a ready processed PDF.",

    STUDY_GROUP_ANSWER_GENERATION_FAILED:
      "The AI companion could not generate an answer. Please try again.",

    STUDY_GROUP_AI_UNAVAILABLE:
      "The AI companion is temporarily unavailable.",

    VALIDATION_ERROR:
      "Please check the information you entered.",
  };

  return (
    messages[error?.code] ||
    error?.message ||
    "Something went wrong. Please try again."
  );
}

function extractItems(result) {
  if (Array.isArray(result)) {
    return result;
  }

  return (
    result?.items ||
    result?.groups ||
    result?.members ||
    result?.channels ||
    result?.messages ||
    []
  );
}

/* =========================================================
   SIMPLE MARKDOWN FOR STUDY GROUP AI RESPONSES

   Moved to components/chat/SimpleMarkdown.jsx so Companion chat
   can use the same renderer instead of duplicating this file.
   ========================================================= */


/* =========================================================
   MODAL
   ========================================================= */

function Modal({
  title,
  children,
  onClose,
}) {
  return (
    <div
      className="sg-modal-overlay"
      onMouseDown={(event) => {
        if (event.target === event.currentTarget) {
          onClose();
        }
      }}
    >
      <div className="sg-modal">
        <div className="sg-modal-head">
          <h2>{title}</h2>

          <button
            type="button"
            onClick={onClose}
          >
            <X size={18} />
          </button>
        </div>

        {children}
      </div>
    </div>
  );
}

/* =========================================================
   PAGE
   ========================================================= */

function GroupStudyPage() {
  const [
    searchParams,
    setSearchParams,
  ] = useSearchParams();

  const {
    accessToken,
    user,
  } = useAuth();

  const {
    requestConfirmation,
    confirmModal,
  } = useConfirmModal();

  /* -------------------------------------------------------
     GROUP LIST STATE
     ------------------------------------------------------- */

  const [activeView, setActiveView] =
    useState("discover");

  const [discoverGroups, setDiscoverGroups] =
    useState([]);

  const [myGroups, setMyGroups] =
    useState([]);

  const [myFilter, setMyFilter] =
    useState("all");

  const [search, setSearch] =
    useState("");

  const [selectedGroup, setSelectedGroup] =
    useState(null);

  const [groupsLoading, setGroupsLoading] =
    useState(false);

  const [pageError, setPageError] =
    useState("");

  const [mutationLoading, setMutationLoading] =
    useState(false);

  const [
    groupsPanelCollapsed,
    setGroupsPanelCollapsed,
  ] = useState(false);

  const [
    detailsPanelCollapsed,
    setDetailsPanelCollapsed,
  ] = useState(false);

  /* -------------------------------------------------------
     GROUP FORM
     ------------------------------------------------------- */

  const [groupModal, setGroupModal] =
    useState(null);

  const [groupForm, setGroupForm] =
    useState({
      name: "",
      description: "",
      visibility: "public",
      max_members: 30,
    });

  /* -------------------------------------------------------
     MEMBERS
     ------------------------------------------------------- */

  const [members, setMembers] =
    useState([]);

  const [membersLoading, setMembersLoading] =
    useState(false);

  const [memberEmail, setMemberEmail] =
    useState("");

  /* -------------------------------------------------------
     CHANNELS
     ------------------------------------------------------- */

  const [channels, setChannels] =
    useState([]);

  const [channelsLoading, setChannelsLoading] =
    useState(false);

  const [selectedChannel, setSelectedChannel] =
    useState(null);

  const [channelModal, setChannelModal] =
    useState(null);

  const [channelForm, setChannelForm] =
    useState({
      name: "",
      description: "",
    });

  /* -------------------------------------------------------
     MESSAGES
     ------------------------------------------------------- */

  const [messages, setMessages] =
    useState([]);

  const [messagesLoading, setMessagesLoading] =
    useState(false);

  const [message, setMessage] =
    useState("");

  const [sendingMessage, setSendingMessage] =
    useState(false);

  const [aiWaitSeconds, setAiWaitSeconds] =
    useState(0);

  const [aiWaiting, setAiWaiting] =
    useState(false);

  const [aiWaitingMessageId, setAiWaitingMessageId] =
    useState(null);

  /* -------------------------------------------------------
     CHANNEL ATTACHMENT
     ------------------------------------------------------- */

  const ATTACHMENT_JOBS_STORAGE_KEY = "spc.studyGroupAttachmentJobs";

  const readStoredAttachmentJobs = () => {
    try {
      const raw = window.sessionStorage.getItem(ATTACHMENT_JOBS_STORAGE_KEY);
      return raw ? JSON.parse(raw) : {};
    } catch {
      return {};
    }
  };

  const writeStoredAttachmentJobs = (jobs) => {
    try {
      window.sessionStorage.setItem(
        ATTACHMENT_JOBS_STORAGE_KEY,
        JSON.stringify(jobs),
      );
    } catch {
      // sessionStorage may be unavailable in restricted browser modes.
    }
  };

  const [attachmentJobs, setAttachmentJobs] =
    useState(() => readStoredAttachmentJobs());

  const [attachmentClock, setAttachmentClock] =
    useState(() => Date.now());

  const attachmentInputRef = useRef(null);
  const attachmentPollRefs = useRef({});

  const currentAttachmentKey =
    selectedGroup?.id && selectedChannel?.id
      ? `${selectedGroup.id}:${selectedChannel.id}`
      : null;

  const attachment = currentAttachmentKey
    ? attachmentJobs[currentAttachmentKey] || null
    : null;

  const attachmentUploading =
    attachment?.status === "uploading";

  const attachmentElapsedSeconds = attachment?.startedAt
    ? Math.max(
        0,
        Math.floor(
          ((attachment.finishedAt || attachmentClock) -
            attachment.startedAt) /
            1000,
        ),
      )
    : 0;

  const [editingMessage, setEditingMessage] =
    useState(null);

  const [editingMessageValue, setEditingMessageValue] =
    useState("");

  /* -------------------------------------------------------
     RESPONSE TIMERS
     ------------------------------------------------------- */

  useEffect(() => {
    if (!aiWaiting) {
      return undefined;
    }

    const interval = window.setInterval(() => {
      setAiWaitSeconds((current) => current + 1);
    }, 1000);

    return () => {
      window.clearInterval(interval);
    };
  }, [aiWaiting]);

  useEffect(() => {
    writeStoredAttachmentJobs(attachmentJobs);

    const hasActiveAttachment = Object.values(attachmentJobs).some(
      (job) =>
        job.status === "uploading" ||
        job.status === "queued" ||
        job.status === "processing",
    );

    if (!hasActiveAttachment) {
      return undefined;
    }

    setAttachmentClock(Date.now());

    const interval = window.setInterval(() => {
      setAttachmentClock(Date.now());
    }, 1000);

    return () => {
      window.clearInterval(interval);
    };
  }, [attachmentJobs]);

  /* -------------------------------------------------------
     MENTIONS / AI
     ------------------------------------------------------- */

  const [showMentionMenu, setShowMentionMenu] =
    useState(false);

  const [
    activeMentionIndex,
    setActiveMentionIndex,
  ] = useState(0);

  const [selectedMentionIds, setSelectedMentionIds] =
    useState([]);

  const [selectedAiMode, setSelectedAiMode] =
    useState(null);

  const [responseFormat, setResponseFormat] =
    useState("paragraph");

  const messagesEndRef = useRef(null);

  const mentionPickerRef =
    useRef(null);

  const mentionMatch =
    message.match(
      /(?:^|\s)@([^\s@]*)$/,
    );

  const mentionQuery =
    (mentionMatch?.[1] || "")
      .trim()
      .toLowerCase();

  const filteredAiModes =
    useMemo(
      () =>
        AI_MODES.filter((ai) =>
          ai.label
            .toLowerCase()
            .startsWith(
              mentionQuery,
            ),
        ),
      [mentionQuery],
    );

  const filteredMentionMembers =
    useMemo(
      () =>
        members.filter((member) => {
          const name =
            member.full_name || "";

          const email =
            member.email || "";

          return (
            name
              .toLowerCase()
              .startsWith(
                mentionQuery,
              ) ||
            email
              .toLowerCase()
              .startsWith(
                mentionQuery,
              )
          );
        }),
      [
        members,
        mentionQuery,
      ],
    );

  const mentionOptions =
    useMemo(
      () => [
        ...filteredAiModes.map(
          (ai) => ({
            type: "ai",
            item: ai,
          }),
        ),
        ...filteredMentionMembers.map(
          (member) => ({
            type: "member",
            item: member,
          }),
        ),
      ],
      [
        filteredAiModes,
        filteredMentionMembers,
      ],
    );

  const hasMentionMatches =
    mentionOptions.length > 0;

  useEffect(() => {
    setActiveMentionIndex(0);
  }, [
    mentionQuery,
    showMentionMenu,
  ]);

  useEffect(() => {
    if (!showMentionMenu) {
      return undefined;
    }

    function handleOutsidePointer(
      event,
    ) {
      if (
        mentionPickerRef.current &&
        !mentionPickerRef.current.contains(
          event.target,
        )
      ) {
        setShowMentionMenu(false);
      }
    }

    document.addEventListener(
      "pointerdown",
      handleOutsidePointer,
    );

    return () => {
      document.removeEventListener(
        "pointerdown",
        handleOutsidePointer,
      );
    };
  }, [showMentionMenu]);

  /* =======================================================
     SIDEBAR / URL VIEW SYNC
     ======================================================= */

  const requestedGroupView =
    searchParams.get("view");

  useEffect(() => {
    if (
      requestedGroupView ===
      "private"
    ) {
      setActiveView("mine");
      setMyFilter("private");
      setSelectedGroup(null);
      return;
    }

    if (
      requestedGroupView ===
      "public"
    ) {
      setActiveView("discover");
      setSelectedGroup(null);
    }
  }, [requestedGroupView]);

  /* =======================================================
     DISCOVER PUBLIC GROUPS
     ======================================================= */

  const loadDiscover = useCallback(async () => {
    if (!accessToken) return;

    setGroupsLoading(true);
    setPageError("");

    try {
      const result =
        await discoverPublicGroups(
          accessToken,
          {
            page: 1,

            // Backend pagination limit.
            pageSize: 20,

            search,
          },
        );

      setDiscoverGroups(
        extractItems(result),
      );
    } catch (error) {
      setPageError(apiMessage(error));
    } finally {
      setGroupsLoading(false);
    }
  }, [accessToken, search]);

  /* =======================================================
     MY GROUPS
     ======================================================= */

  const loadMyGroups = useCallback(async () => {
    if (!accessToken) return;

    setGroupsLoading(true);
    setPageError("");

    try {
      const result =
        await getMyGroups(
          accessToken,
          {
            filter: myFilter,
            page: 1,

            // Backend pagination limit.
            pageSize: 20,
          },
        );

      setMyGroups(
        extractItems(result),
      );
    } catch (error) {
      setPageError(apiMessage(error));
    } finally {
      setGroupsLoading(false);
    }
  }, [accessToken, myFilter]);

  useEffect(() => {
    if (activeView === "discover") {
      loadDiscover();
    } else {
      loadMyGroups();
    }
  }, [
    activeView,
    loadDiscover,
    loadMyGroups,
  ]);

  /* =======================================================
     REFRESH GROUP LISTS
     ======================================================= */

  const refreshGroupLists =
    useCallback(async () => {
      await Promise.all([
        loadDiscover(),
        loadMyGroups(),
      ]);
    }, [
      loadDiscover,
      loadMyGroups,
    ]);

  /* =======================================================
     MEMBERS
     ======================================================= */

  async function loadMembers(
    group = selectedGroup,
  ) {
    if (!group || !accessToken) {
      return;
    }

    setMembersLoading(true);

    try {
      const result =
        await getStudyGroupMembers(
          accessToken,
          group.id,
          {
            page: 1,
            pageSize: 20,
          },
        );

      setMembers(
        extractItems(result),
      );
    } catch (error) {
      setPageError(apiMessage(error));
    } finally {
      setMembersLoading(false);
    }
  }

  /* =======================================================
     CHANNELS
     ======================================================= */

  async function loadChannels(
    group = selectedGroup,
  ) {
    if (!group || !accessToken) {
      return;
    }

    setChannelsLoading(true);

    try {
      const result =
        await getStudyGroupChannels(
          accessToken,
          group.id,
          {
            page: 1,
            pageSize: 20,
          },
        );

      const loadedChannels =
        extractItems(result);

      setChannels(loadedChannels);

      if (loadedChannels.length > 0) {
        setSelectedChannel(
          loadedChannels[0],
        );
      } else {
        setSelectedChannel(null);
        setMessages([]);
      }
    } catch (error) {
      setPageError(apiMessage(error));
    } finally {
      setChannelsLoading(false);
    }
  }

  /* =======================================================
     OPEN GROUP
     ======================================================= */

  async function openGroup(group) {
    if (!group.is_member) {
      return;
    }

    setSelectedGroup(group);
    setSelectedChannel(null);

    setChannels([]);
    setMembers([]);
    setMessages([]);

    setPageError("");

    await Promise.all([
      loadMembers(group),
      loadChannels(group),
    ]);
  }

  /* =======================================================
     LOAD MESSAGES
     ======================================================= */

  const loadMessages =
    useCallback(async () => {
      if (
        !accessToken ||
        !selectedGroup ||
        !selectedChannel
      ) {
        return;
      }

      setMessagesLoading(true);

      try {
        const result =
          await getGroupMessages(
            accessToken,
            selectedGroup.id,
            selectedChannel.id,
            {
              page: 1,
              pageSize: 50,
            },
          );

        setMessages(
          extractItems(result),
        );
      } catch (error) {
        setPageError(apiMessage(error));
      } finally {
        setMessagesLoading(false);
      }
    }, [
      accessToken,
      selectedGroup,
      selectedChannel,
    ]);

  useEffect(() => {
    if (selectedChannel) {
      loadMessages();
    }
  }, [
    selectedChannel,
    loadMessages,
  ]);

  /* =======================================================
     WEBSOCKET
     ======================================================= */

  useEffect(() => {
    if (
      !accessToken ||
      !selectedGroup ||
      !selectedChannel
    ) {
      return undefined;
    }

    let disconnect = null;
    let cancelled = false;
    let reconnectTimer = null;

    async function connect() {
      try {
        disconnect =
          await connectStudyGroupChannel(
            accessToken,
            selectedGroup.id,
            selectedChannel.id,
            {
              onMessage(event) {
                const eventType =
                  event?.type;

                const data =
                  event?.data;

                if (
                  eventType ===
                  "study_group.message.created"
                ) {
                  const newMessage =
                    data?.message ||
                    data;

                  if (!newMessage?.id) {
                    return;
                  }

                  setMessages(
                    (current) => {
                      const exists =
                        current.some(
                          (item) =>
                            item.id ===
                            newMessage.id,
                        );

                      if (exists) {
                        return current;
                      }

                      return [
                        ...current,
                        newMessage,
                      ];
                    },
                  );
                }

                if (
                  eventType ===
                  "study_group.message.updated"
                ) {
                  const updated =
                    data?.message ||
                    data;

                  if (!updated?.id) {
                    return;
                  }

                  if (updated.ai_response?.content) {
                    setAiWaitingMessageId(
                      (waitingMessageId) => {
                        if (
                          waitingMessageId === updated.id
                        ) {
                          setAiWaiting(false);
                          return null;
                        }

                        return waitingMessageId;
                      },
                    );
                  }

                  setMessages(
                    (current) =>
                      current.map(
                        (item) =>
                          item.id ===
                          updated.id
                            ? {
                                ...item,
                                ...updated,
                              }
                            : item,
                      ),
                  );
                }

                if (
                  eventType ===
                  "study_group.message.deleted"
                ) {
                  const messageId =
                    data?.message_id ||
                    data?.id;

                  if (!messageId) {
                    return;
                  }

                  setMessages(
                    (current) =>
                      current.filter(
                        (item) =>
                          item.id !==
                          messageId,
                      ),
                  );
                }
              },

              onClose(event) {
                if (
                  cancelled ||
                  event.code === 1000
                ) {
                  return;
                }

                reconnectTimer =
                  window.setTimeout(
                    connect,
                    1500,
                  );
              },
            },
          );
      } catch {
        if (!cancelled) {
          reconnectTimer =
            window.setTimeout(
              connect,
              1500,
            );
        }
      }
    }

    connect();

    return () => {
      cancelled = true;

      if (reconnectTimer) {
        window.clearTimeout(
          reconnectTimer,
        );
      }

      disconnect?.();
    };
  }, [
    accessToken,
    selectedGroup,
    selectedChannel,
  ]);

  /* =======================================================
     AUTO SCROLL
     ======================================================= */

  useEffect(() => {
    requestAnimationFrame(() => {
      messagesEndRef.current?.scrollIntoView({
        behavior: "smooth",
        block: "end",
      });
    });
  }, [messages, aiWaiting]);

  /* =======================================================
     CREATE / EDIT GROUP
     ======================================================= */

  function openCreateGroup() {
    setGroupForm({
      name: "",
      description: "",
      visibility: "public",
      max_members: 30,
    });

    setGroupModal("create");
  }

  function openEditGroup() {
    if (!selectedGroup) {
      return;
    }

    setGroupForm({
      name:
        selectedGroup.name || "",

      description:
        selectedGroup.description || "",

      visibility:
        selectedGroup.visibility ||
        "public",

      max_members:
        selectedGroup.max_members ||
        30,
    });

    setGroupModal("edit");
  }

  async function submitGroup(event) {
    event.preventDefault();

    if (!accessToken) {
      return;
    }

    const name =
      groupForm.name.trim();

    if (!name) {
      return;
    }

    setMutationLoading(true);
    setPageError("");

    try {
      const payload = {
        name,

        description:
          groupForm.description.trim(),

        visibility:
          groupForm.visibility,

        max_members:
          Number(
            groupForm.max_members,
          ),
      };

      if (groupModal === "create") {
        await createStudyGroup(
          accessToken,
          payload,
        );
      } else {
        const updated =
          await updateStudyGroup(
            accessToken,
            selectedGroup.id,
            payload,
          );

        const updatedGroup =
          updated?.group ||
          updated;

        if (updatedGroup?.id) {
          setSelectedGroup(
            updatedGroup,
          );
        }
      }

      setGroupModal(null);

      await refreshGroupLists();
    } catch (error) {
      setPageError(apiMessage(error));
    } finally {
      setMutationLoading(false);
    }
  }

  /* =======================================================
     DELETE GROUP
     ======================================================= */

  async function handleDeleteGroup() {
    if (
      !selectedGroup ||
      !accessToken
    ) {
      return;
    }

    const confirmed =
      await requestConfirmation({
        title: "Delete study group?",
        message:
          `Delete "${selectedGroup.name}"? This cannot be undone.`,
        confirmLabel: "Delete group",
        tone: "danger",
      });

    if (!confirmed) {
      return;
    }

    setMutationLoading(true);
    setPageError("");

    try {
      await deleteStudyGroup(
        accessToken,
        selectedGroup.id,
      );

      setSelectedGroup(null);
      setSelectedChannel(null);

      setChannels([]);
      setMembers([]);
      setMessages([]);

      await refreshGroupLists();
    } catch (error) {
      setPageError(apiMessage(error));
    } finally {
      setMutationLoading(false);
    }
  }

  /* =======================================================
     JOIN GROUP
     ======================================================= */

  async function handleJoin(group) {
    if (!accessToken) {
      return;
    }

    setMutationLoading(true);
    setPageError("");

    try {
      await joinStudyGroup(
        accessToken,
        group.id,
      );

      await refreshGroupLists();
    } catch (error) {
      setPageError(apiMessage(error));
    } finally {
      setMutationLoading(false);
    }
  }

  /* =======================================================
     LEAVE GROUP
     ======================================================= */

  async function handleLeave() {
    if (
      !selectedGroup ||
      !accessToken
    ) {
      return;
    }

    const confirmed =
      await requestConfirmation({
        title: "Leave study group?",
        message:
          `Leave "${selectedGroup.name}"?`,
        confirmLabel: "Leave group",
        tone: "danger",
      });

    if (!confirmed) {
      return;
    }

    setMutationLoading(true);
    setPageError("");

    try {
      await leaveStudyGroup(
        accessToken,
        selectedGroup.id,
      );

      setSelectedGroup(null);
      setSelectedChannel(null);

      setChannels([]);
      setMembers([]);
      setMessages([]);

      await refreshGroupLists();
    } catch (error) {
      setPageError(apiMessage(error));
    } finally {
      setMutationLoading(false);
    }
  }

  /* =======================================================
     ADD MEMBER
     ======================================================= */

  async function handleAddMember(event) {
    event.preventDefault();

    if (
      !selectedGroup ||
      !accessToken ||
      !memberEmail.trim()
    ) {
      return;
    }

    setMutationLoading(true);
    setPageError("");

    try {
      await addStudyGroupMember(
        accessToken,
        selectedGroup.id,
        memberEmail.trim(),
      );

      setMemberEmail("");

      await loadMembers();
      await refreshGroupLists();
    } catch (error) {
      setPageError(apiMessage(error));
    } finally {
      setMutationLoading(false);
    }
  }

  /* =======================================================
     REMOVE MEMBER
     ======================================================= */

  async function handleRemoveMember(member) {
    if (
      !selectedGroup ||
      !accessToken
    ) {
      return;
    }

    const name =
      member.full_name ||
      member.email ||
      "this member";

    const confirmed =
      await requestConfirmation({
        title: "Remove member?",
        message:
          `Remove ${name} from this study group?`,
        confirmLabel: "Remove",
        tone: "danger",
      });

    if (!confirmed) {
      return;
    }

    setMutationLoading(true);
    setPageError("");

    try {
      await removeStudyGroupMember(
        accessToken,
        selectedGroup.id,
        member.user_id,
      );

      await loadMembers();
      await refreshGroupLists();
    } catch (error) {
      setPageError(apiMessage(error));
    } finally {
      setMutationLoading(false);
    }
  }

  /* =======================================================
     CHANNEL CREATE / EDIT
     ======================================================= */

  function openCreateChannel() {
    setChannelForm({
      name: "",
      description: "",
    });

    setChannelModal("create");
  }

  function openEditChannel(channel) {
    setSelectedChannel(channel);

    setChannelForm({
      name:
        channel.name || "",

      description:
        channel.description || "",
    });

    setChannelModal("edit");
  }

  async function submitChannel(event) {
    event.preventDefault();

    if (
      !selectedGroup ||
      !accessToken
    ) {
      return;
    }

    const name =
      channelForm.name.trim();

    if (!name) {
      return;
    }

    setMutationLoading(true);
    setPageError("");

    try {
      const payload = {
        name,

        description:
          channelForm.description.trim(),
      };

      if (
        channelModal === "create"
      ) {
        await createStudyGroupChannel(
          accessToken,
          selectedGroup.id,
          payload,
        );
      } else {
        await updateStudyGroupChannel(
          accessToken,
          selectedGroup.id,
          selectedChannel.id,
          payload,
        );
      }

      setChannelModal(null);

      await loadChannels();
    } catch (error) {
      setPageError(apiMessage(error));
    } finally {
      setMutationLoading(false);
    }
  }

  /* =======================================================
     DELETE CHANNEL
     ======================================================= */

  async function handleDeleteChannel(
    channel,
  ) {
    if (
      !selectedGroup ||
      !accessToken
    ) {
      return;
    }

    const confirmed =
      await requestConfirmation({
        title: "Delete channel?",
        message:
          `Delete channel "${channel.name}"? This cannot be undone.`,
        confirmLabel: "Delete channel",
        tone: "danger",
      });

    if (!confirmed) {
      return;
    }

    setMutationLoading(true);
    setPageError("");

    try {
      await deleteStudyGroupChannel(
        accessToken,
        selectedGroup.id,
        channel.id,
      );

      if (
        selectedChannel?.id ===
        channel.id
      ) {
        setSelectedChannel(null);
        setMessages([]);
      }

      await loadChannels();
    } catch (error) {
      setPageError(apiMessage(error));
    } finally {
      setMutationLoading(false);
    }
  }

  /* =======================================================
     CHANNEL ATTACHMENTS
     ======================================================= */

  function persistAttachmentJobs(updater) {
    setAttachmentJobs((current) => {
      const next =
        typeof updater === "function" ? updater(current) : updater;
      writeStoredAttachmentJobs(next);
      return next;
    });
  }

  function stopAttachmentPolling(jobKey) {
    const timeoutId = attachmentPollRefs.current[jobKey];

    if (timeoutId) {
      window.clearTimeout(timeoutId);
      delete attachmentPollRefs.current[jobKey];
    }
  }

  function updateAttachmentJob(jobKey, updater) {
    persistAttachmentJobs((current) => {
      const existing = current[jobKey];
      if (!existing) return current;

      const updated =
        typeof updater === "function"
          ? updater(existing)
          : { ...existing, ...updater };

      return { ...current, [jobKey]: updated };
    });
  }

  function dismissAttachment(jobKey) {
    if (!jobKey) return;
    stopAttachmentPolling(jobKey);

    persistAttachmentJobs((current) => {
      const next = { ...current };
      delete next[jobKey];
      return next;
    });
  }

  useEffect(() => {
    return () => {
      Object.values(attachmentPollRefs.current).forEach((timeoutId) => {
        window.clearTimeout(timeoutId);
      });
      attachmentPollRefs.current = {};
    };
  }, []);

  /*
   * Channel navigation only changes which job is displayed.
   * It never clears or cancels another channel's PDF job.
   */
  useEffect(() => {
    setAiWaiting(false);
    setAiWaitSeconds(0);
    setAiWaitingMessageId(null);

    if (attachmentInputRef.current) {
      attachmentInputRef.current.value = "";
    }
  }, [selectedChannel?.id]);

  async function pollAttachmentStatus(
    groupId,
    channelId,
    attachmentId,
    jobKey,
  ) {
    try {
      const result = await getStudyGroupAttachmentStatus(
        accessToken,
        groupId,
        channelId,
        attachmentId,
      );

      const finished =
        result.status === "ready" || result.status === "failed";

      updateAttachmentJob(jobKey, (current) => {
        if (current.id !== attachmentId) return current;

        return {
          ...current,
          status: result.status,
          progress: result.progress ?? 0,
          message: result.message || "",
          error: result.error || null,
          finishedAt: finished
            ? current.finishedAt || Date.now()
            : null,
        };
      });

      if (finished) {
        delete attachmentPollRefs.current[jobKey];
        return;
      }

      attachmentPollRefs.current[jobKey] = window.setTimeout(() => {
        pollAttachmentStatus(groupId, channelId, attachmentId, jobKey);
      }, 2000);
    } catch (error) {
      updateAttachmentJob(jobKey, (current) => ({
        ...current,
        status: "failed",
        error: { message: apiMessage(error) },
        finishedAt: current.finishedAt || Date.now(),
      }));
      delete attachmentPollRefs.current[jobKey];
    }
  }

  /*
   * Re-start polling after returning to Study Groups or after a remount.
   * The backend keeps processing; sessionStorage lets the UI reconnect to it.
   */
  useEffect(() => {
    if (!accessToken) return;

    Object.entries(attachmentJobs).forEach(([jobKey, job]) => {
      const inProgress =
        job.status === "queued" || job.status === "processing";

      if (
        inProgress &&
        job.id &&
        job.groupId &&
        job.channelId &&
        !attachmentPollRefs.current[jobKey]
      ) {
        pollAttachmentStatus(
          job.groupId,
          job.channelId,
          job.id,
          jobKey,
        );
      }
    });
  }, [accessToken]);

  async function handleAttachmentChange(event) {
    const file = event.target.files?.[0];
    if (!file) return;

    if (
      file.type !== "application/pdf" &&
      !file.name.toLowerCase().endsWith(".pdf")
    ) {
      setPageError(
        "Only PDF files can be uploaded to a Study Group channel.",
      );
      event.target.value = "";
      return;
    }

    if (!selectedGroup || !selectedChannel || !accessToken) {
      event.target.value = "";
      return;
    }

    const groupId = selectedGroup.id;
    const channelId = selectedChannel.id;
    const jobKey = `${groupId}:${channelId}`;
    const startedAt = Date.now();

    stopAttachmentPolling(jobKey);
    setPageError("");

    const initialJob = {
      id: null,
      groupId,
      channelId,
      fileName: file.name,
      status: "uploading",
      progress: 0,
      message: "Uploading PDF...",
      error: null,
      startedAt,
      finishedAt: null,
    };

    persistAttachmentJobs((current) => ({
      ...current,
      [jobKey]: initialJob,
    }));

    try {
      const result = await uploadStudyGroupAttachment(
        accessToken,
        groupId,
        channelId,
        file,
      );

      const attachmentId = result?.id;
      if (!attachmentId) {
        throw new Error("The backend did not return an attachment ID.");
      }

      const finished =
        result.status === "ready" || result.status === "failed";

      /*
       * Read storage again here because this async callback can finish
       * after the user has navigated away and the component has unmounted.
       */
      const storedJobs = readStoredAttachmentJobs();
      const completedUploadJob = {
        ...(storedJobs[jobKey] || initialJob),
        id: attachmentId,
        groupId,
        channelId,
        fileName: result.file_name || file.name,
        status: result.status || "queued",
        progress: result.processing_progress ?? 0,
        message:
          result.status === "ready"
            ? "PDF is ready for AI questions."
            : "PDF uploaded. Processing...",
        error: null,
        startedAt: storedJobs[jobKey]?.startedAt || startedAt,
        finishedAt: finished ? Date.now() : null,
      };

      writeStoredAttachmentJobs({
        ...storedJobs,
        [jobKey]: completedUploadJob,
      });

      persistAttachmentJobs((current) => ({
        ...current,
        [jobKey]: completedUploadJob,
      }));

      if (!finished) {
        pollAttachmentStatus(groupId, channelId, attachmentId, jobKey);
      }
    } catch (error) {
      const storedJobs = readStoredAttachmentJobs();
      const failedJob = {
        ...(storedJobs[jobKey] || initialJob),
        status: "failed",
        progress: 0,
        message: "PDF upload failed.",
        error: { message: apiMessage(error) },
        finishedAt: Date.now(),
      };

      writeStoredAttachmentJobs({
        ...storedJobs,
        [jobKey]: failedJob,
      });
      persistAttachmentJobs((current) => ({
        ...current,
        [jobKey]: failedJob,
      }));
    } finally {
      event.target.value = "";
    }
  }

  /* =======================================================
     @ MENU
     ======================================================= */

  function handleMessageChange(event) {
    const value =
      event.target.value;

    setMessage(value);

    /*
     * Show picker when the current word starts
     * with @.
     */
    const match =
      value.match(
        /(?:^|\s)@([^\s@]*)$/,
      );

    if (!match) {
      setShowMentionMenu(false);
      return;
    }

    const query =
      (match[1] || "")
        .trim()
        .toLowerCase();

    const hasAiMatch =
      AI_MODES.some((ai) =>
        ai.label
          .toLowerCase()
          .startsWith(query),
      );

    const hasMemberMatch =
      members.some((member) => {
        const name =
          member.full_name || "";

        const email =
          member.email || "";

        return (
          name
            .toLowerCase()
            .startsWith(query) ||
          email
            .toLowerCase()
            .startsWith(query)
        );
      });

    setShowMentionMenu(
      hasAiMatch ||
      hasMemberMatch,
    );
  }

  function selectHumanMention(member) {
    const userId =
      member.user_id;

    if (!userId) {
      return;
    }

    setSelectedMentionIds(
      (current) =>
        current.includes(userId)
          ? current
          : [
              ...current,
              userId,
            ],
    );

    const name =
      member.full_name ||
      member.email ||
      "Member";

    setMessage((current) =>
      current.replace(
        /@([^\s@]*)$/,
        `@${name} `,
      ),
    );

    /*
     * Human mention = normal message.
     */
    setSelectedAiMode(null);
    setShowMentionMenu(false);
  }

  function selectAiMention(ai) {
    /*
     * AI payload should not contain
     * human mentioned_user_ids.
     */
    setSelectedMentionIds([]);

    setSelectedAiMode(
      ai.value,
    );

    setMessage((current) =>
      current.replace(
        /@([^\s@]*)$/,
        `@${ai.label} `,
      ),
    );

    setShowMentionMenu(false);
  }

  /* =======================================================
     SEND MESSAGE
     ======================================================= */

  async function handleSendMessage(event) {
    event.preventDefault();

    if (
      !selectedGroup ||
      !selectedChannel ||
      !accessToken ||
      !message.trim() ||
      sendingMessage
    ) {
      return;
    }

    const content =
      message.trim();

    const requestedAiMode =
      selectedAiMode;

    setSendingMessage(true);
    setPageError("");

    if (requestedAiMode) {
      setAiWaitSeconds(0);
      setAiWaiting(true);
      setAiWaitingMessageId(null);
    }

    try {
      const result =
        await createGroupMessage(
          accessToken,
          selectedGroup.id,
          selectedChannel.id,
          {
            content,

            mentionedUserIds:
              selectedMentionIds,

            aiMode:
              requestedAiMode,

            responseFormat:
              requestedAiMode
                ? responseFormat
                : null,
          },
        );

      const createdMessage =
        result?.message ||
        result?.user_message ||
        result;

      if (
        requestedAiMode &&
        createdMessage?.id
      ) {
        setAiWaitingMessageId(
          createdMessage.id,
        );

        if (
          createdMessage.ai_response?.content
        ) {
          setAiWaiting(false);
          setAiWaitingMessageId(null);
        }
      }

      if (createdMessage?.id) {
        setMessages((current) => {
          const exists =
            current.some(
              (item) =>
                item.id ===
                createdMessage.id,
            );

          if (exists) {
            return current;
          }

          return [
            ...current,
            createdMessage,
          ];
        });
      }

      setMessage("");
      setSelectedMentionIds([]);
      setSelectedAiMode(null);
      setShowMentionMenu(false);
    } catch (error) {
      if (requestedAiMode) {
        setAiWaiting(false);
        setAiWaitingMessageId(null);
      }

      setPageError(apiMessage(error));
    } finally {
      setSendingMessage(false);
    }
  }

  /* =======================================================
     EDIT MESSAGE
     ======================================================= */

  function beginEditMessage(item) {
    setEditingMessage(item);

    setEditingMessageValue(
      item.content || "",
    );
  }

  async function saveMessageEdit(event) {
    event.preventDefault();

    if (
      !editingMessage ||
      !editingMessageValue.trim()
    ) {
      return;
    }

    setMutationLoading(true);
    setPageError("");

    try {
      const result =
        await updateGroupMessage(
          accessToken,
          selectedGroup.id,
          selectedChannel.id,
          editingMessage.id,
          editingMessageValue.trim(),
          editingMessage.mentioned_user_ids ||
            [],
        );

      const updated =
        result?.message ||
        result;

      setMessages(
        (current) =>
          current.map((item) =>
            item.id ===
            editingMessage.id
              ? {
                  ...item,
                  ...updated,
                }
              : item,
          ),
      );

      setEditingMessage(null);
      setEditingMessageValue("");
    } catch (error) {
      setPageError(apiMessage(error));
    } finally {
      setMutationLoading(false);
    }
  }

  /* =======================================================
     DELETE MESSAGE
     ======================================================= */

  async function handleDeleteMessage(
    item,
  ) {
    const confirmed =
      await requestConfirmation({
        title: "Delete message?",
        message:
          "Delete this message? This cannot be undone.",
        confirmLabel: "Delete message",
        tone: "danger",
      });

    if (!confirmed) {
      return;
    }

    setMutationLoading(true);
    setPageError("");

    try {
      await deleteGroupMessage(
        accessToken,
        selectedGroup.id,
        selectedChannel.id,
        item.id,
      );

      setMessages(
        (current) =>
          current.filter(
            (messageItem) =>
              messageItem.id !==
              item.id,
          ),
      );
    } catch (error) {
      setPageError(apiMessage(error));
    } finally {
      setMutationLoading(false);
    }
  }

  /* =======================================================
     GROUPS TO DISPLAY
     ======================================================= */

  const visibleGroups =
    useMemo(() => {
      return activeView ===
        "discover"
        ? discoverGroups
        : myGroups;
    }, [
      activeView,
      discoverGroups,
      myGroups,
    ]);

  /* =======================================================
     RENDER
     ======================================================= */

  return (
    <AppShell>
      <div
        className={`group-study-page ${
          groupsPanelCollapsed
            ? "groups-panel-collapsed"
            : ""
        } ${
          detailsPanelCollapsed
            ? "details-panel-collapsed"
            : ""
        }`}
      >

        {/* HEADER */}

        <div className="group-study-header">
          <div>
            <h1>Study Groups</h1>

            <p>
              Discover groups, collaborate
              with classmates and study
              together.
            </p>
          </div>

          <button
            className="create-group-button"
            type="button"
            onClick={openCreateGroup}
          >
            <Plus size={18} />
            Create Group
          </button>
        </div>

        {/* ERROR */}

        {pageError && (
          <div className="sg-error">
            {pageError}
          </div>
        )}

        {/* PUBLIC / PRIVATE + GROUP PANEL COLLAPSE */}

        <div className="group-view-tabs">
          <div className="group-view-tab-buttons">
            <button
              type="button"
              className={
                activeView ===
                "discover"
                  ? "active"
                  : ""
              }
              onClick={() => {
                setSearchParams({
                  view: "public",
                });

                setActiveView(
                  "discover",
                );

                setSelectedGroup(null);
              }}
            >
              Public
            </button>

            <button
              type="button"
              className={
                activeView === "mine"
                  ? "active"
                  : ""
              }
              onClick={() => {
                setSearchParams({
                  view: "private",
                });

                setActiveView("mine");
                setMyFilter("private");
                setSelectedGroup(null);
              }}
            >
              Private
            </button>
          </div>

          <button
            type="button"
            className="group-panel-collapse-toggle"
            title={
              groupsPanelCollapsed
                ? "Show groups panel"
                : "Hide groups panel"
            }
            aria-label={
              groupsPanelCollapsed
                ? "Show groups panel"
                : "Hide groups panel"
            }
            aria-expanded={
              !groupsPanelCollapsed
            }
            onClick={() => {
              const nextCollapsed =
                !groupsPanelCollapsed;

              setGroupsPanelCollapsed(
                nextCollapsed,
              );

              setDetailsPanelCollapsed(
                nextCollapsed,
              );
            }}
          >
            {groupsPanelCollapsed ? (
              <ChevronRight size={17} />
            ) : (
              <ChevronLeft size={17} />
            )}
          </button>
        </div>

        {/* SEARCH / PRIVATE LABEL */}

        {activeView ===
        "discover" ? (
          <div className="discover-toolbar">
            <div className="group-search">
              <Search size={18} />

              <input
                value={search}
                onChange={(event) =>
                  setSearch(
                    event.target.value,
                  )
                }
                placeholder="Search public groups"
              />
            </div>
          </div>
        ) : (
          <div className="private-groups-label">
            My Private Groups
          </div>
        )}

        {/* PAGE LAYOUT */}

        <div className="study-group-layout">

          {/* GROUP LIST */}

          <aside className="group-list-panel">

            {groupsLoading ? (
              <div className="sg-empty">
                Loading groups...
              </div>
            ) : visibleGroups.length ===
              0 ? (
              <div className="sg-empty">
                {activeView ===
                "discover"
                  ? "No public groups found."
                  : "No groups found."}
              </div>
            ) : (
              visibleGroups.map(
                (group) => (
                  <div
                    className={`group-card ${
                      selectedGroup?.id ===
                      group.id
                        ? "selected"
                        : ""
                    }`}
                    key={group.id}
                  >
                    <button
                      type="button"
                      className="group-card-main"
                      onClick={() => {
                        if (
                          group.is_member
                        ) {
                          openGroup(
                            group,
                          );
                        }
                      }}
                    >
                      <div className="group-card-icon">
                        {group.visibility ===
                        "private" ? (
                          <Lock
                            size={18}
                          />
                        ) : (
                          <Users
                            size={18}
                          />
                        )}
                      </div>

                      <div className="group-card-info">
                        <strong>
                          {group.name}
                        </strong>

                        <span>
                          {group.member_count ??
                            0}
                          {" / "}
                          {group.max_members ??
                            "∞"}
                          {" members"}
                        </span>

                        {group.description && (
                          <small>
                            {
                              group.description
                            }
                          </small>
                        )}
                      </div>
                    </button>

                    <div className="group-card-action">
                      {!group.is_member &&
                      group.visibility ===
                        "public" ? (
                        <button
                          type="button"
                          disabled={
                            mutationLoading
                          }
                          onClick={() =>
                            handleJoin(
                              group,
                            )
                          }
                        >
                          Join
                        </button>
                      ) : group.is_member ? (
                        <button
                          type="button"
                          onClick={() =>
                            openGroup(
                              group,
                            )
                          }
                        >
                          Open
                        </button>
                      ) : (
                        <span className="private-label">
                          Private
                        </span>
                      )}
                    </div>
                  </div>
                ),
              )
            )}
          </aside>

          {/* GROUP WORKSPACE */}

          <section className="group-workspace">

            {!selectedGroup ? (
              <div className="group-placeholder">
                <Users size={46} />

                <h2>
                  Select a study group
                </h2>

                <p>
                  Open one of your groups
                  to view its members,
                  channels and messages.
                </p>
              </div>
            ) : (
              <>
                {/* GROUP HEADER */}

                <div className="workspace-header">
                  <div>
                    <div className="workspace-title">
                      {selectedGroup.visibility ===
                      "private" ? (
                        <Lock
                          size={18}
                        />
                      ) : (
                        <Users
                          size={18}
                        />
                      )}

                      <h2>
                        {
                          selectedGroup.name
                        }
                      </h2>
                    </div>

                    <p>
                      {selectedGroup.description ||
                        "No description"}
                    </p>
                  </div>

                  <div className="workspace-actions">

                    {selectedGroup.can_manage && (
                      <>
                        <button
                          type="button"
                          onClick={
                            openEditGroup
                          }
                        >
                          <Edit3
                            size={16}
                          />
                          Edit
                        </button>

                        <button
                          type="button"
                          className="danger"
                          disabled={
                            mutationLoading
                          }
                          onClick={
                            handleDeleteGroup
                          }
                        >
                          <Trash2
                            size={16}
                          />
                          Delete
                        </button>
                      </>
                    )}

                    {selectedGroup.is_member &&
                      !selectedGroup.can_manage && (
                        <button
                          type="button"
                          disabled={
                            mutationLoading
                          }
                          onClick={
                            handleLeave
                          }
                        >
                          Leave
                        </button>
                      )}
                  </div>

                  <button
                    type="button"
                    className="details-panel-collapse-toggle"
                    title={
                      detailsPanelCollapsed
                        ? "Show channels and members"
                        : "Hide channels and members"
                    }
                    aria-label={
                      detailsPanelCollapsed
                        ? "Show channels and members"
                        : "Hide channels and members"
                    }
                    aria-expanded={
                      !detailsPanelCollapsed
                    }
                    onClick={() =>
                      setDetailsPanelCollapsed(
                        (current) =>
                          !current,
                      )
                    }
                  >
                    {detailsPanelCollapsed ? (
                      <ChevronRight size={17} />
                    ) : (
                      <ChevronLeft size={17} />
                    )}
                  </button>
                </div>

                <div className="workspace-body">

                  {/* CHANNEL / MEMBER SIDEBAR */}

                  <aside className="channel-sidebar">

                    <div className="channel-heading">
                      <span>
                        Channels
                      </span>

                      {selectedGroup.can_manage && (
                        <button
                          type="button"
                          onClick={
                            openCreateChannel
                          }
                          title="Create channel"
                        >
                          <Plus
                            size={17}
                          />
                        </button>
                      )}
                    </div>

                    {channelsLoading ? (
                      <div className="sg-small-empty">
                        Loading...
                      </div>
                    ) : channels.length ===
                      0 ? (
                      <div className="sg-small-empty">
                        No channels yet.
                      </div>
                    ) : (
                      channels.map(
                        (channel) => (
                          <div
                            className={`channel-row ${
                              selectedChannel?.id ===
                              channel.id
                                ? "active"
                                : ""
                            }`}
                            key={
                              channel.id
                            }
                          >
                            <button
                              type="button"
                              className="channel-select"
                              onClick={() =>
                                setSelectedChannel(
                                  channel,
                                )
                              }
                            >
                              <Hash
                                size={16}
                              />

                              <span>
                                {
                                  channel.name
                                }
                              </span>
                            </button>

                            {selectedGroup.can_manage && (
                              <div className="channel-admin-actions">
                                <button
                                  type="button"
                                  title="Edit channel"
                                  onClick={() =>
                                    openEditChannel(
                                      channel,
                                    )
                                  }
                                >
                                  <Edit3
                                    size={
                                      14
                                    }
                                  />
                                </button>

                                <button
                                  type="button"
                                  title="Delete channel"
                                  onClick={() =>
                                    handleDeleteChannel(
                                      channel,
                                    )
                                  }
                                >
                                  <Trash2
                                    size={
                                      14
                                    }
                                  />
                                </button>
                              </div>
                            )}
                          </div>
                        ),
                      )
                    )}

                    {/* MEMBERS */}

                    <div className="members-heading">
                      <span>
                        Members
                      </span>

                      <span>
                        {members.length}
                      </span>
                    </div>

                    {membersLoading ? (
                      <div className="sg-small-empty">
                        Loading...
                      </div>
                    ) : (
                      members.map(
                        (member) => {
                          const name =
                            member.full_name ||
                            member.email ||
                            "Student";

                          const role =
                            member.role ||
                            "member";

                          return (
                            <div
                              className="member-row"
                              key={
                                member.user_id
                              }
                            >
                              <div className="member-avatar">
                                {initials(
                                  name,
                                )}
                              </div>

                              <div className="member-info">
                                <span>
                                  {name}
                                </span>

                                <small>
                                  {role}
                                </small>
                              </div>

                              {selectedGroup.can_manage &&
                                role ===
                                  "member" && (
                                  <button
                                    type="button"
                                    className="remove-member"
                                    title="Remove member"
                                    onClick={() =>
                                      handleRemoveMember(
                                        member,
                                      )
                                    }
                                  >
                                    <UserMinus
                                      size={
                                        15
                                      }
                                    />
                                  </button>
                                )}
                            </div>
                          );
                        },
                      )
                    )}

                    {/* ADD MEMBER — PRIVATE ONLY */}

                    {selectedGroup.can_manage &&
                      selectedGroup.visibility ===
                        "private" && (
                        <form
                          className="add-member-form"
                          onSubmit={
                            handleAddMember
                          }
                        >
                          <input
                            type="email"
                            value={
                              memberEmail
                            }
                            onChange={(
                              event,
                            ) =>
                              setMemberEmail(
                                event
                                  .target
                                  .value,
                              )
                            }
                            placeholder="Student email"
                            required
                          />

                          <button
                            type="submit"
                            disabled={
                              mutationLoading
                            }
                          >
                            Add Member
                          </button>
                        </form>
                      )}
                  </aside>

                  {/* CHAT */}

                  <main className="channel-chat">

                    {!selectedChannel ? (
                      <div className="group-placeholder">
                        <Hash
                          size={42}
                        />

                        <h3>
                          Select a channel
                        </h3>
                      </div>
                    ) : (
                      <>
                        <div className="channel-chat-header">
                          <div>
                            <h3>
                              <Hash
                                size={
                                  18
                                }
                              />

                              {
                                selectedChannel.name
                              }
                            </h3>

                            {selectedChannel.description && (
                              <p>
                                {
                                  selectedChannel.description
                                }
                              </p>
                            )}
                          </div>
                        </div>

                        {/* MESSAGE LIST */}

                        <div className="group-message-list">

                          {messagesLoading ? (
                            <div className="sg-empty">
                              Loading
                              messages...
                            </div>
                          ) : messages.length ===
                            0 ? (
                            <div className="sg-empty">
                              No messages
                              yet. Start the
                              conversation.
                            </div>
                          ) : (
                            messages.map(
                              (item) => {
                                const member =
                                  members.find(
                                    (
                                      groupMember,
                                    ) =>
                                      groupMember.user_id ===
                                      item.author_id,
                                  );

                                const sender =
                                  member?.full_name ||
                                  member?.email ||
                                  "Student";

                                /*
                                 * Backend message response stores
                                 * the AI answer inside ai_response.
                                 */
                                const aiResponse =
                                  item.ai_response;

                                const isOwnMessage =
                                  item.author_id ===
                                  user?.id;

                                /*
                                 * AI-invoking messages cannot
                                 * be edited.
                                 */
                                const canEdit =
                                  isOwnMessage &&
                                  !item.ai_mode_used;

                                return (
                                  <div
                                    className="group-message"
                                    key={
                                      item.id
                                    }
                                  >
                                    <div className="message-avatar">
                                      {initials(
                                        sender,
                                      )}
                                    </div>

                                    <div className="message-main">

                                      <div className="message-meta">
                                        <strong>
                                          {
                                            sender
                                          }
                                        </strong>

                                        <span>
                                          {timeLabel(
                                            item.sent_at,
                                          )}
                                        </span>
                                      </div>

                                      <p className="message-content">
                                        {
                                          item.content
                                        }
                                      </p>

                                      {(canEdit ||
                                        isOwnMessage) && (
                                        <div className="message-actions">

                                          {canEdit && (
                                            <button
                                              type="button"
                                              onClick={() =>
                                                beginEditMessage(
                                                  item,
                                                )
                                              }
                                            >
                                              Edit
                                            </button>
                                          )}

                                          {isOwnMessage && (
                                            <button
                                              type="button"
                                              onClick={() =>
                                                handleDeleteMessage(
                                                  item,
                                                )
                                              }
                                            >
                                              Delete
                                            </button>
                                          )}
                                        </div>
                                      )}

                                      {/* AI RESPONSE */}

                                      {aiResponse?.content && (
                                        <div className="ai-message">
                                          <div className="message-meta">
                                            <strong>
                                              AI Companion
                                            </strong>

                                            {aiResponse.generated_at && (
                                              <span>
                                                {timeLabel(
                                                  aiResponse.generated_at,
                                                )}
                                              </span>
                                            )}
                                          </div>

                                          <SimpleMarkdown>
                                            {
                                              aiResponse.content
                                            }
                                          </SimpleMarkdown>
                                        </div>
                                      )}
                                    </div>
                                  </div>
                                );
                              },
                            )
                          )}

                          <div
                            ref={
                              messagesEndRef
                            }
                          />
                        </div>

                        {/* COMPOSER */}

                        <div className="group-composer">

                          {aiWaiting && (
                            <div
                              className="ai-waiting-indicator"
                              role="status"
                              aria-live="polite"
                            >
                              <Bot size={16} />

                              <span>
                                AI Companion is analyzing your question...{" "}
                                {formatElapsedTime(
                                  aiWaitSeconds,
                                )}
                              </span>
                            </div>
                          )}

                          {attachment && (
                            <div
                              className={`channel-attachment-status ${attachment.status}`}
                            >
                              <Paperclip size={15} />

                              <div className="channel-attachment-info">
                                <strong>
                                  {attachment.fileName}
                                </strong>

                                <span>
                                  {attachment.status === "uploading" &&
                                    `Uploading PDF... · ${formatElapsedTime(
                                      attachmentElapsedSeconds,
                                    )}`}

                                  {attachment.status === "queued" &&
                                    `PDF queued for processing... · ${formatElapsedTime(
                                      attachmentElapsedSeconds,
                                    )}`}

                                  {attachment.status === "processing" &&
                                    `Processing PDF... ${attachment.progress ?? 0}% · ${formatElapsedTime(
                                      attachmentElapsedSeconds,
                                    )}`}

                                  {attachment.status === "ready" &&
                                    `PDF ready for AI questions · ${formatElapsedTime(
                                      attachmentElapsedSeconds,
                                    )}`}

                                  {attachment.status === "failed" &&
                                    `${
                                      attachment.error?.message ||
                                      attachment.message ||
                                      "PDF processing failed."
                                    } · ${formatElapsedTime(
                                      attachmentElapsedSeconds,
                                    )}`}
                                </span>
                              </div>

                              {attachment.status !== "uploading" &&
                                attachment.status !== "processing" &&
                                attachment.status !== "queued" && (
                                  <button
                                    type="button"
                                    className="attachment-dismiss"
                                    onClick={() =>
                                      dismissAttachment(
                                        currentAttachmentKey,
                                      )
                                    }
                                    aria-label="Dismiss attachment status"
                                  >
                                    <X size={14} />
                                  </button>
                                )}
                            </div>
                          )}

                          {selectedAiMode && (
                            <div className="selected-ai-bar">
                              <Bot
                                size={15}
                              />

                              <span>
                                {
                                  AI_MODES.find(
                                    (item) =>
                                      item.value ===
                                      selectedAiMode,
                                  )?.label
                                }
                              </span>

                              <select
                                value={
                                  responseFormat
                                }
                                onChange={(
                                  event,
                                ) =>
                                  setResponseFormat(
                                    event
                                      .target
                                      .value,
                                  )
                                }
                              >
                                <option value="paragraph">
                                  Paragraph
                                </option>

                                <option value="bullet_points">
                                  Bullet
                                  points
                                </option>

                                <option value="table">
                                  Table
                                </option>
                              </select>

                              <button
                                type="button"
                                onClick={() =>
                                  setSelectedAiMode(
                                    null,
                                  )
                                }
                              >
                                <X
                                  size={
                                    14
                                  }
                                />
                              </button>
                            </div>
                          )}

                          <form
                            className="message-form"
                            onSubmit={
                              handleSendMessage
                            }
                          >
                            <input
                              ref={attachmentInputRef}
                              type="file"
                              accept=".pdf,application/pdf"
                              className="attachment-file-input"
                              onChange={handleAttachmentChange}
                            />

                            <button
                              type="button"
                              className="attachment-button"
                              title="Attach PDF"
                              aria-label="Attach PDF"
                              disabled={attachmentUploading}
                              onClick={() =>
                                attachmentInputRef.current?.click()
                              }
                            >
                              <Paperclip size={18} />
                            </button>

                            <div
                              className="message-input-wrap"
                              ref={mentionPickerRef}
                            >

                              {/* @ PICKER */}

                              {showMentionMenu &&
                                hasMentionMatches && (
                                <div className="mention-menu">

                                  {filteredAiModes.map(
                                    (
                                      ai,
                                      aiIndex,
                                    ) => (
                                      <button
                                        type="button"
                                        key={
                                          ai.value
                                        }
                                        className={
                                          activeMentionIndex ===
                                          aiIndex
                                            ? "active"
                                            : ""
                                        }
                                        onMouseEnter={() =>
                                          setActiveMentionIndex(
                                            aiIndex,
                                          )
                                        }
                                        onClick={() =>
                                          selectAiMention(
                                            ai,
                                          )
                                        }
                                      >
                                        <Bot
                                          size={
                                            16
                                          }
                                        />

                                        <span>
                                          {
                                            ai.label
                                          }
                                        </span>
                                      </button>
                                    ),
                                  )}

                                  {filteredMentionMembers.map(
                                    (
                                      member,
                                      memberIndex,
                                    ) => {
                                      const optionIndex =
                                        filteredAiModes.length +
                                        memberIndex;

                                      const name =
                                        member.full_name ||
                                        member.email ||
                                        "Student";

                                      return (
                                        <button
                                          type="button"
                                          key={
                                            member.user_id
                                          }
                                          className={
                                            activeMentionIndex ===
                                            optionIndex
                                              ? "active"
                                              : ""
                                          }
                                          onMouseEnter={() =>
                                            setActiveMentionIndex(
                                              optionIndex,
                                            )
                                          }
                                          onClick={() =>
                                            selectHumanMention(
                                              member,
                                            )
                                          }
                                        >
                                          <div className="mention-avatar">
                                            {initials(
                                              name,
                                            )}
                                          </div>

                                          <span>
                                            {
                                              name
                                            }
                                          </span>
                                        </button>
                                      );
                                    },
                                  )}
                                </div>
                              )}

                              <input
                                value={
                                  message
                                }
                                onChange={
                                  handleMessageChange
                                }
                                onKeyDown={(
                                  event,
                                ) => {
                                  if (
                                    showMentionMenu &&
                                    hasMentionMatches
                                  ) {
                                    if (
                                      event.key ===
                                      "ArrowDown"
                                    ) {
                                      event.preventDefault();

                                      setActiveMentionIndex(
                                        (current) =>
                                          (
                                            current +
                                            1
                                          ) %
                                          mentionOptions.length,
                                      );

                                      return;
                                    }

                                    if (
                                      event.key ===
                                      "ArrowUp"
                                    ) {
                                      event.preventDefault();

                                      setActiveMentionIndex(
                                        (current) =>
                                          (
                                            current -
                                            1 +
                                            mentionOptions.length
                                          ) %
                                          mentionOptions.length,
                                      );

                                      return;
                                    }

                                    if (
                                      event.key ===
                                      "Enter"
                                    ) {
                                      const option =
                                        mentionOptions[
                                          activeMentionIndex
                                        ];

                                      if (option) {
                                        event.preventDefault();

                                        if (
                                          option.type ===
                                          "ai"
                                        ) {
                                          selectAiMention(
                                            option.item,
                                          );
                                        } else {
                                          selectHumanMention(
                                            option.item,
                                          );
                                        }

                                        return;
                                      }
                                    }
                                  }

                                  if (
                                    event.key ===
                                    "Escape"
                                  ) {
                                    setShowMentionMenu(
                                      false,
                                    );
                                  }
                                }}
                                maxLength={
                                  4000
                                }
                                placeholder={`Message #${selectedChannel.name} — type @ to mention`}
                              />
                            </div>

                            <button
                              type="submit"
                              className="send-group-message"
                              disabled={
                                sendingMessage ||
                                !message.trim()
                              }
                            >
                              <Send
                                size={
                                  18
                                }
                              />
                            </button>
                          </form>
                        </div>
                      </>
                    )}
                  </main>
                </div>
              </>
            )}
          </section>
        </div>
      </div>

      {/* ===================================================
          GROUP MODAL
          =================================================== */}

      {groupModal && (
        <Modal
          title={
            groupModal === "create"
              ? "Create Study Group"
              : "Edit Study Group"
          }
          onClose={() =>
            setGroupModal(null)
          }
        >
          <form
            className="sg-form"
            onSubmit={submitGroup}
          >
            <label>
              Group name

              <input
                value={
                  groupForm.name
                }
                maxLength={100}
                required
                onChange={(event) =>
                  setGroupForm(
                    (current) => ({
                      ...current,

                      name:
                        event.target
                          .value,
                    }),
                  )
                }
              />
            </label>

            <label>
              Description

              <textarea
                value={
                  groupForm.description
                }
                maxLength={1000}
                onChange={(event) =>
                  setGroupForm(
                    (current) => ({
                      ...current,

                      description:
                        event.target
                          .value,
                    }),
                  )
                }
              />
            </label>

            <label>
              Visibility

              <select
                value={
                  groupForm.visibility
                }
                onChange={(event) =>
                  setGroupForm(
                    (current) => ({
                      ...current,

                      visibility:
                        event.target
                          .value,
                    }),
                  )
                }
              >
                <option value="public">
                  Public
                </option>

                <option value="private">
                  Private
                </option>
              </select>
            </label>

            <label>
              Maximum members

              <input
                type="number"
                min="1"
                value={
                  groupForm.max_members
                }
                onChange={(event) =>
                  setGroupForm(
                    (current) => ({
                      ...current,

                      max_members:
                        event.target
                          .value,
                    }),
                  )
                }
              />
            </label>

            <div className="sg-form-actions">
              <button
                type="button"
                onClick={() =>
                  setGroupModal(null)
                }
              >
                Cancel
              </button>

              <button
                type="submit"
                className="primary"
                disabled={
                  mutationLoading
                }
              >
                {groupModal ===
                "create"
                  ? "Create Group"
                  : "Save Changes"}
              </button>
            </div>
          </form>
        </Modal>
      )}

      {/* ===================================================
          CHANNEL MODAL
          =================================================== */}

      {channelModal && (
        <Modal
          title={
            channelModal === "create"
              ? "Create Channel"
              : "Edit Channel"
          }
          onClose={() =>
            setChannelModal(null)
          }
        >
          <form
            className="sg-form"
            onSubmit={submitChannel}
          >
            <label>
              Channel name

              <input
                value={
                  channelForm.name
                }
                required
                onChange={(event) =>
                  setChannelForm(
                    (current) => ({
                      ...current,

                      name:
                        event.target
                          .value,
                    }),
                  )
                }
              />
            </label>

            <label>
              Description

              <textarea
                value={
                  channelForm.description
                }
                onChange={(event) =>
                  setChannelForm(
                    (current) => ({
                      ...current,

                      description:
                        event.target
                          .value,
                    }),
                  )
                }
              />
            </label>

            <div className="sg-form-actions">
              <button
                type="button"
                onClick={() =>
                  setChannelModal(null)
                }
              >
                Cancel
              </button>

              <button
                type="submit"
                className="primary"
                disabled={
                  mutationLoading
                }
              >
                {channelModal ===
                "create"
                  ? "Create Channel"
                  : "Save Changes"}
              </button>
            </div>
          </form>
        </Modal>
      )}

      {/* ===================================================
          EDIT MESSAGE MODAL
          =================================================== */}

      {editingMessage && (
        <Modal
          title="Edit Message"
          onClose={() => {
            setEditingMessage(null);
            setEditingMessageValue("");
          }}
        >
          <form
            className="sg-form"
            onSubmit={saveMessageEdit}
          >
            <label>
              Message

              <textarea
                value={
                  editingMessageValue
                }
                maxLength={4000}
                required
                onChange={(event) =>
                  setEditingMessageValue(
                    event.target.value,
                  )
                }
              />
            </label>

            <div className="sg-form-actions">
              <button
                type="button"
                onClick={() => {
                  setEditingMessage(
                    null,
                  );

                  setEditingMessageValue(
                    "",
                  );
                }}
              >
                Cancel
              </button>

              <button
                type="submit"
                className="primary"
                disabled={
                  mutationLoading
                }
              >
                Save
              </button>
            </div>
          </form>
        </Modal>
      )}
      {confirmModal}
    </AppShell>
  );
}

export default GroupStudyPage;