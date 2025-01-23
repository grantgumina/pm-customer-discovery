from call_searcher import CallSearcher
from dotenv import load_dotenv
import supabase
import os

# Load environment variables
load_dotenv()

supabase = supabase.create_client(
    os.environ.get("SUPABASE_URL"),
    os.environ.get("SUPABASE_KEY")
)

# Initialize your CallProcessor here
searcher = CallSearcher(supabase)

def test_feature_request_search():
    # Test different types of queries
    test_queries = [
        # "Gong",
        "What features did Gong want?",
        "Which customers want Slack integrations?"
        # "Request 5155"
    ]

    print("\nTesting feature request search...")
    print("-" * 50)

    for query in test_queries:
        print(f"\nSearching for: {query}")
        try:


            # call_results = searcher.search_summaries(query, threshold=0.5, limit=5)

            # if call_results:
            #     print(f"Found {len(call_results)} call results:")
            #     for r in call_results:
            #         print(f"Call ID: {r.get('id')}")
            #         print(f"Call Title: {r.get('title')}")

            results = searcher.search_feature_requests(
                query=query,
                threshold=0.8,  # Lower threshold to get more results
                limit=5
            )
            
            if results:
                print(f"Found {len(results)} results:")
                for r in results:
                    print("\nFeature Request:")
                    print(f"ID: {r.get('id')}")
                    print(f"Call ID: {r.get('call_id')}")
                    print(f"Title: {r.get('title')}")
                    print(f"Request: {r.get('request')}")
                    print(f"Context: {r.get('context')}")
                    print(f"Priority: {r.get('priority')}")
                    print(f"Similarity Score: {r.get('similarity'):.2f}")
            else:
                print("No results found")
                
        except Exception as e:
            print(f"Error during search: {str(e)}")
            
if __name__ == "__main__":
    test_feature_request_search()
