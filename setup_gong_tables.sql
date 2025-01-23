-- Enable required extensions
CREATE EXTENSION IF NOT EXISTS vector;

-- Create custom types
CREATE TYPE interaction_type AS ENUM (
    'discovery_call',
    'demo',
    'follow_up',
    'implementation',
    'support',
    'other'
);

-- Create base tables
CREATE TABLE calls (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    call_id TEXT,
    account_id TEXT,
    title TEXT,
    start_time TIMESTAMP WITH TIME ZONE,
    duration INTEGER,
    summary TEXT,
    sentiment TEXT,
    transcript TEXT,
    embedding vector(1536),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE TABLE transcript_segments (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    call_id BIGINT REFERENCES calls(id),
    speaker TEXT,
    content TEXT,
    embedding vector(1536),
    timestamp INTEGER,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE TABLE feature_requests (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    call_id BIGINT REFERENCES calls(id),
    request TEXT,
    context TEXT,
    priority TEXT,
    embedding vector(1536),
    timestamp INTEGER,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Create search functions
CREATE OR REPLACE FUNCTION match_summaries(
    query_embedding vector(1536),
    match_threshold float,
    match_limit int
)
RETURNS TABLE (
    id bigint,
    call_id text,
    content text,
    title text,
    similarity float
)
LANGUAGE plpgsql
AS $$
DECLARE
    query_text text;
BEGIN
    -- Extract the query text
    query_text := REPLACE(REPLACE(query_embedding::text, '[', ''), ']', '');
    
    -- Use a CTE to get unique results with highest similarity
    RETURN QUERY
    WITH unique_matches AS (
        SELECT DISTINCT ON (c.id)  -- This ensures one row per call
            c.id,
            c.call_id,
            c.summary as content,
            c.title,
            GREATEST(
                CASE 
                    WHEN c.call_id::text = query_text::text THEN 1.0
                    WHEN c.title ILIKE '%' || query_text || '%' THEN 0.99
                    ELSE 1 - (c.embedding <=> query_embedding)
                END
            ) as similarity
        FROM calls c
        WHERE 
            c.call_id::text = query_text::text
            OR c.title ILIKE '%' || query_text || '%'
            OR 1 - (c.embedding <=> query_embedding) > match_threshold
        ORDER BY c.id, similarity DESC  -- Take highest similarity for each id
    )
    SELECT * FROM unique_matches
    ORDER BY similarity DESC
    LIMIT match_limit;
END;
$$;

CREATE OR REPLACE FUNCTION match_transcript_segments(
    query_embedding vector(1536),
    similarity_threshold float,
    max_matches int,
    start_date timestamp default null
)
RETURNS TABLE (
    content TEXT,
    call_id BIGINT,
    speaker TEXT,
    ts INT,
    similarity float
)
LANGUAGE plpgsql
AS $$
BEGIN
    SET LOCAL statement_timeout = '5s';
    RETURN QUERY
    SELECT
        ts.content,
        ts.call_id,
        ts.speaker,
        ts.timestamp,
        1 - (ts.embedding <=> query_embedding) as similarity
    FROM transcript_segments ts
    WHERE 
        CASE 
            WHEN start_date IS NOT NULL THEN ts.created_at >= start_date
            ELSE true
        END
        AND 1 - (ts.embedding <=> query_embedding) > similarity_threshold
    ORDER BY ts.embedding <=> query_embedding
    LIMIT max_matches;
END;
$$;

CREATE OR REPLACE FUNCTION match_feature_requests(
    query_embedding vector(1536),
    match_threshold float,
    match_limit int
)
RETURNS TABLE (
    id bigint,
    call_id bigint,
    request text,
    context text,
    priority text,
    title text,
    similarity float
)
LANGUAGE plpgsql
AS $$
BEGIN
    RETURN QUERY
    WITH unique_matches AS (
        SELECT DISTINCT ON (fr.id)
            fr.id,
            fr.call_id,
            fr.request,
            fr.context,
            fr.priority,
            c.title,
            GREATEST(
                1 - (c.embedding <=> query_embedding),
                COALESCE(1 - (fr.embedding <=> query_embedding), 0)
            ) as similarity
        FROM feature_requests fr
        JOIN calls c ON c.id = fr.call_id
        WHERE 
            1 - (c.embedding <=> query_embedding) > match_threshold
            OR (fr.embedding IS NOT NULL AND 1 - (fr.embedding <=> query_embedding) > match_threshold)
        ORDER BY fr.id, similarity DESC
    )
    SELECT * FROM unique_matches
    ORDER BY similarity DESC
    LIMIT match_limit;
END;
$$;

CREATE OR REPLACE FUNCTION match_feature_requests_text(
    query_text text,    -- renamed parameter to avoid confusion
    match_limit int DEFAULT 5
)
RETURNS TABLE (
    id bigint,
    call_id bigint,
    request text,
    context text,
    priority text,
    title text,
    similarity float
)
LANGUAGE plpgsql
AS $$
DECLARE
    matching_rows int;
BEGIN    
    -- Start logging
    INSERT INTO debug_logs (message) 
    VALUES ('START: Searching for text: ' || query_text);

    -- Check what we're comparing against
    SELECT COUNT(*) INTO matching_rows 
    FROM calls c
    WHERE c.call_id = query_text;
    
    INSERT INTO debug_logs (message) 
    VALUES ('Found ' || matching_rows || ' matching call_ids in calls table');

    -- First try exact call_id match
    RETURN QUERY
    SELECT 
        fr.id,
        fr.call_id,
        fr.request,
        fr.context,
        fr.priority,
        c.title,
        1.0::float as similarity
    FROM feature_requests fr
    JOIN calls c ON c.id = fr.call_id
    WHERE c.call_id = query_text;
    
    GET DIAGNOSTICS matching_rows = ROW_COUNT;
    INSERT INTO debug_logs (message) 
    VALUES ('Call ID search returned ' || matching_rows || ' rows');
    
    -- If no call_id match, try title matches
    IF matching_rows = 0 THEN
        INSERT INTO debug_logs (message) 
        VALUES ('Trying title search for: ' || query_text);
        
        RETURN QUERY
        SELECT 
            fr.id,
            fr.call_id,
            fr.request,
            fr.context,
            fr.priority,
            c.title,
            0.99::float as similarity
        FROM calls c
        JOIN feature_requests fr ON fr.call_id = c.id
        WHERE c.title ILIKE '%' || query_text || '%';
        
        GET DIAGNOSTICS matching_rows = ROW_COUNT;
        INSERT INTO debug_logs (message) 
        VALUES ('Title search returned ' || matching_rows || ' rows');
    END IF;
    
    -- Final log
    INSERT INTO debug_logs (message) 
    VALUES ('END: Search complete');
END;
$$;


-- Create indexes for better performance
CREATE INDEX IF NOT EXISTS idx_calls_call_id ON calls(call_id);
CREATE INDEX idx_calls_date ON calls(start_time);
CREATE INDEX idx_calls_created_at ON calls(created_at);
CREATE INDEX idx_transcript_segments_call ON transcript_segments(call_id);
CREATE INDEX idx_feature_requests_call_id ON feature_requests(call_id);
CREATE INDEX idx_feature_mentions_feature ON feature_requests(request);

-- Create vector indexes
CREATE INDEX calls_embedding_idx ON calls 
USING ivfflat (embedding vector_l2_ops)
WITH (lists = 1000);

CREATE INDEX feature_requests_embedding_idx ON feature_requests 
USING ivfflat (embedding vector_l2_ops)
WITH (lists = 100);

CREATE INDEX transcript_segments_embedding_created_idx ON transcript_segments 
USING ivfflat (embedding vector_l2_ops)
WITH (lists = 100);

-- Optimize table settings for vector operations
ALTER TABLE calls SET (autovacuum_vacuum_scale_factor = 0.0);
ALTER TABLE calls SET (autovacuum_vacuum_threshold = 5000);
ALTER TABLE feature_requests SET (autovacuum_vacuum_scale_factor = 0.0);
ALTER TABLE feature_requests SET (autovacuum_vacuum_threshold = 5000);

-- Make sure we have the extension for text search
CREATE EXTENSION IF NOT EXISTS pg_trgm;

-- Create better indexes for text search
DROP INDEX IF EXISTS idx_feature_requests_request_gin;
DROP INDEX IF EXISTS idx_feature_requests_context_gin;
DROP INDEX IF EXISTS idx_calls_title_gin;

CREATE INDEX idx_feature_requests_request_gin ON feature_requests USING gin(request gin_trgm_ops);
CREATE INDEX idx_feature_requests_context_gin ON feature_requests USING gin(context gin_trgm_ops);
CREATE INDEX idx_calls_title_gin ON calls USING gin(title gin_trgm_ops);

-- Set better table statistics targets
ALTER TABLE feature_requests ALTER COLUMN request SET STATISTICS 1000;
ALTER TABLE feature_requests ALTER COLUMN context SET STATISTICS 1000;
ALTER TABLE calls ALTER COLUMN title SET STATISTICS 1000;

-- Analyze tables with increased statistics
ANALYZE feature_requests;
ANALYZE calls;

-- Add index for call_id text searches
CREATE INDEX IF NOT EXISTS idx_calls_call_id ON calls(call_id);
