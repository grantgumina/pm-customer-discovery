from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain.embeddings import OpenAIEmbeddings
from langchain.vectorstores.supabase import SupabaseVectorStore
from supabase.client import create_client
import json
import glob
import os

def process_transcripts():
    # Initialize Supabase client
    supabase_url = os.environ.get("SUPABASE_URL")
    supabase_key = os.environ.get("SUPABASE_SERVICE_KEY")
    supabase = create_client(supabase_url, supabase_key)
    
    # Load all transcript files
    transcripts = []
    for file in glob.glob("transcripts/*.json"):
        with open(file) as f:
            data = json.load(f)
            metadata = {
                "call_id": data["call_metadata"]["id"],
                "date": data["call_metadata"]["started"],
                "account": data["call_metadata"]["accountName"]
            }
            transcript_text = " ".join([
                turn["text"] for turn in data["transcript"]["transcript"]
            ])
            transcripts.append({"text": transcript_text, "metadata": metadata})
    
    # Split into chunks
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=1000,
        chunk_overlap=100
    )
    
    # Create documents with metadata
    documents = []
    for t in transcripts:
        chunks = text_splitter.split_text(t["text"])
        for chunk in chunks:
            documents.append({
                "text": chunk,
                "metadata": t["metadata"]
            })
    
    # Initialize vector store
    embeddings = OpenAIEmbeddings()
    vectorstore = SupabaseVectorStore(
        client=supabase,
        embedding=embeddings,
        table_name="call_transcripts",
        query_name="match_transcripts"
    )
    
    # Add documents to vector store
    vectorstore.add_documents(documents)