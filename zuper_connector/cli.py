"""
Command-line interface for Zuper Connector.

Usage:
    zuper jobs [--count=N] [--status=STATUS] [--from=DATE] [--to=DATE]
    zuper job <job_uid>
    zuper customers [--count=N]
    zuper export <output_file> [--from=DATE] [--to=DATE]
    zuper test
"""

import argparse
import json
import os
import sys
from datetime import datetime

from .client import ZuperClient
from .exceptions import ZuperAPIError, ZuperAuthError


def get_client():
    """Get a configured Zuper client from environment variables."""
    api_key = os.environ.get("ZUPER_API_KEY")
    if not api_key:
        print("Error: ZUPER_API_KEY environment variable not set.")
        print("Set it with: export ZUPER_API_KEY='your_api_key'")
        sys.exit(1)

    base_url = os.environ.get("ZUPER_BASE_URL")
    return ZuperClient(api_key=api_key, base_url=base_url)


def cmd_jobs(args):
    """List jobs."""
    client = get_client()

    params = {"count": args.count}
    if args.status:
        params["job_status"] = args.status
    if args.from_date:
        params["from_date"] = args.from_date
    if args.to_date:
        params["to_date"] = args.to_date

    try:
        response = client.get_all_jobs(**params)
        jobs = response.get("data", [])
        total = response.get("total_records", len(jobs))

        print(f"Found {total} jobs (showing {len(jobs)})\n")
        print(f"{'Work Order':<15} {'Status':<15} {'Title':<40} {'UID'}")
        print("-" * 100)

        for job in jobs:
            wo = job.get("work_order_number", "N/A")
            status = job.get("current_job_status", {}).get("status_name", "N/A")
            title = job.get("job_title", "N/A")[:38]
            uid = job.get("job_uid", "N/A")
            print(f"{wo:<15} {status:<15} {title:<40} {uid}")

    except ZuperAuthError as e:
        print(f"Authentication error: {e}")
        sys.exit(1)
    except ZuperAPIError as e:
        print(f"API error: {e}")
        sys.exit(1)


def cmd_job(args):
    """Get job details."""
    client = get_client()

    try:
        response = client.get_job_details(args.job_uid)
        job = response.get("data", {})

        print(json.dumps(job, indent=2, default=str))

    except ZuperAPIError as e:
        print(f"Error: {e}")
        sys.exit(1)


def cmd_customers(args):
    """List customers."""
    client = get_client()

    try:
        response = client.get_customers(limit=args.count)
        customers = response.get("data", [])
        total = response.get("total_records", len(customers))

        print(f"Found {total} customers (showing {len(customers)})\n")
        print(f"{'Name':<30} {'Email':<35} {'UID'}")
        print("-" * 100)

        for cust in customers:
            name = cust.get("customer_name", "N/A")[:28]
            email = cust.get("customer_email", "N/A")[:33]
            uid = cust.get("customer_uid", "N/A")
            print(f"{name:<30} {email:<35} {uid}")

    except ZuperAPIError as e:
        print(f"Error: {e}")
        sys.exit(1)


def cmd_export(args):
    """Export jobs to CSV."""
    client = get_client()

    try:
        import csv
    except ImportError:
        print("Error: csv module not available")
        sys.exit(1)

    params = {"count": 1000}
    if args.from_date:
        params["from_date"] = args.from_date
    if args.to_date:
        params["to_date"] = args.to_date

    try:
        print("Fetching jobs...")
        all_jobs = list(client.iter_all_jobs(**params))
        print(f"Found {len(all_jobs)} jobs")

        if not all_jobs:
            print("No jobs to export.")
            return

        # Determine fields
        fieldnames = [
            "job_uid",
            "work_order_number",
            "job_title",
            "status_name",
            "status_type",
            "customer_name",
            "scheduled_start_time",
            "scheduled_end_time",
            "created_at",
        ]

        with open(args.output_file, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
            writer.writeheader()

            for job in all_jobs:
                row = {
                    "job_uid": job.get("job_uid"),
                    "work_order_number": job.get("work_order_number"),
                    "job_title": job.get("job_title"),
                    "status_name": job.get("current_job_status", {}).get("status_name"),
                    "status_type": job.get("current_job_status", {}).get("status_type"),
                    "customer_name": job.get("customer", {}).get("customer_name")
                    if job.get("customer")
                    else None,
                    "scheduled_start_time": job.get("scheduled_start_time"),
                    "scheduled_end_time": job.get("scheduled_end_time"),
                    "created_at": job.get("created_at"),
                }
                writer.writerow(row)

        print(f"Exported {len(all_jobs)} jobs to {args.output_file}")

    except ZuperAPIError as e:
        print(f"Error: {e}")
        sys.exit(1)


def cmd_test(args):
    """Test API connection."""
    client = get_client()

    print(f"Testing connection to: {client.base_url}")
    print(f"API Key: {client.api_key[:8]}...{client.api_key[-4:]}")
    print()

    try:
        response = client.get_all_jobs(count=1)
        total = response.get("total_records", 0)
        print(f"SUCCESS! Connected to Zuper API.")
        print(f"Total jobs in account: {total}")

    except ZuperAuthError as e:
        print(f"FAILED: Authentication error")
        print(f"  {e}")
        print("\nCheck your API key and try again.")
        sys.exit(1)

    except ZuperAPIError as e:
        print(f"FAILED: API error")
        print(f"  {e}")
        print("\nCheck your base URL region (us/eu/ap).")
        sys.exit(1)


def main():
    """Main entry point for CLI."""
    parser = argparse.ArgumentParser(
        prog="zuper",
        description="Zuper Field Service Management API CLI",
    )
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # jobs command
    jobs_parser = subparsers.add_parser("jobs", help="List jobs")
    jobs_parser.add_argument(
        "--count", "-n", type=int, default=20, help="Number of jobs to fetch"
    )
    jobs_parser.add_argument("--status", "-s", help="Filter by job status")
    jobs_parser.add_argument("--from", dest="from_date", help="From date (YYYY-MM-DD)")
    jobs_parser.add_argument("--to", dest="to_date", help="To date (YYYY-MM-DD)")

    # job command
    job_parser = subparsers.add_parser("job", help="Get job details")
    job_parser.add_argument("job_uid", help="Job UID")

    # customers command
    cust_parser = subparsers.add_parser("customers", help="List customers")
    cust_parser.add_argument(
        "--count", "-n", type=int, default=20, help="Number of customers to fetch"
    )

    # export command
    export_parser = subparsers.add_parser("export", help="Export jobs to CSV")
    export_parser.add_argument("output_file", help="Output CSV file path")
    export_parser.add_argument(
        "--from", dest="from_date", help="From date (YYYY-MM-DD)"
    )
    export_parser.add_argument("--to", dest="to_date", help="To date (YYYY-MM-DD)")

    # test command
    subparsers.add_parser("test", help="Test API connection")

    args = parser.parse_args()

    if args.command is None:
        parser.print_help()
        sys.exit(0)

    commands = {
        "jobs": cmd_jobs,
        "job": cmd_job,
        "customers": cmd_customers,
        "export": cmd_export,
        "test": cmd_test,
    }

    commands[args.command](args)


if __name__ == "__main__":
    main()
