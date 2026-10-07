
import {
  Fragment,
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
  MoreHorizontal,
  Paperclip,
  Plus,
  Search,
  Settings,
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
  transferStudyGroupOwnership,
  updateGroupMessage,
  updateStudyGroup,
  updateStudyGroupChannel,
  updateStudyGroupMemberRole,
  uploadStudyGroupAttachment,
} from "../../services/groupService.js";

import "./groupStudy.css";
import "./groupStudyPanels.css";
import "./groupStudyBrowse.css";

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


const DISCOVER_FILTERS = [
  { label: "All", value: "all" },
  { label: "AI", value: "AI" },
  { label: "Web", value: "Web" },
  { label: "DB", value: "DB" },
  { label: "CS Theory", value: "CS Theory" },
  { label: "Systems", value: "Systems" },
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
    useState("mine");

  const [discoverGroups, setDiscoverGroups] =
    useState([]);

  const [myGroups, setMyGroups] =
    useState([]);

  const [myFilter, setMyFilter] =
    useState("all");

  const [search, setSearch] =
    useState("");

  const [discoverCategory, setDiscoverCategory] =
    useState("all");

  const [selectedGroup, setSelectedGroup] =
    useState(null);

  const [groupsLoading, setGroupsLoading] =
    useState(false);

  const [pageError, setPageError] =
    useState("");

  const [mutationLoading, setMutationLoading] =
    useState(false);

  const [groupSettingsOpen, setGroupSettingsOpen] =
    useState(false);

  const [groupDetailsTab, setGroupDetailsTab] =
    useState("overview");

  const [groupDetailsMemberSearch, setGroupDetailsMemberSearch] =
    useState("");

  const [groupDetailsMemberFilter, setGroupDetailsMemberFilter] =
    useState("all");

  const [groupDetailsMemberMenuId, setGroupDetailsMemberMenuId] =
    useState(null);

  const [detailsForm, setDetailsForm] =
    useState({
      name: "",
      description: "",
    });

  const [messageSearch, setMessageSearch] =
    useState("");

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

  const [addMemberModalOpen, setAddMemberModalOpen] =
    useState(false);

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

  const [channelActionMenuId, setChannelActionMenuId] =
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

  const [selectedMentionIds, setSelectedMentionIds] =
    useState([]);

  const [selectedAiMode, setSelectedAiMode] =
    useState(null);

  const [responseFormat, setResponseFormat] =
    useState("paragraph");

  const messagesEndRef = useRef(null);

  /* =======================================================
     SIDEBAR / URL VIEW SYNC
     ======================================================= */

  const requestedGroupView =
    searchParams.get("view");

  useEffect(() => {
    if (requestedGroupView === "mine") {
      setActiveView("mine");
      setMyFilter("all");
      setSelectedGroup(null);
      return;
    }

    if (requestedGroupView === "public") {
      setActiveView("mine");
      setMyFilter("public");
      setSelectedGroup(null);
      return;
    }

    if (requestedGroupView === "private") {
      setActiveView("mine");
      setMyFilter("private");
      setSelectedGroup(null);
      return;
    }

    if (requestedGroupView === "discover") {
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

  function openGroupDetails() {
    if (!selectedGroup) {
      return;
    }

    setGroupDetailsTab("overview");
    setGroupDetailsMemberSearch("");
    setGroupDetailsMemberFilter("all");
    setGroupDetailsMemberMenuId(null);
    setDetailsForm({
      name: selectedGroup.name || "",
      description: selectedGroup.description || "",
    });
    setAddMemberModalOpen(false);
    setGroupSettingsOpen(true);
  }

  async function handleSaveGroupDetails(event) {
    event.preventDefault();

    if (
      !selectedGroup ||
      !selectedGroup.can_manage ||
      !accessToken ||
      !detailsForm.name.trim()
    ) {
      return;
    }

    setMutationLoading(true);
    setPageError("");

    try {
      const updated = await updateStudyGroup(
        accessToken,
        selectedGroup.id,
        {
          name: detailsForm.name.trim(),
          description: detailsForm.description.trim(),
          visibility: selectedGroup.visibility || "public",
          max_members: selectedGroup.max_members || 30,
        },
      );

      const updatedGroup = updated?.group || updated;

      if (updatedGroup?.id) {
        setSelectedGroup(updatedGroup);
        setDetailsForm({
          name: updatedGroup.name || "",
          description: updatedGroup.description || "",
        });
      }

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
      setAddMemberModalOpen(false);
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
     MEMBER ROLES / OWNERSHIP
     ======================================================= */

  async function handlePromoteMember(member) {
    if (
      !selectedGroup ||
      !selectedGroup.is_owner ||
      !accessToken ||
      member.role !== "member"
    ) {
      return;
    }

    const name =
      member.full_name ||
      member.email ||
      "this member";

    if (!window.confirm(`Promote ${name} to admin?`)) {
      return;
    }

    setMutationLoading(true);
    setPageError("");

    try {
      await updateStudyGroupMemberRole(
        accessToken,
        selectedGroup.id,
        member.user_id,
        "admin",
      );

      await loadMembers();
      await refreshGroupLists();
    } catch (error) {
      setPageError(apiMessage(error));
    } finally {
      setMutationLoading(false);
    }
  }

  async function handleDemoteAdmin(member) {
    if (
      !selectedGroup ||
      !selectedGroup.is_owner ||
      !accessToken ||
      member.role !== "admin"
    ) {
      return;
    }

    const name =
      member.full_name ||
      member.email ||
      "this admin";

    if (!window.confirm(`Demote ${name} to member?`)) {
      return;
    }

    setMutationLoading(true);
    setPageError("");

    try {
      await updateStudyGroupMemberRole(
        accessToken,
        selectedGroup.id,
        member.user_id,
        "member",
      );

      await loadMembers();
      await refreshGroupLists();
    } catch (error) {
      setPageError(apiMessage(error));
    } finally {
      setMutationLoading(false);
    }
  }

  async function handleTransferOwnership(member) {
    if (
      !selectedGroup ||
      !selectedGroup.is_owner ||
      !accessToken ||
      member.role === "owner"
    ) {
      return;
    }

    const name =
      member.full_name ||
      member.email ||
      "this member";

    const confirmed = window.confirm(
      `Transfer ownership of "${selectedGroup.name}" to ${name}?\n\nYou will become an admin.`,
    );

    if (!confirmed) {
      return;
    }

    setMutationLoading(true);
    setPageError("");

    try {
      await transferStudyGroupOwnership(
        accessToken,
        selectedGroup.id,
        member.user_id,
      );

      const result = await getMyGroups(accessToken, {
        filter: "all",
        page: 1,
        pageSize: 20,
      });

      const updatedGroups = extractItems(result);
      setMyGroups(updatedGroups);

      const updatedGroup = updatedGroups.find(
        (group) => group.id === selectedGroup.id,
      );

      if (updatedGroup) {
        setSelectedGroup(updatedGroup);
      }

      await loadMembers(updatedGroup || selectedGroup);
      await loadDiscover();
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
    skipConfirm = false,
  ) {
    if (
      !selectedGroup ||
      !accessToken
    ) {
      return;
    }

    if (!skipConfirm) {
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
    }

    setChannelActionMenuId(null);
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

    setShowMentionMenu(
      Boolean(match),
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

  const browseDiscoverGroups = useMemo(() => {
    if (discoverCategory === "all") {
      return discoverGroups;
    }

    return discoverGroups.filter((group) => {
      const category = String(group.category || "").trim().toLowerCase();
      return category === discoverCategory.toLowerCase();
    });
  }, [discoverGroups, discoverCategory]);

  function showMyGroupsBrowse() {
    setSearchParams({ view: "mine" });
    setActiveView("mine");
    setMyFilter("all");
    setSelectedGroup(null);
  }

  function showDiscoverBrowse() {
    setSearchParams({ view: "discover" });
    setActiveView("discover");
    setDiscoverCategory("all");
    setSelectedGroup(null);
  }

  const filteredMessages = useMemo(() => {
    const query = messageSearch.trim().toLowerCase();

    if (!query) {
      return messages;
    }

    return messages.filter((item) => {
      const member = members.find(
        (groupMember) => groupMember.user_id === item.author_id,
      );

      const sender =
        member?.full_name || member?.email || "Student";

      const aiContent = item.ai_response?.content || "";

      return [sender, item.content || "", aiContent]
        .join(" ")
        .toLowerCase()
        .includes(query);
    });
  }, [messageSearch, messages, members]);

  /* =======================================================
     RENDER
     ======================================================= */

  return (
    <AppShell>
      <div
        className={`group-study-page ${
          !selectedGroup ? "sg-browse-mode" : "sg-workspace-mode"
        } ${
          groupsPanelCollapsed
            ? "groups-panel-collapsed"
            : ""
        } ${
          detailsPanelCollapsed
            ? "details-panel-collapsed"
            : ""
        }`}
      >

        {!selectedGroup && (
          <section className="sg-browse">
            <div className="sg-browse-topbar">
              <div className="sg-browse-tabs">
                <button
                  type="button"
                  className={activeView === "mine" ? "active" : ""}
                  onClick={showMyGroupsBrowse}
                >
                  My Groups
                  {myGroups.length > 0 && (
                    <span>{myGroups.length}</span>
                  )}
                </button>

                <button
                  type="button"
                  className={activeView === "discover" ? "active" : ""}
                  onClick={showDiscoverBrowse}
                >
                  Discover
                </button>
              </div>

              <button
                className="sg-browse-create"
                type="button"
                onClick={openCreateGroup}
              >
                <Plus size={16} />
                Create Group
              </button>
            </div>

            {pageError && (
              <div className="sg-error">{pageError}</div>
            )}

            {activeView === "discover" && (
              <div className="sg-discover-controls">
                <label className="sg-browse-search">
                  <Search size={17} />
                  <input
                    value={search}
                    onChange={(event) => setSearch(event.target.value)}
                    placeholder="Search groups..."
                  />
                </label>

                <div className="sg-category-tabs">
                  {DISCOVER_FILTERS.map((filter) => (
                    <button
                      key={filter.value}
                      type="button"
                      className={discoverCategory === filter.value ? "active" : ""}
                      onClick={() => setDiscoverCategory(filter.value)}
                    >
                      {filter.label}
                    </button>
                  ))}
                </div>
              </div>
            )}

            {groupsLoading ? (
              <div className="sg-browse-empty">Loading groups...</div>
            ) : activeView === "mine" ? (
              myGroups.length === 0 ? (
                <div className="sg-browse-empty">You have not joined any study groups yet.</div>
              ) : (
                <div className="sg-my-groups-list">
                  {myGroups.map((group) => (
                    <button
                      key={group.id}
                      type="button"
                      className="sg-my-group-row"
                      onClick={() => openGroup(group)}
                    >
                      <div className="sg-group-avatar">{initials(group.name)}</div>
                      <div className="sg-my-group-copy">
                        <div className="sg-group-title-line">
                          <strong>{group.name}</strong>
                          {group.membership_role && (
                            <span className={`sg-role-badge ${group.membership_role}`}>
                              {group.membership_role}
                            </span>
                          )}
                          {group.visibility && (
                            <span className={`sg-visibility-badge ${group.visibility}`}>
                              {group.visibility}
                            </span>
                          )}
                        </div>
                        <div className="sg-group-meta">
                          {group.subject || group.course || group.description || null}
                          {(group.subject || group.course || group.description) && group.member_count != null ? " · " : ""}
                          {group.member_count != null ? `${group.member_count} members` : ""}
                          {group.online_count != null ? ` · ${group.online_count} online` : ""}
                        </div>
                      </div>
                    </button>
                  ))}
                </div>
              )
            ) : browseDiscoverGroups.length === 0 ? (
              <div className="sg-browse-empty">No public groups found.</div>
            ) : (
              <div className="sg-discover-grid">
                {browseDiscoverGroups.map((group) => (
                  <article className="sg-discover-card" key={group.id}>
                    <div className="sg-discover-card-head">
                      <div className="sg-group-avatar">{initials(group.name)}</div>
                      {group.category && (
                        <span className="sg-category-badge">{group.category}</span>
                      )}
                    </div>

                    <strong className="sg-discover-name">{group.name}</strong>
                    {(group.subject || group.course) && (
                      <span className="sg-discover-subject">
                        {group.subject || group.course}
                      </span>
                    )}
                    {group.description && (
                      <p>{group.description}</p>
                    )}

                    <div className="sg-discover-footer">
                      <span>
                        {group.member_count != null
                          ? `${group.member_count} ${group.member_count === 1 ? "member" : "members"}`
                          : ""}
                        {group.online_count != null ? ` · ${group.online_count} online` : ""}
                      </span>

                      {group.is_member ? (
                        <button type="button" onClick={() => openGroup(group)}>
                          Open
                        </button>
                      ) : (
                        <button
                          type="button"
                          disabled={mutationLoading}
                          onClick={() => handleJoin(group)}
                        >
                          Join
                        </button>
                      )}
                    </div>
                  </article>
                ))}
              </div>
            )}
          </section>
        )}

        {selectedGroup && (
          <>
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

        {/* DISCOVER PUBLIC / MY GROUPS + GROUP PANEL COLLAPSE */}

        <div className="group-view-tabs">
          <div className="group-view-tab-buttons">
            <button
              type="button"
              className={
                activeView === "discover"
                  ? "active"
                  : ""
              }
              onClick={() => {
                setSearchParams({
                  view: "discover",
                });

                setActiveView("discover");
                setSelectedGroup(null);
              }}
            >
              Discover Public
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
                  view: "mine",
                });

                setActiveView("mine");
                setSelectedGroup(null);
              }}
            >
              My Groups
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
            onClick={() =>
              setGroupsPanelCollapsed(
                (current) =>
                  !current,
              )
            }
          >
            {groupsPanelCollapsed ? (
              <ChevronRight size={17} />
            ) : (
              <ChevronLeft size={17} />
            )}
          </button>
        </div>

        {/* DISCOVER SEARCH / MY GROUPS FILTERS */}

        {activeView === "discover" ? (
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
          <div className="discover-toolbar">
            <div className="group-view-tab-buttons">
              {[
                ["all", "All"],
                ["public", "Public"],
                ["private", "Private"],
                ["owned", "Owned"],
              ].map(([value, label]) => (
                <button
                  key={value}
                  type="button"
                  className={
                    myFilter === value
                      ? "active"
                      : ""
                  }
                  onClick={() => {
                    setMyFilter(value);
                    setSelectedGroup(null);
                  }}
                >
                  {label}
                </button>
              ))}
            </div>
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

                  <div className="workspace-tools">
                    <label className="workspace-message-search">
                      <Search size={15} />
                      <input
                        type="search"
                        value={messageSearch}
                        onChange={(event) =>
                          setMessageSearch(event.target.value)
                        }
                        placeholder="Search messages..."
                        aria-label="Search messages"
                      />
                    </label>

                    <button
                      type="button"
                      className="workspace-settings-button"
                      title="Group settings"
                      aria-label="Group settings"
                      onClick={openGroupDetails}
                    >
                      <Settings size={17} />
                    </button>
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

                    <button
                      type="button"
                      className="workspace-back-button"
                      onClick={() => {
                        setSelectedGroup(null);
                        setSelectedChannel(null);
                        setChannels([]);
                        setMembers([]);
                        setMessages([]);
                      }}
                    >
                      <ChevronLeft size={15} />
                      All Groups
                    </button>

                    <div className="workspace-sidebar-group">
                      <div className="workspace-sidebar-avatar">
                        {initials(selectedGroup.name)}
                      </div>

                      <div className="workspace-sidebar-copy">
                        <div className="workspace-sidebar-name">
                          {selectedGroup.name}
                        </div>
                        <div className="workspace-sidebar-meta">
                          {selectedGroup.member_count ?? members.length} members
                          {selectedGroup.membership_role
                            ? ` · ${selectedGroup.membership_role}`
                            : ""}
                        </div>
                      </div>
                    </div>

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
                              onClick={() => {
                                setSelectedChannel(
                                  channel,
                                );
                                setChannelActionMenuId(
                                  null,
                                );
                              }}
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
                              <div className="channel-row-menu">
                                <button
                                  type="button"
                                  className="channel-more-button"
                                  aria-label={`Channel options for ${channel.name}`}
                                  title="Channel options"
                                  onClick={(event) => {
                                    event.stopPropagation();
                                    setChannelActionMenuId(
                                      (current) =>
                                        current === channel.id
                                          ? null
                                          : channel.id,
                                    );
                                  }}
                                >
                                  <MoreHorizontal size={16} />
                                </button>

                                {channelActionMenuId === channel.id && (
                                  <div className="channel-inline-actions">
                                    <button
                                      type="button"
                                      className="danger"
                                      disabled={mutationLoading}
                                      onClick={() =>
                                        handleDeleteChannel(
                                          channel,
                                          true,
                                        )
                                      }
                                    >
                                      Delete
                                    </button>

                                    <button
                                      type="button"
                                      onClick={() =>
                                        setChannelActionMenuId(
                                          null,
                                        )
                                      }
                                    >
                                      Cancel
                                    </button>
                                  </div>
                                )}
                              </div>
                            )}

                          </div>
                        ),
                      )
                    )}

                    {channelModal === "create" && (
                      <form
                        className="inline-channel-create"
                        onSubmit={submitChannel}
                      >
                        <input
                          autoFocus
                          value={channelForm.name}
                          onChange={(event) =>
                            setChannelForm((current) => ({
                              ...current,
                              name: event.target.value,
                            }))
                          }
                          placeholder="new-channel"
                          maxLength={100}
                          required
                        />

                        <div className="inline-channel-create-actions">
                          <button
                            type="submit"
                            className="primary"
                            disabled={mutationLoading || !channelForm.name.trim()}
                          >
                            Add
                          </button>
                          <button
                            type="button"
                            onClick={() => {
                              setChannelModal(null);
                              setChannelForm({ name: "", description: "" });
                            }}
                          >
                            Cancel
                          </button>
                        </div>
                      </form>
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

                              <span className={`member-role-badge ${role}`}>
                                {role}
                              </span>
                            </div>
                          );
                        },
                      )
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
                          ) : filteredMessages.length ===
                            0 ? (
                            <div className="sg-empty">
                              {messageSearch.trim()
                                ? "No messages match your search."
                                : "No messages yet. Start the conversation."}
                            </div>
                          ) : (
                            filteredMessages.map(
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
                                  <Fragment
                                    key={item.id}
                                  >
                                    <div
                                      className={`group-message ${
                                        isOwnMessage
                                          ? "own-message"
                                          : ""
                                      }`}
                                    >
                                      <div className="message-avatar">
                                        {initials(
                                          sender,
                                        )}
                                      </div>

                                      <div className="message-main">
                                        <div className="message-meta">
                                          <strong>
                                            {sender}
                                          </strong>

                                          <span>
                                            {timeLabel(
                                              item.sent_at,
                                            )}
                                          </span>
                                        </div>

                                        <p className="message-content">
                                          {item.content}
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
                                      </div>
                                    </div>

                                    {aiResponse?.content && (
                                      <div className="group-message ai-response-message">
                                        <div className="message-avatar ai-avatar">
                                          <Bot size={16} />
                                        </div>

                                        <div className="message-main">
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

                                          <div className="ai-message">
                                            <SimpleMarkdown>
                                              {aiResponse.content}
                                            </SimpleMarkdown>
                                          </div>
                                        </div>
                                      </div>
                                    )}
                                  </Fragment>
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

                            <div className="message-input-wrap">

                              {/* @ PICKER */}

                              {showMentionMenu && (
                                <div className="mention-menu">

                                  <div className="mention-section-title">
                                    AI
                                    Companions
                                  </div>

                                  {AI_MODES.map(
                                    (ai) => (
                                      <button
                                        type="button"
                                        key={
                                          ai.value
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

                                  <div className="mention-section-title">
                                    Group
                                    Members
                                  </div>

                                  {members.map(
                                    (member) => {
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
          </>
        )}

      </div>

      {/* ===================================================
          GROUP DETAILS DRAWER
          =================================================== */}

      {groupSettingsOpen && selectedGroup && (
        <aside
          className="group-details-drawer"
          aria-label="Group details"
        >
          <div className="group-details-head">
            <h2>Group Details</h2>

            <button
              type="button"
              className="group-details-close"
              onClick={() => {
                setAddMemberModalOpen(false);
                setGroupSettingsOpen(false);
              }}
              aria-label="Close group details"
              title="Close"
            >
              <X size={18} />
            </button>
          </div>

          <div className="group-details-tabs">
            {[
              ["overview", "Overview"],
              ["members", `Members (${members.length})`],
              ["settings", "Settings"],
            ].map(([value, label]) => (
              <button
                key={value}
                type="button"
                className={
                  groupDetailsTab === value
                    ? "active"
                    : ""
                }
                onClick={() => {
                  setGroupDetailsTab(value);
                  setGroupDetailsMemberMenuId(null);
                }}
              >
                {label}
              </button>
            ))}
          </div>

          <div className="group-details-body">
            {groupDetailsTab === "overview" && (() => {
              const owner =
                members.find((member) => member.role === "owner");

              const founder =
                members.find(
                  (member) =>
                    member.user_id === selectedGroup.created_by,
                );

              const createdDate = selectedGroup.created_at
                ? new Date(selectedGroup.created_at).toLocaleDateString(
                    undefined,
                    {
                      year: "numeric",
                      month: "short",
                      day: "numeric",
                    },
                  )
                : null;

              return (
                <div className="group-overview">
                  <div className="group-overview-identity">
                    <div className="group-overview-avatar">
                      {initials(selectedGroup.name)}
                    </div>

                    <h3>{selectedGroup.name}</h3>

                    <div className="group-overview-badges">
                      <span className="group-visibility-badge">
                        {selectedGroup.visibility === "private"
                          ? "Private"
                          : "Public"}
                      </span>

                      {selectedGroup.membership_role && (
                        <span
                          className={`member-role-badge ${selectedGroup.membership_role}`}
                        >
                          {selectedGroup.membership_role}
                        </span>
                      )}
                    </div>
                  </div>

                  <div className="group-overview-description">
                    <span>Description</span>
                    <p>
                      {selectedGroup.description ||
                        "No description provided."}
                    </p>
                  </div>

                  <div className="group-overview-facts">
                    {createdDate && (
                      <div>
                        <span>Created</span>
                        <strong>{createdDate}</strong>
                      </div>
                    )}

                    {founder && (
                      <div>
                        <span>Founded by</span>
                        <strong>
                          {founder.full_name ||
                            founder.email ||
                            "Member"}
                        </strong>
                      </div>
                    )}

                    {owner && (
                      <div>
                        <span>Current owner</span>
                        <strong>
                          {owner.full_name ||
                            owner.email ||
                            "Owner"}
                        </strong>
                      </div>
                    )}

                    <div>
                      <span>Members</span>
                      <strong>
                        {selectedGroup.member_count ??
                          members.length}
                      </strong>
                    </div>
                  </div>
                </div>
              );
            })()}

            {groupDetailsTab === "members" && (
              <div className="group-details-members">
                <label className="group-details-search">
                  <Search size={15} />
                  <input
                    type="search"
                    value={groupDetailsMemberSearch}
                    onChange={(event) =>
                      setGroupDetailsMemberSearch(
                        event.target.value,
                      )
                    }
                    placeholder="Search members..."
                  />
                </label>

                <div className="group-member-toolbar">
                  <div className="group-member-filters">
                    {["all", "owner", "admin", "member"].map(
                      (role) => (
                        <button
                          key={role}
                          type="button"
                          className={
                            groupDetailsMemberFilter === role
                              ? "active"
                              : ""
                          }
                          onClick={() =>
                            setGroupDetailsMemberFilter(role)
                          }
                        >
                          {role === "all"
                            ? "All"
                            : role[0].toUpperCase() + role.slice(1)}
                        </button>
                      ),
                    )}
                  </div>

                  {selectedGroup.can_manage && (
                    <button
                      type="button"
                      className="group-member-add-label"
                      onClick={() => {
                        setMemberEmail("");
                        setAddMemberModalOpen(true);
                      }}
                    >
                      <Plus size={13} />
                      Add
                    </button>
                  )}
                </div>

                <div className="group-details-member-list">
                  {members
                    .filter((member) => {
                      const role = member.role || "member";

                      if (
                        groupDetailsMemberFilter !== "all" &&
                        role !== groupDetailsMemberFilter
                      ) {
                        return false;
                      }

                      const query =
                        groupDetailsMemberSearch
                          .trim()
                          .toLowerCase();

                      if (!query) {
                        return true;
                      }

                      return [
                        member.full_name,
                        member.email,
                        role,
                      ]
                        .filter(Boolean)
                        .some((value) =>
                          String(value)
                            .toLowerCase()
                            .includes(query),
                        );
                    })
                    .map((member) => {
                      const name =
                        member.full_name ||
                        member.email ||
                        "Student";

                      const role =
                        member.role ||
                        "member";

                      const isCurrentUser =
                        Boolean(
                          user?.id &&
                            member.user_id === user.id,
                        );

                      const canOpenActions =
                        selectedGroup.can_manage &&
                        role !== "owner" &&
                        !isCurrentUser;

                      return (
                        <div
                          className="group-details-member"
                          key={member.user_id}
                        >
                          <div className="group-details-member-avatar">
                            {initials(name)}
                          </div>

                          <div className="group-details-member-info">
                            <div>
                              <strong>{name}</strong>

                              {isCurrentUser && (
                                <small className="member-you">
                                  (you)
                                </small>
                              )}

                              <span
                                className={`member-role-badge ${role}`}
                              >
                                {role}
                              </span>
                            </div>

                            {member.email && (
                              <small>{member.email}</small>
                            )}
                          </div>

                          {canOpenActions && (
                            <div className="group-member-menu-wrap">
                              <button
                                type="button"
                                className="group-member-menu-button"
                                onClick={() =>
                                  setGroupDetailsMemberMenuId(
                                    (current) =>
                                      current === member.user_id
                                        ? null
                                        : member.user_id,
                                  )
                                }
                                aria-label={`Manage ${name}`}
                              >
                                <MoreHorizontal size={17} />
                              </button>

                              {groupDetailsMemberMenuId ===
                                member.user_id && (
                                <div className="group-member-menu">
                                  {selectedGroup.is_owner &&
                                    role === "member" && (
                                      <button
                                        type="button"
                                        onClick={async () => {
                                          setGroupDetailsMemberMenuId(null);
                                          await handlePromoteMember(member);
                                        }}
                                      >
                                        Make admin
                                      </button>
                                    )}

                                  {selectedGroup.is_owner &&
                                    role === "admin" && (
                                      <button
                                        type="button"
                                        onClick={async () => {
                                          setGroupDetailsMemberMenuId(null);
                                          await handleDemoteAdmin(member);
                                        }}
                                      >
                                        Make member
                                      </button>
                                    )}

                                  {selectedGroup.is_owner && (
                                    <button
                                      type="button"
                                      onClick={async () => {
                                        setGroupDetailsMemberMenuId(null);
                                        await handleTransferOwnership(member);
                                      }}
                                    >
                                      Transfer ownership
                                    </button>
                                  )}

                                  {role === "member" && (
                                    <button
                                      type="button"
                                      className="danger"
                                      onClick={async () => {
                                        setGroupDetailsMemberMenuId(null);
                                        await handleRemoveMember(member);
                                      }}
                                    >
                                      Remove member
                                    </button>
                                  )}
                                </div>
                              )}
                            </div>
                          )}
                        </div>
                      );
                    })}
                </div>
              </div>
            )}

            {groupDetailsTab === "settings" && (
              <div className="group-details-settings">
                {selectedGroup.can_manage && (
                  <form
                    className="group-information-card"
                    onSubmit={handleSaveGroupDetails}
                  >
                    <h3>Group Information</h3>

                    <label>
                      <span>Name</span>
                      <input
                        type="text"
                        value={detailsForm.name}
                        onChange={(event) =>
                          setDetailsForm((current) => ({
                            ...current,
                            name: event.target.value,
                          }))
                        }
                        required
                      />
                    </label>

                    <label>
                      <span>Description</span>
                      <textarea
                        value={detailsForm.description}
                        onChange={(event) =>
                          setDetailsForm((current) => ({
                            ...current,
                            description: event.target.value,
                          }))
                        }
                        rows={4}
                      />
                    </label>

                    <button
                      type="submit"
                      className="group-details-primary"
                      disabled={mutationLoading}
                    >
                      Save Changes
                    </button>
                  </form>
                )}

                {!selectedGroup.can_manage && (
                  <div className="group-information-card">
                    <h3>Group Information</h3>
                    <p className="group-settings-readonly">
                      Group information can only be edited by
                      the owner or an administrator.
                    </p>
                  </div>
                )}

                {selectedGroup.is_member &&
                  !selectedGroup.is_owner && (
                    <div className="group-danger-card">
                      <h3>Leave Group</h3>
                      <p>
                        You will lose access to all channels and
                        messages.
                      </p>

                      <button
                        type="button"
                        className="group-details-danger-outline"
                        disabled={mutationLoading}
                        onClick={async () => {
                          setGroupSettingsOpen(false);
                          await handleLeave();
                        }}
                      >
                        Leave Group
                      </button>
                    </div>
                  )}

                {selectedGroup.is_owner && (
                  <>
                    <div className="group-information-card">
                      <h3>Ownership</h3>
                      <p className="group-settings-readonly">
                        Transfer ownership to another member from
                        the Members tab before leaving this group.
                      </p>
                    </div>

                    <div className="group-danger-card">
                      <h3>Delete Group</h3>
                      <p>
                        Permanently delete this study group and
                        its access.
                      </p>

                      <button
                        type="button"
                        className="group-details-danger-outline"
                        disabled={mutationLoading}
                        onClick={async () => {
                          setGroupSettingsOpen(false);
                          await handleDeleteGroup();
                        }}
                      >
                        Delete Group
                      </button>
                    </div>
                  </>
                )}
              </div>
            )}
          </div>
        </aside>
      )}

      {addMemberModalOpen && selectedGroup && (
        <div
          className="sg-add-member-backdrop"
          role="presentation"
          onMouseDown={(event) => {
            if (event.target === event.currentTarget) {
              setAddMemberModalOpen(false);
            }
          }}
        >
          <section
            className="sg-add-member-modal"
            role="dialog"
            aria-modal="true"
            aria-labelledby="sg-add-member-title"
          >
            <div className="sg-add-member-modal-head">
              <div>
                <h3 id="sg-add-member-title">Add Member</h3>
                <p>{selectedGroup.name}</p>
              </div>

              <button
                type="button"
                className="sg-add-member-close"
                onClick={() => setAddMemberModalOpen(false)}
                aria-label="Close add member dialog"
              >
                <X size={18} />
              </button>
            </div>

            <form
              className="sg-add-member-modal-body"
              onSubmit={handleAddMember}
            >
              <label htmlFor="sg-member-email">Email address</label>
              <input
                id="sg-member-email"
                type="email"
                value={memberEmail}
                onChange={(event) => setMemberEmail(event.target.value)}
                placeholder="student@nus.edu.sg"
                autoFocus
                required
              />

              <div className="sg-add-member-modal-actions">
                <button
                  type="button"
                  className="sg-add-member-cancel"
                  onClick={() => setAddMemberModalOpen(false)}
                >
                  Cancel
                </button>

                <button
                  type="submit"
                  className="sg-add-member-send"
                  disabled={mutationLoading || !memberEmail.trim()}
                >
                  {mutationLoading ? "Adding..." : "Add Member"}
                </button>
              </div>
            </form>
          </section>
        </div>
      )}

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

      {channelModal === "edit" && (
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