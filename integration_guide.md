# Search Results History Feature - Integration Guide

## Overview

This guide provides complete instructions for integrating the Search Results History feature into your InsightAgentBot project. The feature provides persistent logging, analytics, and export capabilities for all agent interactions.

## Files Structure

```
project/
├── app.py (updated)
├── agent.py (existing)
├── database_connection.py (existing)
├── tools.py (existing)
├── search_history.py (new)
├── search_history_ui.py (new)
├── browser_storage.py (new)
└── requirements.txt (updated)
```

## Installation Steps

### 1. Add Required Dependencies

Update your `requirements.txt` file:

```txt
streamlit
langchain
langchain-openai
langchain-community
langchain-google-genai
pyodbc
pandas
plotly
tavily-python
uuid
```

### 2. File Integration

1. **Replace your existing `app.py`** with the updated version provided
2. **Add the new files**:
   - `search_history.py`
   - `search_history_ui.py`
   - `browser_storage.py`

### 3. Import Updates

Ensure these imports are added to your main `app.py`:

```python
from search_history import search_history_manager
from search_history_ui import render_search_history_tab, render_history_sidebar, get_search_stats_for_sidebar
```

## Key Features Implemented

### 1. **Persistent Browser Storage**
- Uses localStorage for data persistence across page refreshes
- Automatic fallback to session state
- Storage size management (limited to 100 entries)

### 2. **Intelligent Data Parsing**
- Extracts product brands and models from user queries
- Identifies pricing information from agent responses
- Detects vendors and URLs
- Categorizes data sources (database, web, mixed)

### 3. **Comprehensive Analytics**
- Search frequency tracking
- Brand and model popularity
- Vendor analysis
- Source distribution
- Time-based trends

### 4. **Advanced Filtering**
- Filter by brand, model, source
- Date range filtering
- Real-time search within history

### 5. **Export Capabilities**
- CSV export with all structured data
- JSON export for programmatic access
- Customizable date ranges

### 6. **User Interface**
- Dedicated history tab
- Sidebar integration with recent searches
- Expandable search entries
- One-click query re-running

## Usage Examples

### Basic Usage

The feature automatically logs every agent interaction. Users can:

1. **View History**: Navigate to the "Search History" tab
2. **Filter Results**: Use the filters section to narrow down searches
3. **Re-run Queries**: Click "Re-run Query" button on any historical entry
4. **Export Data**: Use the Export tab to download history in CSV/JSON format

### Advanced Analytics

Access detailed analytics including:
- Daily search trends
- Most searched brands/models
- Vendor frequency analysis
- Source distribution charts

### Data Export

```python
# Export recent history
history = search_history_manager.load_history_from_browser()
recent_searches = history[:10]  # Last 10 searches

# Export with filters
filtered_history = search_history_manager.get_filtered_history(
    brand_filter="Apple",
    date_from=datetime.now() - timedelta(days=7)
)
```

## Configuration Options

### Storage Limits

Modify storage limits in `browser_storage.py`:

```python
# Change maximum entries stored
if len(st.session_state.search_history) > 200:  # Increase from 100
    st.session_state.search_history = st.session_state.search_history[:200]
```

### Parsing Patterns

Customize brand/model extraction in `search_history.py`:

```python
# Add new brand patterns
brand_patterns = [
    r'\b(Apple|Samsung|YourBrand)\b',
    # Add more patterns here
]
```

### Analytics Customization

Modify analytics tracking in `search_history_ui.py`:

```python
# Add custom metrics
def render_analytics_view(history):
    # Add your custom analytics here
    pass
```

## Browser Storage Details

### Data Structure

Each search entry contains:

```json
{
  "record_id": "uuid-string",
  "timestamp": "2025-01-26T10:30:00",
  "user_query": "What is the price of iPhone 15?",
  "product_brand": "Apple",
  "product_model": "iPhone 15",
  "price_details": ["$999.00", "$899.00"],
  "vendors": ["amazon.com", "bestbuy.com"],
  "verified_urls": ["https://amazon.com/..."],
  "source": "database + web",
  "notes": "Detailed response",
  "raw_response": "Full agent response text..."
}
```

### Storage Keys

- `insight_agent_search_history`: Main search history array
- `insight_agent_analytics`: Analytics summary data

### Browser Compatibility

The localStorage implementation works in all modern browsers. For older browsers, the system gracefully falls back to session-only storage.

## Troubleshooting

### Common Issues

1. **History Not Persisting**
   - Check browser localStorage is enabled
   - Verify no browser extensions are blocking localStorage
   - Clear browser cache and reload

2. **Large Storage Usage**
   - Reduce entry limit in `browser_storage.py`
   - Implement automatic cleanup of old entries

3. **Parsing Issues**
   - Update regex patterns in `parse_agent_response()`
   - Add debug logging to see what's being extracted

### Debug Mode

Enable debug logging by adding to your code:

```python
import logging
logging.basicConfig(level=logging.DEBUG)

# In search_history.py
print(f"Parsed data: {parsed_data}")
```

## Security Considerations

1. **Data Privacy**: All data stays in user's browser localStorage
2. **No Server Storage**: No sensitive data transmitted to servers
3. **Automatic Cleanup**: Old entries are automatically removed
4. **Export Control**: Users control their own data export

## Performance Optimization

1. **Lazy Loading**: History loads only when accessed
2. **Pagination**: Large histories are paginated for performance
3. **Efficient Storage**: JSON compression minimizes storage size
4. **Memory Management**: Session state is cleaned regularly

## Future Enhancements

Potential improvements you can implement:

1. **Cloud Sync**: Add optional cloud backup
2. **Advanced Search**: Full-text search within responses
3. **Data Visualization**: More detailed charts and graphs
4. **API Integration**: Connect with external analytics services
5. **Machine Learning**: Pattern recognition in search behavior

## Support

For issues or questions:

1. Check the browser console for JavaScript errors
2. Verify all imports are working correctly
3. Test with a clean browser profile
4. Review the session state in Streamlit

The implementation is designed to be robust and handle edge cases gracefully, providing a seamless user experience while maintaining data integrity.