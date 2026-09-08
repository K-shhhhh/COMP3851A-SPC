-- The following scripts delete the entire database environment.
-- This is for testing purposes during developing stage.

/* Delete this line and the last line to uncomment the script.

-- Drop all tables
DROP TABLE IF EXISTS user_activity_logs CASCADE;
DROP TABLE IF EXISTS sessions CASCADE;
DROP TABLE IF EXISTS knowledge_edges CASCADE;
DROP TABLE IF EXISTS knowledge_nodes CASCADE;
DROP TABLE IF EXISTS knowledge_graphs CASCADE;
DROP TABLE IF EXISTS ai_response_feedbacks CASCADE;
DROP TABLE IF EXISTS ai_response_sources CASCADE;
DROP TABLE IF EXISTS ai_responses CASCADE;
DROP TABLE IF EXISTS chunks CASCADE;
DROP TABLE IF EXISTS attachments CASCADE;
DROP TABLE IF EXISTS messages CASCADE;
DROP TABLE IF EXISTS channels CASCADE;
DROP TABLE IF EXISTS groups CASCADE;
DROP TABLE IF EXISTS memberships CASCADE;
DROP TABLE IF EXISTS users CASCADE;

-- Drop custom enum types
DROP TYPE IF EXISTS actions CASCADE;
DROP TYPE IF EXISTS ratings CASCADE;
DROP TYPE IF EXISTS ai_modes CASCADE;
DROP TYPE IF EXISTS group_types CASCADE;
DROP TYPE IF EXISTS member_roles CASCADE;
DROP TYPE IF EXISTS user_roles CASCADE;
DROP TYPE IF EXISTS status CASCADE;

-- Drop vector extension
drop extension if exists vector;

*/