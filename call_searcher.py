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

    def search_transcript_segments(self, query: str, threshold: float = 0.5, limit: int = 5, use_date_filter: bool = None) -> List[Dict]:
        """Search transcript segments in batches with optional date filtering"""
        query_embedding = self.embeddings.embed_query(query)
        
        # Use instance default if not specified
        use_date_filter = self.default_date_filter if use_date_filter is None else use_date_filter
        
        # Only apply date filter if enabled
        start_date = datetime.now() - timedelta(days=90) if use_date_filter else None
        
        results = []
        batch_size = 1  # Reduced batch size
        retries = 2     # Add retries

        for offset in range(0, limit, batch_size):
            retry_count = 0
            while retry_count < retries:
                try:
                    params = {
                        'query_embedding': query_embedding,
                        'similarity_threshold': threshold + (0.1 * retry_count),  # Increase threshold on retries
                        'max_matches': batch_size
                    }
                    if start_date:
                        params['start_date'] = start_date.isoformat()
                        
                    batch = self.supabase.rpc(
                        'match_transcript_segments',
                        params
                    ).execute()
                    
                    if batch.data:
                        results.extend(batch.data)
                        break  # Success, exit retry loop
                    
                    if len(batch.data) < batch_size:
                        break
                        
                except Exception as e:
                    print(f"Error in batch {offset} (attempt {retry_count + 1}): {str(e)}")
                    retry_count += 1
                    if retry_count == retries:
                        print("Skipping batch after all retries failed")
                    continue

        results.sort(key=lambda x: x.get('similarity', 0), reverse=True)
        return results[:limit]

    def search_summaries(self, query: str, threshold: float = 0.5, limit: int = 5) -> List[Dict]:
        """Search call summaries"""
        query_embedding = self.embeddings.embed_query(query)
        
        try:
            result = self.supabase.rpc(
                'match_summaries',
                {
                    'query_embedding': query_embedding,
                    'match_threshold': threshold,
                    'match_limit': limit  # Use the limit directly
                }
            ).execute()
            
            return result.data if result.data else []
                
        except Exception as e:
            print(f"Error in summaries search: {str(e)}")
            return []

    def search_feature_requests_text(self, query: str, threshold: float = 0.5, limit: int = 5) -> List[Dict]:
        """Search feature requests with text search"""
        try:
            result = self.supabase.rpc(
                'match_feature_requests_text',
                {
                    'query_text': query,
                    'match_limit': limit
                }
            ).execute()
            return result.data if result.data else []
        except Exception as e:
            print(f"Error in feature requests text search: {str(e)}")
            return []

    def search_feature_requests(self, query: str, threshold: float = 0.5, limit: int = 5) -> List[Dict]:
        """Search feature requests with better error handling"""
        query_embedding = self.embeddings.embed_query(query)
        
        try:
            result = self.supabase.rpc(
                'match_feature_requests',
                {
                    'query_embedding': query_embedding,
                    'match_threshold': threshold,
                    'match_limit': limit
                }
            ).execute()
            
            return result.data if result.data else []
                
        except Exception as e:
            if "timeout" in str(e).lower():
                print("Search timed out, trying with higher threshold...")
                # Try again with a higher threshold
                try:
                    result = self.supabase.rpc(
                        'match_feature_requests',
                        {
                            'query_embedding': query_embedding,
                            'match_threshold': 0.8,  # Much higher threshold
                            'match_limit': limit
                        }
                    ).execute()
                    return result.data if result.data else []
                except:
                    pass
            print(f"Error in feature requests search: {str(e)}")
            return []