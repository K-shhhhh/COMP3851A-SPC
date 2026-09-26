# Study Group Database Integration

## Ownership boundary

The API, application service, domain models, repository contract, and in-memory
adapter are complete. The PostgreSQL adapter remains the database developer's
responsibility. Do not change the API/service rules to fit SQLAlchemy; implement
the domain contract in:

`Backend/app/domains/study_groups/infrastructure/repository.py`

The required method signatures are defined in:

`Backend/app/domains/study_groups/domain/repository.py`

## Membership methods still required

- `find_active_user_id_by_email(...)`
- `list_members(...)`

Email lookup must be case-insensitive and must exclude deactivated or
soft-deleted accounts. Member listing returns only safe profile fields plus the
membership role and joining time.

## Channel methods required

- `list_channels(...)`
- `get_channel(...)`
- `channel_name_exists(...)`
- `create_channel(...)`
- `update_channel(...)`
- `soft_delete_channel(...)`

Use the existing `channels` ORM table. Always scope channel operations by both
`group_id` and `channel_id`, exclude `deleted_at IS NOT NULL`, and enforce an
active case-insensitive unique channel name inside each group. Deletion is soft
deletion. The service already performs membership and owner/admin permission
checks; the repository still must prevent cross-group reads and writes through
its query filters.

## Completion and switch

1. Implement every missing abstract method in the PostgreSQL adapter.
2. Add PostgreSQL integration tests for membership lookup/listing and the full
   channel lifecycle.
3. Confirm the deployed migration contains the required `channels` fields and
   active-name uniqueness rule.
4. Replace `InMemoryStudyGroupRepository` with
   `PostgreSQLStudyGroupRepository(session)` only in
   `Backend/app/api/dependencies.py`.
5. Run unit, security, PostgreSQL integration, and frontend workflow tests.

Until all five steps pass, keep dependency injection on the shared in-memory
adapter. This avoids partially working production persistence.
