-- Enable vector extension for semantic search
CREATE EXTENSION IF NOT EXISTS vector;

-- Enum for interaction types
CREATE TYPE interaction_type AS ENUM ('discovery_call', 'demo', 'follow_up', 'implementation', 'support', 'other');

-- Table for storing call metadata
CREATE TABLE calls (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    call_id TEXT,
    account_id TEXT,
    title TEXT,
    start_time TIMESTAMP WITH TIME ZONE,
    duration INTEGER,
    summary TEXT,  -- AI-generated summary of the call
    sentiment TEXT,   -- AI-analyzed sentiment score
    transcript TEXT,
    embedding vector(1536),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Table for storing transcript segments with embeddings
CREATE TABLE transcript_segments (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    call_id BIGINT REFERENCES calls(id),
    speaker TEXT,
    content TEXT,
    embedding vector(1536),  -- For OpenAI embeddings
    timestamp INTEGER,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Table for feature mentions and discussions
CREATE TABLE feature_requests (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    call_id BIGINT REFERENCES calls(id),
    request TEXT,
    context TEXT,
    priority TEXT,
    timestamp INTEGER,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Drop and recreate match_summaries function with explicit column references
CREATE OR REPLACE FUNCTION match_summaries(
    query_embedding vector(1536),
    match_threshold float,
    match_limit int
)
RETURNS TABLE (
    id bigint,
    call_id text,
    title text,
    content text,
    similarity float
)
LANGUAGE plpgsql
AS $$
BEGIN
    SET LOCAL statement_timeout = '10s';
    RETURN QUERY
    SELECT
        c.id,                -- Explicitly reference calls table
        c.call_id,
        c.title,
        c.summary as content,
        1 - (c.embedding <=> query_embedding) as similarity
    FROM calls c            -- Use table alias consistently
    WHERE 1 - (c.embedding <=> query_embedding) > match_threshold
    ORDER BY similarity DESC
    LIMIT match_limit;
END;
$$;

-- Function to match feature requests
CREATE OR REPLACE FUNCTION match_feature_requests (
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
    similarity float
)
LANGUAGE plpgsql
AS $$
BEGIN
    SET LOCAL statement_timeout = '10s';  -- Add 10-second timeout
    RETURN QUERY
    SELECT
        fr.id,
        fr.call_id,
        fr.request,
        fr.context,
        fr.priority,
        1 - (fr.embedding <=> query_embedding) as similarity
    FROM feature_requests fr
    WHERE 1 - (fr.embedding <=> query_embedding) > match_threshold
    ORDER BY similarity DESC
    LIMIT match_limit;
END;
$$;

-- Create indexes for better performance
CREATE INDEX IF NOT EXISTS idx_feature_requests_call_id ON feature_requests(call_id);

-- Indexes for performance
CREATE INDEX idx_calls_date ON calls(start_time);
CREATE INDEX idx_transcript_segments_call ON transcript_segments(call_id);
CREATE INDEX idx_feature_mentions_feature ON feature_requests(request);

-- Drop and recreate indexes with better parameters
DROP INDEX IF EXISTS calls_embedding_idx;
CREATE INDEX calls_embedding_idx ON calls 
USING ivfflat (embedding vector_l2_ops)
WITH (lists = 1000);  -- More lists for better search performance

-- Remove clustering command since ivfflat doesn't support it
-- Just analyze the table to update statistics
ANALYZE calls;

-- Add a regular B-tree index on created_at for date filtering
CREATE INDEX idx_calls_created_at ON calls(start_time);

-- Add vector index for feature_requests
ALTER TABLE feature_requests 
ADD COLUMN IF NOT EXISTS embedding vector(1536);

CREATE INDEX IF NOT EXISTS feature_requests_embedding_idx ON feature_requests 
USING ivfflat (embedding vector_l2_ops)
WITH (lists = 100);

-- First, drop existing indexes
DROP INDEX IF EXISTS transcript_segments_embedding_idx;
DROP INDEX IF EXISTS idx_transcript_segments_created;

-- Create a more efficient composite index
CREATE INDEX transcript_segments_embedding_created_idx ON transcript_segments 
USING ivfflat (embedding vector_l2_ops)
WITH (lists = 100);  -- Reduced lists for faster searches

-- Regular B-tree index for date filtering
CREATE INDEX idx_transcript_segments_created_call ON transcript_segments(created_at, call_id);

-- Update the search function to be more efficient
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
    SET LOCAL statement_timeout = '5s';  -- Reduced timeout
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

-- Add this after your other functions
CREATE OR REPLACE FUNCTION match_calls (
    query_embedding vector(1536),
    similarity_threshold float,
    match_count int,
    start_date timestamp default null  -- Optional date filter
)
RETURNS TABLE (
    id bigint,
    title text,
    summary text,
    sentiment text,
    content text,
    similarity float
)
LANGUAGE plpgsql
AS $$
BEGIN
    SET LOCAL statement_timeout = '10s';
    RETURN QUERY
    SELECT
        calls.id,
        calls.title,
        calls.summary,
        calls.sentiment,
        calls.transcript as content,
        1 - (calls.embedding <=> query_embedding) as similarity
    FROM calls
    WHERE 1 - (calls.embedding <=> query_embedding) > similarity_threshold
        AND (start_date IS NULL OR calls.created_at >= start_date)
    ORDER BY similarity DESC
    LIMIT match_count;
END;
$$;

-- Function to match calls with title
CREATE OR REPLACE FUNCTION match_calls_with_title(
  query_embedding vector(1536),
  query_text text,
  similarity_threshold float,
  match_count int
)
RETURNS TABLE (
  id bigint,
  title text,
  summary text,
  similarity float
)
LANGUAGE plpgsql
AS $$
BEGIN
  RETURN QUERY
  SELECT
    c.id,
    c.title,
    c.summary,
    (c.embedding <=> query_embedding) as similarity
  FROM calls c
  WHERE 
    (c.embedding <=> query_embedding) < (1 - similarity_threshold)
    or c.title ilike '%' || query_text || '%'
  ORDER BY 
    case 
      when c.title ilike '%' || query_text || '%' then 0  -- Prioritize title matches
      else 1
    end,
    similarity
  LIMIT match_count;
END;
$$;

-- Add a new function to match feature requests with date filtering
CREATE OR REPLACE FUNCTION match_recent_feature_requests(
    query_embedding vector(1536),
    match_threshold float,
    match_limit int,
    start_date timestamp
)
RETURNS TABLE (
    id bigint,
    call_id bigint,
    request text,
    context text,
    priority text,
    similarity float
)
LANGUAGE plpgsql
AS $$
BEGIN
    SET LOCAL statement_timeout = '10s';
    RETURN QUERY
    SELECT
        fr.id,
        fr.call_id,
        fr.request,
        fr.context,
        fr.priority,
        1 - (fr.embedding <=> query_embedding) as similarity
    FROM feature_requests fr
    JOIN calls c ON fr.call_id = c.id
    WHERE 
        c.created_at >= start_date  -- Add date filter
        AND 1 - (fr.embedding <=> query_embedding) > match_threshold
    ORDER BY similarity DESC
    LIMIT match_limit;
END;
$$;

-- Remove the call_summaries table and its index (if you've already created them)
DROP TABLE IF EXISTS call_summaries CASCADE;
DROP INDEX IF EXISTS idx_call_summaries_call_id;

-- Add better indexes for vector searches
ALTER TABLE calls 
SET (autovacuum_vacuum_scale_factor = 0.0);

ALTER TABLE calls 
SET (autovacuum_vacuum_threshold = 5000);

-- Same for feature_requests
ALTER TABLE feature_requests 
SET (autovacuum_vacuum_scale_factor = 0.0);

ALTER TABLE feature_requests 
SET (autovacuum_vacuum_threshold = 5000);

DROP INDEX IF EXISTS calls_embedding_idx;
CREATE INDEX calls_embedding_idx ON calls 
USING ivfflat (embedding vector_l2_ops)
WITH (lists = 1000);  -- More lists for better search performance

-- Remove clustering command since ivfflat doesn't support it
-- Just analyze the table to update statistics
ANALYZE calls;

-- Add a regular B-tree index on created_at for date filtering
CREATE INDEX idx_calls_created_at ON calls(start_time);
