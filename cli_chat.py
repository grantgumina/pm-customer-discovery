from typing import List, Dict
import typer
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.prompt import Prompt
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
from supabase import create_client
from call_processor import CallProcessor
from dotenv import load_dotenv
import os

class ChatCLI:
    def __init__(self, call_processor):
        self.call_processor = call_processor
        self.console = Console()
        self.chat = ChatOpenAI(temperature=0.7)
        self.conversation_history = [
            SystemMessage(content="""You are a helpful AI assistant with access to call transcript data. 
            When answering questions, use the context from call transcripts when provided, but you can also 
            answer general questions. Always be clear about what information comes from calls versus your general knowledge.""")
        ]

    def search_calls(self, query: str) -> List[Dict]:
        """Search call transcripts, summaries, and feature requests and return relevant segments"""
        results = {
            'transcripts': self.call_processor.search_transcript_segments(query, threshold=0.6, limit=5),
            'summaries': self.call_processor.search_summaries(query, threshold=0.6, limit=5),
            'features': self.call_processor.search_feature_requests(query, threshold=0.6, limit=5)
        }
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
                context += f"Call {call_id} - {title}:\n{content}\n\n"
        
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

    def chat_loop(self):
        """Main chat loop"""
        self.console.print(Panel("Welcome to Call Explorer! Ask me anything about your calls.", 
                               title="🤖 Call Explorer", 
                               border_style="blue"))
        
        while True:
            try:
                # Get user input
                user_input = Prompt.ask("\n[bold blue]You")
                
                if user_input.lower() in ['quit', 'exit', 'bye']:
                    self.console.print("\n[bold green]Goodbye! 👋")
                    break

                # Search for relevant call segments
                segments = self.search_calls(user_input)
                context = self.format_context(segments)

                # Add context and user query to conversation
                self.conversation_history.append(HumanMessage(
                    content=f"Context from calls:\n{context}\n\nUser question: {user_input}"
                ))

                # Get AI response
                response = self.chat.invoke(self.conversation_history)
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
    
    call_processor = CallProcessor(supabase)  # Add your necessary init parameters
    
    chat_cli = ChatCLI(call_processor)
    chat_cli.chat_loop()

if __name__ == "__main__":
    typer.run(main) 