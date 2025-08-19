import streamlit as st
from langchain_core.tools import tool
from tavily import TavilyClient
from pydantic import BaseModel, Field
from langchain_community.tools.sql_database.tool import QuerySQLDatabaseTool
import ast 
import requests
from typing import Optional
from decimal import Decimal
import database_connection as dbc
import re
import os

# Initialize Tavily client with API key from environment
# TavilyClient will also read TAVILY_API_KEY from the environment if not provided explicitly
_tavily_api_key = os.getenv("TAVILY_API_KEY")
tavily_client = TavilyClient(api_key=_tavily_api_key) if _tavily_api_key is not None else TavilyClient()

class SQLQUERY(BaseModel):
    sql_query: str = Field(..., description="Syntactically valid SQL query to execute.")

def format_sql_result(result):
    """Format SQL query results for better readability"""
    if not result or result == "[]":
        return "No results found."
    
    try:
        # Handle string representation of results
        if isinstance(result, str):
            # Try to evaluate the string as a Python literal
            try:
                evaluated_result = ast.literal_eval(result)
            except:
                return result
        else:
            evaluated_result = result
        
        # Handle list of tuples (common SQL result format)
        if isinstance(evaluated_result, list):
            if not evaluated_result:
                return "No results found."
            
            # Check if it's a list of single-value tuples (like price results)
            if all(isinstance(item, tuple) and len(item) == 1 for item in evaluated_result):
                # Extract values and format them
                non_zero_values = []
                zero_count = 0
                
                for item in evaluated_result:
                    value = item[0]
                    if isinstance(value, Decimal):
                        # Convert Decimal to float and format as whole number
                        float_val = float(value)
                        if float_val == 0:
                            zero_count += 1
                            continue  # Skip zero values for now
                        non_zero_values.append(int(float_val))
                    elif isinstance(value, (int, float)):
                        if value == 0:
                            zero_count += 1
                            continue  # Skip zero values for now
                        non_zero_values.append(int(value))
                    else:
                        val_str = str(value).strip()
                        if val_str and val_str != '0' and val_str != '0.0':
                            non_zero_values.append(val_str)
                
                if not non_zero_values and zero_count == 0:
                    return "No results found."
                
                # Remove duplicates while preserving order
                seen = set()
                unique_values = []
                for val in non_zero_values:
                    if val not in seen:
                        seen.add(val)
                        unique_values.append(val)
                
                # Sort the unique values
                try:
                    unique_values.sort()
                except:
                    pass  # Keep original order if sorting fails
                
                # Format the response
                result_lines = []
                
                if zero_count > 0:
                    result_lines.append(f"Found {zero_count} entries with 0$ price (likely placeholders)")
                
                if unique_values:
                    if len(unique_values) <= 25:
                        result_lines.append("Non-zero prices found:")
                        for price in unique_values:
                            result_lines.append(f"• {price}$")
                    else:
                        result_lines.append(f"Found {len(unique_values)} unique non-zero prices. First 25:")
                        for price in unique_values[:25]:
                            result_lines.append(f"• {price}$")
                        result_lines.append(f"... and {len(unique_values) - 25} more prices")
                
                return "\n".join(result_lines) if result_lines else "No non-zero results found."
            
            # Handle other tuple formats (multiple columns)
            elif all(isinstance(item, tuple) for item in evaluated_result):
                formatted_rows = []
                for row in evaluated_result[:15]:  # Limit to first 15 rows
                    formatted_values = []
                    for val in row:
                        if isinstance(val, Decimal):
                            formatted_values.append(f"{int(float(val))}")
                        elif isinstance(val, (int, float)):
                            formatted_values.append(f"{int(val)}")
                        else:
                            formatted_values.append(str(val))
                    formatted_rows.append(" | ".join(formatted_values))
                
                if len(evaluated_result) > 15:
                    formatted_rows.append(f"... and {len(evaluated_result) - 15} more rows")
                
                return "\n".join(formatted_rows)
            
            # Handle list of single values
            else:
                formatted_values = []
                for item in evaluated_result[:25]:  # Limit to first 25 items
                    if isinstance(item, Decimal):
                        formatted_values.append(f"{int(float(item))}")
                    elif isinstance(item, (int, float)) and item != 0:
                        formatted_values.append(f"{int(item)}")
                    else:
                        formatted_values.append(str(item))
                
                return "\n".join([f"• {val}" for val in formatted_values])
        
        # Handle single values
        elif isinstance(evaluated_result, (int, float, Decimal)):
            if isinstance(evaluated_result, Decimal):
                return f"{int(float(evaluated_result))}"
            else:
                return f"{int(evaluated_result)}"
        
        # Default string representation
        return str(evaluated_result)
        
    except Exception as e:
        print(f"Error formatting result: {e}")
        return str(result)

# Tools
@tool
def execute_sql_query(query: SQLQUERY) -> str:
    """
    Useful tool to execute a SQL query against the database and get results. You must call this tool after each generated SQL query.
    Input must be a syntactically valid SQL query.
    """

    print(f"CONSOLE: Executing SQL query:\n{query.sql_query}")
    raw_query = query.sql_query.strip()
    # if it's a Price query, enforce DISTINCT and exclude zeros
    if re.match(r"(?i)^SELECT\s+Price", raw_query):
        # add DISTINCT
        if not re.search(r"(?i)^SELECT\s+DISTINCT", raw_query):
            raw_query = re.sub(r"(?i)^SELECT\s+", "SELECT DISTINCT ", raw_query)
        # inject Price > 0
        if re.search(r"(?i)\bWHERE\b", raw_query):
            raw_query = re.sub(r"(?i)\bWHERE\b", "WHERE Price > 0 AND", raw_query)
        else:
            raw_query = raw_query.replace(
                "FROM quotesresponses",
                "FROM quotesresponses WHERE Price > 0"
            )
    print(f"CONSOLE: Modified SQL query:\n{raw_query}")
    db = dbc.get_db()
    execute_query_tool = QuerySQLDatabaseTool(db=db)
    raw_result = execute_query_tool.invoke(raw_query)
    print(f"CONSOLE: SQL query result: {raw_result}")
    
    # Format the result for better display
    formatted_result = format_sql_result(raw_result)
    print(f"CONSOLE: Formatted result: {formatted_result}")
    
    return formatted_result

@tool
def web_search_tool(query: str) -> str:
    """Search the web for current product prices and information. Returns search results with URLs that need to be verified.
    
    Args:
        query: Search query (e.g., "Agilent E4980A current price buy sell")
    """
    response = tavily_client.search(
        query= query,  
        search_depth="advanced", 
        topic="general", 
        include_raw_content= True,
        include_domains= ["used-line.com", "testunlimited.com", "ebay.com"],
        max_results=10,
        )
    response_formatted= [f"Result number {idx}:\nURL: {res['url']}.\n Content:{res['content']}.\n\n\n" for idx, res in enumerate(response["results"])]
    output = "\n\n".join(response_formatted)
    return output


def check_urls(urls, timeout=5):
    """
    Given a list of URLs, check each one and return a list of
    (url, bool) indicating whether the URL is alive (HTTP status 2xx/3xx).
    """
    results = []
    for url in urls:
        try:
            # Use HEAD for efficiency; fallback to GET if HEAD not allowed
            resp = requests.head(url, timeout=timeout)
            is_up = resp.status_code < 400
        except requests.exceptions.RequestException:
            is_up = False
        results.append((url, is_up))
    return results

@tool
def check_urls_status(urls: Optional[list[str]]):
    """Useful tool to check whether the urls are working or not. Use this tool only after `web_search_tool` to verify if there are URLs returned by the search before responding to the user.
    Args:
        urls: A list of URLs to check.
    """
    if urls is None:
        return "No URLs provided for checking. Please, try again and provide the list of urls returned by the `web_search_tool` tool"
    results=[]
    for url, ok in check_urls(urls,):
        status_text = "✅ OK" if ok else "❌ Not working"
        results.append(f"{url}: {status_text}")

    return results



def query_as_list(db_conn, query_str):
    """Executes a SQL query and returns a cleaned list of unique results."""
    if db_conn is None:
        print("Database connection is None")
        return []
    
    try:
        print(f"Executing query: {query_str}")
        res = db_conn.run(query_str)
        print(f"Query result: {res}")
        
        # Handle different result types
        if res is None:
            return []
        
        if isinstance(res, str):
            try:
                # Try to evaluate as literal
                evaluated_res = ast.literal_eval(res)
            except (SyntaxError, ValueError):
                # If evaluation fails, try to parse as simple text
                if res.strip() == "":
                    return []
                # Split by newlines or commas and clean
                items = [item.strip() for item in res.replace('\n', ',').split(',') if item.strip()]
                return list(set(items))
        else:
            evaluated_res = res
        
        # Handle list of tuples or similar structures
        if isinstance(evaluated_res, list):
            # Flatten list of tuples and remove empty strings
            processed_res = []
            for item in evaluated_res:
                if isinstance(item, (tuple, list)):
                    for sub_item in item:
                        if str(sub_item).strip():
                            processed_res.append(str(sub_item).strip())
                else:
                    if str(item).strip():
                        processed_res.append(str(item).strip())
            
            return list(set(processed_res))
        
        # If it's a single value, return as list
        return [str(evaluated_res).strip()] if str(evaluated_res).strip() else []
        
    except Exception as e:
        print(f"Error in query_as_list: {e}")
        return []


def test_database_schema():
    """Test database connection with SQL Server compatible syntax"""
    try:
        db = dbc.get_db()
        if db is not None:
            # Use SQL Server compatible syntax - change LIMIT to TOP
            _ = db.run("SELECT TOP 5 DISTINCT CompanyName FROM quotesresponses")
            return True
    except Exception as e:
        print(f"Database schema test failed: {e}")
        return False

