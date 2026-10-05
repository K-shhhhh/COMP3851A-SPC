"""Unit tests for Study Group application rules using local memory."""

import pytest

from app.domains.chats.domain.answering import (
    ChatAnswerGenerator,
    GeneratedAnswer,
)
from app.domains.chats.domain.embedding import QuestionEmbeddingProvider
from app.domains.chats.domain.models import ChatSource
from app.domains.chats.domain.retrieval import GroundingChunk
from app.domains.study_groups.application.services import StudyGroupService
from app.domains.study_groups.domain.exceptions import (
    PrivateStudyGroupJoinError,
    StudyGroupAlreadyMemberError,
    StudyGroupChannelNameConflictError,
    StudyGroupChannelNotFoundError,
    StudyGroupMentionedUserNotMemberError,
    StudyGroupMessageNotFoundError,
    StudyGroupMessagePermissionDeniedError,
    StudyGroupNotFoundError,
    StudyGroupPermissionDeniedError,
    StudyGroupTargetUserNotFoundError,
    StudyGroupNoReadyChunksError,
)
from app.domains.study_groups.domain.models import (
    MyGroupsFilter,
    StudyGroupAiMode,
    StudyGroupMemberRole,
    StudyGroupVisibility,
)
from app.domains.study_groups.infrastructure.memory_repository import (
    InMemoryStudyGroupRepository,
)
from app.domains.study_groups.infrastructure.memory_retrieval import (
    InMemoryStudyGroupReadyChunkRepository,
)


class RecordingAnswerGenerator(ChatAnswerGenerator):
    """Record AI options while returning one authorized test citation."""

    def __init__(self) -> None:
        self.mode: str | None = None
        self.response_format: str | None = None

    async def answer_question(
        self,
        *,
        question: str,
        chunks: tuple[GroundingChunk, ...],
        response_format: str | None = None,
        mode: str | None = None,
    ) -> GeneratedAnswer:
        """Return a deterministic response and retain supplied options."""

        self.mode = mode
        self.response_format = response_format
        return GeneratedAnswer(
            content=f"{mode} response to {question}",
            sources=(chunks[0].source,),
        )


class RecordingQuestionEmbeddingProvider(QuestionEmbeddingProvider):
    """Return one valid vector and record the group question."""

    def __init__(self) -> None:
        self.question: str | None = None

    async def embed_question(self, question: str) -> tuple[float, ...]:
        self.question = question
        return (0.5,) * 768


@pytest.fixture
def service() -> StudyGroupService:
    """Return an isolated Study Group service for each test."""

    return StudyGroupService(InMemoryStudyGroupRepository())


@pytest.mark.asyncio
async def test_discover_and_my_groups_have_distinct_visibility(service) -> None:
    """Discover exposes public groups while My Groups includes memberships."""

    owner = "11111111-1111-1111-1111-111111111111"
    visitor = "22222222-2222-2222-2222-222222222222"
    public_group = await service.create_group(
        user_id=owner,
        name="Public revision",
        description="Exam preparation",
        visibility=StudyGroupVisibility.PUBLIC,
        max_members=10,
    )
    await service.create_group(
        user_id=owner,
        name="Private revision",
        description=None,
        visibility=StudyGroupVisibility.PRIVATE,
        max_members=10,
    )

    discovered, total = await service.discover_public_groups(
        user_id=visitor,
        page=1,
        page_size=20,
        search="revision",
    )
    assert total == 1
    assert discovered[0].group.group_id == public_group.group.group_id
    assert discovered[0].is_member is False

    await service.join_public_group(
        group_id=public_group.group.group_id,
        user_id=visitor,
    )
    mine, mine_total = await service.list_my_groups(
        user_id=visitor,
        group_filter=MyGroupsFilter.ALL,
        page=1,
        page_size=20,
    )
    assert mine_total == 1
    assert mine[0].is_member is True


@pytest.mark.asyncio
async def test_join_leave_and_private_access_rules(service) -> None:
    """Enforce public joining, private isolation, and admin ownership."""

    owner = "11111111-1111-1111-1111-111111111111"
    member = "22222222-2222-2222-2222-222222222222"
    public_group = await service.create_group(
        user_id=owner,
        name="Public group",
        description=None,
        visibility=StudyGroupVisibility.PUBLIC,
        max_members=5,
    )
    private_group = await service.create_group(
        user_id=owner,
        name="Private group",
        description=None,
        visibility=StudyGroupVisibility.PRIVATE,
        max_members=5,
    )

    with pytest.raises(StudyGroupNotFoundError):
        await service.get_group(
            group_id=private_group.group.group_id,
            user_id=member,
        )
    with pytest.raises(PrivateStudyGroupJoinError):
        await service.join_public_group(
            group_id=private_group.group.group_id,
            user_id=member,
        )

    await service.join_public_group(
        group_id=public_group.group.group_id,
        user_id=member,
    )
    with pytest.raises(StudyGroupAlreadyMemberError):
        await service.join_public_group(
            group_id=public_group.group.group_id,
            user_id=member,
        )
    await service.leave_group(
        group_id=public_group.group.group_id,
        user_id=member,
    )

    with pytest.raises(StudyGroupPermissionDeniedError):
        await service.leave_group(
            group_id=public_group.group.group_id,
            user_id=owner,
        )


@pytest.mark.asyncio
async def test_non_admin_cannot_update_or_delete_group(service) -> None:
    """Keep group management restricted to owners and admins."""

    owner = "11111111-1111-1111-1111-111111111111"
    member = "22222222-2222-2222-2222-222222222222"
    group = await service.create_group(
        user_id=owner,
        name="Access control",
        description=None,
        visibility=StudyGroupVisibility.PUBLIC,
        max_members=5,
    )
    await service.join_public_group(
        group_id=group.group.group_id,
        user_id=member,
    )

    with pytest.raises(StudyGroupPermissionDeniedError):
        await service.update_group(
            group_id=group.group.group_id,
            user_id=member,
            name="Unauthorized rename",
            description=None,
            visibility=StudyGroupVisibility.PUBLIC,
            max_members=5,
        )


@pytest.mark.asyncio
async def test_admin_adds_lists_and_removes_member_by_email() -> None:
    """Cover the simplified private-group membership workflow."""

    repository = InMemoryStudyGroupRepository()
    service = StudyGroupService(repository)
    owner = "11111111-1111-1111-1111-111111111111"
    member = "22222222-2222-2222-2222-222222222222"
    await repository.seed_user(
        user_id=owner,
        full_name="Group Owner",
        email="owner@example.com",
    )
    await repository.seed_user(
        user_id=member,
        full_name="Group Member",
        email="member@example.com",
    )
    group = await service.create_group(
        user_id=owner,
        name="Private revision",
        description=None,
        visibility=StudyGroupVisibility.PRIVATE,
        max_members=5,
    )

    membership = await service.add_member_by_email(
        group_id=group.group.group_id,
        requester_user_id=owner,
        email="MEMBER@example.com",
    )
    assert membership.user_id == member

    members, total = await service.list_members(
        group_id=group.group.group_id,
        user_id=member,
        page=1,
        page_size=20,
    )
    assert total == 2
    assert [item.full_name for item in members] == [
        "Group Owner",
        "Group Member",
    ]

    await service.remove_member(
        group_id=group.group.group_id,
        requester_user_id=owner,
        target_user_id=member,
    )
    with pytest.raises(StudyGroupNotFoundError):
        await service.list_members(
            group_id=group.group.group_id,
            user_id=member,
            page=1,
            page_size=20,
        )


@pytest.mark.asyncio
async def test_admin_cannot_add_inactive_user_or_remove_owner() -> None:
    """Protect inactive accounts and administrative memberships."""

    repository = InMemoryStudyGroupRepository()
    service = StudyGroupService(repository)
    owner = "11111111-1111-1111-1111-111111111111"
    inactive = "33333333-3333-3333-3333-333333333333"
    await repository.seed_user(
        user_id=owner,
        full_name="Group Owner",
        email="owner@example.com",
    )
    await repository.seed_user(
        user_id=inactive,
        full_name="Inactive Student",
        email="inactive@example.com",
        is_active=False,
    )
    group = await service.create_group(
        user_id=owner,
        name="Protected group",
        description=None,
        visibility=StudyGroupVisibility.PRIVATE,
        max_members=5,
    )

    with pytest.raises(StudyGroupTargetUserNotFoundError):
        await service.add_member_by_email(
            group_id=group.group.group_id,
            requester_user_id=owner,
            email="inactive@example.com",
        )
    with pytest.raises(StudyGroupPermissionDeniedError):
        await service.remove_member(
            group_id=group.group.group_id,
            requester_user_id=owner,
            target_user_id=owner,
        )


@pytest.mark.asyncio
async def test_owner_controls_roles_and_transfers_ownership() -> None:
    """Keep creator history separate from active owner permissions."""

    repository = InMemoryStudyGroupRepository()
    service = StudyGroupService(repository)
    creator = "11111111-1111-1111-1111-111111111111"
    member = "22222222-2222-2222-2222-222222222222"
    group = await service.create_group(
        user_id=creator,
        name="Role model",
        description=None,
        visibility=StudyGroupVisibility.PUBLIC,
        max_members=5,
    )
    group_id = group.group.group_id
    assert group.membership_role == StudyGroupMemberRole.OWNER
    assert group.is_owner is True

    await service.join_public_group(group_id=group_id, user_id=member)
    promoted = await service.set_member_role(
        group_id=group_id,
        requester_user_id=creator,
        target_user_id=member,
        role=StudyGroupMemberRole.ADMIN,
    )
    assert promoted.role == StudyGroupMemberRole.ADMIN

    new_owner = await service.transfer_ownership(
        group_id=group_id,
        requester_user_id=creator,
        target_user_id=member,
    )
    assert new_owner.role == StudyGroupMemberRole.OWNER

    creator_view = await service.get_group(
        group_id=group_id,
        user_id=creator,
    )
    member_view = await service.get_group(
        group_id=group_id,
        user_id=member,
    )
    assert creator_view.group.created_by == creator
    assert creator_view.membership_role == StudyGroupMemberRole.ADMIN
    assert creator_view.is_owner is False
    assert member_view.is_owner is True

    await service.leave_group(group_id=group_id, user_id=creator)
    with pytest.raises(StudyGroupPermissionDeniedError):
        await service.leave_group(group_id=group_id, user_id=member)


@pytest.mark.asyncio
async def test_admin_can_manage_group_but_cannot_control_owner_roles() -> None:
    """Admins manage content and ordinary members, not ownership."""

    repository = InMemoryStudyGroupRepository()
    service = StudyGroupService(repository)
    owner = "11111111-1111-1111-1111-111111111111"
    admin = "22222222-2222-2222-2222-222222222222"
    member = "33333333-3333-3333-3333-333333333333"
    group = await service.create_group(
        user_id=owner,
        name="Admin boundaries",
        description=None,
        visibility=StudyGroupVisibility.PUBLIC,
        max_members=5,
    )
    group_id = group.group.group_id
    await service.join_public_group(group_id=group_id, user_id=admin)
    await service.join_public_group(group_id=group_id, user_id=member)
    await service.set_member_role(
        group_id=group_id,
        requester_user_id=owner,
        target_user_id=admin,
        role=StudyGroupMemberRole.ADMIN,
    )

    await service.update_group(
        group_id=group_id,
        user_id=admin,
        name="Admin updated",
        description=None,
        visibility=StudyGroupVisibility.PUBLIC,
        max_members=5,
    )
    await service.remove_member(
        group_id=group_id,
        requester_user_id=admin,
        target_user_id=member,
    )
    with pytest.raises(StudyGroupPermissionDeniedError):
        await service.set_member_role(
            group_id=group_id,
            requester_user_id=admin,
            target_user_id=owner,
            role=StudyGroupMemberRole.MEMBER,
        )
    with pytest.raises(StudyGroupPermissionDeniedError):
        await service.delete_group(group_id=group_id, user_id=admin)

    await service.leave_group(group_id=group_id, user_id=admin)


@pytest.mark.asyncio
async def test_channel_lifecycle_and_member_permissions(service) -> None:
    """Allow members to read channels while only admins may manage them."""

    owner = "11111111-1111-1111-1111-111111111111"
    member = "22222222-2222-2222-2222-222222222222"
    group = await service.create_group(
        user_id=owner,
        name="Channel group",
        description=None,
        visibility=StudyGroupVisibility.PUBLIC,
        max_members=5,
    )
    group_id = group.group.group_id
    await service.join_public_group(group_id=group_id, user_id=member)

    created = await service.create_channel(
        group_id=group_id,
        user_id=owner,
        name="  Exam   preparation  ",
        description=" Week 8 revision ",
    )
    assert created.name == "Exam preparation"
    assert created.description == "Week 8 revision"

    channels, total = await service.list_channels(
        group_id=group_id,
        user_id=member,
        page=1,
        page_size=20,
    )
    assert total == 1
    assert channels[0].channel_id == created.channel_id

    with pytest.raises(StudyGroupPermissionDeniedError):
        await service.update_channel(
            group_id=group_id,
            channel_id=created.channel_id,
            user_id=member,
            name="Member rename",
            description=None,
        )

    with pytest.raises(StudyGroupChannelNameConflictError):
        await service.create_channel(
            group_id=group_id,
            user_id=owner,
            name="exam PREPARATION",
            description=None,
        )

    updated = await service.update_channel(
        group_id=group_id,
        channel_id=created.channel_id,
        user_id=owner,
        name="Final exam",
        description=None,
    )
    assert updated.name == "Final exam"

    await service.delete_channel(
        group_id=group_id,
        channel_id=created.channel_id,
        user_id=owner,
    )
    with pytest.raises(StudyGroupChannelNotFoundError):
        await service.get_channel(
            group_id=group_id,
            channel_id=created.channel_id,
            user_id=member,
        )


@pytest.mark.asyncio
async def test_nonmember_cannot_read_public_group_channels(service) -> None:
    """Require membership even when the containing group is public."""

    owner = "11111111-1111-1111-1111-111111111111"
    outsider = "33333333-3333-3333-3333-333333333333"
    group = await service.create_group(
        user_id=owner,
        name="Public channel group",
        description=None,
        visibility=StudyGroupVisibility.PUBLIC,
        max_members=5,
    )
    with pytest.raises(StudyGroupPermissionDeniedError):
        await service.list_channels(
            group_id=group.group.group_id,
            user_id=outsider,
            page=1,
            page_size=20,
        )


@pytest.mark.asyncio
async def test_normal_message_lifecycle_and_author_permissions(service) -> None:
    """Cover member history and author-only editing/deletion."""

    owner = "11111111-1111-1111-1111-111111111111"
    author = "22222222-2222-2222-2222-222222222222"
    group = await service.create_group(
        user_id=owner,
        name="Message group",
        description=None,
        visibility=StudyGroupVisibility.PUBLIC,
        max_members=5,
    )
    group_id = group.group.group_id
    await service.join_public_group(group_id=group_id, user_id=author)
    channel = await service.create_channel(
        group_id=group_id,
        user_id=owner,
        name="General",
        description=None,
    )

    created = await service.create_message(
        group_id=group_id,
        channel_id=channel.channel_id,
        user_id=author,
        content="  Hello study group  ",
    )
    assert created.content == "Hello study group"
    assert created.mentioned_user_ids == ()

    history, total = await service.list_messages(
        group_id=group_id,
        channel_id=channel.channel_id,
        user_id=owner,
        page=1,
        page_size=20,
    )
    assert total == 1
    assert history[0].message_id == created.message_id

    with pytest.raises(StudyGroupMessagePermissionDeniedError):
        await service.update_message(
            group_id=group_id,
            channel_id=channel.channel_id,
            message_id=created.message_id,
            user_id=owner,
            content="Owner cannot rewrite this",
        )

    updated = await service.update_message(
        group_id=group_id,
        channel_id=channel.channel_id,
        message_id=created.message_id,
        user_id=author,
        content="Updated message",
    )
    assert updated.content == "Updated message"
    assert updated.edited_at is not None

    await service.delete_message(
        group_id=group_id,
        channel_id=channel.channel_id,
        message_id=created.message_id,
        user_id=author,
    )
    with pytest.raises(StudyGroupMessageNotFoundError):
        await service.get_message(
            group_id=group_id,
            channel_id=channel.channel_id,
            message_id=created.message_id,
            user_id=owner,
        )


@pytest.mark.asyncio
async def test_message_mentions_require_active_group_members(service) -> None:
    """Store unique member mentions and reject users outside the group."""

    owner = "11111111-1111-1111-1111-111111111111"
    author = "22222222-2222-2222-2222-222222222222"
    outsider = "33333333-3333-3333-3333-333333333333"
    group = await service.create_group(
        user_id=owner,
        name="Mention group",
        description=None,
        visibility=StudyGroupVisibility.PUBLIC,
        max_members=5,
    )
    group_id = group.group.group_id
    await service.join_public_group(group_id=group_id, user_id=author)
    channel = await service.create_channel(
        group_id=group_id,
        user_id=owner,
        name="Mentions",
        description=None,
    )

    created = await service.create_message(
        group_id=group_id,
        channel_id=channel.channel_id,
        user_id=author,
        content="Can you review this?",
        mentioned_user_ids=[owner, owner],
    )
    assert created.mentioned_user_ids == (owner,)

    with pytest.raises(StudyGroupMentionedUserNotMemberError):
        await service.create_message(
            group_id=group_id,
            channel_id=channel.channel_id,
            user_id=author,
            content="This mention is not allowed",
            mentioned_user_ids=[outsider],
        )

    updated = await service.update_message(
        group_id=group_id,
        channel_id=channel.channel_id,
        message_id=created.message_id,
        user_id=author,
        content="No mention now",
        mentioned_user_ids=[],
    )
    assert updated.mentioned_user_ids == ()


@pytest.mark.asyncio
@pytest.mark.parametrize("ai_mode", list(StudyGroupAiMode))
async def test_ai_mode_generates_and_persists_scoped_companion_response(
    ai_mode: StudyGroupAiMode,
) -> None:
    """Pass an explicit mode to the generator using only channel chunks."""

    repository = InMemoryStudyGroupRepository()
    chunk_repository = InMemoryStudyGroupReadyChunkRepository()
    answer_generator = RecordingAnswerGenerator()
    service = StudyGroupService(
        repository,
        chunk_repository=chunk_repository,
        answer_generator=answer_generator,
    )
    owner = "11111111-1111-1111-1111-111111111111"
    group = await service.create_group(
        user_id=owner,
        name="AI mode group",
        description=None,
        visibility=StudyGroupVisibility.PUBLIC,
        max_members=5,
    )
    group_id = group.group.group_id
    channel = await service.create_channel(
        group_id=group_id,
        user_id=owner,
        name="AI discussion",
        description=None,
    )
    source = ChatSource(
        note_id=1,
        note_title="Channel note",
        chunk_id=1,
        page=1,
    )
    await chunk_repository.replace_channel_chunks(
        group_id=group_id,
        channel_id=channel.channel_id,
        chunks=(
            GroundingChunk(
                content="Backpropagation computes gradients.",
                source=source,
            ),
        ),
    )

    message = await service.create_message(
        group_id=group_id,
        channel_id=channel.channel_id,
        user_id=owner,
        content="Summarize backpropagation",
        ai_mode=ai_mode,
        response_format="bullet_points",
    )

    assert answer_generator.mode == ai_mode.value
    assert answer_generator.response_format == "bullet_points"
    assert message.ai_mode_used == ai_mode
    assert message.ai_response is not None
    assert message.ai_response.mode == ai_mode
    assert message.ai_response.sources == (source,)

    with pytest.raises(StudyGroupMessagePermissionDeniedError):
        await service.update_message(
            group_id=group_id,
            channel_id=channel.channel_id,
            message_id=message.message_id,
            user_id=owner,
            content="Rewrite the AI question",
        )


@pytest.mark.asyncio
async def test_group_semantic_path_uses_exact_channel_and_limit() -> None:
    """Embed once and pass only bounded channel-scoped results to answering."""

    repository = InMemoryStudyGroupRepository()
    chunk_repository = InMemoryStudyGroupReadyChunkRepository()
    answer_generator = RecordingAnswerGenerator()
    embedding_provider = RecordingQuestionEmbeddingProvider()
    service = StudyGroupService(
        repository,
        chunk_repository=chunk_repository,
        answer_generator=answer_generator,
        question_embedding_provider=embedding_provider,
        semantic_search_limit=1,
    )
    owner = "11111111-1111-1111-1111-111111111111"
    group = await service.create_group(
        user_id=owner,
        name="Semantic group",
        description=None,
        visibility=StudyGroupVisibility.PUBLIC,
        max_members=5,
    )
    channel = await service.create_channel(
        group_id=group.group.group_id,
        user_id=owner,
        name="Semantic channel",
        description=None,
    )
    selected_source = ChatSource(
        note_id=1,
        note_title="Selected note",
        chunk_id=1,
        page=1,
    )
    ignored_source = ChatSource(
        note_id=2,
        note_title="Ignored note",
        chunk_id=2,
        page=2,
    )
    await chunk_repository.replace_channel_chunks(
        group_id=group.group.group_id,
        channel_id=channel.channel_id,
        chunks=(
            GroundingChunk(content="Selected context", source=selected_source),
            GroundingChunk(content="Ignored context", source=ignored_source),
        ),
    )

    message = await service.create_message(
        group_id=group.group.group_id,
        channel_id=channel.channel_id,
        user_id=owner,
        content="  Explain this topic  ",
        ai_mode=StudyGroupAiMode.DEFAULT,
    )

    assert embedding_provider.question == "Explain this topic"
    assert message.ai_response is not None
    assert message.ai_response.sources == (selected_source,)


@pytest.mark.asyncio
async def test_ai_mode_requires_ready_chunks_in_same_channel() -> None:
    """Reject companion invocation when the exact channel has no context."""

    repository = InMemoryStudyGroupRepository()
    service = StudyGroupService(
        repository,
        chunk_repository=InMemoryStudyGroupReadyChunkRepository(),
        answer_generator=RecordingAnswerGenerator(),
    )
    owner = "11111111-1111-1111-1111-111111111111"
    group = await service.create_group(
        user_id=owner,
        name="No chunks group",
        description=None,
        visibility=StudyGroupVisibility.PUBLIC,
        max_members=5,
    )
    channel = await service.create_channel(
        group_id=group.group.group_id,
        user_id=owner,
        name="Empty channel",
        description=None,
    )

    with pytest.raises(StudyGroupNoReadyChunksError):
        await service.create_message(
            group_id=group.group.group_id,
            channel_id=channel.channel_id,
            user_id=owner,
            content="Create a quiz",
            ai_mode=StudyGroupAiMode.QUIZ,
        )


@pytest.mark.asyncio
async def test_message_scope_rejects_wrong_channel_and_nonmember(service) -> None:
    """Prevent cross-channel reads and public-group nonmember access."""

    owner = "11111111-1111-1111-1111-111111111111"
    outsider = "33333333-3333-3333-3333-333333333333"
    group = await service.create_group(
        user_id=owner,
        name="Scoped messages",
        description=None,
        visibility=StudyGroupVisibility.PUBLIC,
        max_members=5,
    )
    group_id = group.group.group_id
    first_channel = await service.create_channel(
        group_id=group_id,
        user_id=owner,
        name="First",
        description=None,
    )
    second_channel = await service.create_channel(
        group_id=group_id,
        user_id=owner,
        name="Second",
        description=None,
    )
    message = await service.create_message(
        group_id=group_id,
        channel_id=first_channel.channel_id,
        user_id=owner,
        content="Channel-scoped message",
    )

    with pytest.raises(StudyGroupMessageNotFoundError):
        await service.get_message(
            group_id=group_id,
            channel_id=second_channel.channel_id,
            message_id=message.message_id,
            user_id=owner,
        )
    with pytest.raises(StudyGroupPermissionDeniedError):
        await service.list_messages(
            group_id=group_id,
            channel_id=first_channel.channel_id,
            user_id=outsider,
            page=1,
            page_size=20,
        )
