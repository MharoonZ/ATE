import sqlite3
import json
import uuid
from datetime import datetime
from typing import List, Dict, Optional
import streamlit as st
import pickle
import os

class SessionManager:
    """Manages persistent chat sessions and message history across browser sessions."""
    
    def __init__(self, db_path: str = "chat_sessions.db"):
        self.db_path = db_path
        self.init_database()
    
    def init_database(self):
        """Initialize the chat sessions database."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Create chat_sessions table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS chat_sessions (
                        session_id TEXT PRIMARY KEY,
                        user_login TEXT NOT NULL,
                        session_title TEXT,
                        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                        last_updated DATETIME DEFAULT CURRENT_TIMESTAMP,
                        message_count INTEGER DEFAULT 0,
                        is_active BOOLEAN DEFAULT 1
                    )
                """)
                
                # Create chat_messages table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS chat_messages (
                        message_id INTEGER PRIMARY KEY AUTOINCREMENT,
                        session_id TEXT NOT NULL,
                        role TEXT NOT NULL,  -- 'user' or 'assistant'
                        content TEXT NOT NULL,
                        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                        message_index INTEGER NOT NULL,
                        FOREIGN KEY (session_id) REFERENCES chat_sessions (session_id)
                    )
                """)
                
                # Create indexes for better performance
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_session_user ON chat_sessions(user_login)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_session_updated ON chat_sessions(last_updated)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_messages_session ON chat_messages(session_id)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_messages_timestamp ON chat_messages(timestamp)")
                
                conn.commit()
                print("Chat sessions database initialized successfully")
                
        except Exception as e:
            print(f"Error initializing chat sessions database: {e}")
            st.error(f"Failed to initialize chat sessions: {e}")
    
    def create_new_session(self, user_login: str, session_title: str = None) -> str:
        """Create a new chat session and return the session ID."""
        try:
            session_id = str(uuid.uuid4())
            
            if not session_title:
                session_title = f"Chat Session - {datetime.now().strftime('%Y-%m-%d %H:%M')}"
            
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                cursor.execute("""
                    INSERT INTO chat_sessions 
                    (session_id, user_login, session_title, created_at, last_updated)
                    VALUES (?, ?, ?, ?, ?)
                """, (
                    session_id,
                    user_login,
                    session_title,
                    datetime.now().isoformat(),
                    datetime.now().isoformat()
                ))
                
                conn.commit()
                print(f"New chat session created: {session_id}")
                return session_id
                
        except Exception as e:
            print(f"Error creating new session: {e}")
            st.error(f"Failed to create new session: {e}")
            return str(uuid.uuid4())  # Fallback to temporary session
    
    def get_user_sessions(self, user_login: str, limit: int = 50) -> List[Dict]:
        """Get all sessions for a specific user."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                
                cursor.execute("""
                    SELECT session_id, session_title, created_at, last_updated, 
                           message_count, is_active
                    FROM chat_sessions 
                    WHERE user_login = ? AND is_active = 1
                    ORDER BY last_updated DESC 
                    LIMIT ?
                """, (user_login, limit))
                
                sessions = []
                for row in cursor.fetchall():
                    sessions.append({
                        'session_id': row['session_id'],
                        'title': row['session_title'],
                        'created_at': row['created_at'],
                        'last_updated': row['last_updated'],
                        'message_count': row['message_count'],
                        'is_active': row['is_active']
                    })
                
                return sessions
                
        except Exception as e:
            print(f"Error getting user sessions: {e}")
            return []
    
    def save_message(self, session_id: str, role: str, content: str, message_index: int):
        """Save a message to the database."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Insert the message
                cursor.execute("""
                    INSERT INTO chat_messages 
                    (session_id, role, content, timestamp, message_index)
                    VALUES (?, ?, ?, ?, ?)
                """, (
                    session_id,
                    role,
                    content,
                    datetime.now().isoformat(),
                    message_index
                ))
                
                # Update session statistics
                cursor.execute("""
                    UPDATE chat_sessions 
                    SET last_updated = ?, 
                        message_count = (
                            SELECT COUNT(*) FROM chat_messages 
                            WHERE session_id = ?
                        )
                    WHERE session_id = ?
                """, (
                    datetime.now().isoformat(),
                    session_id,
                    session_id
                ))
                
                conn.commit()
                
        except Exception as e:
            print(f"Error saving message: {e}")
    
    def load_session_messages(self, session_id: str) -> List[Dict]:
        """Load all messages for a specific session."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                
                cursor.execute("""
                    SELECT role, content, timestamp, message_index
                    FROM chat_messages 
                    WHERE session_id = ?
                    ORDER BY message_index ASC
                """, (session_id,))
                
                messages = []
                for row in cursor.fetchall():
                    messages.append({
                        'role': row['role'],
                        'content': row['content'],
                        'timestamp': row['timestamp'],
                        'message_index': row['message_index']
                    })
                
                return messages
                
        except Exception as e:
            print(f"Error loading session messages: {e}")
            return []
    
    def update_session_title(self, session_id: str, new_title: str):
        """Update the title of a session."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                cursor.execute("""
                    UPDATE chat_sessions 
                    SET session_title = ?, last_updated = ?
                    WHERE session_id = ?
                """, (new_title, datetime.now().isoformat(), session_id))
                
                conn.commit()
                
        except Exception as e:
            print(f"Error updating session title: {e}")
    
    def delete_session(self, session_id: str, user_login: str) -> bool:
        """Delete a session and all its messages."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Verify ownership
                cursor.execute("""
                    SELECT user_login FROM chat_sessions 
                    WHERE session_id = ?
                """, (session_id,))
                
                result = cursor.fetchone()
                if not result or result[0] != user_login:
                    return False
                
                # Delete messages first (foreign key constraint)
                cursor.execute("DELETE FROM chat_messages WHERE session_id = ?", (session_id,))
                
                # Delete session
                cursor.execute("DELETE FROM chat_sessions WHERE session_id = ?", (session_id,))
                
                conn.commit()
                return True
                
        except Exception as e:
            print(f"Error deleting session: {e}")
            return False
    
    def archive_session(self, session_id: str, user_login: str) -> bool:
        """Archive a session (mark as inactive)."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                cursor.execute("""
                    UPDATE chat_sessions 
                    SET is_active = 0, last_updated = ?
                    WHERE session_id = ? AND user_login = ?
                """, (datetime.now().isoformat(), session_id, user_login))
                
                conn.commit()
                return cursor.rowcount > 0
                
        except Exception as e:
            print(f"Error archiving session: {e}")
            return False
    
    def generate_session_title(self, first_message: str) -> str:
        """Generate a meaningful title from the first user message."""
        if not first_message:
            return f"Chat Session - {datetime.now().strftime('%Y-%m-%d %H:%M')}"
        
        # Clean and truncate the message for title
        clean_message = first_message.strip()
        if len(clean_message) > 50:
            clean_message = clean_message[:47] + "..."
        
        # Remove common prefixes
        prefixes_to_remove = [
            "what is", "what are", "how do", "how to", "can you", "please", "help me"
        ]
        
        lower_message = clean_message.lower()
        for prefix in prefixes_to_remove:
            if lower_message.startswith(prefix):
                clean_message = clean_message[len(prefix):].strip()
                break
        
        # Capitalize first letter
        if clean_message:
            clean_message = clean_message[0].upper() + clean_message[1:]
        
        return clean_message or f"Chat - {datetime.now().strftime('%H:%M')}"
    
    def get_session_statistics(self, user_login: str) -> Dict:
        """Get statistics about user's chat sessions."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Total sessions
                cursor.execute("""
                    SELECT COUNT(*) FROM chat_sessions 
                    WHERE user_login = ? AND is_active = 1
                """, (user_login,))
                total_sessions = cursor.fetchone()[0]
                
                # Total messages
                cursor.execute("""
                    SELECT COUNT(*) FROM chat_messages cm
                    JOIN chat_sessions cs ON cm.session_id = cs.session_id
                    WHERE cs.user_login = ? AND cs.is_active = 1
                """, (user_login,))
                total_messages = cursor.fetchone()[0]
                
                # Recent activity (last 7 days)
                from datetime import timedelta
                seven_days_ago = (datetime.now() - timedelta(days=7)).isoformat()
                cursor.execute("""
                    SELECT COUNT(*) FROM chat_sessions 
                    WHERE user_login = ? AND last_updated >= ? AND is_active = 1
                """, (user_login, seven_days_ago))
                recent_sessions = cursor.fetchone()[0]
                
                return {
                    'total_sessions': total_sessions,
                    'total_messages': total_messages,
                    'recent_sessions': recent_sessions
                }
                
        except Exception as e:
            print(f"Error getting session statistics: {e}")
            return {}

# Global instance — local file for now. To use a Render disk later, uncomment below and set CHAT_DB_PATH.
# _session_db_path = os.getenv("CHAT_DB_PATH", "/data/chat_sessions.db")
# session_manager = SessionManager(db_path=_session_db_path)
session_manager = SessionManager(db_path="chat_sessions.db")