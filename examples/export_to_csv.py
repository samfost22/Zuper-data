#!/usr/bin/env python3
"""
Example script to export Zuper jobs to CSV.

Usage:
    python export_to_csv.py [output_file.csv]

Environment Variables:
    ZUPER_API_KEY: Your Zuper API key
    ZUPER_BASE_URL: (Optional) Base URL for Zuper API
"""

import os
import csv
import sys
from datetime import datetime

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from zuper_connector import ZuperClient, ZuperAPIError


def flatten_job(job: dict) -> dict:
    """Flatten nested job data for CSV export."""
    flat = {}

    # Basic fields
    flat["job_uid"] = job.get("job_uid", "")
    flat["job_title"] = job.get("job_title", job.get("title", ""))
    flat["job_status"] = job.get("job_status", job.get("status", ""))
    flat["priority"] = job.get("priority", "")
    flat["created_at"] = job.get("created_at", "")
    flat["updated_at"] = job.get("updated_at", "")
    flat["scheduled_start_time"] = job.get("scheduled_start_time", "")
    flat["scheduled_end_time"] = job.get("scheduled_end_time", "")
    flat["actual_start_time"] = job.get("actual_start_time", "")
    flat["actual_end_time"] = job.get("actual_end_time", "")

    # Customer info
    customer = job.get("customer", {})
    if isinstance(customer, dict):
        flat["customer_uid"] = customer.get("customer_uid", "")
        flat["customer_name"] = customer.get("customer_name", customer.get("name", ""))
        flat["customer_email"] = customer.get("email", "")
    else:
        flat["customer_uid"] = customer if customer else ""
        flat["customer_name"] = ""
        flat["customer_email"] = ""

    # Location info
    location = job.get("customer_address", job.get("location", {}))
    if isinstance(location, dict):
        flat["address"] = location.get("street", location.get("address", ""))
        flat["city"] = location.get("city", "")
        flat["state"] = location.get("state", "")
        flat["zip_code"] = location.get("zip_code", location.get("postal_code", ""))
    else:
        flat["address"] = str(location) if location else ""
        flat["city"] = ""
        flat["state"] = ""
        flat["zip_code"] = ""

    # Assigned user
    assigned_to = job.get("assigned_to", job.get("users", []))
    if isinstance(assigned_to, list) and assigned_to:
        first_user = assigned_to[0]
        if isinstance(first_user, dict):
            flat["assigned_user_uid"] = first_user.get("user_uid", "")
            flat["assigned_user_name"] = first_user.get("name", first_user.get("full_name", ""))
        else:
            flat["assigned_user_uid"] = str(first_user)
            flat["assigned_user_name"] = ""
    else:
        flat["assigned_user_uid"] = ""
        flat["assigned_user_name"] = ""

    # Job category
    category = job.get("job_category", job.get("category", ""))
    if isinstance(category, dict):
        flat["job_category"] = category.get("category_name", category.get("name", ""))
    else:
        flat["job_category"] = str(category) if category else ""

    # Notes
    flat["notes"] = job.get("notes", job.get("description", ""))

    return flat


def main():
    # Get output filename from args or use default
    output_file = sys.argv[1] if len(sys.argv) > 1 else "zuper_jobs_export.csv"

    # Get API key from environment or use directly
    api_key = os.environ.get("ZUPER_API_KEY", "0c73f76f734550cab45861cfaa4939d8")
    base_url = os.environ.get("ZUPER_BASE_URL")

    # Initialize client
    client = ZuperClient(api_key=api_key, base_url=base_url)

    try:
        print(f"Exporting Zuper jobs to {output_file}...")

        # Define CSV columns
        columns = [
            "job_uid",
            "job_title",
            "job_status",
            "priority",
            "job_category",
            "customer_uid",
            "customer_name",
            "customer_email",
            "address",
            "city",
            "state",
            "zip_code",
            "assigned_user_uid",
            "assigned_user_name",
            "scheduled_start_time",
            "scheduled_end_time",
            "actual_start_time",
            "actual_end_time",
            "created_at",
            "updated_at",
            "notes",
        ]

        # Open CSV file and write
        with open(output_file, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=columns, extrasaction="ignore")
            writer.writeheader()

            job_count = 0
            for job in client.iter_all_jobs(limit=100):
                flat_job = flatten_job(job)
                writer.writerow(flat_job)
                job_count += 1

                # Progress indicator
                if job_count % 100 == 0:
                    print(f"  Exported {job_count} jobs...")

        print(f"Successfully exported {job_count} jobs to {output_file}")

    except ZuperAPIError as e:
        print(f"API Error: {e}")
        sys.exit(1)
    finally:
        client.close()


if __name__ == "__main__":
    main()
