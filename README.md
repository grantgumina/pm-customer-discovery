# Gong Call Explorer

An intelligent assistant for exploring and analyzing Gong call transcripts using vector similarity search and LLMs.

## Overview

Gong Call Explorer processes Gong call transcripts and allows natural language querying of call content, summaries, and feature requests. It uses OpenAI embeddings for semantic search and ChatGPT for natural language understanding and response generation.

## Project Files

- `cli_chat.py` - Main CLI interface for interacting with the assistant
- `call_searcher.py` - Handles searching through call data using vector similarity
- `call_processor.py` - Processes and stores call data with embeddings
- `gong_api.py` - Interface for retrieving call data from Gong
- `setup_gong_tables.sql` - Database schema and search functions
- `store_calls.py` - Script for batch importing calls
- `test_script.py` - Tests for core functionality
- `requirements.txt` - Python dependencies

## Setup

1. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

2. Set up environment variables:
   ```bash
   OPENAI_API_KEY=your_key
   SUPABASE_URL=your_url
   SUPABASE_KEY=your_key
   GONG_API_KEY=your_key
   ```

3. Initialize the database:
   ```bash
   # Connect to your Supabase project's database URL
   # You can find this in your Supabase project settings
   psql -h db.your-project-ref.supabase.co -U postgres -d postgres -f setup_gong_tables.sql
   
   # Or using the connection string format:
   # psql postgresql://postgres:[YOUR-PASSWORD]@db.your-project-ref.supabase.co:5432/postgres -f setup_gong_tables.sql
   ```

   Note: You'll need to:
   1. Enable the pgvector extension in your Supabase project
   2. Have your database password ready
   3. Allow connections from your IP address in Supabase dashboard

## Usage

Process calls:
```bash
python store_calls.py
```
Note: be sure to specify a date range in the script.

Run the CLI:
```bash
python cli_chat.py
```
Commands:
- `/all` - Search all time periods
- `/recent` - Search recent calls only (default)
- `/quit` - Exit the program

## Requirements

- Python 3.8+
- PostgreSQL with pgvector
- OpenAI API access
- Supabase project
- Gong API access

## Architecture

1. **Search Flow**
```mermaid
graph LR
    A[User Query] --> B[CallSearcher]
    B --> C[OpenAI Embeddings]
    C --> D[(Vector Search)]
    D --> E[Search Results]
    E --> F[Context Window]
    F --> G[ChatGPT]
    G --> H[User Response]
```

2. **Data Storage**
   - Call transcripts are chunked into segments
   - OpenAI embeddings are generated for each chunk
   - Embeddings are stored in Supabase with pgvector

3. **Search Process**
   - User query is converted to embedding
   - Vector similarity search finds relevant content
   - Results are combined from multiple tables
   - Context window is constructed for LLM

3. **Response Generation**
   - Context and query sent to ChatGPT
   - Response formatted with citations
   - Sources tracked and displayed

4. **Performance Optimization**
    - Vector search uses IVFFlat indexes with optimized list sizes
    - Batched searching with retries and timeouts
    - Date-based filtering to reduce search space
    - Composite indexes for common query patterns
    - Optimized table statistics and vacuum settings

### Components

1. **Database (Supabase)**
   - `calls` table: Stores call metadata, summaries, and embeddings
   - `transcript_segments` table: Contains chunked transcript content with embeddings
   - `feature_requests` table: Stores extracted feature requests with embeddings
   - Uses pgvector for similarity search
   - Custom SQL functions for optimized vector search

2. **Call Processor**
   ```python
   class CallProcessor:
       def store_call_data():  # Processes raw call data
       def store_transcript_segments():  # Chunks and embeds transcripts
       def analyze_transcript():  # Extracts insights using LLM
   ```

3. **Call Searcher**
   ```python
   class CallSearcher:
       def search_summaries():  # Searches call summaries
       def search_transcript_segments():  # Searches transcript chunks
       def search_feature_requests():  # Searches feature requests
   ```

4. **Chat CLI**
   ```python
   class ChatCLI:
       def search_calls():  # Combines different search types
       def format_context():  # Prepares context for LLM
       def format_response():  # Formats LLM response with citations
   ```

### Context Window Construction

1. **Search Results Gathering**
   ```python
   results = {
       'summaries': search_summaries(query),
       'transcripts': search_transcript_segments(query),
       'features': search_feature_requests(query)
   }
   ```

2. **Context Formatting**
   ```python
   context = """
   📝 Related call summaries:
   Call ID: {call_id}
   Title: {title}
   Summary: {content}

   ✨ Related feature requests:
   Request {id}:
   Feature: {request}
   Customer Quote: "{context}"
   Priority: {priority}
   """
   ```

3. **LLM Prompt Construction**
   ```python
   prompt = f"""
   Context from calls:
   {context}

   User question: {user_input}
   """
   ```

### Response Generation

1. The LLM receives:
   - System message defining its role and response format
   - Context from relevant calls
   - User's question

2. The LLM generates a response incorporating:
   - Information from the provided context
   - Clear attribution to source calls
   - Formatted bullet points for lists

3. Response Processing:
   - Citations are added for referenced calls
   - Markdown formatting is applied
   - Response is displayed in the CLI
