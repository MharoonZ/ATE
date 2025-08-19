import streamlit as st
from datetime import datetime, timedelta
from session_manager import session_manager
import json
import sqlite3
from session_manager import SessionManager

def render_session_sidebar(user_login: str):
    """Render the session management section in the sidebar."""
    
    with st.sidebar:
        st.markdown("---")
        st.markdown("### 💬 Chat Sessions")
        
        # Get user sessions
        sessions = session_manager.get_user_sessions(user_login)
        stats = session_manager.get_session_statistics(user_login)
        
        # Display stats
        if stats.get('total_sessions', 0) > 0:
            col1, col2 = st.columns(2)
            with col1:
                st.metric("Total Sessions", stats.get('total_sessions', 0))
            with col2:
                st.metric("Recent (7d)", stats.get('recent_sessions', 0))
            
            st.metric("Total Messages", stats.get('total_messages', 0))
        
        # New session button
        if st.button("➕ New Session", use_container_width=True, type="primary"):
            create_new_session(user_login)
        
        # Current session info
        current_session_id = st.session_state.get('current_session_id')
        if current_session_id:
            current_session = next(
                (s for s in sessions if s['session_id'] == current_session_id), 
                None
            )
            if current_session:
                st.markdown(f"**Current:** {current_session['title'][:30]}...")
        
        # Session list
        if sessions:
            st.markdown("**Recent Sessions:**")
            
            # Limit display to most recent sessions
            display_sessions = sessions[:10]
            
            for session in display_sessions:
                # Create a container for each session
                with st.container():
                    # Session title (clickable)
                    session_title = session['title']
                    if len(session_title) > 35:
                        session_title = session_title[:32] + "..."
                    
                    # Check if this is the current session
                    is_current = session['session_id'] == current_session_id
                    button_type = "primary" if is_current else "secondary"
                    
                    # Session button
                    if st.button(
                        f"{'🔵 ' if is_current else '💬 '}{session_title}", 
                        key=f"session_{session['session_id'][:8]}",
                        use_container_width=True,
                        type=button_type,
                        help=f"Created: {format_datetime(session['created_at'])}\nMessages: {session['message_count']}"
                    ):
                        load_session(session['session_id'])
                    
                    # Session actions (in columns)
                    col1, col2, col3 = st.columns([1, 1, 1])
                    
                    with col1:
                        if st.button("📝", key=f"edit_{session['session_id'][:8]}", help="Rename"):
                            st.session_state.editing_session = session['session_id']
                            st.rerun()
                    
                    with col2:
                        if st.button("📥", key=f"export_{session['session_id'][:8]}", help="Export"):
                            export_session(session['session_id'])
                    
                    with col3:
                        if st.button("🗑️", key=f"delete_{session['session_id'][:8]}", help="Delete"):
                            st.session_state.deleting_session = session['session_id']
                            st.rerun()
            
            # Show more sessions link
            if len(sessions) > 10:
                if st.button(f"📂 View All Sessions ({len(sessions)})", use_container_width=True):
                    st.session_state.show_all_sessions = True
                    st.rerun()
        
        else:
            st.info("No sessions yet. Start a new conversation!")
        
        # Handle session editing
        handle_session_editing(user_login)
        
        # Handle session deletion
        handle_session_deletion(user_login)

def create_new_session(user_login: str):
    """Create a new chat session."""
    try:
        # Save current session if it has messages
        save_current_session_if_needed()
        
        # Create new session
        new_session_id = session_manager.create_new_session(user_login)
        
        # Update session state
        st.session_state.current_session_id = new_session_id
        st.session_state.messages = []
        st.session_state.session_needs_title = True
        
        # Clear any existing agent history for new session
        if hasattr(st.session_state, 'store'):
            if new_session_id in st.session_state.store:
                del st.session_state.store[new_session_id]
        
        st.success("New session created!")
        st.rerun()
        
    except Exception as e:
        st.error(f"Failed to create new session: {e}")

def load_session(session_id: str):
    """Load an existing chat session."""
    try:
        # Save current session if it has unsaved messages
        save_current_session_if_needed()
        
        # Load messages from database
        messages = session_manager.load_session_messages(session_id)
        
        # Convert to Streamlit format
        st.session_state.messages = [
            {"role": msg["role"], "content": msg["content"]} 
            for msg in messages
        ]
        
        # Update current session
        st.session_state.current_session_id = session_id
        st.session_state.session_needs_title = False
        
        st.success("Session loaded!")
        st.rerun()
        
    except Exception as e:
        st.error(f"Failed to load session: {e}")

def save_current_session_if_needed():
    """Save current session messages if there are any unsaved changes."""
    if not st.session_state.get('messages'):
        return
    
    current_session_id = st.session_state.get('current_session_id')
    if not current_session_id:
        return
    
    # Check if we need to save messages
    # This is a simplified approach - in production you might want more sophisticated tracking
    try:
        existing_messages = session_manager.load_session_messages(current_session_id)
        
        # If current messages are different from saved ones, save them
        if len(st.session_state.messages) != len(existing_messages):
            save_current_session()
    
    except Exception as e:
        print(f"Error checking if session needs saving: {e}")

def save_current_session():
    """Save the current session messages to database."""
    try:
        current_session_id = st.session_state.get('current_session_id')
        if not current_session_id or not st.session_state.get('messages'):
            return
        
        # Delete existing messages for this session
        with session_manager.get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM chat_messages WHERE session_id = ?", (current_session_id,))
            conn.commit()
        
        # Save all current messages
        for i, message in enumerate(st.session_state.messages):
            session_manager.save_message(
                current_session_id,
                message["role"],
                message["content"],
                i
            )
        
        # Update session title if needed
        if st.session_state.get('session_needs_title') and st.session_state.messages:
            first_user_message = next(
                (msg["content"] for msg in st.session_state.messages if msg["role"] == "user"),
                None
            )
            if first_user_message:
                new_title = session_manager.generate_session_title(first_user_message)
                session_manager.update_session_title(current_session_id, new_title)
                st.session_state.session_needs_title = False
        
    except Exception as e:
        print(f"Error saving current session: {e}")

def handle_session_editing(user_login: str):
    """Handle session title editing."""
    editing_session = st.session_state.get('editing_session')
    
    if editing_session:
        st.markdown("**Edit Session Title:**")
        
        # Get current title
        sessions = session_manager.get_user_sessions(user_login)
        current_session = next(
            (s for s in sessions if s['session_id'] == editing_session),
            None
        )
        
        if current_session:
            new_title = st.text_input(
                "New title:",
                value=current_session['title'],
                key=f"edit_title_{editing_session[:8]}"
            )
            
            col1, col2 = st.columns(2)
            with col1:
                if st.button("💾 Save", key=f"save_title_{editing_session[:8]}"):
                    session_manager.update_session_title(editing_session, new_title)
                    del st.session_state.editing_session
                    st.success("Title updated!")
                    st.rerun()
            
            with col2:
                if st.button("❌ Cancel", key=f"cancel_edit_{editing_session[:8]}"):
                    del st.session_state.editing_session
                    st.rerun()

def handle_session_deletion(user_login: str):
    """Handle session deletion with confirmation."""
    deleting_session = st.session_state.get('deleting_session')
    
    if deleting_session:
        st.markdown("**⚠️ Delete Session?**")
        st.warning("This action cannot be undone!")
        
        col1, col2 = st.columns(2)
        with col1:
            if st.button("🗑️ Delete", key=f"confirm_delete_{deleting_session[:8]}", type="primary"):
                success = session_manager.delete_session(deleting_session, user_login)
                if success:
                    # If deleting current session, create a new one
                    if deleting_session == st.session_state.get('current_session_id'):
                        create_new_session(user_login)
                    else:
                        st.success("Session deleted!")
                else:
                    st.error("Failed to delete session!")
                
                del st.session_state.deleting_session
                st.rerun()
        
        with col2:
            if st.button("❌ Cancel", key=f"cancel_delete_{deleting_session[:8]}"):
                del st.session_state.deleting_session
                st.rerun()

def export_session(session_id: str):
    """Export a session to JSON format."""
    try:
        messages = session_manager.load_session_messages(session_id)
        
        if not messages:
            st.warning("No messages to export in this session.")
            return
        
        # Get session info
        sessions = session_manager.get_user_sessions(st.session_state.get('user_login', 'unknown'))
        session_info = next(
            (s for s in sessions if s['session_id'] == session_id),
            {'title': 'Unknown Session', 'created_at': datetime.now().isoformat()}
        )
        
        # Prepare export data
        export_data = {
            'session_id': session_id,
            'title': session_info['title'],
            'created_at': session_info['created_at'],
            'exported_at': datetime.now().isoformat(),
            'message_count': len(messages),
            'messages': messages
        }
        
        # Convert to JSON
        json_data = json.dumps(export_data, indent=2, ensure_ascii=False)
        
        # Create download button
        filename = f"chat_session_{session_info['title'][:20]}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        
        st.download_button(
            label="📥 Download Session",
            data=json_data,
            file_name=filename,
            mime="application/json",
            use_container_width=True
        )
        
        st.success("Session export ready for download!")
        
    except Exception as e:
        st.error(f"Failed to export session: {e}")

def render_all_sessions_view(user_login: str):
    """Render a full view of all user sessions."""
    if st.session_state.get('show_all_sessions', False):
        st.header("💬 All Chat Sessions")
        
        sessions = session_manager.get_user_sessions(user_login, limit=100)
        
        if sessions:
            # Create a more detailed view
            for session in sessions:
                with st.expander(
                    f"💬 {session['title']} ({session['message_count']} messages)",
                    expanded=False
                ):
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        st.write(f"**Created:** {format_datetime(session['created_at'])}")
                        st.write(f"**Last Updated:** {format_datetime(session['last_updated'])}")
                        st.write(f"**Messages:** {session['message_count']}")
                    
                    with col2:
                        if st.button(f"📂 Load Session", key=f"load_full_{session['session_id'][:8]}"):
                            load_session(session['session_id'])
                            st.session_state.show_all_sessions = False
                            st.rerun()
                        
                        if st.button(f"📥 Export", key=f"export_full_{session['session_id'][:8]}"):
                            export_session(session['session_id'])
                        
                        if st.button(f"🗑️ Delete", key=f"delete_full_{session['session_id'][:8]}"):
                            st.session_state.deleting_session = session['session_id']
                            st.rerun()
        
        if st.button("← Back to Chat"):
            st.session_state.show_all_sessions = False
            st.rerun()

def format_datetime(dt_string: str) -> str:
    """Format datetime string for display."""
    try:
        dt = datetime.fromisoformat(dt_string.replace('Z', '+00:00'))
        return dt.strftime("%Y-%m-%d %H:%M")
    except:
        return dt_string

def initialize_session_for_user(user_login: str):
    """Initialize or load the current session for a user."""
    
    # Check if user already has a current session
    if 'current_session_id' not in st.session_state:
        # Try to get the most recent session
        sessions = session_manager.get_user_sessions(user_login, limit=1)
        
        if sessions:
            # Load the most recent session
            most_recent = sessions[0]
            st.session_state.current_session_id = most_recent['session_id']
            
            # Load messages
            messages = session_manager.load_session_messages(most_recent['session_id'])
            st.session_state.messages = [
                {"role": msg["role"], "content": msg["content"]} 
                for msg in messages
            ]
            st.session_state.session_needs_title = False
        else:
            # Create a new session for first-time user
            session_id = session_manager.create_new_session(user_login)
            st.session_state.current_session_id = session_id
            st.session_state.messages = []
            st.session_state.session_needs_title = True

# Add method to SessionManager class
def get_db_connection(self):
    """Get database connection (add this method to SessionManager class)."""
    return sqlite3.connect(self.db_path)

# Add the method to the SessionManager class
SessionManager.get_db_connection = get_db_connection