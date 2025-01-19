import requests
import json
import os
import base64
from datetime import datetime, timedelta
from typing import List, Dict, Optional
import supabase
from langchain_openai import ChatOpenAI

class GongAPI:
    def __init__(self, access_key: str, access_key_secret: str):
        self.base_url = "https://us-4637.api.gong.io"
        self.access_key = access_key
        self.access_key_secret = access_key_secret
        self.supabase = supabase.create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY"))
        
    def _get_headers(self) -> Dict[str, str]:
        """Return headers needed for Gong API authentication"""
        base64_token = base64.b64encode(f'{self.access_key}:{self.access_key_secret}'.encode()).decode()
        return {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "Authorization": f"Basic {base64_token}",
            "Cache-Control": "no-cache"
        }
    
    def get_calls(self, from_date: Optional[datetime] = None, to_date: Optional[datetime] = None) -> List[Dict]:
        """
        Fetch all calls within the specified date range using cursor-based pagination
        If no dates specified, fetches last 30 days
        """
        if not from_date:
            from_date = datetime.now() - timedelta(days=30)
        if not to_date:
            to_date = datetime.now()

        all_calls = []
        cursor = None
        
        while True:
            
            if cursor:
                url = f"{self.base_url}/v2/calls?fromDateTime={from_date.strftime('%Y-%m-%dT%H:%M:%S.000Z')}&toDateTime={to_date.strftime('%Y-%m-%dT%H:%M:%S.000Z')}&cursor={cursor}"
            else:
                url = f"{self.base_url}/v2/calls?fromDateTime={from_date.strftime('%Y-%m-%dT%H:%M:%S.000Z')}&toDateTime={to_date.strftime('%Y-%m-%dT%H:%M:%S.000Z')}"
            
            response = requests.get(
                url,
                headers=self._get_headers(),
            )
            response.raise_for_status()
            
            data = response.json()
            calls = data.get("calls", [])
            all_calls.extend(calls)
            
            # Get the cursor for the next page
            cursor = data.get("records", {}).get("cursor")

            print(f"Cursor: {cursor}")

            # Tell the user our progress
            total_calls = data.get("records", {}).get("totalRecords")
            current_page_size = data.get("records", {}).get("currentPageSize")
            currentPageNumber = data.get("records", {}).get("currentPageSize")
            print(f"{current_page_size} of {total_calls} calls retrieved")
                         
            # If no cursor is returned, we've reached the end
            if not cursor:
                break
            
            print("Fetching next 100 records...")
        
        print(f"Retrieved a total of {len(all_calls)} calls")
        return all_calls

    def get_transcript(self, call_id: str) -> Dict:
        """Fetch the transcript for a specific call"""

        payload = {
            "filter": {
                "callIds": [call_id]
            }
        }

        response = requests.post(
            f"{self.base_url}/v2/calls/transcript",
            headers=self._get_headers(),
            json=payload,
        )
        response.raise_for_status()
        
        return response.json()

    def add_call_to_supabase(self, call):
        """Store calls in supabase"""
        try:
            if call.get("duration") > 10:
                transcript = self.get_transcript(call.get("id"))
                transcript_text = self.extract_transcript_text(transcript)

                # Call OpenAI for analysis
                llm = ChatOpenAI(temperature=0)
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
                    response = llm.invoke(prompt)
                    # Parse the response as JSON
                    analysis = json.loads(response.content)
                except json.JSONDecodeError as e:
                    print(f"Error parsing OpenAI response as JSON: {str(e)}")
                    analysis = {
                        "summary": "",
                        "feature_requests": [],
                        "sentiment": "unknown"
                    }
                except Exception as e:
                    print(f"Error getting summary from OpenAI: {str(e)}")
                    analysis = {
                        "summary": "",
                        "feature_requests": [],
                        "sentiment": "unknown"
                    }

                call_data = {
                    "call_id": call.get("id"),
                    "account_id": call.get("clientUniqueId", "unknown"),
                    "title": call.get("title"),
                    "summary": analysis.get("summary"),
                    "start_time": call.get("started"),
                    "sentiment": analysis.get("sentiment", "unknown"),
                    "duration": call.get("duration"),
                    "transcript": transcript_text
                }
                response = self.supabase.table("calls").insert(call_data).execute()
                # Get the inserted row's data from the response
                inserted_row = response.data[0]
                call_row_id = inserted_row['id']
                for feature_request in analysis["feature_requests"]:
                    print(f"Feature request: {feature_request}")
                    feature_request_data = {
                        "call_id": int(call_row_id),
                        "request": feature_request.get("request"),
                        "context": feature_request.get("context"),
                        "priority": feature_request.get("priority")
                    }

                    self.supabase.table("feature_requests").insert(feature_request_data).execute()

        except Exception as e:
            print(f"Error adding calls to supabase: {str(e)}")

    def get_transcripts_from_calls(self, calls: List[Dict], output_dir: str = "transcripts"):
        """Download all available transcripts and save them with call metadata"""
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)

        # Get all calls
        print(f"Found {len(calls)} calls to process")

        transcripts = []

        for call in calls:
            call_id = call["id"]
            try:
                # Get transcript
                print(f"Call ID: {call_id}")
                transcript = self.get_transcript(call_id)

                transcripts.append(transcript)
                
                # Combine call metadata with transcript
                data = {
                    "call_metadata": call,
                    "transcript": transcript
                }
                
                # Create filename using call date and account info
                call_date = datetime.fromisoformat(call["started"].replace("Z", "+00:00"))
                account_name = call.get("accountName", "unknown_account")
                filename = f"{call_date.strftime('%Y-%m-%d')}_{account_name}_{call_id}.json"
                filename = "".join(c for c in filename if c.isalnum() or c in "._- ")
                
                # Save to file
                filepath = os.path.join(output_dir, filename)
                with open(filepath, "w", encoding="utf-8") as f:
                    json.dump(data, f, ensure_ascii=False, indent=2)
                
                print(f"Successfully saved transcript: {filename}")                
            except Exception as e:
                print(f"Error processing call {call_id}: {str(e)}")
        
        return transcripts

    def extract_transcript_text(self, transcript_data):
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

    def extract_transcript_details(self, transcript_data):
        """Extract transcript with speaker and timing details"""
        segments = []
        
        for transcript in transcript_data.get("callTranscripts", []):
            for segment in transcript.get("transcript", []):
                speaker_id = segment.get("speakerId")
                topic = segment.get("topic")
                
                for sentence in segment.get("sentences", []):
                    segments.append({
                        "speaker_id": speaker_id,
                        "topic": topic,
                        "text": sentence.get("text", ""),
                        "start_time": sentence.get("start"),
                        "end_time": sentence.get("end")
                    })
        
        return segments