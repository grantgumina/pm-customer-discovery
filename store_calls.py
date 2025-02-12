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
    from_date = datetime(2024, 5, 1)
    to_date = datetime(2024, 10, 1)
    calls = gong.get_calls(from_date, to_date)

    # Process each call
    for call in calls:
        print(f"Call\n{call}")
        if call.get("duration", 0) > 10:  # Skip short calls
            # Get transcript
            transcript_data = gong.get_transcript(call["id"])
            
            # Extract and analyze
            transcript_text = processor.extracxt_transcript_text(transcript_data)

            analysis = processor.analyze_transcript(transcript_text)
            
            # Store in database
            processor.store_call_data(call, transcript_text, transcript_data, analysis)

            print(f"Processed call {call['id']}")

if __name__ == "__main__":
    main() 