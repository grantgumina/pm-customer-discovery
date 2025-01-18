-- Enable vector extension for semantic search
CREATE EXTENSION IF NOT EXISTS vector;

-- Enum for interaction types
CREATE TYPE interaction_type AS ENUM ('discovery_call', 'demo', 'follow_up', 'implementation', 'support', 'other');

-- Table for storing customer/account information
CREATE TABLE accounts (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    industry TEXT,
    segment TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Table for storing call metadata
CREATE TABLE calls (
    id TEXT PRIMARY KEY,
    account_id TEXT REFERENCES accounts(id),
    title TEXT,
    interaction_type interaction_type,
    start_time TIMESTAMP WITH TIME ZONE,
    duration INTEGER,
    participants JSONB,
    summary TEXT,  -- AI-generated summary of the call
    key_topics JSONB,  -- AI-extracted key topics
    sentiment FLOAT,   -- AI-analyzed sentiment score
    metadata JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Table for storing transcript segments with embeddings
CREATE TABLE transcript_segments (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    call_id TEXT REFERENCES calls(id),
    account_id TEXT REFERENCES accounts(id),
    speaker TEXT,
    content TEXT,
    embedding vector(1536),  -- For OpenAI embeddings
    timestamp INTEGER,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Table for feature mentions and discussions
CREATE TABLE feature_mentions (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    call_id TEXT REFERENCES calls(id),
    account_id TEXT REFERENCES accounts(id),
    feature_name TEXT,
    mention_type TEXT,  -- e.g., 'request', 'feedback', 'interest', 'complaint'
    sentiment FLOAT,
    context TEXT,
    timestamp INTEGER,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Indexes for performance
CREATE INDEX idx_calls_account ON calls(account_id);
CREATE INDEX idx_calls_date ON calls(start_time);
CREATE INDEX idx_transcript_segments_call ON transcript_segments(call_id);
CREATE INDEX idx_feature_mentions_feature ON feature_mentions(feature_name);
CREATE INDEX idx_feature_mentions_account ON feature_mentions(account_id);

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