/* Delete this line and the last line to run the script

-- ==========================================
-- 1. USERS (10 rows)
-- [ 3 administrators, 7 students ]
-- ==========================================
INSERT INTO users (user_id, email, username, hash_password, salt, user_role, user_status, created_at, last_updated_at) 
VALUES 
('11111111-1111-1111-1111-111111111111', 'admin_alice@school.edu', 'admin_alice', 'hash_1', 'salt_1', 'administrator', 'active', now() - interval '30 days', now()),
('22222222-2222-2222-2222-222222222222', 'student_bob@school.edu', 'student_bob', 'hash_2', 'salt_2', 'student', 'active', now() - interval '28 days', now()),
('33333333-3333-3333-3333-333333333333', 'student_charlie@school.edu', 'student_charlie', 'hash_3', 'salt_3', 'student', 'active', now() - interval '27 days', now()),
('44444444-4444-4444-4444-444444444444', 'student_diana@school.edu', 'student_diana', 'hash_4', 'salt_4', 'student', 'active', now() - interval '25 days', now()),
('55555555-5555-5555-5555-555555555555', 'admin_eve@school.edu', 'admin_eve', 'hash_5', 'salt_5', 'administrator', 'active', now() - interval '20 days', now()),
('66666666-6666-6666-6666-666666666666', 'student_frank@school.edu', 'student_frank', 'hash_6', 'salt_6', 'student', 'active', now() - interval '15 days', now()),
('77777777-7777-7777-7777-777777777777', 'student_grace@school.edu', 'student_grace', 'hash_7', 'salt_7', 'student', 'active', now() - interval '14 days', now()),
('88888888-8888-8888-8888-888888888888', 'student_hank@school.edu', 'student_hank', 'hash_8', 'salt_8', 'student', 'deactivated', now() - interval '10 days', now()),
('99999999-9999-9999-9999-999999999999', 'admin_irene@school.edu', 'admin_irene', 'hash_9', 'salt_9', 'administrator', 'active', now() - interval '5 days', now()),
('aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa', 'student_jack@school.edu', 'student_jack', 'hash_10', 'salt_10', 'student', 'active', now() - interval '2 days', now());

-- ==========================================
-- 2. GROUPS (5 rows)
-- ==========================================
INSERT INTO groups (group_id, group_name, group_type, description, created_by, current_admin, max_members, group_status, created_at, last_updated_at)
VALUES 
('bbbbbbbb-1111-1111-1111-bbbbbbbbbbbb', 'CS101 Study Group', 'private', 'Intro to Computer Science', '11111111-1111-1111-1111-111111111111', '11111111-1111-1111-1111-111111111111', 50, 'active', now() - interval '29 days', now()),
('bbbbbbbb-2222-2222-2222-bbbbbbbbbbbb', 'Math 202', 'public', 'Advanced Calculus Discussions', '55555555-5555-5555-5555-555555555555', '55555555-5555-5555-5555-555555555555', 100, 'active', now() - interval '19 days', now()),
('bbbbbbbb-3333-3333-3333-bbbbbbbbbbbb', 'History 105', 'public', 'World History Study', '99999999-9999-9999-9999-999999999999', '99999999-9999-9999-9999-999999999999', 30, 'active', now() - interval '4 days', now()),
('bbbbbbbb-4444-4444-4444-bbbbbbbbbbbb', 'Physics Lab Team', 'private', 'Lab assignments coordination', '11111111-1111-1111-1111-111111111111', '11111111-1111-1111-1111-111111111111', 5, 'active', now() - interval '2 days', now()),
('bbbbbbbb-5555-5555-5555-bbbbbbbbbbbb', 'Art History Personal', 'personal', 'Personal notes on Art', '22222222-2222-2222-2222-222222222222', '22222222-2222-2222-2222-222222222222', 1, 'active', now() - interval '1 days', now());

-- ==========================================
-- 3. CHANNELS (5 rows)
-- ==========================================
INSERT INTO channels (channel_id, channel_name, group_id, description, created_by, created_at, last_updated_at)
VALUES 
('cccccccc-1111-1111-1111-cccccccccccc', 'cs-general', 'bbbbbbbb-1111-1111-1111-bbbbbbbbbbbb', 'General CS Q&A', '11111111-1111-1111-1111-111111111111', now() - interval '28 days', now()),
('cccccccc-2222-2222-2222-cccccccccccc', 'math-homework', 'bbbbbbbb-2222-2222-2222-bbbbbbbbbbbb', 'Calculus homework help', '55555555-5555-5555-5555-555555555555', now() - interval '18 days', now()),
('cccccccc-3333-3333-3333-cccccccccccc', 'history-debates', 'bbbbbbbb-3333-3333-3333-bbbbbbbbbbbb', 'Debating historical events', '99999999-9999-9999-9999-999999999999', now() - interval '3 days', now()),
('cccccccc-4444-4444-4444-cccccccccccc', 'physics-data', 'bbbbbbbb-4444-4444-4444-bbbbbbbbbbbb', 'Dropping lab results here', '11111111-1111-1111-1111-111111111111', now() - interval '1 days', now()),
('cccccccc-5555-5555-5555-cccccccccccc', 'renaissance-notes', 'bbbbbbbb-5555-5555-5555-bbbbbbbbbbbb', 'My personal notes', '22222222-2222-2222-2222-222222222222', now() - interval '1 days', now());

-- ==========================================
-- 4. MEMBERSHIPS (10 rows)
-- ==========================================
INSERT INTO memberships (user_id, group_id, member_role, joined_at)
VALUES 
('11111111-1111-1111-1111-111111111111', 'bbbbbbbb-1111-1111-1111-bbbbbbbbbbbb', 'admin', now() - interval '29 days'),
('22222222-2222-2222-2222-222222222222', 'bbbbbbbb-1111-1111-1111-bbbbbbbbbbbb', 'member', now() - interval '28 days'),
('33333333-3333-3333-3333-333333333333', 'bbbbbbbb-1111-1111-1111-bbbbbbbbbbbb', 'member', now() - interval '27 days'),
('55555555-5555-5555-5555-555555555555', 'bbbbbbbb-2222-2222-2222-bbbbbbbbbbbb', 'admin', now() - interval '19 days'),
('44444444-4444-4444-4444-444444444444', 'bbbbbbbb-2222-2222-2222-bbbbbbbbbbbb', 'member', now() - interval '15 days'),
('66666666-6666-6666-6666-666666666666', 'bbbbbbbb-2222-2222-2222-bbbbbbbbbbbb', 'member', now() - interval '14 days'),
('99999999-9999-9999-9999-999999999999', 'bbbbbbbb-3333-3333-3333-bbbbbbbbbbbb', 'admin', now() - interval '4 days'),
('77777777-7777-7777-7777-777777777777', 'bbbbbbbb-3333-3333-3333-bbbbbbbbbbbb', 'member', now() - interval '3 days'),
('aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa', 'bbbbbbbb-4444-4444-4444-bbbbbbbbbbbb', 'member', now() - interval '1 days'),
('22222222-2222-2222-2222-222222222222', 'bbbbbbbb-5555-5555-5555-bbbbbbbbbbbb', 'admin', now() - interval '1 days');

-- ==========================================
-- 5. MESSAGES (10 rows)
-- Generates message_id 1 through 10
-- ==========================================
INSERT INTO messages (user_id, channel_id, message_content, ai_mode_used, sent_at)
VALUES 
('22222222-2222-2222-2222-222222222222', 'cccccccc-1111-1111-1111-cccccccccccc', 'Can someone explain how foreign keys work?', 'default', now() - interval '20 hours'),
('11111111-1111-1111-1111-111111111111', 'cccccccc-1111-1111-1111-cccccccccccc', 'Let me trigger the AI facilitator to answer this.', 'facilitator', now() - interval '19 hours'),
('33333333-3333-3333-3333-333333333333', 'cccccccc-1111-1111-1111-cccccccccccc', 'Could the AI summarize the last lecture?', 'summarizer', now() - interval '18 hours'),
('44444444-4444-4444-4444-444444444444', 'cccccccc-2222-2222-2222-cccccccccccc', 'I am stuck on problem 5. Help?', 'default', now() - interval '15 hours'),
('55555555-5555-5555-5555-555555555555', 'cccccccc-2222-2222-2222-cccccccccccc', 'Let''s do a quick quiz on limits.', 'quiz', now() - interval '14 hours'),
('66666666-6666-6666-6666-666666666666', 'cccccccc-2222-2222-2222-cccccccccccc', 'I got 42 for the limit, is that right?', 'default', now() - interval '13 hours'),
('77777777-7777-7777-7777-777777777777', 'cccccccc-3333-3333-3333-cccccccccccc', 'What caused the fall of Rome?', 'default', now() - interval '10 hours'),
('99999999-9999-9999-9999-999999999999', 'cccccccc-3333-3333-3333-cccccccccccc', 'Let the AI facilitator pull some sources for that.', 'facilitator', now() - interval '9 hours'),
('aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa', 'cccccccc-4444-4444-4444-cccccccccccc', 'Uploading the lab data from today.', 'default', now() - interval '2 hours'),
('22222222-2222-2222-2222-222222222222', 'cccccccc-5555-5555-5555-cccccccccccc', 'Summarize my notes on Da Vinci.', 'summarizer', now() - interval '1 hours');

-- ==========================================
-- 6. ATTACHMENTS (5 rows)
-- Generates attachment_id 1 through 5
-- ==========================================
INSERT INTO attachments (uploaded_by, channel_id, message_id, file_name, file_type, file_size_bytes, object_path, processing_status, uploaded_at)
VALUES 
('11111111-1111-1111-1111-111111111111', 'cccccccc-1111-1111-1111-cccccccccccc', 2, 'database_schema.pdf', 'application/pdf', 102400, 's3://bucket/cs101/database_schema.pdf', 'completed', now() - interval '19 hours'),
('33333333-3333-3333-3333-333333333333', 'cccccccc-1111-1111-1111-cccccccccccc', 3, 'lecture_transcript.txt', 'text/plain', 45000, 's3://bucket/cs101/lecture_transcript.txt', 'completed', now() - interval '18 hours'),
('55555555-5555-5555-5555-555555555555', 'cccccccc-2222-2222-2222-cccccccccccc', 5, 'limits_worksheet.docx', 'application/msword', 85000, 's3://bucket/math202/limits_worksheet.docx', 'completed', now() - interval '14 hours'),
('99999999-9999-9999-9999-999999999999', 'cccccccc-3333-3333-3333-cccccccccccc', 8, 'roman_empire_sources.pdf', 'application/pdf', 2500000, 's3://bucket/hist105/roman_empire_sources.pdf', 'processing', now() - interval '9 hours'),
('aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa', 'cccccccc-4444-4444-4444-cccccccccccc', 9, 'lab_results.csv', 'text/csv', 12000, 's3://bucket/phys/lab_results.csv', 'completed', now() - interval '2 hours');

-- ==========================================
-- 7. CHUNKS (10 rows)
-- Generates chunk_id 1 through 10
-- ==========================================
INSERT INTO chunks (attachment_id, chunk_order, chunk_content, embedding_model_version, vector_embedding, created_at)
VALUES 
(1, 1, 'A foreign key is a column or group of columns in a relational database table.', 'text-embedding-3-small', array_fill(0.111::real, ARRAY[1536])::vector, now() - interval '19 hours'),
(1, 2, 'It acts as a cross-reference between tables because it references the primary key.', 'text-embedding-3-small', array_fill(0.222::real, ARRAY[1536])::vector, now() - interval '19 hours'),
(2, 1, 'Welcome to CS101 lecture 4. Today we will cover SQL joins.', 'text-embedding-3-small', array_fill(0.333::real, ARRAY[1536])::vector, now() - interval '18 hours'),
(2, 2, 'An inner join returns records that have matching values in both tables.', 'text-embedding-3-small', array_fill(0.444::real, ARRAY[1536])::vector, now() - interval '18 hours'),
(3, 1, 'Question 1: Calculate the limit as x approaches 0 for sin(x)/x.', 'text-embedding-3-small', array_fill(0.555::real, ARRAY[1536])::vector, now() - interval '14 hours'),
(3, 2, 'The fundamental theorem of calculus connects differentiation and integration.', 'text-embedding-3-small', array_fill(0.666::real, ARRAY[1536])::vector, now() - interval '14 hours'),
(4, 1, 'The Western Roman Empire fell in 476 AD when Romulus Augustulus was deposed.', 'text-embedding-3-small', array_fill(0.777::real, ARRAY[1536])::vector, now() - interval '9 hours'),
(4, 2, 'Economic instability and reliance on mercenary armies contributed to the decline.', 'text-embedding-3-small', array_fill(0.888::real, ARRAY[1536])::vector, now() - interval '9 hours'),
(5, 1, 'Timestamp,Velocity,Acceleration\n0.0s,0.0,9.81\n0.5s,4.9,9.81', 'text-embedding-3-small', array_fill(0.999::real, ARRAY[1536])::vector, now() - interval '2 hours'),
(5, 2, '1.0s,9.8,9.81\n1.5s,14.7,9.81', 'text-embedding-3-small', array_fill(0.123::real, ARRAY[1536])::vector, now() - interval '2 hours');

-- ==========================================
-- 8. KNOWLEDGE GRAPHS (5 rows)
-- Generates graph_id 1 through 5
-- ==========================================
INSERT INTO knowledge_graphs (user_id, graph_name, description, created_at, last_updated_at)
VALUES 
('11111111-1111-1111-1111-111111111111', 'Database Concepts', 'Relational database theory map', now() - interval '20 days', now()),
('55555555-5555-5555-5555-555555555555', 'Calculus Map', 'Mapping derivatives and integrals', now() - interval '18 days', now()),
('99999999-9999-9999-9999-999999999999', 'Roman Empire Timeline', 'Events leading to the fall of Rome', now() - interval '5 days', now()),
('aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa', 'Physics Kinematics', 'Nodes for velocity, mass, and force', now() - interval '2 days', now()),
('22222222-2222-2222-2222-222222222222', 'Renaissance Artists', 'Connections between Da Vinci and peers', now() - interval '1 days', now());

-- ==========================================
-- 9. KNOWLEDGE NODES (10 rows)
-- Generates node_id 1 through 10
-- ==========================================
INSERT INTO knowledge_nodes (graph_id, node_label, node_properties, position_x, position_y, created_at, last_updated_at)
VALUES 
(1, 'Primary Key', '{"importance": "high", "color": "blue"}'::jsonb, 100.0, 200.0, now(), now()),
(1, 'Foreign Key', '{"importance": "high", "color": "green"}'::jsonb, 300.0, 200.0, now(), now()),
(2, 'Derivative', '{"concept": "rate of change"}'::jsonb, 150.0, 150.0, now(), now()),
(2, 'Integral', '{"concept": "area under curve"}'::jsonb, 150.0, 400.0, now(), now()),
(3, 'Romulus Augustulus', '{"role": "emperor"}'::jsonb, 500.0, 100.0, now(), now()),
(3, 'Odoacer', '{"role": "barbarian king"}'::jsonb, 700.0, 100.0, now(), now()),
(4, 'Velocity', '{"unit": "m/s"}'::jsonb, 100.0, 100.0, now(), now()),
(4, 'Acceleration', '{"unit": "m/s^2"}'::jsonb, 200.0, 100.0, now(), now()),
(5, 'Leonardo Da Vinci', '{"profession": "polymath"}'::jsonb, 300.0, 300.0, now(), now()),
(5, 'Mona Lisa', '{"type": "painting"}'::jsonb, 400.0, 300.0, now(), now());

-- ==========================================
-- 10. KNOWLEDGE EDGES (5 rows)
-- Generates edge_id 1 through 5
-- ==========================================
INSERT INTO knowledge_edges (graph_id, source_node_id, target_node_id, edge_label, edge_properties, created_at, last_updated_at)
VALUES 
(1, 2, 1, 'REFERENCES', '{"weight": 1.0}'::jsonb, now(), now()),
(2, 3, 4, 'INVERSE_OF', '{"theorem": "fundamental theorem of calculus"}'::jsonb, now(), now()),
(3, 6, 5, 'DEPOSED', '{"year": 476}'::jsonb, now(), now()),
(4, 8, 7, 'RATE_OF_CHANGE_OF', '{"formula": "dv/dt"}'::jsonb, now(), now()),
(5, 9, 10, 'PAINTED', '{"year": 1503}'::jsonb, now(), now());

-- ==========================================
-- 11. AI RESPONSES (5 rows)
-- Generates response_id 1 through 5
-- ==========================================
INSERT INTO ai_responses (message_id, ai_mode_used, response, confidence_score, attempt_number, is_selected, execution_time_ms, token_count, generated_at)
VALUES 
(2, 'facilitator', '{"text": "A foreign key links to a primary key in another table."}'::jsonb, 0.95, 1, true, 1250, 45, now() - interval '19 hours'),
(3, 'summarizer', '{"text": "The lecture covered SQL joins, specifically inner joins."}'::jsonb, 0.98, 1, true, 2100, 80, now() - interval '18 hours'),
(5, 'quiz', '{"question": "What is the limit of sin(x)/x as x approaches 0?", "options": ["0", "1", "infinity", "undefined"]}'::jsonb, 0.92, 1, true, 3400, 150, now() - interval '14 hours'),
(8, 'facilitator', '{"text": "Rome fell in 476 AD due to economic issues and barbarian invasions."}'::jsonb, 0.89, 2, true, 4100, 200, now() - interval '9 hours'),
(10, 'summarizer', '{"text": "Da Vinci was a Renaissance polymath famous for painting the Mona Lisa."}'::jsonb, 0.99, 1, true, 1500, 60, now() - interval '1 hours');

-- ==========================================
-- 12. AI RESPONSE SOURCES (5 rows)
-- Generates retrieval_id 1 through 5
-- ==========================================
INSERT INTO ai_response_sources (response_id, chunk_id, node_id, edge_id, similarity_score, rerank_score, is_used_in_prompt)
VALUES 
(1, 1, 2, 1, 0.88, 0.92, true),
(2, 3, NULL, NULL, 0.91, 0.95, true),
(3, 5, NULL, NULL, 0.85, 0.89, true),
(4, 7, 5, 3, 0.94, 0.96, true),
(5, NULL, 9, 5, 0.99, 0.99, true);

-- ==========================================
-- 13. AI RESPONSE FEEDBACKS (5 rows)
-- ==========================================
INSERT INTO ai_response_feedbacks (response_id, user_id, rating, feedback_text, created_at)
VALUES 
(1, '22222222-2222-2222-2222-222222222222', 'good', 'Very helpful and concise!', now() - interval '18 hours'),
(2, '33333333-3333-3333-3333-333333333333', 'good', 'Perfect summary.', now() - interval '17 hours'),
(3, '66666666-6666-6666-6666-666666666666', 'bad', 'The quiz options were confusing.', now() - interval '13 hours'),
(4, '77777777-7777-7777-7777-777777777777', 'good', 'Great historical context provided.', now() - interval '8 hours'),
(5, '22222222-2222-2222-2222-222222222222', 'good', 'Nailed it.', now() - interval '30 minutes');

-- ==========================================
-- 14. SESSIONS (10 rows)
-- ==========================================
INSERT INTO sessions (user_id, hash_session_token, ip_address, started_at, expired_at)
VALUES 
('11111111-1111-1111-1111-111111111111', 'token_111', '192.168.1.10', now() - interval '20 hours', now() + interval '4 hours'),
('22222222-2222-2222-2222-222222222222', 'token_222', '192.168.1.15', now() - interval '20 hours', now() + interval '4 hours'),
('33333333-3333-3333-3333-333333333333', 'token_333', '192.168.1.20', now() - interval '18 hours', now() + interval '6 hours'),
('44444444-4444-4444-4444-444444444444', 'token_444', '192.168.1.25', now() - interval '15 hours', now() + interval '9 hours'),
('55555555-5555-5555-5555-555555555555', 'token_555', '192.168.1.30', now() - interval '14 hours', now() + interval '10 hours'),
('66666666-6666-6666-6666-666666666666', 'token_666', '192.168.1.35', now() - interval '13 hours', now() + interval '11 hours'),
('77777777-7777-7777-7777-777777777777', 'token_777', '192.168.1.40', now() - interval '10 hours', now() + interval '14 hours'),
('99999999-9999-9999-9999-999999999999', 'token_999', '192.168.1.50', now() - interval '9 hours', now() + interval '15 hours'),
('aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa', 'token_aaa', '192.168.1.55', now() - interval '2 hours', now() + interval '22 hours'),
('22222222-2222-2222-2222-222222222222', 'token_222_b', '192.168.1.16', now() - interval '1 hours', now() + interval '23 hours');

-- ==========================================
-- 15. USER ACTIVITY LOGS (10 rows)
-- ==========================================
INSERT INTO user_activity_logs (user_id, user_action, entity_type, entity_id, ip_address, user_agent, metadata, created_at)
VALUES 
('22222222-2222-2222-2222-222222222222', 'login', 'session', '2', '192.168.1.15', 'Chrome/119.0', '{"method": "oauth"}'::jsonb, now() - interval '20 hours'),
('22222222-2222-2222-2222-222222222222', 'send', 'message', '1', '192.168.1.15', 'Chrome/119.0', '{"channel": "cs-general"}'::jsonb, now() - interval '20 hours'),
('11111111-1111-1111-1111-111111111111', 'upload', 'attachment', '1', '192.168.1.10', 'Firefox/120.0', '{"size": 102400}'::jsonb, now() - interval '19 hours'),
('33333333-3333-3333-3333-333333333333', 'ai_request', 'message', '3', '192.168.1.20', 'Safari/17.1', '{"mode": "summarizer"}'::jsonb, now() - interval '18 hours'),
('55555555-5555-5555-5555-555555555555', 'create', 'group', 'bbbbbbbb-2222-2222-2222-bbbbbbbbbbbb', '192.168.1.30', 'Edge/118.0', '{"group_type": "public"}'::jsonb, now() - interval '19 days'),
('66666666-6666-6666-6666-666666666666', 'ai_feedback', 'ai_response', '3', '192.168.1.35', 'Chrome/119.0', '{"rating": "bad"}'::jsonb, now() - interval '13 hours'),
('99999999-9999-9999-9999-999999999999', 'upload', 'attachment', '4', '192.168.1.50', 'Firefox/120.0', '{"status": "processing"}'::jsonb, now() - interval '9 hours'),
('88888888-8888-8888-8888-888888888888', 'delete', 'user', '88888888-8888-8888-8888-888888888888', '192.168.1.45', 'Chrome/119.0', '{"reason": "graduated"}'::jsonb, now() - interval '10 days'),
('aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa', 'join', 'group', 'bbbbbbbb-4444-4444-4444-bbbbbbbbbbbb', '192.168.1.55', 'Safari/17.1', '{"role": "member"}'::jsonb, now() - interval '1 days'),
('22222222-2222-2222-2222-222222222222', 'ai_request', 'message', '10', '192.168.1.16', 'Mobile Safari/17.1', '{"mode": "summarizer"}'::jsonb, now() - interval '1 hours');

*/