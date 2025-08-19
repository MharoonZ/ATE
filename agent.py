import streamlit as st
import gc
from langchain_openai import ChatOpenAI
from langchain.agents import AgentExecutor, create_openai_tools_agent
from langchain import hub
from langchain_core.runnables import ConfigurableFieldSpec
from langchain_core.runnables.history import RunnableWithMessageHistory
from langchain_core.chat_history import BaseChatMessageHistory
from langchain_community.chat_message_histories import ChatMessageHistory
from search_history import search_history_manager
from models import chat_model

# Initialize variables to None first
runnable_agent_with_history = None
agent_executor_instance = None

def initialize_agent():
    """Initialize the agent and return the runnable agent with history."""
    global runnable_agent_with_history, chat_model, agent_executor_instance
    
    try:
        print("Loading prompts and tools...")
        from prompts import system_prompt
        
        # Import tools with error handling
        try:
            from tools import execute_sql_query, web_search_tool
            print("Tools imported successfully!")
        except Exception as tools_error:
            print(f"Error importing tools: {tools_error}")
            # Create a fallback if tools import fails
            from langchain.tools import Tool
            
            def fallback_sql_tool(query: str) -> str:
                return "SQL tool temporarily unavailable due to syntax compatibility issues."
            
            def fallback_web_tool(query: str) -> str:
                return "Web search tool temporarily unavailable."
            
            execute_sql_query = Tool(
                name="execute_sql_query",
                description="Execute SQL queries on the database",
                func=fallback_sql_tool
            )
            
            web_search_tool = Tool(
                name="web_search_tool", 
                description="Search the web for information",
                func=fallback_web_tool
            )
            
            print("Using fallback tools due to import error")

        print("Initializing language model...")


        print("Loading agent prompt template...")
        # Get the prompt template
        try:
            agent_prompt_template = hub.pull("hwchase17/openai-functions-agent")
        except Exception as e:
            print(f"Error loading prompt template: {e}")
            raise Exception("Failed to load prompt template")
        
        if hasattr(agent_prompt_template, 'messages') and \
            len(agent_prompt_template.messages) > 0 and \
            hasattr(agent_prompt_template.messages[0], 'prompt') and \
            hasattr(agent_prompt_template.messages[0].prompt, 'template'):
            agent_prompt_template.messages[0].prompt.template = system_prompt
        else:
            print("Error: Could not customize the agent's system prompt.")
            return None

        print("Setting up tools...")
        tools_list = [execute_sql_query, web_search_tool]
        
        print("Creating agent...")
        # Create OpenAI tools agent
        openai_tools_agent = create_openai_tools_agent(
            llm=chat_model,
            tools=tools_list,
            prompt=agent_prompt_template
        )
        
        print("Creating agent executor...")
        # Create agent executor with streaming enabled
        agent_executor_instance = AgentExecutor(
            agent=openai_tools_agent,
            tools=tools_list,
            verbose=False,  
            handle_parsing_errors=True,
            return_intermediate_steps=False,  
            max_iterations=3,  
            max_execution_time=30  
        )

        print("Setting up message history...")
        # Create runnable with message history
        runnable_agent_with_history = RunnableWithMessageHistory(
            runnable=agent_executor_instance,
            get_session_history=get_session_history,
            input_messages_key="input",
            history_messages_key="chat_history",
            history_factory_config=[
                ConfigurableFieldSpec(
                    id="session_id",
                    annotation=str,
                    name="Session ID",
                    description="Unique identifier for the chat session.",
                    default="",
                    is_shared=True,
                )
            ],
        )
        
        print("Agent initialized successfully!")
        return runnable_agent_with_history
        
    except Exception as e:
        print(f"Failed to initialize agent: {e}")
        return None

# In-memory store for chat histories
store = {}

def get_session_history(session_id_str: str) -> BaseChatMessageHistory:
    """Retrieves or creates a chat history for a given session ID."""
    if session_id_str not in store:
        store[session_id_str] = ChatMessageHistory()
    return store[session_id_str]

def reset_chat_history():
    """Resets the chat history and messages for the current session."""
    st.session_state.messages = []
    session_id = str(st.session_state.id)
    if session_id in store:
        del store[session_id]
    if "_final_output_yielded" in st.session_state:
        del st.session_state._final_output_yielded
    gc.collect()
    st.success("Chat history cleared!")
    st.rerun()

def log_interaction(user_query: str, agent_response: str, session_id: str):
    """Log the interaction to search history."""
    try:
        # Determine source based on response content
        source = "database"
        if "url:" in agent_response.lower() or "http" in agent_response.lower():
            if "price" in agent_response.lower() or "sql" in agent_response.lower():
                source = "both"
            else:
                source = "web"
        
        # Log to search history
        record_id = search_history_manager.log_search(
            user_query=user_query,
            agent_response=agent_response,
            session_id=session_id,
            source=source
        )
        
        if record_id > 0:
            print(f"Interaction logged with record ID: {record_id}")
        
    except Exception as e:
        print(f"Error logging interaction: {e}")
        # Don't fail the main interaction if logging fails