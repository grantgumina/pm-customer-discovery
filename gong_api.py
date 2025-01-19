import requests
import base64
from datetime import datetime, timedelta
from typing import List, Dict, Optional

class GongAPI:
    """Pure Gong API interactions"""
    def __init__(self, access_key: str, access_key_secret: str):
        self.base_url = "https://us-4637.api.gong.io"
        self.access_key = access_key
        self.access_key_secret = access_key_secret
        
    def _get_headers(self) -> Dict[str, str]:
        base64_token = base64.b64encode(f'{self.access_key}:{self.access_key_secret}'.encode()).decode()
        return {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "Authorization": f"Basic {base64_token}",
            "Cache-Control": "no-cache"
        }
    
    def get_calls(self, from_date: Optional[datetime] = None, to_date: Optional[datetime] = None) -> List[Dict]:
        """Fetch all calls within the specified date range"""
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