#!/usr/bin/env python3
"""
Example script to fetch jobs from Zuper API.

Usage:
    python fetch_jobs.py

Environment Variables:
    ZUPER_API_KEY: Your Zuper API key
    ZUPER_BASE_URL: (Optional) Base URL for Zuper API
"""

import os
import json
from datetime import datetime, timedelta

# Add parent directory to path for imports
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from zuper_connector import ZuperClient, ZuperAPIError


def main():
    # Get API key from environment or use directly
    api_key = os.environ.get("ZUPER_API_KEY", "0c73f76f734550cab45861cfaa4939d8")
    base_url = os.environ.get("ZUPER_BASE_URL")

    # Initialize client
    client = ZuperClient(api_key=api_key, base_url=base_url)

    try:
        # Example 1: Get first page of jobs
        print("=" * 60)
        print("Fetching first page of jobs...")
        print("=" * 60)

        response = client.get_all_jobs(page=1, limit=10)

        jobs = response.get("data", [])
        pagination = response.get("pagination", {})

        print(f"Total jobs: {pagination.get('total_records', 'N/A')}")
        print(f"Total pages: {pagination.get('total_pages', 'N/A')}")
        print(f"Current page: {pagination.get('current_page', 'N/A')}")
        print(f"Jobs on this page: {len(jobs)}")
        print()

        # Display job summaries
        for job in jobs:
            job_uid = job.get("job_uid", "N/A")
            job_title = job.get("job_title", job.get("title", "N/A"))
            status = job.get("job_status", job.get("status", "N/A"))
            created_at = job.get("created_at", "N/A")

            print(f"  - [{job_uid}] {job_title}")
            print(f"    Status: {status} | Created: {created_at}")

        print()

        # Example 2: Get jobs from the last 30 days
        print("=" * 60)
        print("Fetching jobs from the last 30 days...")
        print("=" * 60)

        today = datetime.now()
        thirty_days_ago = today - timedelta(days=30)

        response = client.get_all_jobs(
            page=1,
            limit=10,
            from_date=thirty_days_ago.strftime("%Y-%m-%d"),
            to_date=today.strftime("%Y-%m-%d"),
            sort="DESC",
            sort_by="created_at"
        )

        jobs = response.get("data", [])
        print(f"Found {len(jobs)} jobs in the last 30 days")
        print()

        # Example 3: Iterate through all jobs (with limit for demo)
        print("=" * 60)
        print("Iterating through jobs (first 5 for demo)...")
        print("=" * 60)

        count = 0
        for job in client.iter_all_jobs(limit=5):
            count += 1
            job_uid = job.get("job_uid", "N/A")
            print(f"  {count}. Job UID: {job_uid}")

            if count >= 5:
                print("  ... (stopping at 5 for demo)")
                break

        print()

        # Example 4: Get specific job details (if we have any jobs)
        if jobs:
            print("=" * 60)
            print("Fetching details for first job...")
            print("=" * 60)

            first_job_uid = jobs[0].get("job_uid")
            if first_job_uid:
                job_details = client.get_job_details(first_job_uid)
                print(f"Job Details for {first_job_uid}:")
                print(json.dumps(job_details, indent=2, default=str)[:1000])
                if len(json.dumps(job_details)) > 1000:
                    print("... (truncated)")

        print()
        print("=" * 60)
        print("Done!")
        print("=" * 60)

    except ZuperAPIError as e:
        print(f"API Error: {e}")
        if e.response:
            print(f"Response: {json.dumps(e.response, indent=2)}")
    finally:
        client.close()


if __name__ == "__main__":
    main()
