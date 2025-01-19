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
    call_id TEXT,
    account_id TEXT,
    similarity float
)
LANGUAGE plpgsql
AS $$
BEGIN
    RETURN QUERY
    SELECT
        ts.content,
        ts.call_id,
        ts.account_id,
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
    1 - (calls.embedding <=> query_embedding) as similarity
  from calls
  where 1 - (calls.embedding <=> query_embedding) > similarity_threshold
  order by similarity desc
  limit match_count;
end;
$$;