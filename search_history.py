import sqlite3
import json
import csv
import pandas as pd
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple, Any
import re
import streamlit as st
from urllib.parse import urlparse
import os

from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any

from langchain_core.prompts import ChatPromptTemplate


from models import chat_model

class DataInsights(BaseModel):
	"""Model to represent data insights for search results."""
	product_brand: Optional[str] = Field(..., description="Brand of the product identified in the user's query. Eg(`Agilent HP Keysight`, `Keithley`, ...)")
	product_model: Optional[str] = Field(..., description="Model of the product identified in the user's query.. Eg('34401A', 'DMM6500', 'SL1203A', ...)")
	price_details: Optional[List[str]] = Field(..., description="List of price details extracted from the search result.")
	verified_urls: Optional[List[str]] = Field(..., description="List of verified URLs related to the product.")
	# source: str = Field(..., description="Source of the data (e.g., 'web', 'database', 'mixed').")
	notes: str= Field(..., description="Additional context or observations about the query or results. ")
	vendors: Optional[List[str]]= Field(..., description="List of vendors providing the product. ")

chat_prompt_template= ChatPromptTemplate.from_template(
	template="You are an AI assistant that provides data insights based on user queries. Your task is to extract structured information from the agent results. \n\nUser Query: {user_query}\n\nAgent Response: {agent_response}\n\nPlease provide the following details:\n- Product Brand\n- Product Model\n- Price Details (as a list)\n- Verified URLs (as a list)\n- Vendors (as a list)\n- Notes (contextual observations about the query or results)\n\nReturn the data in JSON format. If the `agent_response` is empty or does not contain relevant information, return an empty JSON object. Do not try to make up an answer"
)

chat_model_with_structured_output= chat_model.bind_tools(tools= [DataInsights])

chain= chat_prompt_template | chat_model_with_structured_output

class SearchHistoryManager:
	"""Manages search history logging, retrieval, and analysis for InsightAgentBot."""
	
	def __init__(self, db_path: str = "search_history.db"):
		self.db_path = db_path
		self.init_database()
	
	def init_database(self):
		"""Initialize the search history database with required tables."""
		try:
			with sqlite3.connect(self.db_path) as conn:
				cursor = conn.cursor()
				
				# Create search_history table
				cursor.execute("""
					CREATE TABLE IF NOT EXISTS search_history (
						record_id INTEGER PRIMARY KEY AUTOINCREMENT,
						timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
						user_query TEXT NOT NULL,
						product_brand TEXT,
						product_model TEXT,
						price_details TEXT,  -- JSON string
						vendors TEXT,        -- JSON string
						verified_urls TEXT,  -- JSON string
						source TEXT,         -- 'database', 'web', 'both'
						notes TEXT,
						session_id TEXT
					)
				""")
				
				# Create indexes for better performance
				cursor.execute("CREATE INDEX IF NOT EXISTS idx_timestamp ON search_history(timestamp)")
				cursor.execute("CREATE INDEX IF NOT EXISTS idx_brand ON search_history(product_brand)")
				cursor.execute("CREATE INDEX IF NOT EXISTS idx_model ON search_history(product_model)")
				cursor.execute("CREATE INDEX IF NOT EXISTS idx_session ON search_history(session_id)")
				
				conn.commit()
				print("Search history database initialized successfully")
				
		except Exception as e:
			print(f"Error initializing search history database: {e}")
			st.error(f"Failed to initialize search history: {e}")
	
	def extract_product_info(self, query: str, response: str) -> Tuple[Optional[str], Optional[str]]:
		"""Extract product brand and model from user query and agent response."""
		# Extract data insights from agent response:
		print("Parsing agent response:\n", response)
		parsed_data = {}
		result = chain.invoke({"user_query": query, "agent_response": response})
		print("Structured output from agent:\n", result)
		# Safely extract structured output
		tool_calls = result.additional_kwargs.get("tool_calls", [])
		if tool_calls:
			try:
				parsed_json = json.loads(tool_calls[0]["function"]["arguments"])
			except (KeyError, ValueError, TypeError):
				st.error("Failed to parse structured output; proceeding with empty data.")
				parsed_json = {}
		else:
			parsed_json = {}

		print("parsed_json:", parsed_json)
		# Extract brand and model from user query
		parsed_data["product_brand"] = parsed_json.get("product_brand", "")
		parsed_data["product_model"] = parsed_json.get("product_model", "")
		parsed_data["price_details"] = parsed_json.get("price_details", [])
		parsed_data["vendors"] = parsed_json.get("vendors", [])
		parsed_data["notes"] = parsed_json.get("notes", "")
		parsed_data["verified_urls"] = parsed_json.get("verified_urls", [])

		# consider 'web' only if we actually extracted URLs
		parsed_data["source"] = "web" if parsed_data.get("verified_urls") else "database"

		print("parsed_data:\n", parsed_data)

		return parsed_data
	
	def log_search(self, user_query: str, agent_response: str, session_id: str, 
				   source: str = "both", notes: str = "") -> int:
		"""Log a search interaction to the history database."""
		try:
			# Extract information from query and response
			parsed_data = self.extract_product_info(user_query, agent_response)
			brand = parsed_data.get("product_brand", "")
			model = parsed_data.get("product_model", "")
			price_details = parsed_data.get("price_details", [])
			vendors = parsed_data.get("vendors", [])
			urls = parsed_data.get("verified_urls", [])
			# verified_urls = self.verify_urls(urls) if urls else []
			source = parsed_data.get("source", "database")
			notes = parsed_data.get("notes", notes)
			
			with sqlite3.connect(self.db_path) as conn:
				cursor = conn.cursor()
				
				cursor.execute("""
					INSERT INTO search_history 
					(user_query, product_brand, product_model, price_details, 
					 vendors, verified_urls, source, notes, session_id)
					VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
				""", (
					user_query,
					brand,
					model,
					json.dumps(price_details),
					json.dumps(vendors),
					json.dumps(urls),
					source,
					notes,
					session_id
				))
				
				record_id = cursor.lastrowid
				conn.commit()
				
				print(f"Search logged with ID: {record_id}")
				return record_id
				
		except Exception as e:
			print(f"Error logging search: {e}")
			st.error(f"Failed to log search: {e}")
			return -1
	
	def get_search_history(self, limit: int = 50, offset: int = 0, 
						  brand_filter: str = None, model_filter: str = None,
						  date_from: datetime = None, date_to: datetime = None,
						  session_id: str = None) -> List[Dict]:
		"""Retrieve search history with optional filtering."""
		try:
			with sqlite3.connect(self.db_path) as conn:
				conn.row_factory = sqlite3.Row  # Enable column access by name
				cursor = conn.cursor()
				
				# Build query with filters
				query = "SELECT * FROM search_history WHERE 1=1"
				params = []
				
				if brand_filter:
					query += " AND product_brand LIKE ?"
					params.append(f"%{brand_filter}%")
				
				if model_filter:
					query += " AND product_model LIKE ?"
					params.append(f"%{model_filter}%")
				
				if date_from:
					query += " AND timestamp >= ?"
					params.append(date_from.strftime("%Y-%m-%d %H:%M:%S"))
				
				if date_to:
					query += " AND timestamp <= ?"
					params.append(date_to.strftime("%Y-%m-%d %H:%M:%S"))
				
				if session_id:
					query += " AND session_id = ?"
					params.append(session_id)
				
				query += " ORDER BY timestamp DESC LIMIT ? OFFSET ?"
				params.extend([limit, offset])
				
				cursor.execute(query, params)
				rows = cursor.fetchall()
				
				# Convert to list of dictionaries with JSON parsing
				history = []
				for row in rows:
					record = dict(row)
					
					# Parse JSON fields
					try:
						record['price_details'] = json.loads(record['price_details'] or '[]')
					except:
						record['price_details'] = []
					
					try:
						record['vendors'] = json.loads(record['vendors'] or '[]')
					except:
						record['vendors'] = []
					
					try:
						record['verified_urls'] = json.loads(record['verified_urls'] or '[]')
					except:
						record['verified_urls'] = []
					
					history.append(record)
				
				return history
				
		except Exception as e:
			print(f"Error retrieving search history: {e}")
			st.error(f"Failed to retrieve search history: {e}")
			return []
	
	def export_to_csv(self, filename: str = None, **filters) -> str:
		"""Export search history to CSV file."""
		if filename is None:
			timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
			filename = f"search_history_{timestamp}.csv"
		
		try:
			# Get all history records with filters
			history = self.get_search_history(limit=10000, **filters)
			
			if not history:
				return None
			
			# Prepare data for CSV
			csv_data = []
			for record in history:
				csv_row = {
					'Record ID': record['record_id'],
					'Timestamp': record['timestamp'],
					'User Query': record['user_query'],
					'Product Brand': record['product_brand'] or '',
					'Product Model': record['product_model'] or '',
					'Price Count': len(record['price_details']),
					'Price Range': self._format_price_range(record['price_details']),
					'Vendors': ', '.join(record['vendors']),
					'URL Count': len(record['verified_urls']),
					'Source': record['source'],
					'Notes': record['notes'] or ''
				}
				csv_data.append(csv_row)
			
			# Write to CSV
			df = pd.DataFrame(csv_data)
			df.to_csv(filename, index=False)
			
			return filename
			
		except Exception as e:
			print(f"Error exporting to CSV: {e}")
			st.error(f"Failed to export to CSV: {e}")
			return None
	
	def _format_price_range(self, price_details: List[Dict]) -> str:
		"""Format price range string for display."""
		if not price_details:
			return "No prices"
		
		prices = [p['value'] for p in price_details]
		if len(prices) == 1:
			return f"${prices[0]:,.2f}"
		else:
			return f"${min(prices):,.2f} - ${max(prices):,.2f}"
	
	def get_statistics(self) -> Dict:
		"""Get basic statistics about search history."""
		try:
			with sqlite3.connect(self.db_path) as conn:
				cursor = conn.cursor()
				
				# Total searches
				cursor.execute("SELECT COUNT(*) FROM search_history")
				total_searches = cursor.fetchone()[0]
				
				# Unique brands
				cursor.execute("SELECT COUNT(DISTINCT product_brand) FROM search_history WHERE product_brand IS NOT NULL")
				unique_brands = cursor.fetchone()[0]
				
				# Searches with prices
				cursor.execute("SELECT COUNT(*) FROM search_history WHERE price_details != '[]' AND price_details IS NOT NULL")
				searches_with_prices = cursor.fetchone()[0]
				
				# Recent activity (last 7 days)
				seven_days_ago = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d %H:%M:%S")
				cursor.execute("SELECT COUNT(*) FROM search_history WHERE timestamp >= ?", (seven_days_ago,))
				recent_searches = cursor.fetchone()[0]
				
				return {
					'total_searches': total_searches,
					'unique_brands': unique_brands,
					'searches_with_prices': searches_with_prices,
					'recent_searches': recent_searches
				}
				
		except Exception as e:
			print(f"Error getting statistics: {e}")
			return {}
	
	def clear_history(self, days_to_keep: int = None) -> bool:
		"""Clear search history. If days_to_keep is specified, only clear older records."""
		try:
			with sqlite3.connect(self.db_path) as conn:
				cursor = conn.cursor()
				
				if days_to_keep is not None:
					cutoff_date = (datetime.now() - timedelta(days=days_to_keep)).strftime("%Y-%m-%d %H:%M:%S")
					cursor.execute("DELETE FROM search_history WHERE timestamp < ?", (cutoff_date,))
				else:
					cursor.execute("DELETE FROM search_history")
				
				deleted_count = cursor.rowcount
				conn.commit()
				
				print(f"Cleared {deleted_count} search history records")
				return True
				
		except Exception as e:
			print(f"Error clearing history: {e}")
			st.error(f"Failed to clear history: {e}")
			return False

# Global instance — local file for now. To use a Render disk later, uncomment below and set SEARCH_DB_PATH.
# _history_db_path = os.getenv("SEARCH_DB_PATH", "/data/search_history.db")
# search_history_manager = SearchHistoryManager(db_path=_history_db_path)
search_history_manager = SearchHistoryManager(db_path="search_history.db")