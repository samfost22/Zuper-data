#!/usr/bin/env python3
"""
NetSuite Integration Validation Dashboard

A Streamlit dashboard to identify completed jobs with line items
that are missing the NetSuite Saleorder ID custom field.

Usage:
    streamlit run dashboard/netsuite_dashboard.py

Environment Variables:
    ZUPER_API_KEY: Your Zuper API key
    ZUPER_BASE_URL: (Optional) Base URL for Zuper API
"""

import os
import sys
from datetime import datetime, date
from typing import List, Dict, Any

import streamlit as st
import pandas as pd

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from zuper_connector import ZuperClient, ZuperAPIError
from zuper_connector.validators import NetSuiteValidator


# Page configuration
st.set_page_config(
    page_title="NetSuite Integration Dashboard",
    page_icon="🔍",
    layout="wide",
)


def get_client() -> ZuperClient:
    """Initialize and return a ZuperClient instance."""
    api_key = os.environ.get("ZUPER_API_KEY", "0c73f76f734550cab45861cfaa4939d8")
    base_url = os.environ.get("ZUPER_BASE_URL")
    return ZuperClient(api_key=api_key, base_url=base_url)


def get_zuper_web_url() -> str:
    """Get the Zuper web app URL for job links."""
    # Default to US region web app
    return os.environ.get("ZUPER_WEB_URL", "https://us.zuperpro.com")


@st.cache_data(ttl=300)  # Cache for 5 minutes
def fetch_flagged_jobs(from_date: str, to_date: str) -> List[Dict[str, Any]]:
    """
    Fetch jobs that are flagged for missing NetSuite ID.

    Args:
        from_date: Start date (YYYY-MM-DD)
        to_date: End date (YYYY-MM-DD)

    Returns:
        List of flagged jobs formatted for display
    """
    client = get_client()
    validator = NetSuiteValidator(client)
    web_url = get_zuper_web_url()

    flagged_jobs = []

    try:
        # Get all jobs in date range
        for job in client.iter_all_jobs(
            count=100,
            from_date=from_date,
            to_date=to_date,
        ):
            # Get full job details
            try:
                job_details = client.get_job_details(job.get("job_uid"))
                full_job = job_details.get("data", {})

                if validator.is_flagged_job(full_job):
                    formatted = validator.format_job_for_display(full_job, web_url)
                    flagged_jobs.append(formatted)
            except Exception as e:
                # Skip jobs we can't fetch
                continue

    except ZuperAPIError as e:
        st.error(f"API Error: {e}")
    finally:
        client.close()

    return flagged_jobs


def main():
    """Main dashboard application."""

    # Header
    st.title("🔍 NetSuite Integration Dashboard")
    st.markdown(
        """
        This dashboard identifies **completed jobs with line items** that are
        **missing the NetSuite Saleorder ID** custom field.
        """
    )

    st.divider()

    # Sidebar filters
    st.sidebar.header("Filters")

    # Date range filter - default to YTD
    current_year = datetime.now().year
    default_start = date(current_year, 1, 1)
    default_end = date.today()

    col1, col2 = st.sidebar.columns(2)
    with col1:
        start_date = st.date_input(
            "From Date",
            value=default_start,
            max_value=default_end,
        )
    with col2:
        end_date = st.date_input(
            "To Date",
            value=default_end,
            min_value=start_date,
        )

    # Refresh button
    if st.sidebar.button("🔄 Refresh Data", use_container_width=True):
        st.cache_data.clear()

    st.sidebar.divider()

    # Info section
    st.sidebar.markdown(
        """
        ### Flagging Criteria
        A job is flagged if:
        1. ✅ Status type = **COMPLETE**
        2. ✅ Has **line items** (products)
        3. ❌ Missing **NetSuite Saleorder ID**
        """
    )

    # Main content
    with st.spinner("Fetching jobs from Zuper..."):
        flagged_jobs = fetch_flagged_jobs(
            from_date=start_date.strftime("%Y-%m-%d"),
            to_date=end_date.strftime("%Y-%m-%d"),
        )

    # Summary metrics
    col1, col2, col3 = st.columns(3)

    with col1:
        st.metric(
            label="Flagged Jobs",
            value=len(flagged_jobs),
            help="Jobs missing NetSuite Saleorder ID",
        )

    with col2:
        total_line_items = sum(job.get("line_items", 0) for job in flagged_jobs)
        st.metric(
            label="Total Line Items",
            value=total_line_items,
            help="Total products/services on flagged jobs",
        )

    with col3:
        date_range = f"{start_date.strftime('%b %d')} - {end_date.strftime('%b %d, %Y')}"
        st.metric(
            label="Date Range",
            value=date_range,
        )

    st.divider()

    # Results table
    if flagged_jobs:
        st.subheader(f"⚠️ {len(flagged_jobs)} Jobs Missing NetSuite Saleorder ID")

        # Convert to DataFrame for display
        df = pd.DataFrame(flagged_jobs)

        # Reorder and rename columns for display
        display_columns = {
            "work_order_number": "Work Order #",
            "job_title": "Job Title",
            "customer": "Customer",
            "line_items": "Line Items",
            "status": "Status",
            "completed_at": "Completed At",
            "job_url": "View Job",
        }

        # Select and rename columns
        df_display = df[list(display_columns.keys())].rename(columns=display_columns)

        # Format the job URL as a clickable link
        df_display["View Job"] = df_display["View Job"].apply(
            lambda x: f"[Open]({x})" if x.startswith("http") else x
        )

        # Display the dataframe with clickable links
        st.dataframe(
            df_display,
            use_container_width=True,
            hide_index=True,
            column_config={
                "Work Order #": st.column_config.NumberColumn(format="%d"),
                "Line Items": st.column_config.NumberColumn(format="%d"),
                "View Job": st.column_config.LinkColumn(display_text="Open"),
            },
        )

        # Export option
        st.divider()

        csv = df.to_csv(index=False)
        st.download_button(
            label="📥 Download CSV",
            data=csv,
            file_name=f"netsuite_flagged_jobs_{date.today().isoformat()}.csv",
            mime="text/csv",
        )

    else:
        st.success("✅ No flagged jobs found! All completed jobs with line items have NetSuite Saleorder IDs.")

    # Footer
    st.divider()
    st.caption(
        f"Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} | "
        f"Data cached for 5 minutes"
    )


if __name__ == "__main__":
    main()
