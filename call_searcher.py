from typing import List, Dict
from langchain_openai import ChatOpenAI
from langchain_openai import OpenAIEmbeddings
import json
from datetime import datetime, timedelta

class CallSearcher:
    """Search through all call data"""
    def __init__(self, supabase_client):
        self.supabase = supabase_client
        self.llm = ChatOpenAI(temperature=0)
        self.embeddings = OpenAIEmbeddings()
        self.default_date_filter = True  # Add this flag

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


    def search_transcript_segments(self, query: str, threshold: float = 0.5, limit: int = 5, use_date_filter: bool = None) -> List[Dict]:
        """Search transcript segments in batches with optional date filtering"""
        query_embedding = self.embeddings.embed_query(query)
        
        # Use instance default if not specified
        use_date_filter = self.default_date_filter if use_date_filter is None else use_date_filter
        
        # Only apply date filter if enabled
        start_date = datetime.now() - timedelta(days=90) if use_date_filter else None
        
        results = []
        batch_size = 2

        for offset in range(0, limit, batch_size):
            try:
                params = {
                    'query_embedding': query_embedding,
                    'similarity_threshold': threshold,
                    'max_matches': batch_size
                }
                # Only add start_date if it exists
                if start_date:
                    params['start_date'] = start_date.isoformat()
                    
                batch = self.supabase.rpc(
                    'match_transcript_segments',
                    params
                ).execute()
                
                if batch.data:
                    results.extend(batch.data)
                
                if len(batch.data) < batch_size:
                    break
                    
            except Exception as e:
                print(f"Error in transcript segment batch at {offset}: {str(e)}")
                continue

        results.sort(key=lambda x: x.get('similarity', 0), reverse=True)
        return results[:limit]

    def search_summaries(self, query: str, threshold: float = 0.5, limit: int = 5) -> List[Dict]:
        """Search call summaries in batches"""
        query_embedding = self.embeddings.embed_query(query)
        results = []
        batch_size = 2

        for offset in range(0, limit, batch_size):
            try:
                batch = self.supabase.rpc(
                    'match_summaries',
                    {
                        'query_embedding': query_embedding,
                        'match_threshold': threshold,
                        'match_limit': batch_size
                    }
                ).execute()
                
                if batch.data:
                    results.extend(batch.data)
                
                if len(batch.data) < batch_size:
                    break
                    
            except Exception as e:
                print(f"Error in summaries batch at {offset}: {str(e)}")
                continue

        results.sort(key=lambda x: x.get('similarity', 0), reverse=True)
        return results[:limit]

    def search_feature_requests(self, query: str, threshold: float = 0.5, limit: int = 5) -> List[Dict]:
        """Search feature requests with date filtering"""
        query_embedding = self.embeddings.embed_query(query)
        
        # Add date filtering to reduce search space
        three_months_ago = datetime.now() - timedelta(days=90)
        
        results = []
        batch_size = 2
        
        for offset in range(0, limit, batch_size):
            try:
                batch = self.supabase.rpc(
                    'match_recent_feature_requests',  # New function with date filter
                    {
                        'query_embedding': query_embedding,
                        'match_threshold': threshold,
                        'match_limit': batch_size,
                        'start_date': three_months_ago.isoformat()
                    }
                ).execute()
                
                if batch.data:
                    results.extend(batch.data)
                
                if len(batch.data) < batch_size:
                    break
                    
            except Exception as e:
                print(f"Error in batch starting at {offset}: {str(e)}")
                continue
        
        # Sort by similarity and limit to requested amount
        results.sort(key=lambda x: x.get('similarity', 0), reverse=True)
        return results[:limit]