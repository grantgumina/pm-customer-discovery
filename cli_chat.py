from typing import List, Dict
import typer
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.prompt import Prompt
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
from supabase import create_client
from call_searcher import CallSearcher
from dotenv import load_dotenv
import os

class ChatCLI:
    def __init__(self, call_searcher):
        self.call_searcher = call_searcher
        self.console = Console()
        self.chat = ChatOpenAI(temperature=1)
        self.conversation_history = [
            SystemMessage(content="""You are a helpful AI assistant with access to call summaries, transcripts, and feature request data. 
            When answering questions, use the context provided. Always be clear about what information comes from calls versus your general knowledge.
            
            IMPORTANT: When users ask about specific companies or customers:
            1. First check if there are any calls with titles that contain the company name. If you find matching titles, mention them explicitly: "I found X calls involving [company]...".
            2. Second, check if there are any calls whose IDs match the ID provided. If you find matching IDs, mention them explicitly: "I found X calls involving [company]...".
            3. Then provide relevant details from the call summary
            4. If you don't find any matching titles or summaries, say so explicitly

            When answering questions where you list out information, please format the output
            as bullet points so it's easy to read.
            """)
        ]

    def search_calls(self, query: str, use_date_filter: bool = None) -> List[Dict]:
        """Search call transcripts, summaries, and feature requests"""
        results = {
            'transcripts': [],
            'summaries': self.call_searcher.search_summaries(
                query, 
                threshold=0.8,
                limit=10,
            ),
            # 'features': [],
            'features': self.call_searcher.search_feature_requests(
                query, 
                threshold=0.8,
                limit=10,
            )
        }

        # # Another option would be to search for summaries first, then search for feature requests for the found calls
        # # Get call IDs from summaries
        # summary_call_ids = [summary.get('call_id') for summary in results['summaries'] if summary.get('call_id')]

        # # Search for feature requests for each call ID
        # for call_id in summary_call_ids:
        #     feature_results = self.call_searcher.search_feature_requests(
        #         call_id,
        #         threshold=0.3,  # Lower threshold since we want exact matches
        #         limit=5
        #     )
        #     # Add any new feature requests found
        #     results['features'].extend([
        #         fr for fr in feature_results 
        #         if fr not in results['features']  # Avoid duplicates
        #     ])
        return results

    def format_context(self, results: Dict[str, List[Dict]]) -> str:
        """Format search results into a readable context string"""
        if not any(results.values()):
            return "No relevant information found."
        
        context = ""
        
        if results['summaries']:
            context += "📝 Related call summaries:\n\n"
            for summary in results['summaries']:
                call_id = summary.get('call_id', 'Unknown')
                title = summary.get('title', 'No title available')
                content = summary.get('content', summary.get('summary', 'No content available'))
                context += f"Call ID: {call_id}\nTitle: {title}\nSummary: {content}\n\n"
        
        if results['transcripts']:
            context += "🎯 Relevant transcript segments:\n\n"
            for segment in results['transcripts']:
                call_id = segment.get('call_id', 'Unknown')
                title = segment.get('title', 'No title available')
                content = segment.get('content', segment.get('transcript', 'No content available'))
                context += f"Call {call_id} - {title}:\n{content}\n\n"
            
        if results['features']:
            context += "✨ Related feature requests:\n\n"
            for feature in results['features']:
                feature_id = feature.get('id', 'Unknown')
                request = feature.get('request', 'No request available')
                customer_context = feature.get('context', 'No context available')
                priority = feature.get('priority', 'Unknown priority')
                
                context += f"Request {feature_id}:\n"
                context += f"Feature: {request}\n"
                context += f"Customer Quote: \"{customer_context}\"\n"
                context += f"Priority: {priority}\n\n"
            
        return context.strip()

    def format_response(self, response_content: str, results: Dict[str, List[Dict]]) -> str:
        """Add citations only for sources actually referenced in the response"""
        if "Sources:" not in response_content:
            sources = set()  # Use set to avoid duplicates
            
            # Collect all possible call IDs and titles
            all_sources = {}  # Dictionary of call_id -> title
            for result_type in ['summaries', 'transcripts', 'features']:
                for item in results.get(result_type, []):
                    call_id = item.get('call_id', 'Unknown')
                    title = item.get('title', 'No title available')
                    all_sources[call_id] = title
            
            # Only include sources that are actually mentioned in the response
            for call_id, title in all_sources.items():
                # Check if the call_id or company name from title appears in the response
                if (str(call_id) in response_content or 
                    any(company in response_content for company in title.split('|'))):
                    sources.add(f"- Call {call_id} - {title}")
            
            if sources:
                response_content += "\n\nSources:\n" + "\n".join(sorted(sources))
            
        return response_content

    def chat_loop(self):
        """Main chat loop"""
        self.console.print(Panel(
            "Welcome to Call Explorer! Ask me anything about your calls.\n"
            "Commands:\n"
            "- /all - Search all time\n"
            "- /recent - Search recent calls only (default)\n"
            "- /quit - Exit the program", 
            title="🤖 Call Explorer", 
            border_style="blue"
        ))
        
        while True:
            try:
                user_input = Prompt.ask("\n[bold blue]You")
                
                if user_input.lower() in ['quit', 'exit', 'bye', '/quit']:
                    self.console.print("\n[bold green]Goodbye! 👋")
                    break

                # Handle commands
                if user_input == '/all':
                    self.call_searcher.default_date_filter = False
                    self.console.print("[yellow]Searching all time periods")
                    continue
                    
                if user_input == '/recent':
                    self.call_searcher.default_date_filter = True
                    self.console.print("[yellow]Searching recent calls only")
                    continue

                # Search for relevant call segments and create context for AI
                segments = self.search_calls(user_input)
                context = self.format_context(segments)

                # Combine found context and user's question to conversation
                self.conversation_history.append(HumanMessage(
                    content=f"Context from calls:\n{context}\n\nUser question: {user_input}"
                ))

                # Send conversation to AI for a response
                response = self.chat.invoke(self.conversation_history)
                
                # Add citations if needed
                response.content = self.format_response(response.content, segments)

                self.conversation_history.append(response)

                # Display response with markdown formatting
                self.console.print("\n[bold green]Assistant")
                self.console.print(Panel(Markdown(response.content)))

            except KeyboardInterrupt:
                self.console.print("\n[bold green]Goodbye! 👋")
                break
            except Exception as e:
                self.console.print(f"[bold red]Error: {str(e)}")

def main():

    # Load environment variables from .env file
    load_dotenv()

    supabase = create_client(
        os.environ.get("SUPABASE_URL"),
        os.environ.get("SUPABASE_KEY")
    )

    # Initialize your CallProcessor here
    
    call_searcher = CallSearcher(supabase)
    
    chat_cli = ChatCLI(call_searcher)
    chat_cli.chat_loop()

if __name__ == "__main__":
    typer.run(main) 