from typing import List, Dict
from langchain_openai import ChatOpenAI
from langchain_openai import OpenAIEmbeddings
import json
from langchain.text_splitter import RecursiveCharacterTextSplitter

class CallProcessor:
    """Process and analyze call data"""
    def __init__(self, supabase_client):
        self.supabase = supabase_client
        self.llm = ChatOpenAI(temperature=0)
        self.embeddings = OpenAIEmbeddings()
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=12000,  # Characters, not tokens, but a safe size
            chunk_overlap=1000,
            length_function=len
        )

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
        # Split long transcripts into chunks
        chunks = self.text_splitter.split_text(transcript_text)
        
        # Analyze each chunk
        all_analyses = []
        for chunk in chunks:
            prompt = """Analyze this segment of a call transcript and provide the following in JSON format:
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

            Transcript segment:
            """ + chunk

            try:
                response = self.llm.invoke(prompt)
                analysis = json.loads(response.content)
                all_analyses.append(analysis)
            except Exception as e:
                print(f"Error analyzing chunk: {str(e)}")

        # Combine analyses
        combined_analysis = {
            "summary": " ".join(a["summary"] for a in all_analyses),
            "feature_requests": sum((a["feature_requests"] for a in all_analyses), []),
            "sentiment": self._combine_sentiments([a["sentiment"] for a in all_analyses])
        }
        
        return combined_analysis

    def _combine_sentiments(self, sentiments: List[str]) -> str:
        """Combine multiple sentiment analyses into one"""
        sentiment_counts = {
            "positive": sentiments.count("positive"),
            "negative": sentiments.count("negative"),
            "neutral": sentiments.count("neutral")
        }
        return max(sentiment_counts, key=sentiment_counts.get)

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