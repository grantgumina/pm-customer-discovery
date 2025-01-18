from langchain.chat_models import ChatOpenAI
from langchain.chains import ConversationalRetrievalChain
from langchain.memory import ConversationBufferMemory
from langchain.vectorstores.supabase import SupabaseVectorStore
from langchain.embeddings import OpenAIEmbeddings
from supabase.client import create_client
import os

def create_chat_interface():
    # Initialize Supabase client
    supabase_url = os.environ.get("SUPABASE_URL")
    supabase_key = os.environ.get("SUPABASE_SERVICE_KEY")
    supabase = create_client(supabase_url, supabase_key)
    
    # Initialize vector store
    embeddings = OpenAIEmbeddings()
    vectorstore = SupabaseVectorStore(
        client=supabase,
        embedding=embeddings,
        table_name="call_transcripts",
        query_name="match_transcripts"
    )
    
    # Initialize LLM
    llm = ChatOpenAI(temperature=0)
    
    # Create memory
    memory = ConversationBufferMemory(
        memory_key="chat_history",
        return_messages=True
    )
    
    # Create chain
    qa_chain = ConversationalRetrievalChain.from_llm(
        llm=llm,
        retriever=vectorstore.as_retriever(),
        memory=memory,
        return_source_documents=True
    )
    
    return qa_chain

# Rest of chat() function remains the same...