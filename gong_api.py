import requests
import json
import os
import base64
from datetime import datetime, timedelta
from typing import List, Dict, Optional
import supabase
from langchain_community.chat_models import ChatOpenAI

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
            # Don't add short calls which won't be useful
            if call.get("duration") < 10:

                account_data = {
                    "account_id": call["clientUniqueId"],
                }
                self.supabase.table("accounts").insert(account_data).execute()

                # TODO - make a call to OpenAI to get the following:
                # - Summary of the call
                # - Any feature requests
                # Get transcript for this call
                transcript = self.get_transcript(call.get("id"))
                
                # Extract transcript text
                transcript_content = ""
                if transcript.get("callTranscripts"):
                    for sentence in transcript.get("transcript").get("sentences"):
                        if sentence.get("text"):
                            transcript_content += sentence.get("text") + " "
                
                print(transcript_content)

                return

                # Call OpenAI for analysis
                llm = ChatOpenAI(temperature=0)
                prompt = f"""Please analyze this call transcript and provide:
                1. A brief summary of the key points discussed
                2. Any feature requests or product feedback mentioned
                
                Transcript:
                {transcript_content}
                """
                
                try:
                    response = llm(prompt)
                    summary = response.content
                except Exception as e:
                    print(f"Error getting summary from OpenAI: {str(e)}")
                    summary = ""

                

                call_data = {
                    "call_id": call["id"],
                    "account_id": call["clientUniqueId"],
                    "start_time": call["started"],
                    "duration": call["duration"],

                }
                self.supabase.table("calls").insert(call_data).execute()

        except Exception as e:
            print(f"Error adding calls to supabase: {str(e)}")

        return

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