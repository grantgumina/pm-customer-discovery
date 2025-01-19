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

    # Example search for transcript segments
    segments = processor.search_transcript_segments(query="pricing", threshold=0.9, limit=3)
    for segment in segments:
        print(f"\nFrom call: {segment['call_id']}")
        print(f"Speaker: {segment['speaker']} said:")
        print(f"{segment['content']}")
        print(f"Similarity: {segment['similarity']}")

    # # Example search for similar calls
    # results = processor.search_similar_calls("customers requesting Slack integration")
    # for result in results:
    #     print(f"\nCall ID: {result['id']}")
    #     print(f"Summary: {result['summary']}")
    #     print(f"Similarity: {result['similarity']}")

if __name__ == "__main__":
    main() 