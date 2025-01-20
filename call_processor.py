from typing import List, Dict
from langchain_openai import ChatOpenAI
from langchain_openai import OpenAIEmbeddings
import json

class CallProcessor:
    """Process and analyze call data"""
    def __init__(self, supabase_client):
        self.supabase = supabase_client
        self.llm = ChatOpenAI(temperature=0)
        self.embeddings = OpenAIEmbeddings()

    def extract_transcript_text(self, transcript_data: Dict) -> str:
        """Extract all sentences from a transcript with speaker identification"""
        transcript_lines = []
        
        # Get the array of transcripts
        transcripts = transcript_data.get("callTranscripts", [])
        
        for transcript in transcripts:
            # Get the transcript object which contains the segments
            transcript_obj = transcript.get("transcript", [])
            
            # Iterate through each speaker segment
            for segment in transcript_obj:
                speaker_id = segment.get("speakerId")
                sentences = segment.get("sentences", [])
                
                # Combine all sentences for this speaker's turn
                speaker_text = " ".join(
                    sentence.get("text", "") 
                    for sentence in sentences 
                    if sentence.get("text")
                )
                
                if speaker_text:
                    transcript_lines.append(f"Speaker {speaker_id}: {speaker_text}")
        
        # Join all lines with newlines
        return "\n".join(transcript_lines)

    def analyze_transcript(self, transcript_text: str) -> Dict:
        """Get OpenAI analysis of transcript"""
        prompt = """Analyze this call transcript and provide the following in JSON format:
        {
            "summary": "Brief summary of key points discussed",
            "feature_requests": [
                {
                    "request": "Description of feature request",
                    "context": "The exact conversation sentences said around this request",
                    "priority": "High/Medium/Low based on customer emphasis"
                }
            ],
            "sentiment": "Overall sentiment about the product (positive, negative, neutral)"
        }

        Transcript:
        """ + transcript_text

        try:
            response = self.llm.invoke(prompt)
            return json.loads(response.content)
        except Exception as e:
            print(f"Error analyzing transcript: {str(e)}")
            return {
                "summary": "",
                "feature_requests": [],
                "sentiment": "unknown"
            }

    def store_call_data(self, call: Dict, transcript_text: str, transcript_data: Dict, analysis: Dict) -> int:
        """Store call data and analysis in Supabase"""
        # Create embeddings for the call summary
        summary_embedding = self.embeddings.embed_query(analysis["summary"])
        
        # Prepare call data
        call_data = {
            "call_id": call["id"],
            "title": call.get("title", ""),
            "duration": call.get("duration", 0),
            "start_time": call.get("started", ""),
            "summary": analysis["summary"],
            "sentiment": analysis["sentiment"],
            "transcript": transcript_text,
            "embedding": summary_embedding
        }

        # Insert into calls table
        result = self.supabase.table("calls").insert(call_data).execute()
        
        if not result.data:
            raise Exception("Failed to insert call data")
            
        call_row_id = result.data[0]["id"]
        
        # Store transcript segments
        self.store_transcript_segments(call_row_id, transcript_data)
        
        # Store feature requests
        for feature_request in analysis.get("feature_requests", []):
            # Create embedding for the feature request
            request_text = f"{feature_request.get('request')} {feature_request.get('context')}"
            feature_embedding = self.embeddings.embed_query(request_text)
            
            feature_data = {
                "call_id": call_row_id,
                "request": feature_request.get("request"),
                "context": feature_request.get("context"),
                "priority": feature_request.get("priority"),
                "embedding": feature_embedding
            }
            
            # Insert into feature_requests table
            self.supabase.table("feature_requests").insert(feature_data).execute()
            
        return call_row_id

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

    def store_transcript_segments(self, call_id: int, transcript_data: Dict):
        """Store individual segments of the transcript with embeddings for granular search"""
        segments = []
        
        # Get the array of transcripts
        for transcript in transcript_data.get("callTranscripts", []):
            # Get each speaker's segments
            for segment in transcript.get("transcript", []):
                speaker_id = segment.get("speakerId")
                sentences = segment.get("sentences", [])
                
                # Group sentences into meaningful chunks (e.g., by speaker turn)
                segment_text = " ".join(
                    sentence.get("text", "") 
                    for sentence in sentences 
                    if sentence.get("text")
                )
                
                if segment_text:
                    # Get timestamp from first sentence
                    timestamp = sentences[0].get("start") if sentences else None
                    
                    segments.append({
                        "call_id": call_id,
                        "speaker": speaker_id,
                        "content": segment_text,
                        "timestamp": timestamp,
                        "embedding": self.embeddings.embed_query(segment_text)
                    })
        
        # Batch insert all segments
        if segments:
            self.supabase.table("transcript_segments").insert(segments).execute()

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