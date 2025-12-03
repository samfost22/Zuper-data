"""
NetSuite Integration Validator

Validates that completed jobs with line items have the required
NetSuite Saleorder ID custom field populated.
"""

from typing import List, Dict, Any, Optional
from datetime import datetime


class NetSuiteValidator:
    """
    Validator for NetSuite integration compliance.

    Identifies completed jobs that have line items (products) but are
    missing the NetSuite Saleorder ID custom field.
    """

    NETSUITE_FIELD_NAME = "NetSuite Saleorder ID"
    COMPLETED_STATUS_TYPE = "COMPLETE"

    def __init__(self, client):
        """
        Initialize the validator with a ZuperClient instance.

        Args:
            client: An initialized ZuperClient instance
        """
        self.client = client

    @staticmethod
    def job_has_line_items(job: Dict[str, Any]) -> bool:
        """
        Check if a job has line items (products).

        Args:
            job: Job data dictionary

        Returns:
            True if the job has at least one product/line item
        """
        products = job.get("products", [])
        return len(products) > 0

    @staticmethod
    def job_is_completed(job: Dict[str, Any]) -> bool:
        """
        Check if a job has completed status.

        Args:
            job: Job data dictionary

        Returns:
            True if the job's current status type is COMPLETE
        """
        current_status = job.get("current_job_status", {})
        status_type = current_status.get("status_type", "").upper()
        return status_type == NetSuiteValidator.COMPLETED_STATUS_TYPE

    @staticmethod
    def get_netsuite_id(job: Dict[str, Any]) -> Optional[str]:
        """
        Get the NetSuite Saleorder ID from a job's custom fields.

        Args:
            job: Job data dictionary

        Returns:
            The NetSuite Saleorder ID value, or None if not found/empty
        """
        custom_fields = job.get("custom_fields", [])

        for field in custom_fields:
            if field.get("label") == NetSuiteValidator.NETSUITE_FIELD_NAME:
                value = field.get("value", "")
                # Return None if empty or whitespace only
                if value and value.strip():
                    return value.strip()
                return None

        return None

    @staticmethod
    def job_missing_netsuite_id(job: Dict[str, Any]) -> bool:
        """
        Check if a job is missing the NetSuite Saleorder ID.

        Args:
            job: Job data dictionary

        Returns:
            True if the NetSuite Saleorder ID is missing or empty
        """
        return NetSuiteValidator.get_netsuite_id(job) is None

    def is_flagged_job(self, job: Dict[str, Any]) -> bool:
        """
        Determine if a job should be flagged.

        A job is flagged if:
        1. It has completed status (status_type = COMPLETE)
        2. It has line items (products)
        3. It is missing the NetSuite Saleorder ID

        Args:
            job: Job data dictionary

        Returns:
            True if the job meets all flagging criteria
        """
        return (
            self.job_is_completed(job) and
            self.job_has_line_items(job) and
            self.job_missing_netsuite_id(job)
        )

    def get_flagged_jobs(
        self,
        from_date: Optional[str] = None,
        to_date: Optional[str] = None,
        **kwargs,
    ) -> List[Dict[str, Any]]:
        """
        Fetch and return all flagged jobs.

        Args:
            from_date: Start date filter (YYYY-MM-DD format)
            to_date: End date filter (YYYY-MM-DD format)
            **kwargs: Additional filters to pass to get_all_jobs

        Returns:
            List of jobs that meet the flagging criteria
        """
        flagged_jobs = []

        # Default to YTD if no dates provided
        if from_date is None:
            from_date = f"{datetime.now().year}-01-01"
        if to_date is None:
            to_date = datetime.now().strftime("%Y-%m-%d")

        # Iterate through all jobs in the date range
        for job in self.client.iter_all_jobs(
            count=100,
            from_date=from_date,
            to_date=to_date,
            **kwargs,
        ):
            # Need full job details to check custom fields and products
            try:
                job_details = self.client.get_job_details(job.get("job_uid"))
                full_job = job_details.get("data", {})

                if self.is_flagged_job(full_job):
                    flagged_jobs.append(full_job)
            except Exception:
                # Skip jobs we can't fetch details for
                continue

        return flagged_jobs

    @staticmethod
    def format_job_for_display(job: Dict[str, Any], base_url: str = "") -> Dict[str, Any]:
        """
        Format a job for dashboard display.

        Args:
            job: Job data dictionary
            base_url: Base URL for constructing job links

        Returns:
            Dictionary with formatted display fields
        """
        job_uid = job.get("job_uid", "")
        work_order = job.get("work_order_number", "N/A")

        # Get customer info
        customer = job.get("customer", "")
        if isinstance(customer, dict):
            customer_name = customer.get("customer_name", customer.get("name", "N/A"))
        else:
            customer_name = str(customer) if customer else "N/A"

        # Get job title
        job_title = job.get("job_title", "N/A")

        # Get status info
        current_status = job.get("current_job_status", {})
        status_name = current_status.get("status_name", "N/A")

        # Get product count
        products = job.get("products", [])
        product_count = len(products)

        # Get completed date from job_status history
        completed_at = "N/A"
        for status in job.get("job_status", []):
            if status.get("status_type", "").upper() == "COMPLETE":
                completed_at = status.get("created_at", "N/A")
                break

        # Construct job URL
        job_url = f"{base_url}/jobs/{job_uid}" if base_url else job_uid

        return {
            "work_order_number": work_order,
            "job_uid": job_uid,
            "job_title": job_title,
            "customer": customer_name,
            "status": status_name,
            "line_items": product_count,
            "completed_at": completed_at,
            "job_url": job_url,
        }
