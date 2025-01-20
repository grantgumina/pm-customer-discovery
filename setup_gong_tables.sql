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

-- Function to match summaries
CREATE OR REPLACE FUNCTION match_summaries (
    query_embedding vector(1536),
    match_threshold float,
    match_limit int
)
RETURNS TABLE (
    id bigint,
    call_id text,
    content text,
    similarity float
)
LANGUAGE plpgsql
AS $$
BEGIN
    RETURN QUERY
    SELECT
        c.id,
        c.call_id,
        c.summary as content,
        1 - (c.embedding <=> query_embedding) as similarity
    FROM calls c
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

-- Add vector index for calls
CREATE INDEX IF NOT EXISTS calls_embedding_idx ON calls 
USING ivfflat (embedding vector_l2_ops)
WITH (lists = 100);

-- Add vector index for feature_requests
ALTER TABLE feature_requests 
ADD COLUMN IF NOT EXISTS embedding vector(1536);

CREATE INDEX IF NOT EXISTS feature_requests_embedding_idx ON feature_requests 
USING ivfflat (embedding vector_l2_ops)
WITH (lists = 100);

-- Create a function to search similar segments
CREATE OR REPLACE FUNCTION match_transcript_segments(
    query_embedding vector(1536),
    similarity_threshold float,
    max_matches int
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
    RETURN QUERY
    SELECT
        ts.content,
        ts.call_id,
        ts.speaker,
        ts.timestamp,
        1 - (ts.embedding <=> query_embedding) as similarity
    FROM transcript_segments ts
    WHERE 1 - (ts.embedding <=> query_embedding) > similarity_threshold
    ORDER BY ts.embedding <=> query_embedding
    LIMIT max_matches;
END;
$$;

-- Add this after your other functions
create or replace function match_calls (
  query_embedding vector(1536),
  similarity_threshold float,
  match_count int
)
returns table (
  id bigint,
  title text,
  summary text,
  sentiment text,
  content text,
  similarity float
)
language plpgsql
as $$
begin
  return query
  select
    calls.id,
    calls.title,
    calls.summary,
    calls.sentiment,
    calls.transcript as content,
    1 - (calls.embedding <=> query_embedding) as similarity
  from calls
  where 1 - (calls.embedding <=> query_embedding) > similarity_threshold
  order by similarity desc
  limit match_count;
end;
$$;

-- Remove the call_summaries table and its index (if you've already created them)
DROP TABLE IF EXISTS call_summaries CASCADE;
DROP INDEX IF EXISTS idx_call_summaries_call_id;