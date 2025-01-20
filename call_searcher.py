from typing import List, Dict
from langchain_openai import ChatOpenAI
from langchain_openai import OpenAIEmbeddings
import json

class CallSearcher:
    """Search through all call data"""
    def __init__(self, supabase_client):
        self.supabase = supabase_client
        self.llm = ChatOpenAI(temperature=0)
        self.embeddings = OpenAIEmbeddings()

    def search_similar_calls(self, query: str, threshold: float = 0.7, limit: int = 5) -> List[Dict]:
        """Search for similar calls based on semantic similarity and title matching
        
        Args:
            query: Search query text
            threshold: Minimum similarity score (0-1) to include in results
            limit: Maximum number of results to return
            
        Returns:
            List of matching call dictionaries with similarity scores
        """
        # Create embedding for the search query
        query_embedding = self.embeddings.embed_query(query)
        
        # Perform similarity search using Postgres vector similarity and title matching
        result = self.supabase.rpc(
            'match_calls_with_title',  # You'll need to create this function
            {
                'query_embedding': query_embedding,
                'query_text': query,
                'similarity_threshold': threshold,
                'match_count': limit
            }
        ).execute()
        
        return result.data


    def search_transcript_segments(self, query: str, threshold: float = 0.9, limit: int = 5) -> List[Dict]:
        """Search for specific moments in transcripts that match the query"""
        query_embedding = self.embeddings.embed_query(query)
        
        result = self.supabase.rpc(
            'match_transcript_segments',
            {
                'query_embedding': query_embedding,
                'similarity_threshold': threshold,
                'max_matches': limit
            }
        ).execute()
        
        return result.data

    def search_summaries(self, query: str, threshold: float = 0.6, limit: int = 3) -> List[Dict]:
        """Search through call summaries using semantic search"""
        query_embedding = self.embeddings.embed_query(query)
        
        response = self.supabase.rpc(
            'match_summaries',  # You'll need to create this function
            {
                'query_embedding': query_embedding,
                'match_threshold': threshold,
                'match_limit': limit
            }
        ).execute()
        
        return response.data

    def search_feature_requests(self, query: str, threshold: float = 0.6, limit: int = 3) -> List[Dict]:
        """Search through feature requests using semantic search"""
        query_embedding = self.embeddings.embed_query(query)
        
        response = self.supabase.rpc(
            'match_feature_requests',  # You'll need to create this function
            {
                'query_embedding': query_embedding,
                'match_threshold': threshold,
                'match_limit': limit
            }
        ).execute()
        
        return response.data