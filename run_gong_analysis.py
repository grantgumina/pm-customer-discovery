from dotenv import load_dotenv
import os
from gong_api import GongAPI
from datetime import datetime

def main():
    # Load environment variables from .env file
    load_dotenv()
    
    # Get credentials from environment variables
    access_key = os.environ.get("GONG_ACCESS_KEY")
    access_key_secret = os.environ.get("GONG_ACCESS_KEY_SECRET")
    
    if not access_key or not access_key_secret:
        raise ValueError("Missing Gong API credentials in .env file")
    
    # Initialize Gong API client
    gong = GongAPI(access_key, access_key_secret)

    from_date = datetime(2025, 1, 1)
    to_date = datetime(2025, 1, 17)
    calls = gong.get_calls(from_date, to_date)

    for call in calls:
        print("Adding the first call to supabase")
        gong.add_call_to_supabase(call)
        break

    # transcripts = gong.get_transcripts_from_calls(calls)
    
    # Process transcripts
    # print("\nProcessing transcripts...")
    
    # print("\nAll done! Your formatted transcripts are ready for LLM analysis.")

if __name__ == "__main__":
    main() 