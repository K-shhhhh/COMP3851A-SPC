"""Authenticated HTTP endpoints for public and private Study Groups."""

from uuid import UUID

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    Query,
    Response,
    UploadFile,
    WebSocket,
    WebSocketDisconnect,
    status,
)

from app.api.dependencies import (
    get_auth_service,
    get_current_user,
    get_note_service,
    get_study_group_service,
)
from app.api.error_handlers import ApiError
from app.core.config import settings
from app.domains.auth.application.services import AuthService
from app.domains.auth.domain.models import User
from app.domains.notes.application.services import NoteService
from app.domains.notes.domain.exceptions import (
    AttachmentNotFoundError,
    AttachmentStorageError,
    EmptyFileError,
    FileTooLargeError,
    InvalidPdfError,
    ProcessingDispatchError,
    UnsafeFilenameError,
    UnsupportedFileTypeError,
)
from app.domains.notes.presentation.schemas import (
    NoteResponse,
    NoteStatusResponse,
)
from app.domains.study_groups.application.services import (
    StudyGroupService,
)
from app.domains.study_groups.domain.exceptions import (
    InvalidStudyGroupMessageError,
    InvalidStudyGroupError,
    PrivateStudyGroupJoinError,
    StudyGroupAlreadyMemberError,
    StudyGroupAiUnavailableError,
    StudyGroupAnswerGenerationError,
    StudyGroupChannelNameConflictError,
    StudyGroupChannelNotFoundError,
    StudyGroupFullError,
    StudyGroupMembershipNotFoundError,
    StudyGroupMentionedUserNotMemberError,
    StudyGroupMessageNotFoundError,
    StudyGroupMessagePermissionDeniedError,
    StudyGroupNotFoundError,
    StudyGroupNoReadyChunksError,
    StudyGroupPermissionDeniedError,
    StudyGroupTargetUserNotFoundError,
)
from app.domains.study_groups.domain.models import (
    MyGroupsFilter,
    StudyGroupMemberRole,
)
from app.domains.study_groups.presentation.schemas import (
    AddStudyGroupMemberRequest,
    CreateStudyGroupChannelRequest,
    CreateStudyGroupMessageRequest,
    CreateStudyGroupRequest,
    DiscoverPublicResponse,
    MyGroupsResponse,
    StudyGroupMemberListResponse,
    StudyGroupMessageListResponse,
    StudyGroupMessageResponse,
    StudyGroupChannelListResponse,
    StudyGroupChannelResponse,
    StudyGroupMembershipResponse,
    StudyGroupMemberResponse,
    StudyGroupResponse,
    TransferStudyGroupOwnershipRequest,
    UpdateStudyGroupMemberRoleRequest,
    UpdateStudyGroupRequest,
    UpdateStudyGroupChannelRequest,
    UpdateStudyGroupMessageRequest,
)
from app.domains.study_groups.presentation.realtime import (
    study_group_connections,
)


router = APIRouter(
    prefix="/study-groups",
    tags=["Study Groups"],
)

websocket_router = APIRouter(
    prefix="/ws/study-groups",
    tags=["Study Group WebSocket"],
)


# Static routes must appear before /{group_id}. Otherwise FastAPI may attempt
# to interpret "discover" or "mine" as a group identifier.
@router.get(
    "/discover",
    response_model=DiscoverPublicResponse,
)
async def discover_public_groups(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    search: str | None = Query(default=None, max_length=100),
    current_user: User = Depends(get_current_user),
    service: StudyGroupService = Depends(get_study_group_service),
) -> DiscoverPublicResponse:
    """Return active public groups for the discovery screen."""

    try:
        groups, total = await service.discover_public_groups(
            user_id=current_user.id,
            page=page,
            page_size=page_size,
            search=search,
        )
    except Exception as exc:
        _raise_study_group_api_error(exc)
        raise

    return DiscoverPublicResponse(
        items=[
            StudyGroupResponse.from_summary(group)
            for group in groups
        ],
        page=page,
        page_size=page_size,
        total=total,
    )


@router.get(
    "/mine",
    response_model=MyGroupsResponse,
)
async def list_my_groups(
    group_filter: MyGroupsFilter = Query(
        default=MyGroupsFilter.ALL,
        alias="filter",
    ),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    service: StudyGroupService = Depends(get_study_group_service),
) -> MyGroupsResponse:
    """Return groups owned by or joined by the current student."""

    try:
        groups, total = await service.list_my_groups(
            user_id=current_user.id,
            group_filter=group_filter,
            page=page,
            page_size=page_size,
        )
    except Exception as exc:
        _raise_study_group_api_error(exc)
        raise

    return MyGroupsResponse(
        items=[
            StudyGroupResponse.from_summary(group)
            for group in groups
        ],
        page=page,
        page_size=page_size,
        total=total,
    )


@router.post(
    "",
    response_model=StudyGroupResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_study_group(
    payload: CreateStudyGroupRequest,
    current_user: User = Depends(get_current_user),
    service: StudyGroupService = Depends(get_study_group_service),
) -> StudyGroupResponse:
    """Create a public or private group owned by the current student."""

    try:
        group = await service.create_group(
            user_id=current_user.id,
            name=payload.name,
            description=payload.description,
            visibility=payload.visibility,
            max_members=payload.max_members,
        )
    except Exception as exc:
        _raise_study_group_api_error(exc)
        raise

    return StudyGroupResponse.from_summary(group)


@router.get(
    "/{group_id}",
    response_model=StudyGroupResponse,
)
async def get_study_group(
    group_id: UUID,
    current_user: User = Depends(get_current_user),
    service: StudyGroupService = Depends(get_study_group_service),
) -> StudyGroupResponse:
    """Return a public group or an accessible private group."""

    try:
        group = await service.get_group(
            group_id=str(group_id),
            user_id=current_user.id,
        )
    except Exception as exc:
        _raise_study_group_api_error(exc)
        raise

    return StudyGroupResponse.from_summary(group)


@router.get(
    "/{group_id}/members",
    response_model=StudyGroupMemberListResponse,
)
async def list_group_members(
    group_id: UUID,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    service: StudyGroupService = Depends(get_study_group_service),
) -> StudyGroupMemberListResponse:
    """List group members for an authenticated member."""

    try:
        members, total = await service.list_members(
            group_id=str(group_id),
            user_id=current_user.id,
            page=page,
            page_size=page_size,
        )
    except Exception as exc:
        _raise_study_group_api_error(exc)
        raise

    return StudyGroupMemberListResponse(
        items=[
            StudyGroupMemberResponse.from_member(member)
            for member in members
        ],
        page=page,
        page_size=page_size,
        total=total,
    )


@router.post(
    "/{group_id}/members",
    response_model=StudyGroupMembershipResponse,
    status_code=status.HTTP_201_CREATED,
)
async def add_group_member(
    group_id: UUID,
    payload: AddStudyGroupMemberRequest,
    current_user: User = Depends(get_current_user),
    service: StudyGroupService = Depends(get_study_group_service),
) -> StudyGroupMembershipResponse:
    """Add an active student by email as the owner/admin."""

    try:
        membership = await service.add_member_by_email(
            group_id=str(group_id),
            requester_user_id=current_user.id,
            email=str(payload.email),
        )
    except Exception as exc:
        _raise_study_group_api_error(exc)
        raise

    return StudyGroupMembershipResponse.from_membership(membership)


@router.patch(
    "/{group_id}/members/{target_user_id}/role",
    response_model=StudyGroupMembershipResponse,
)
async def update_group_member_role(
    group_id: UUID,
    target_user_id: UUID,
    payload: UpdateStudyGroupMemberRoleRequest,
    current_user: User = Depends(get_current_user),
    service: StudyGroupService = Depends(get_study_group_service),
) -> StudyGroupMembershipResponse:
    """Promote a member or demote an admin as the group owner."""

    try:
        membership = await service.set_member_role(
            group_id=str(group_id),
            requester_user_id=current_user.id,
            target_user_id=str(target_user_id),
            role=StudyGroupMemberRole(payload.role),
        )
    except Exception as exc:
        _raise_study_group_api_error(exc)
        raise

    return StudyGroupMembershipResponse.from_membership(membership)


@router.post(
    "/{group_id}/ownership/transfer",
    response_model=StudyGroupMembershipResponse,
)
async def transfer_group_ownership(
    group_id: UUID,
    payload: TransferStudyGroupOwnershipRequest,
    current_user: User = Depends(get_current_user),
    service: StudyGroupService = Depends(get_study_group_service),
) -> StudyGroupMembershipResponse:
    """Transfer the single owner role to another active group member."""

    try:
        membership = await service.transfer_ownership(
            group_id=str(group_id),
            requester_user_id=current_user.id,
            target_user_id=str(payload.new_owner_user_id),
        )
    except Exception as exc:
        _raise_study_group_api_error(exc)
        raise

    return StudyGroupMembershipResponse.from_membership(membership)


@router.delete(
    "/{group_id}/members/me",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def leave_study_group(
    group_id: UUID,
    current_user: User = Depends(get_current_user),
    service: StudyGroupService = Depends(get_study_group_service),
) -> Response:
    """Remove the current student's membership from a group."""

    try:
        await service.leave_group(
            group_id=str(group_id),
            user_id=current_user.id,
        )
    except Exception as exc:
        _raise_study_group_api_error(exc)
        raise

    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.delete(
    "/{group_id}/members/{target_user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def remove_group_member(
    group_id: UUID,
    target_user_id: UUID,
    current_user: User = Depends(get_current_user),
    service: StudyGroupService = Depends(get_study_group_service),
) -> Response:
    """Remove an ordinary member as the group owner/admin."""

    try:
        await service.remove_member(
            group_id=str(group_id),
            requester_user_id=current_user.id,
            target_user_id=str(target_user_id),
        )
    except Exception as exc:
        _raise_study_group_api_error(exc)
        raise

    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get(
    "/{group_id}/channels",
    response_model=StudyGroupChannelListResponse,
)
async def list_group_channels(
    group_id: UUID,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    service: StudyGroupService = Depends(get_study_group_service),
) -> StudyGroupChannelListResponse:
    """List active channels for a group member."""

    try:
        channels, total = await service.list_channels(
            group_id=str(group_id),
            user_id=current_user.id,
            page=page,
            page_size=page_size,
        )
    except Exception as exc:
        _raise_study_group_api_error(exc)
        raise

    return StudyGroupChannelListResponse(
        items=[
            StudyGroupChannelResponse.from_channel(channel)
            for channel in channels
        ],
        page=page,
        page_size=page_size,
        total=total,
    )


@router.post(
    "/{group_id}/channels",
    response_model=StudyGroupChannelResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_group_channel(
    group_id: UUID,
    payload: CreateStudyGroupChannelRequest,
    current_user: User = Depends(get_current_user),
    service: StudyGroupService = Depends(get_study_group_service),
) -> StudyGroupChannelResponse:
    """Create an admin-named channel as the group owner/admin."""

    try:
        channel = await service.create_channel(
            group_id=str(group_id),
            user_id=current_user.id,
            name=payload.name,
            description=payload.description,
        )
    except Exception as exc:
        _raise_study_group_api_error(exc)
        raise

    return StudyGroupChannelResponse.from_channel(channel)


@router.get(
    "/{group_id}/channels/{channel_id}",
    response_model=StudyGroupChannelResponse,
)
async def get_group_channel(
    group_id: UUID,
    channel_id: UUID,
    current_user: User = Depends(get_current_user),
    service: StudyGroupService = Depends(get_study_group_service),
) -> StudyGroupChannelResponse:
    """Return one active channel to a group member."""

    try:
        channel = await service.get_channel(
            group_id=str(group_id),
            channel_id=str(channel_id),
            user_id=current_user.id,
        )
    except Exception as exc:
        _raise_study_group_api_error(exc)
        raise

    return StudyGroupChannelResponse.from_channel(channel)


@router.post(
    "/{group_id}/channels/{channel_id}/attachments",
    response_model=NoteResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def upload_group_channel_attachment(
    group_id: UUID,
    channel_id: UUID,
    file: UploadFile = File(...),
    title: str | None = Form(default=None, max_length=150),
    current_user: User = Depends(get_current_user),
    group_service: StudyGroupService = Depends(get_study_group_service),
    note_service: NoteService = Depends(get_note_service),
) -> NoteResponse:
    """Upload a PDF to a Study Group channel as an active member."""

    try:
        # This lookup verifies that the group/channel exists and that the
        # authenticated student is an active group member.
        await group_service.get_channel(
            group_id=str(group_id),
            channel_id=str(channel_id),
            user_id=current_user.id,
        )
        data = await file.read(settings.MAX_NOTE_UPLOAD_SIZE_BYTES + 1)
        attachment = await note_service.upload_channel_attachment(
            user_id=current_user.id,
            channel_id=str(channel_id),
            original_filename=file.filename,
            content_type=file.content_type,
            data=data,
            title=title,
        )
    except Exception as exc:
        _raise_group_attachment_api_error(exc)
        raise
    finally:
        await file.close()

    return NoteResponse.from_attachment(attachment)


@router.get(
    "/{group_id}/channels/{channel_id}/attachments/{attachment_id}/status",
    response_model=NoteStatusResponse,
)
async def get_group_channel_attachment_status(
    group_id: UUID,
    channel_id: UUID,
    attachment_id: int,
    current_user: User = Depends(get_current_user),
    group_service: StudyGroupService = Depends(get_study_group_service),
    note_service: NoteService = Depends(get_note_service),
) -> NoteStatusResponse:
    """Return processing status for an accessible channel attachment."""

    try:
        await group_service.get_channel(
            group_id=str(group_id),
            channel_id=str(channel_id),
            user_id=current_user.id,
        )
        attachment = await note_service.get_channel_attachment(
            attachment_id=attachment_id,
            user_id=current_user.id,
            channel_id=str(channel_id),
        )
    except Exception as exc:
        _raise_group_attachment_api_error(exc)
        raise

    return NoteStatusResponse.from_attachment(attachment)


@router.put(
    "/{group_id}/channels/{channel_id}",
    response_model=StudyGroupChannelResponse,
)
async def update_group_channel(
    group_id: UUID,
    channel_id: UUID,
    payload: UpdateStudyGroupChannelRequest,
    current_user: User = Depends(get_current_user),
    service: StudyGroupService = Depends(get_study_group_service),
) -> StudyGroupChannelResponse:
    """Update a channel as the group owner/admin."""

    try:
        channel = await service.update_channel(
            group_id=str(group_id),
            channel_id=str(channel_id),
            user_id=current_user.id,
            name=payload.name,
            description=payload.description,
        )
    except Exception as exc:
        _raise_study_group_api_error(exc)
        raise

    return StudyGroupChannelResponse.from_channel(channel)


@router.delete(
    "/{group_id}/channels/{channel_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_group_channel(
    group_id: UUID,
    channel_id: UUID,
    current_user: User = Depends(get_current_user),
    service: StudyGroupService = Depends(get_study_group_service),
) -> Response:
    """Soft-delete a channel as the group owner/admin."""

    try:
        await service.delete_channel(
            group_id=str(group_id),
            channel_id=str(channel_id),
            user_id=current_user.id,
        )
    except Exception as exc:
        _raise_study_group_api_error(exc)
        raise

    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get(
    "/{group_id}/channels/{channel_id}/messages",
    response_model=StudyGroupMessageListResponse,
)
async def list_group_messages(
    group_id: UUID,
    channel_id: UUID,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    service: StudyGroupService = Depends(get_study_group_service),
) -> StudyGroupMessageListResponse:
    """Return oldest-first message history to an active group member."""

    try:
        messages, total = await service.list_messages(
            group_id=str(group_id),
            channel_id=str(channel_id),
            user_id=current_user.id,
            page=page,
            page_size=page_size,
        )
    except Exception as exc:
        _raise_study_group_api_error(exc)
        raise

    return StudyGroupMessageListResponse(
        items=[
            StudyGroupMessageResponse.from_message(message)
            for message in messages
        ],
        page=page,
        page_size=page_size,
        total=total,
    )


@router.post(
    "/{group_id}/channels/{channel_id}/messages",
    response_model=StudyGroupMessageResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_group_message(
    group_id: UUID,
    channel_id: UUID,
    payload: CreateStudyGroupMessageRequest,
    current_user: User = Depends(get_current_user),
    service: StudyGroupService = Depends(get_study_group_service),
) -> StudyGroupMessageResponse:
    """Create a normal text message as an active group member."""

    try:
        message = await service.create_message(
            group_id=str(group_id),
            channel_id=str(channel_id),
            user_id=current_user.id,
            content=payload.content,
            mentioned_user_ids=[
                str(user_id) for user_id in payload.mentioned_user_ids
            ],
            ai_mode=payload.ai_mode,
            response_format=payload.response_format,
        )
    except Exception as exc:
        _raise_study_group_api_error(exc)
        raise

    response = StudyGroupMessageResponse.from_message(message)
    await study_group_connections.broadcast(
        group_id=str(group_id),
        channel_id=str(channel_id),
        event={
            "type": "study_group.message.created",
            "data": response.model_dump(mode="json"),
        },
    )
    return response


@router.get(
    "/{group_id}/channels/{channel_id}/messages/{message_id}",
    response_model=StudyGroupMessageResponse,
)
async def get_group_message(
    group_id: UUID,
    channel_id: UUID,
    message_id: int,
    current_user: User = Depends(get_current_user),
    service: StudyGroupService = Depends(get_study_group_service),
) -> StudyGroupMessageResponse:
    """Return one active message to an active group member."""

    try:
        message = await service.get_message(
            group_id=str(group_id),
            channel_id=str(channel_id),
            message_id=message_id,
            user_id=current_user.id,
        )
    except Exception as exc:
        _raise_study_group_api_error(exc)
        raise

    return StudyGroupMessageResponse.from_message(message)


@router.put(
    "/{group_id}/channels/{channel_id}/messages/{message_id}",
    response_model=StudyGroupMessageResponse,
)
async def update_group_message(
    group_id: UUID,
    channel_id: UUID,
    message_id: int,
    payload: UpdateStudyGroupMessageRequest,
    current_user: User = Depends(get_current_user),
    service: StudyGroupService = Depends(get_study_group_service),
) -> StudyGroupMessageResponse:
    """Replace message text when the requester is its author."""

    try:
        message = await service.update_message(
            group_id=str(group_id),
            channel_id=str(channel_id),
            message_id=message_id,
            user_id=current_user.id,
            content=payload.content,
            mentioned_user_ids=[
                str(user_id) for user_id in payload.mentioned_user_ids
            ],
        )
    except Exception as exc:
        _raise_study_group_api_error(exc)
        raise

    response = StudyGroupMessageResponse.from_message(message)
    await study_group_connections.broadcast(
        group_id=str(group_id),
        channel_id=str(channel_id),
        event={
            "type": "study_group.message.updated",
            "data": response.model_dump(mode="json"),
        },
    )
    return response


@router.delete(
    "/{group_id}/channels/{channel_id}/messages/{message_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_group_message(
    group_id: UUID,
    channel_id: UUID,
    message_id: int,
    current_user: User = Depends(get_current_user),
    service: StudyGroupService = Depends(get_study_group_service),
) -> Response:
    """Soft-delete a message when the requester is its author."""

    try:
        await service.delete_message(
            group_id=str(group_id),
            channel_id=str(channel_id),
            message_id=message_id,
            user_id=current_user.id,
        )
    except Exception as exc:
        _raise_study_group_api_error(exc)
        raise

    await study_group_connections.broadcast(
        group_id=str(group_id),
        channel_id=str(channel_id),
        event={
            "type": "study_group.message.deleted",
            "data": {
                "group_id": str(group_id),
                "channel_id": str(channel_id),
                "message_id": message_id,
            },
        },
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.put(
    "/{group_id}",
    response_model=StudyGroupResponse,
)
async def update_study_group(
    group_id: UUID,
    payload: UpdateStudyGroupRequest,
    current_user: User = Depends(get_current_user),
    service: StudyGroupService = Depends(get_study_group_service),
) -> StudyGroupResponse:
    """Update a group as its owner or an authorized group admin."""

    try:
        group = await service.update_group(
            group_id=str(group_id),
            user_id=current_user.id,
            name=payload.name,
            description=payload.description,
            visibility=payload.visibility,
            max_members=payload.max_members,
        )
    except Exception as exc:
        _raise_study_group_api_error(exc)
        raise

    return StudyGroupResponse.from_summary(group)


@router.delete(
    "/{group_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_study_group(
    group_id: UUID,
    current_user: User = Depends(get_current_user),
    service: StudyGroupService = Depends(get_study_group_service),
) -> Response:
    """Soft-delete a group as its owner or an authorized admin."""

    try:
        await service.delete_group(
            group_id=str(group_id),
            user_id=current_user.id,
        )
    except Exception as exc:
        _raise_study_group_api_error(exc)
        raise

    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/{group_id}/join",
    response_model=StudyGroupResponse,
    status_code=status.HTTP_201_CREATED,
)
async def join_public_group(
    group_id: UUID,
    current_user: User = Depends(get_current_user),
    service: StudyGroupService = Depends(get_study_group_service),
) -> StudyGroupResponse:
    """Join an active public group as the current student."""

    try:
        group = await service.join_public_group(
            group_id=str(group_id),
            user_id=current_user.id,
        )
    except Exception as exc:
        _raise_study_group_api_error(exc)
        raise

    return StudyGroupResponse.from_summary(group)


@websocket_router.websocket(
    "/{group_id}/channels/{channel_id}",
)
async def study_group_channel_websocket(
    websocket: WebSocket,
    group_id: UUID,
    channel_id: UUID,
    ticket: str = Query(min_length=1),
    auth_service: AuthService = Depends(get_auth_service),
    service: StudyGroupService = Depends(get_study_group_service),
) -> None:
    """Deliver committed channel events to an authenticated group member."""

    user_id = await auth_service.consume_websocket_ticket(ticket)
    if user_id is None:
        await websocket.close(
            code=4401,
            reason="Invalid or expired WebSocket ticket.",
        )
        return

    try:
        await service.get_channel(
            group_id=str(group_id),
            channel_id=str(channel_id),
            user_id=user_id,
        )
    except Exception:
        await websocket.close(
            code=4403,
            reason="Study Group channel access denied.",
        )
        return

    await study_group_connections.connect(
        websocket=websocket,
        group_id=str(group_id),
        channel_id=str(channel_id),
        user_id=user_id,
    )
    await websocket.send_json(
        {
            "type": "study_group.connection.ready",
            "data": {
                "group_id": str(group_id),
                "channel_id": str(channel_id),
                "user_id": user_id,
            },
        }
    )

    try:
        while True:
            try:
                payload = await websocket.receive_json()
            except ValueError:
                await websocket.send_json(
                    {
                        "type": "study_group.error",
                        "data": {"code": "INVALID_JSON"},
                    }
                )
                continue

            if not isinstance(payload, dict) or payload.get("type") != "ping":
                await websocket.send_json(
                    {
                        "type": "study_group.error",
                        "data": {"code": "UNSUPPORTED_EVENT"},
                    }
                )
                continue

            await websocket.send_json(
                {
                    "type": "pong",
                    "data": {},
                }
            )
    except WebSocketDisconnect:
        pass
    finally:
        await study_group_connections.disconnect(
            websocket=websocket,
            group_id=str(group_id),
            channel_id=str(channel_id),
        )


def _raise_study_group_api_error(exc: Exception) -> None:
    """Translate expected domain failures into the shared API contract."""

    if isinstance(exc, StudyGroupNoReadyChunksError):
        raise ApiError(
            status_code=409,
            code="STUDY_GROUP_NO_READY_CHUNKS",
            message=str(exc),
        ) from exc

    if isinstance(exc, StudyGroupAiUnavailableError):
        raise ApiError(
            status_code=503,
            code="STUDY_GROUP_AI_UNAVAILABLE",
            message=str(exc),
        ) from exc

    if isinstance(exc, StudyGroupAnswerGenerationError):
        raise ApiError(
            status_code=502,
            code="STUDY_GROUP_ANSWER_GENERATION_FAILED",
            message=str(exc),
        ) from exc

    if isinstance(exc, StudyGroupMentionedUserNotMemberError):
        raise ApiError(
            status_code=422,
            code="STUDY_GROUP_MENTIONED_USER_NOT_MEMBER",
            message=str(exc),
        ) from exc

    if isinstance(exc, StudyGroupMessageNotFoundError):
        raise ApiError(
            status_code=404,
            code="STUDY_GROUP_MESSAGE_NOT_FOUND",
            message="The requested group message was not found.",
        ) from exc

    if isinstance(exc, StudyGroupMessagePermissionDeniedError):
        raise ApiError(
            status_code=403,
            code="STUDY_GROUP_MESSAGE_PERMISSION_DENIED",
            message=str(exc),
        ) from exc

    if isinstance(exc, StudyGroupChannelNotFoundError):
        raise ApiError(
            status_code=404,
            code="STUDY_GROUP_CHANNEL_NOT_FOUND",
            message="The requested study group channel was not found.",
        ) from exc

    if isinstance(exc, StudyGroupNotFoundError):
        raise ApiError(
            status_code=404,
            code="STUDY_GROUP_NOT_FOUND",
            message="The requested study group was not found.",
        ) from exc

    if isinstance(exc, StudyGroupPermissionDeniedError):
        raise ApiError(
            status_code=403,
            code="STUDY_GROUP_PERMISSION_DENIED",
            message=str(exc),
        ) from exc

    if isinstance(exc, StudyGroupTargetUserNotFoundError):
        raise ApiError(
            status_code=404,
            code="STUDY_GROUP_TARGET_USER_NOT_FOUND",
            message=str(exc),
        ) from exc

    if isinstance(exc, PrivateStudyGroupJoinError):
        raise ApiError(
            status_code=403,
            code="PRIVATE_GROUP_INVITATION_REQUIRED",
            message=str(exc),
        ) from exc

    if isinstance(exc, StudyGroupAlreadyMemberError):
        raise ApiError(
            status_code=409,
            code="ALREADY_GROUP_MEMBER",
            message=str(exc),
        ) from exc

    if isinstance(exc, StudyGroupMembershipNotFoundError):
        raise ApiError(
            status_code=409,
            code="NOT_GROUP_MEMBER",
            message=str(exc),
        ) from exc

    if isinstance(exc, StudyGroupFullError):
        raise ApiError(
            status_code=409,
            code="STUDY_GROUP_FULL",
            message=str(exc),
        ) from exc

    if isinstance(exc, StudyGroupChannelNameConflictError):
        raise ApiError(
            status_code=409,
            code="STUDY_GROUP_CHANNEL_NAME_CONFLICT",
            message=str(exc),
        ) from exc

    if isinstance(exc, InvalidStudyGroupError):
        raise ApiError(
            status_code=422,
            code="VALIDATION_ERROR",
            message=str(exc),
        ) from exc

    if isinstance(exc, InvalidStudyGroupMessageError):
        raise ApiError(
            status_code=422,
            code="VALIDATION_ERROR",
            message=str(exc),
        ) from exc


def _raise_group_attachment_api_error(exc: Exception) -> None:
    """Translate Study Group attachment failures to the shared API shape."""

    # Preserve group/channel authorization and not-found errors.
    if isinstance(
        exc,
        (StudyGroupChannelNotFoundError, StudyGroupPermissionDeniedError),
    ):
        _raise_study_group_api_error(exc)

    if isinstance(exc, AttachmentNotFoundError):
        raise ApiError(
            status_code=404,
            code="STUDY_GROUP_ATTACHMENT_NOT_FOUND",
            message="The requested channel attachment was not found.",
        ) from exc

    if isinstance(exc, FileTooLargeError):
        raise ApiError(
            status_code=413,
            code="FILE_TOO_LARGE",
            message=str(exc),
            details={"maximum_size_bytes": exc.maximum_size_bytes},
        ) from exc

    if isinstance(exc, UnsupportedFileTypeError):
        raise ApiError(
            status_code=415,
            code="UNSUPPORTED_FILE_TYPE",
            message=str(exc),
        ) from exc

    validation_errors = (EmptyFileError, InvalidPdfError, UnsafeFilenameError)
    if isinstance(exc, validation_errors):
        raise ApiError(
            status_code=422,
            code="INVALID_CHANNEL_ATTACHMENT",
            message=str(exc),
        ) from exc

    if isinstance(exc, AttachmentStorageError):
        raise ApiError(
            status_code=503,
            code="FILE_STORAGE_UNAVAILABLE",
            message="Private file storage is temporarily unavailable.",
            retryable=True,
        ) from exc

    if isinstance(exc, ProcessingDispatchError):
        raise ApiError(
            status_code=503,
            code="PROCESSING_UNAVAILABLE",
            message=str(exc),
            retryable=True,
        ) from exc
