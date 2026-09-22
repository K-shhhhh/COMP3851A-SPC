import { useEffect, useRef, useState } from "react";
import {
  Hash,
  Lock,
  MoreVertical,
  Plus,
  Search,
  Users,
  X,
} from "lucide-react";

import AppShell from "../../components/layout/AppShell.jsx";

import "./groupStudy.css";

function generateId() {
  return `${Date.now()}-${Math.random().toString(36).slice(2, 10)}`;
}

function formatChannelName(value) {
  return value
    .trim()
    .toLowerCase()
    .replace(/\s+/g, "-")
    .replace(/[^a-z0-9-_]/g, "");
}

const createDefaultChannels = () => [
  {
    id: generateId(),
    name: "general",
    description: "General discussion and announcements",
    isDefault: true,
    messages: [],
  },
  {
    id: generateId(),
    name: "resources",
    description: "Share useful study resources",
    isDefault: false,
    messages: [],
  },
  {
    id: generateId(),
    name: "study-sessions",
    description: "Organise study sessions",
    isDefault: false,
    messages: [],
  },
];

function GroupStudyPage() {
  const [groups, setGroups] = useState([]);

  const [groupType, setGroupType] = useState("public");
  const [selectedGroupId, setSelectedGroupId] = useState(null);
  const [selectedChannelId, setSelectedChannelId] = useState(null);

  const [search, setSearch] = useState("");
  const [message, setMessage] = useState("");

  const [showCreateGroup, setShowCreateGroup] = useState(false);

  const [showGroupMenu, setShowGroupMenu] = useState(false);
  const [openChannelMenuId, setOpenChannelMenuId] = useState(null);

  const [groupModal, setGroupModal] = useState(null);
  const [channelModal, setChannelModal] = useState(null);

  const [editingChannelId, setEditingChannelId] = useState(null);
  const [editValue, setEditValue] = useState("");

  const [newGroup, setNewGroup] = useState({
    name: "",
    subject: "",
    type: "public",
  });

  /*
   * References for dropdown menus.
   */
  const groupMenuRef = useRef(null);
  const channelMenuRef = useRef(null);

  /*
   * Reference placed at the bottom of the chat.
   *
   * We use it to automatically scroll to the newest
   * message after a message is sent or a channel changes.
   */
  const messagesEndRef = useRef(null);

  /*
   * Close dropdown menus when clicking outside them.
   */
  useEffect(() => {
    function handleOutsideClick(event) {
      const clickedInsideGroupMenu =
        groupMenuRef.current?.contains(event.target);

      const clickedInsideChannelMenu =
        channelMenuRef.current?.contains(event.target);

      if (!clickedInsideGroupMenu) {
        setShowGroupMenu(false);
      }

      if (!clickedInsideChannelMenu) {
        setOpenChannelMenuId(null);
      }
    }

    document.addEventListener("mousedown", handleOutsideClick);

    return () => {
      document.removeEventListener("mousedown", handleOutsideClick);
    };
  }, []);

  const visibleGroups = groups.filter(
    (group) =>
      group.type === groupType &&
      group.name.toLowerCase().includes(search.toLowerCase()),
  );

  const selectedGroup =
    groups.find((group) => group.id === selectedGroupId) ?? null;

  const selectedChannel =
    selectedGroup?.channels.find(
      (channel) => channel.id === selectedChannelId,
    ) ?? null;

  const editingChannel =
    selectedGroup?.channels.find(
      (channel) => channel.id === editingChannelId,
    ) ?? null;

  /*
   * Automatically scroll to the bottom of the chat.
   *
   * This runs when:
   * - a new message is added;
   * - the selected channel changes;
   * - the selected group changes.
   */
  useEffect(() => {
    if (!selectedChannel) return;

    messagesEndRef.current?.scrollIntoView({
      behavior: "smooth",
      block: "end",
    });
  }, [
    selectedChannelId,
    selectedGroupId,
    selectedChannel?.messages.length,
  ]);

  function closeMenus() {
    setShowGroupMenu(false);
    setOpenChannelMenuId(null);
  }

  function closeGroupModal() {
    setGroupModal(null);
    setEditValue("");
  }

  function closeChannelModal() {
    setChannelModal(null);
    setEditingChannelId(null);
    setEditValue("");
  }

  function selectGroup(group) {
    setSelectedGroupId(group.id);
    setSelectedChannelId(group.channels[0]?.id ?? null);
    setMessage("");
    closeMenus();
  }

  function changeGroupType(type) {
    setGroupType(type);
    setSearch("");
    setMessage("");
    closeMenus();

    const firstGroup = groups.find((group) => group.type === type);

    if (firstGroup) {
      setSelectedGroupId(firstGroup.id);
      setSelectedChannelId(firstGroup.channels[0]?.id ?? null);
    } else {
      setSelectedGroupId(null);
      setSelectedChannelId(null);
    }
  }

  function handleCreateGroup(event) {
    event.preventDefault();

    const name = newGroup.name.trim();
    const subject = newGroup.subject.trim();

    if (!name || !subject) return;

    const channels = createDefaultChannels();

    const group = {
      id: generateId(),
      name,
      subject,
      type: newGroup.type,

      members: [
        {
          id: generateId(),
          name: "John Student",
          initials: "JS",
        },
      ],

      channels,
    };

    setGroups((currentGroups) => [...currentGroups, group]);

    setGroupType(group.type);
    setSelectedGroupId(group.id);
    setSelectedChannelId(channels[0].id);

    setNewGroup({
      name: "",
      subject: "",
      type: "public",
    });

    setShowCreateGroup(false);
  }

  function handleRenameGroup(event) {
    event.preventDefault();

    const name = editValue.trim();

    if (!name || !selectedGroup) return;

    setGroups((currentGroups) =>
      currentGroups.map((group) =>
        group.id === selectedGroup.id
          ? {
              ...group,
              name,
            }
          : group,
      ),
    );

    closeGroupModal();
  }

  function handleAddChannel(event) {
    event.preventDefault();

    if (!selectedGroup) return;

    const originalName = editValue.trim();
    const name = formatChannelName(originalName);

    if (!name) return;

    const channelAlreadyExists = selectedGroup.channels.some(
      (channel) =>
        channel.name.toLowerCase() === name.toLowerCase(),
    );

    if (channelAlreadyExists) return;

    const channel = {
      id: generateId(),
      name,
      description: `${originalName} discussion`,
      isDefault: false,
      messages: [],
    };

    setGroups((currentGroups) =>
      currentGroups.map((group) =>
        group.id === selectedGroup.id
          ? {
              ...group,
              channels: [...group.channels, channel],
            }
          : group,
      ),
    );

    setSelectedChannelId(channel.id);

    closeGroupModal();
  }

  function handleDeleteGroup() {
    if (!selectedGroup) return;

    const deletedGroupId = selectedGroup.id;

    const remainingGroups = groups.filter(
      (group) => group.id !== deletedGroupId,
    );

    setGroups(remainingGroups);

    const nextGroup = remainingGroups.find(
      (group) => group.type === groupType,
    );

    if (nextGroup) {
      setSelectedGroupId(nextGroup.id);
      setSelectedChannelId(nextGroup.channels[0]?.id ?? null);
    } else {
      setSelectedGroupId(null);
      setSelectedChannelId(null);
    }

    setMessage("");
    closeMenus();
    closeGroupModal();
  }

  function openRenameChannel(channel) {
    setEditingChannelId(channel.id);
    setEditValue(channel.name);
    setChannelModal("rename");
    setOpenChannelMenuId(null);
  }

  function openDeleteChannel(channel) {
    if (channel.isDefault) return;

    setEditingChannelId(channel.id);
    setEditValue("");
    setChannelModal("delete");
    setOpenChannelMenuId(null);
  }

  function handleRenameChannel(event) {
    event.preventDefault();

    if (!selectedGroup || !editingChannel) return;

    const newName = formatChannelName(editValue);

    if (!newName) return;

    const channelAlreadyExists = selectedGroup.channels.some(
      (channel) =>
        channel.id !== editingChannel.id &&
        channel.name.toLowerCase() === newName.toLowerCase(),
    );

    if (channelAlreadyExists) return;

    setGroups((currentGroups) =>
      currentGroups.map((group) => {
        if (group.id !== selectedGroup.id) return group;

        return {
          ...group,

          channels: group.channels.map((channel) =>
            channel.id === editingChannel.id
              ? {
                  ...channel,
                  name: newName,
                  description: channel.isDefault
                    ? channel.description
                    : `${editValue.trim()} discussion`,
                }
              : channel,
          ),
        };
      }),
    );

    closeChannelModal();
  }

  function handleDeleteChannel() {
    if (!selectedGroup || !editingChannel) return;

    if (editingChannel.isDefault) return;

    const remainingChannels = selectedGroup.channels.filter(
      (channel) => channel.id !== editingChannel.id,
    );

    setGroups((currentGroups) =>
      currentGroups.map((group) =>
        group.id === selectedGroup.id
          ? {
              ...group,
              channels: remainingChannels,
            }
          : group,
      ),
    );

    if (selectedChannelId === editingChannel.id) {
      const nextChannel =
        remainingChannels.find((channel) => channel.isDefault) ??
        remainingChannels[0] ??
        null;

      setSelectedChannelId(nextChannel?.id ?? null);
      setMessage("");
    }

    closeChannelModal();
  }

  function handleSendMessage(event) {
    event.preventDefault();

    const text = message.trim();

    if (!text || !selectedGroup || !selectedChannel) return;

    const newMessage = {
      id: generateId(),

      author: "John Student",
      initials: "JS",

      time: new Date().toLocaleTimeString([], {
        hour: "2-digit",
        minute: "2-digit",
      }),

      text,
    };

    setGroups((currentGroups) =>
      currentGroups.map((group) => {
        if (group.id !== selectedGroup.id) return group;

        return {
          ...group,

          channels: group.channels.map((channel) => {
            if (channel.id !== selectedChannel.id) {
              return channel;
            }

            return {
              ...channel,
              messages: [...channel.messages, newMessage],
            };
          }),
        };
      }),
    );

    setMessage("");
  }

  return (
    <AppShell>
      <div className="study-groups-page">
        {/* =========================
            GROUP LIST
        ========================= */}

        <section className="groups-panel">
          <div className="group-type-toggle">
            <button
              type="button"
              className={groupType === "public" ? "active" : ""}
              onClick={() => changeGroupType("public")}
            >
              <Users size={14} />
              Public
            </button>

            <button
              type="button"
              className={groupType === "private" ? "active" : ""}
              onClick={() => changeGroupType("private")}
            >
              <Lock size={14} />
              Private
            </button>
          </div>

          <button
            type="button"
            className="create-group-button"
            onClick={() => {
              setNewGroup({
                name: "",
                subject: "",
                type: groupType,
              });

              setShowCreateGroup(true);
            }}
          >
            <Plus size={17} />
            Create Group
          </button>

          <div className="group-search">
            <Search size={16} />

            <input
              type="text"
              placeholder="Search groups..."
              value={search}
              onChange={(event) => setSearch(event.target.value)}
            />
          </div>

          {groupType === "private" && (
            <p className="groups-list-label">MY GROUPS</p>
          )}

          <div className="groups-list">
            {visibleGroups.length === 0 ? (
              <div className="groups-empty">
                <Users size={28} />

                <strong>
                  No {groupType === "public" ? "public" : "private"} groups
                </strong>

                <span>Create a group to get started.</span>
              </div>
            ) : (
              visibleGroups.map((group) => (
                <button
                  type="button"
                  key={group.id}
                  className={`group-card ${
                    selectedGroupId === group.id ? "active" : ""
                  }`}
                  onClick={() => selectGroup(group)}
                >
                  <div className="group-card-icon">
                    {group.type === "private" ? (
                      <Lock size={16} />
                    ) : (
                      <Users size={16} />
                    )}
                  </div>

                  <div className="group-card-info">
                    <strong>{group.name}</strong>

                    <span>{group.subject}</span>

                    <div className="group-card-meta">
                      <span>
                        {group.members.length}{" "}
                        {group.members.length === 1
                          ? "member"
                          : "members"}
                      </span>
                    </div>
                  </div>
                </button>
              ))
            )}
          </div>
        </section>

        {/* =========================
            GROUP DETAILS
        ========================= */}

        <aside className="group-details-panel">
          {selectedGroup ? (
            <>
              <div className="selected-group-heading">
                <div className="selected-group-title">
                  <div>
                    <strong>{selectedGroup.name}</strong>

                    <span>
                      {selectedGroup.members.length}{" "}
                      {selectedGroup.members.length === 1
                        ? "member"
                        : "members"}
                    </span>
                  </div>

                  <div
                    className="group-actions-wrapper"
                    ref={groupMenuRef}
                  >
                    <button
                      type="button"
                      className="group-actions-button"
                      aria-label="Group options"
                      onClick={() => {
                        setShowGroupMenu((current) => !current);
                        setOpenChannelMenuId(null);
                      }}
                    >
                      <MoreVertical size={17} />
                    </button>

                    {showGroupMenu && (
                      <div className="group-actions-menu">
                        <button
                          type="button"
                          onClick={() => {
                            setEditValue(selectedGroup.name);
                            setGroupModal("rename");
                            setShowGroupMenu(false);
                          }}
                        >
                          Rename Group
                        </button>

                        <button
                          type="button"
                          onClick={() => {
                            setEditValue("");
                            setGroupModal("add-channel");
                            setShowGroupMenu(false);
                          }}
                        >
                          Add Channel
                        </button>

                        <button
                          type="button"
                          className="danger"
                          onClick={() => {
                            setGroupModal("delete");
                            setShowGroupMenu(false);
                          }}
                        >
                          Delete Group
                        </button>
                      </div>
                    )}
                  </div>
                </div>
              </div>

              {/* CHANNELS */}

              <div className="channels-section">
                <div className="channels-heading">
                  <p>CHANNELS</p>

                  <button
                    type="button"
                    className="add-channel-small-button"
                    aria-label="Add channel"
                    onClick={() => {
                      setEditValue("");
                      setGroupModal("add-channel");
                      closeMenus();
                    }}
                  >
                    <Plus size={14} />
                  </button>
                </div>

                {selectedGroup.channels.map((channel) => (
                  <div
                    className={`channel-row ${
                      selectedChannelId === channel.id ? "active" : ""
                    }`}
                    key={channel.id}
                  >
                    <button
                      type="button"
                      className="channel-main-button"
                      onClick={() => {
                        setSelectedChannelId(channel.id);
                        setMessage("");
                        closeMenus();
                      }}
                    >
                      <Hash size={14} />
                      <span>{channel.name}</span>
                    </button>

                    <div
                      className="channel-actions-wrapper"
                      ref={
                        openChannelMenuId === channel.id
                          ? channelMenuRef
                          : null
                      }
                    >
                      <button
                        type="button"
                        className="channel-actions-button"
                        aria-label={`Options for ${channel.name}`}
                        onClick={(event) => {
                          event.stopPropagation();

                          setOpenChannelMenuId((currentId) =>
                            currentId === channel.id ? null : channel.id,
                          );

                          setShowGroupMenu(false);
                        }}
                      >
                        <MoreVertical size={15} />
                      </button>

                      {openChannelMenuId === channel.id && (
                        <div className="channel-actions-menu">
                          <button
                            type="button"
                            onClick={() => openRenameChannel(channel)}
                          >
                            Rename Channel
                          </button>

                          {!channel.isDefault && (
                            <button
                              type="button"
                              className="danger"
                              onClick={() => openDeleteChannel(channel)}
                            >
                              Delete Channel
                            </button>
                          )}

                          {channel.isDefault && (
                            <span className="channel-protected-label">
                              Default channel
                            </span>
                          )}
                        </div>
                      )}
                    </div>
                  </div>
                ))}
              </div>

              {/* MEMBERS */}

              <div className="members-section">
                <p>MEMBERS</p>

                {selectedGroup.members.map((member) => (
                  <div className="member-row" key={member.id}>
                    <span className="member-avatar">
                      {member.initials}
                    </span>

                    <span>{member.name}</span>
                  </div>
                ))}
              </div>
            </>
          ) : (
            <div className="group-details-empty">
              Select or create a group
            </div>
          )}
        </aside>

        {/* =========================
            CHAT
        ========================= */}

        <section className="group-chat">
          {selectedGroup && selectedChannel ? (
            <>
              <header className="group-chat-header">
                <Hash size={17} />

                <strong>{selectedChannel.name}</strong>

                <span>{selectedChannel.description}</span>
              </header>

              <div className="group-chat-messages">
                {selectedChannel.messages.length === 0 ? (
                  <div className="chat-empty-state">
                    <Hash size={32} />

                    <strong>
                      Welcome to #{selectedChannel.name}
                    </strong>

                    <span>
                      This is the beginning of the conversation in{" "}
                      {selectedGroup.name}.
                    </span>
                  </div>
                ) : (
                  selectedChannel.messages.map((chatMessage) => (
                    <div
                      className="group-message"
                      key={chatMessage.id}
                    >
                      <div className="message-avatar">
                        {chatMessage.initials}
                      </div>

                      <div className="message-content">
                        <div className="message-heading">
                          <strong>{chatMessage.author}</strong>

                          <span>{chatMessage.time}</span>
                        </div>

                        <p>{chatMessage.text}</p>
                      </div>
                    </div>
                  ))
                )}

                {/*
                 * Invisible element at the end of the message list.
                 * scrollIntoView() moves the chat here whenever
                 * a new message is added.
                 */}
                <div ref={messagesEndRef} />
              </div>

              <form
                className="group-message-form"
                onSubmit={handleSendMessage}
              >
                <input
                  type="text"
                  value={message}
                  onChange={(event) =>
                    setMessage(event.target.value)
                  }
                  placeholder={`Message #${selectedChannel.name}`}
                />

                <button type="submit">Send</button>
              </form>
            </>
          ) : (
            <div className="group-chat-empty">
              <Users size={42} />

              <strong>No group selected</strong>

              <span>
                Create or select a study group to start chatting.
              </span>
            </div>
          )}
        </section>

        {/* =========================
            CREATE GROUP MODAL
        ========================= */}

        {showCreateGroup && (
          <div
            className="create-group-overlay"
            onMouseDown={(event) => {
              if (event.target === event.currentTarget) {
                setShowCreateGroup(false);
              }
            }}
          >
            <div className="create-group-modal">
              <div className="create-group-modal-header">
                <div>
                  <h2>Create Study Group</h2>

                  <p>
                    Create a new group for your study sessions.
                  </p>
                </div>

                <button
                  type="button"
                  className="close-modal-button"
                  onClick={() => setShowCreateGroup(false)}
                >
                  <X size={20} />
                </button>
              </div>

              <form onSubmit={handleCreateGroup}>
                <label>
                  Group name

                  <input
                    type="text"
                    placeholder="e.g. Machine Learning Study Group"
                    value={newGroup.name}
                    onChange={(event) =>
                      setNewGroup((current) => ({
                        ...current,
                        name: event.target.value,
                      }))
                    }
                    autoFocus
                  />
                </label>

                <label>
                  Subject

                  <input
                    type="text"
                    placeholder="e.g. Machine Learning"
                    value={newGroup.subject}
                    onChange={(event) =>
                      setNewGroup((current) => ({
                        ...current,
                        subject: event.target.value,
                      }))
                    }
                  />
                </label>

                <div className="create-group-type">
                  <span>Group type</span>

                  <div>
                    <button
                      type="button"
                      className={
                        newGroup.type === "public" ? "active" : ""
                      }
                      onClick={() =>
                        setNewGroup((current) => ({
                          ...current,
                          type: "public",
                        }))
                      }
                    >
                      <Users size={16} />
                      Public
                    </button>

                    <button
                      type="button"
                      className={
                        newGroup.type === "private" ? "active" : ""
                      }
                      onClick={() =>
                        setNewGroup((current) => ({
                          ...current,
                          type: "private",
                        }))
                      }
                    >
                      <Lock size={16} />
                      Private
                    </button>
                  </div>
                </div>

                <div className="create-group-modal-actions">
                  <button
                    type="button"
                    className="cancel-create-button"
                    onClick={() => setShowCreateGroup(false)}
                  >
                    Cancel
                  </button>

                  <button
                    type="submit"
                    className="confirm-create-button"
                    disabled={
                      !newGroup.name.trim() ||
                      !newGroup.subject.trim()
                    }
                  >
                    Create Group
                  </button>
                </div>
              </form>
            </div>
          </div>
        )}

        {/* =========================
            GROUP MANAGEMENT MODAL
        ========================= */}

        {groupModal && (
          <div
            className="create-group-overlay"
            onMouseDown={(event) => {
              if (event.target === event.currentTarget) {
                closeGroupModal();
              }
            }}
          >
            <div className="create-group-modal management-modal">
              <div className="create-group-modal-header">
                <div>
                  <h2>
                    {groupModal === "rename" && "Rename Group"}

                    {groupModal === "add-channel" && "Create Channel"}

                    {groupModal === "delete" && "Delete Group"}
                  </h2>

                  <p>
                    {groupModal === "rename" &&
                      "Choose a new name for this study group."}

                    {groupModal === "add-channel" &&
                      "Create a new chat channel for this group."}

                    {groupModal === "delete" &&
                      `Are you sure you want to delete "${selectedGroup?.name}"?`}
                  </p>
                </div>

                <button
                  type="button"
                  className="close-modal-button"
                  onClick={closeGroupModal}
                >
                  <X size={20} />
                </button>
              </div>

              {groupModal === "rename" && (
                <form onSubmit={handleRenameGroup}>
                  <label>
                    Group name

                    <input
                      type="text"
                      value={editValue}
                      onChange={(event) =>
                        setEditValue(event.target.value)
                      }
                      autoFocus
                    />
                  </label>

                  <div className="create-group-modal-actions">
                    <button
                      type="button"
                      className="cancel-create-button"
                      onClick={closeGroupModal}
                    >
                      Cancel
                    </button>

                    <button
                      type="submit"
                      className="confirm-create-button"
                      disabled={!editValue.trim()}
                    >
                      Save
                    </button>
                  </div>
                </form>
              )}

              {groupModal === "add-channel" && (
                <form onSubmit={handleAddChannel}>
                  <label>
                    Channel name

                    <input
                      type="text"
                      placeholder="e.g. exam-preparation"
                      value={editValue}
                      onChange={(event) =>
                        setEditValue(event.target.value)
                      }
                      autoFocus
                    />
                  </label>

                  <div className="create-group-modal-actions">
                    <button
                      type="button"
                      className="cancel-create-button"
                      onClick={closeGroupModal}
                    >
                      Cancel
                    </button>

                    <button
                      type="submit"
                      className="confirm-create-button"
                      disabled={!editValue.trim()}
                    >
                      Create Channel
                    </button>
                  </div>
                </form>
              )}

              {groupModal === "delete" && (
                <div className="delete-group-content">
                  <div className="delete-warning">
                    This will permanently delete the group,
                    its channels and all messages.
                  </div>

                  <div className="create-group-modal-actions">
                    <button
                      type="button"
                      className="cancel-create-button"
                      onClick={closeGroupModal}
                    >
                      Cancel
                    </button>

                    <button
                      type="button"
                      className="delete-group-button"
                      onClick={handleDeleteGroup}
                    >
                      Delete Group
                    </button>
                  </div>
                </div>
              )}
            </div>
          </div>
        )}

        {/* =========================
            CHANNEL MANAGEMENT MODAL
        ========================= */}

        {channelModal && editingChannel && (
          <div
            className="create-group-overlay"
            onMouseDown={(event) => {
              if (event.target === event.currentTarget) {
                closeChannelModal();
              }
            }}
          >
            <div className="create-group-modal management-modal">
              <div className="create-group-modal-header">
                <div>
                  <h2>
                    {channelModal === "rename"
                      ? "Rename Channel"
                      : "Delete Channel"}
                  </h2>

                  <p>
                    {channelModal === "rename"
                      ? `Rename #${editingChannel.name}.`
                      : `Are you sure you want to delete #${editingChannel.name}?`}
                  </p>
                </div>

                <button
                  type="button"
                  className="close-modal-button"
                  onClick={closeChannelModal}
                >
                  <X size={20} />
                </button>
              </div>

              {channelModal === "rename" && (
                <form onSubmit={handleRenameChannel}>
                  <label>
                    Channel name

                    <input
                      type="text"
                      value={editValue}
                      onChange={(event) =>
                        setEditValue(event.target.value)
                      }
                      autoFocus
                    />
                  </label>

                  <div className="create-group-modal-actions">
                    <button
                      type="button"
                      className="cancel-create-button"
                      onClick={closeChannelModal}
                    >
                      Cancel
                    </button>

                    <button
                      type="submit"
                      className="confirm-create-button"
                      disabled={!editValue.trim()}
                    >
                      Save
                    </button>
                  </div>
                </form>
              )}

              {channelModal === "delete" && (
                <div className="delete-group-content">
                  <div className="delete-warning">
                    This will permanently delete #
                    {editingChannel.name} and all messages inside
                    this channel.
                  </div>

                  <div className="create-group-modal-actions">
                    <button
                      type="button"
                      className="cancel-create-button"
                      onClick={closeChannelModal}
                    >
                      Cancel
                    </button>

                    <button
                      type="button"
                      className="delete-group-button"
                      onClick={handleDeleteChannel}
                    >
                      Delete Channel
                    </button>
                  </div>
                </div>
              )}
            </div>
          </div>
        )}
      </div>
    </AppShell>
  );
}

export default GroupStudyPage;