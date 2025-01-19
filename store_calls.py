from dotenv import load_dotenv
import os
from datetime import datetime
from gong_api import GongAPI
from call_processor import CallProcessor
from supabase import create_client

def main():
    # Load environment variables
    load_dotenv()
    
    # Initialize clients
    gong = GongAPI(
        os.environ.get("GONG_ACCESS_KEY"),
        os.environ.get("GONG_ACCESS_KEY_SECRET")
    )
    
    supabase = create_client(
        os.environ.get("SUPABASE_URL"),
        os.environ.get("SUPABASE_KEY")
    )
    
    processor = CallProcessor(supabase)

    # Get calls from Gong
    from_date = datetime(2025, 1, 1)
    to_date = datetime(2025, 1, 17)
    calls = gong.get_calls(from_date, to_date)

    # Process each call
    for call in calls:
        if call.get("duration", 0) > 10:  # Skip short calls
            # Get transcript
            transcript_data = gong.get_transcript(call["id"])
            
            # Extract and analyze
            transcript_text = processor.extract_transcript_text(transcript_data)

            print(transcript_text)

            analysis = processor.analyze_transcript(transcript_text)
            
            # Store in database
            processor.store_call_data(call, transcript_text, transcript_data, analysis)
            break #only process one call for now

if __name__ == "__main__":
    main() 