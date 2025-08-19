import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
from search_history import search_history_manager
import plotly.express as px
import plotly.graph_objects as go

def render_search_history_sidebar():
    """Render the search history section in the sidebar."""
    
    with st.sidebar:
        st.markdown("---")
        st.markdown("### 📊 Search History")
        
        # Get basic statistics
        stats = search_history_manager.get_statistics()
        
        if stats.get('total_searches', 0) > 0:
            # Display quick stats
            col1, col2 = st.columns(2)
            with col1:
                st.metric("Total Searches", stats.get('total_searches', 0))
                st.metric("Unique Brands", stats.get('unique_brands', 0))
            with col2:
                st.metric("With Prices", stats.get('searches_with_prices', 0))
                st.metric("Last 7 Days", stats.get('recent_searches', 0))
            
            # Quick actions
            if st.button("📖 View Full History", use_container_width=True):
                st.session_state.show_history = True
            
            if st.button("📊 View Analytics", use_container_width=True):
                st.session_state.show_analytics = True
            
            # Export option
            if st.button("📥 Export CSV", use_container_width=True):
                export_search_history()
            
            # Clear history option
            if st.button("🗑️ Clear History", use_container_width=True, type="secondary"):
                clear_search_history()
        
        else:
            st.info("No search history yet. Start by asking questions!")

def render_search_history_main():
    """Render the main search history interface."""
    
    if st.session_state.get('show_history', False):
        st.header("📊 Search History")
        
        # Filters
        with st.expander("🔍 Filter Options", expanded=True):
            col1, col2, col3, col4 = st.columns(4)
            
            with col1:
                brand_filter = st.text_input("Brand Filter", placeholder="e.g., Agilent")
            
            with col2:
                model_filter = st.text_input("Model Filter", placeholder="e.g., E5071C")
            
            with col3:
                days_back = st.selectbox(
                    "Time Period",
                    [7, 30, 90, 365, None],
                    format_func=lambda x: f"Last {x} days" if x else "All time"
                )
            
            with col4:
                records_per_page = st.selectbox("Records per page", [10, 25, 50, 100], index=1)
        
        # Calculate date filter
        date_from = None
        if days_back:
            date_from = datetime.now() - timedelta(days=days_back)
        
        # Pagination
        if 'history_page' not in st.session_state:
            st.session_state.history_page = 0
        
        # Get filtered history
        history = search_history_manager.get_search_history(
            limit=records_per_page,
            offset=st.session_state.history_page * records_per_page,
            brand_filter=brand_filter if brand_filter else None,
            model_filter=model_filter if model_filter else None,
            date_from=date_from
        )
        
        if history:
            # Pagination controls
            col1, col2, col3 = st.columns([1, 2, 1])
            with col1:
                if st.button("◀ Previous", disabled=st.session_state.history_page == 0):
                    st.session_state.history_page -= 1
                    st.rerun()
            
            with col2:
                st.write(f"Page {st.session_state.history_page + 1}")
            
            with col3:
                if st.button("Next ▶", disabled=len(history) < records_per_page):
                    st.session_state.history_page += 1
                    st.rerun()
            
            # Display history records
            for i, record in enumerate(history):
                with st.expander(
                    f"🔍 {record['timestamp'][:16]} - {record['user_query'][:60]}{'...' if len(record['user_query']) > 60 else ''}"
                ):
                    render_history_record(record)
        
        else:
            st.info("No search history found matching your filters.")
        
        # Back button
        if st.button("← Back to Chat"):
            st.session_state.show_history = False
            st.rerun()

def render_history_record(record):
    """Render a single history record."""
    
    col1, col2 = st.columns([2, 1])
    
    with col1:
        st.markdown(f"**Query:** {record['user_query']}")
        
        if record['product_brand'] or record['product_model']:
            st.markdown(f"**Product:** {record['product_brand'] or 'Unknown'} {record['product_model'] or ''}")
        
        # Price information
        if record['price_details']:
            print("Price details found inside search_history_ui:\n", record['price_details'])  # Debugging line
            prices = [p for p in record['price_details']]
            if len(prices) == 1:
                st.markdown(f"**Price:** ${prices[0]}")
            else:
                st.markdown(f"**Price Range:** ${min(prices)} - ${max(prices)} ({len(prices)} prices)")
        
        # Vendors
        if record['vendors']:
            st.markdown(f"**Vendors:** {', '.join(record['vendors'])}")
        
        # URLs
        if record['verified_urls']:
            st.markdown(f"**Working URLs:** {len(record['verified_urls'])}")
            for url in record['verified_urls']:  # Show first 10 URLs
                st.markdown(f"  - [{url}]({url})")
            if len(record['verified_urls']) > 10:
                st.markdown(f"  - ... and {len(record['verified_urls']) - 3} more")
        if record['notes']:
            st.markdown(f"**Additional notes:** {record['notes']}")
    
    with col2:
        st.markdown(f"**ID:** {record['record_id']}")
        st.markdown(f"**Source:** {record['source'].title()}")
        st.markdown(f"**Time:** {record['timestamp'][11:19]}")
        
        # Re-run query button
        if st.button(f"🔄 Re-run", key=f"rerun_{record['record_id']}"):
            rerun_query(record['user_query'])

def render_analytics():
    """Render search history analytics."""
    
    if st.session_state.get('show_analytics', False):
        st.header("📊 Search Analytics")
        
        # Get comprehensive history for analysis
        history = search_history_manager.get_search_history(limit=1000)
        
        if not history:
            st.info("No data available for analytics.")
            return
        
        # Convert to DataFrame for easier analysis
        df_data = []
        for record in history:
            df_data.append({
                'timestamp': pd.to_datetime(record['timestamp']),
                'brand': record['product_brand'] or 'Unknown',
                'model': record['product_model'] or 'Unknown',
                'source': record['source'],
                'price_count': len(record['price_details']),
                'url_count': len(record['verified_urls']),
                'vendor_count': len(record['vendors']),
                'has_prices': len(record['price_details']) > 0
            })
        
        df = pd.DataFrame(df_data)
        
        # Time-based analysis
        st.subheader("📈 Search Activity Over Time")
        
        # Daily search counts
        daily_counts = df.groupby(df['timestamp'].dt.date).size()
        fig_timeline = px.line(
            x=daily_counts.index, 
            y=daily_counts.values,
            title="Daily Search Activity",
            labels={'x': 'Date', 'y': 'Number of Searches'}
        )
        st.plotly_chart(fig_timeline, use_container_width=True)
        
        # Brand analysis
        col1, col2 = st.columns(2)
        
        with col1:
            st.subheader("🏷️ Most Searched Brands")
            brand_counts = df['brand'].value_counts().head(10)
            if len(brand_counts) > 0:
                fig_brands = px.bar(
                    x=brand_counts.values,
                    y=brand_counts.index,
                    orientation='h',
                    title="Top Brands by Search Count"
                )
                st.plotly_chart(fig_brands, use_container_width=True)
        
        with col2:
            st.subheader("📊 Search Sources")
            source_counts = df['source'].value_counts()
            fig_sources = px.pie(
                values=source_counts.values,
                names=source_counts.index,
                title="Search Source Distribution"
            )
            st.plotly_chart(fig_sources, use_container_width=True)
        
        # Success metrics
        st.subheader("✅ Search Success Metrics")
        
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            searches_with_prices = df['has_prices'].sum()
            st.metric(
                "Searches with Prices",
                f"{searches_with_prices}/{len(df)}",
                f"{searches_with_prices/len(df)*100:.1f}%"
            )
        
        with col2:
            avg_urls = df['url_count'].mean()
            st.metric("Avg URLs per Search", f"{avg_urls:.1f}")
        
        with col3:
            avg_vendors = df['vendor_count'].mean()
            st.metric("Avg Vendors per Search", f"{avg_vendors:.1f}")
        
        with col4:
            unique_brands = df['brand'].nunique()
            st.metric("Unique Brands", unique_brands)
        
        # Back button
        if st.button("← Back to Chat"):
            st.session_state.show_analytics = False
            st.rerun()

def export_search_history():
    """Export search history to CSV."""
    try:
        with st.spinner("Exporting search history..."):
            filename = search_history_manager.export_to_csv()
            
            if filename:
                # Read the file for download
                with open(filename, 'rb') as f:
                    csv_data = f.read()
                
                st.download_button(
                    label="📥 Download CSV",
                    data=csv_data,
                    file_name=filename,
                    mime="text/csv",
                    use_container_width=True
                )
                
                st.success(f"Search history exported successfully!")
            else:
                st.error("Failed to export search history.")
                
    except Exception as e:
        st.error(f"Export failed: {e}")

def clear_search_history():
    """Clear search history with confirmation."""
    if 'confirm_clear' not in st.session_state:
        st.session_state.confirm_clear = False
    
    if not st.session_state.confirm_clear:
        st.warning("⚠️ This will permanently delete all search history!")
        col1, col2 = st.columns(2)
        with col1:
            if st.button("✅ Confirm Delete", type="primary"):
                st.session_state.confirm_clear = True
                st.rerun()
        with col2:
            if st.button("❌ Cancel"):
                pass
    else:
        success = search_history_manager.clear_history()
        if success:
            st.success("Search history cleared successfully!")
            st.session_state.confirm_clear = False
        else:
            st.error("Failed to clear search history.")

def rerun_query(query: str):
    """Re-run a historical query."""
    # Add the query to the chat input
    st.session_state.rerun_query = query
    st.session_state.show_history = False
    st.success(f"Re-running query: {query}")
    st.rerun()