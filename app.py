import uuid
import time
import streamlit as st
import gc

# --- Page Configuration MUST BE FIRST ---
st.set_page_config(
    page_title="InsightAgentBot: Talk to Our Data & the Web",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded"
)

from agent import runnable_agent_with_history, reset_chat_history, initialize_agent, log_interaction
from search_history_ui import render_search_history_sidebar, render_search_history_main, render_analytics
from session_ui import render_session_sidebar, render_all_sessions_view, initialize_session_for_user, save_current_session

# --- Constants ---
CURRENT_USER = "Fady"  # This would typically come from authentication

# --- Function to Stream Agent Responses ---
def stream_agent_responses(final_response_string: str, delay_seconds: float = 0.05):
    """
    Streams a given final response string character by character.
    Escapes '$' for Markdown compatibility.
    """
    if not isinstance(final_response_string, str):
        yield str(final_response_string)
        return

    for char_idx, char in enumerate(final_response_string):
        if char == '$':
            yield '\\'
            yield '$'
        else:
            yield char
        
        if char_idx < 50:
            time.sleep(delay_seconds)
        else:
            time.sleep(delay_seconds * 1.5)

# --- Session State Initialization ---
if "id" not in st.session_state:
    st.session_state.id = str(uuid.uuid4())
if "user_login" not in st.session_state:
    st.session_state.user_login = CURRENT_USER
if "messages" not in st.session_state:
    st.session_state.messages = []
if "chain_runnable" not in st.session_state:
    st.session_state.chain_runnable = None
if "chain_initialized" not in st.session_state:
    st.session_state.chain_initialized = False
if "show_history" not in st.session_state:
    st.session_state.show_history = False
if "show_analytics" not in st.session_state:
    st.session_state.show_analytics = False
if "show_all_sessions" not in st.session_state:
    st.session_state.show_all_sessions = False

# --- Initialize user session ---
initialize_session_for_user(CURRENT_USER)

# --- Check for History/Analytics/Sessions View ---
if st.session_state.show_history:
    render_search_history_main()
    st.stop()

if st.session_state.show_analytics:
    render_analytics()
    st.stop()

if st.session_state.show_all_sessions:
    render_all_sessions_view(CURRENT_USER)
    st.stop()

# --- Agent and Chain Initialization ---
if not st.session_state.chain_initialized:
    # Create progress placeholders
    status_placeholder = st.empty()
    progress_bar = st.progress(0)
    
    # Create a dedicated section for database connection logs - CLOSED by default
    with st.expander("🔍 Database Connection Details", expanded=False):
        db_log_container = st.container()
    
    try:
        # Test database connection first
        status_placeholder.info("🔌 Testing database connection...")
        progress_bar.progress(10)
        
        try:
            with db_log_container:
                from database_connection import get_database
            progress_bar.progress(20)
            
            with db_log_container:
                db = get_database()
            progress_bar.progress(50)
            
            if db is None:
                raise Exception("Database connection failed - cannot initialize agent")
            
            status_placeholder.success("✅ Database connected successfully!")
            progress_bar.progress(60)
            
        except Exception as db_error:
            progress_bar.empty()
            status_placeholder.error(f"❌ Database connection failed: {db_error}")
            with db_log_container:
                st.error(f"❌ Final error: {db_error}")
            st.error("Please check your database connection and try again.")
            st.stop()
        
        # Initialize the agent
        status_placeholder.info("🤖 Initializing AI Agent...")
        progress_bar.progress(70)
        
        try:
            if runnable_agent_with_history is None:
                st.session_state.chain_runnable = initialize_agent()
            else:
                st.session_state.chain_runnable = runnable_agent_with_history
            
            progress_bar.progress(90)
            
            if st.session_state.chain_runnable is not None:
                st.session_state.chain_initialized = True
                progress_bar.progress(100)
                status_placeholder.success("✅ AI Agent initialized successfully!")
                
                # Clean up progress indicators after success
                import time
                time.sleep(2)  # Give users time to see the success message
                status_placeholder.empty()
                progress_bar.empty()
            else:
                raise Exception("Failed to initialize the agent")
                
        except Exception as agent_error:
            progress_bar.empty()
            status_placeholder.error(f"❌ Agent initialization failed: {agent_error}")
            st.error("Please refresh the page and try again.")
            st.stop()
            
    except ImportError as e:
        progress_bar.empty()
        status_placeholder.error("❌ Failed to import required modules")
        st.error(f"Import error: {e}")
        st.stop()
    except Exception as e:
        progress_bar.empty()
        error_msg = str(e)
        if "pyodbc" in error_msg or "ODBC" in error_msg:
            status_placeholder.error("❌ Database Connection Issue:")
            st.error("Please install Microsoft ODBC Driver for SQL Server")
            st.markdown("""
            **To fix this issue:**
            1. Download and install the ODBC Driver from: https://docs.microsoft.com/en-us/sql/connect/odbc/download-odbc-driver-for-sql-server
            2. Restart your application after installation
            """)
        else:
            status_placeholder.error(f"❌ Failed to initialize the AI agent: {e}")
        
        import traceback
        with st.expander("Show detailed error"):
            st.code(traceback.format_exc())
        st.stop()

# --- Enhanced Chat History Reset ---
def enhanced_reset_chat_history():
    """Enhanced reset that also saves the session before clearing."""
    # Save current session before clearing
    save_current_session()
    
    # Clear current session state
    st.session_state.messages = []
    
    # Clear agent history
    session_id = str(st.session_state.get('current_session_id', st.session_state.id))
    from agent import store
    if session_id in store:
        del store[session_id]
    
    # Create new session
    from session_ui import create_new_session
    create_new_session(CURRENT_USER)
    
    gc.collect()
    st.success("Chat history cleared and new session created!")
    st.rerun()

# --- Sidebar UI ---
with st.sidebar:
    st.title("🤖 SQL Agent Controls")
    st.markdown("---")
    st.info(
        "This AI agent interacts with a SQL database. "
        "Ask questions about the data, and the agent will attempt to answer them by generating and executing SQL queries."
    )

    # User info
    st.markdown(f"**User:** {CURRENT_USER}")
    
    if st.button("Clear Current Chat ↺", on_click=enhanced_reset_chat_history, use_container_width=True, type="primary"):
        pass # Action handled by on_click

    # Render session management
    render_session_sidebar(CURRENT_USER)

    # Render search history sidebar
    render_search_history_sidebar()

    st.markdown("---")
    st.markdown("### Database Information")
    st.caption("The agent is connected to a Microsoft SQL Server database. It can query tables like `quotesresponses`.")

# --- Main Chat Interface ---
st.title("Chat with Updated Products Database 📊")
st.markdown("<sub>Powered by Langchain & OpenAI with Persistent Sessions</sub>", unsafe_allow_html=True)

# Display current session info
current_session_id = st.session_state.get('current_session_id')
if current_session_id:
    from session_manager import session_manager
    sessions = session_manager.get_user_sessions(CURRENT_USER)
    current_session = next(
        (s for s in sessions if s['session_id'] == current_session_id), 
        None
    )
    if current_session:
        st.info(f"💬 Current Session: **{current_session['title']}** | Messages: {len(st.session_state.messages)} | Created: {current_session['created_at'][:16]}")

# Display welcome message if chat is empty
if not st.session_state.messages:
    st.info("Welcome! I'm ready to help you query the database. Try asking something like: 'What are the distinct company names?' or 'How many records are in quotesresponses?'")

# Display chat messages
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# Handle re-run query
if hasattr(st.session_state, 'rerun_query'):
    prompt = st.session_state.rerun_query
    del st.session_state.rerun_query
else:
    prompt = st.chat_input("Ask a question about the database...")

# Chat input
if prompt:
    # Add message to session state
    st.session_state.messages.append({"role": "user", "content": prompt})
    
    # Save the user message immediately
    current_session_id = st.session_state.get('current_session_id')
    if current_session_id:
        from session_manager import session_manager
        session_manager.save_message(
            current_session_id,
            "user",
            prompt,
            len(st.session_state.messages) - 1
        )
    
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        if not st.session_state.chain_initialized or not st.session_state.chain_runnable:
            st.error("The AI Agent is not initialized. Please refresh or check the logs.")
            st.stop()

        current_chain = st.session_state.chain_runnable
        full_response_content = ""

        try:
            # Each interaction uses the current session ID for history
            chat_session_id = str(current_session_id or st.session_state.id)
            input_payload = {"input": prompt}

            # Create placeholder for streaming response
            message_placeholder = st.empty()
            full_response = ""
            
            # Stream the response chunk by chunk for better UX
            for chunk in current_chain.stream(
                input_payload,
                config={"configurable": {"session_id": chat_session_id}}
            ):
                # Handle different chunk types from the agent
                if isinstance(chunk, dict):
                    # Check for agent output
                    if 'agent' in chunk and 'messages' in chunk['agent']:
                        for message in chunk['agent']['messages']:
                            if hasattr(message, 'content') and message.content:
                                # Add content to response
                                full_response += message.content
                                message_placeholder.markdown(full_response + "▌")
                                time.sleep(0.01)  # Small delay for smoother streaming
                    
                    # Check for final output
                    elif 'output' in chunk:
                        output_text = chunk['output']
                        # Add remaining content if any
                        if output_text and output_text not in full_response:
                            remaining_text = output_text[len(full_response):]
                            for char in remaining_text:
                                full_response += char
                                message_placeholder.markdown(full_response + "▌")
                                time.sleep(0.005)  # Character-by-character streaming
            
            # Remove cursor and show final response
            if not full_response:
                # Fallback: if streaming didn't work, use invoke
                with st.spinner("Processing..."):
                    response_container = current_chain.invoke(
                        input_payload,
                        config={"configurable": {"session_id": chat_session_id}}
                    )
                    full_response = response_container.get('output', str(response_container))
            
            # Clean up the response formatting
            if isinstance(full_response, str):
                # Remove any duplicate formatting issues
                full_response = full_response.replace('\n,\n', '\n')
                full_response = full_response.replace(',,', ',')
                full_response = full_response.replace(', ,', ',')
            
            message_placeholder.markdown(full_response)
            full_response_content = full_response

            # Log the interaction to search history
            log_interaction(prompt, full_response_content, chat_session_id)

        except Exception as e:
            st.error(f"Error during chat generation: {e}")
            import traceback
            st.error(f"Traceback: {traceback.format_exc()}")
            full_response_content = "Sorry, I encountered an error while processing your request. Please try again."
            message_placeholder.markdown(full_response_content)

    # Add assistant response to session state
    st.session_state.messages.append({"role": "assistant", "content": full_response_content})
    
    # Save the assistant message
    if current_session_id:
        session_manager.save_message(
            current_session_id,
            "assistant",
            full_response_content,
            len(st.session_state.messages) - 1
        )
        
        # Update session title if this is the first interaction
        if st.session_state.get('session_needs_title'):
            new_title = session_manager.generate_session_title(prompt)
            session_manager.update_session_title(current_session_id, new_title)
            st.session_state.session_needs_title = False
    
    st.rerun()

# Auto-save session periodically (every 10 messages)
if len(st.session_state.messages) > 0 and len(st.session_state.messages) % 10 == 0:
    save_current_session()