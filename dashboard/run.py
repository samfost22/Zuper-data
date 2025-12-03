"""Run the NetSuite dashboard."""

import os
import sys


def main():
    """Launch the Streamlit dashboard."""
    try:
        import streamlit.web.cli as stcli
    except ImportError:
        print("Error: streamlit not installed.")
        print("Install with: pip install streamlit pandas")
        sys.exit(1)

    # Get the path to the dashboard script
    dashboard_path = os.path.join(os.path.dirname(__file__), "netsuite_dashboard.py")

    if not os.path.exists(dashboard_path):
        print(f"Error: Dashboard not found at {dashboard_path}")
        sys.exit(1)

    # Check for API key
    if not os.environ.get("ZUPER_API_KEY"):
        print("Warning: ZUPER_API_KEY environment variable not set.")
        print("Set it with: export ZUPER_API_KEY='your_api_key'")
        print()

    sys.argv = ["streamlit", "run", dashboard_path, "--server.headless", "true"]
    sys.exit(stcli.main())


if __name__ == "__main__":
    main()
