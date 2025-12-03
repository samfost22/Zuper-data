"""
Zuper API Client

Main client for interacting with the Zuper API.
"""

import time
from typing import Optional, Dict, Any, List, Iterator
from datetime import datetime
import requests

from .exceptions import (
    ZuperAPIError,
    ZuperAuthError,
    ZuperRateLimitError,
    ZuperNotFoundError,
)


class ZuperClient:
    """
    Client for interacting with the Zuper API.

    Args:
        api_key: Your Zuper API key
        base_url: Base URL for the Zuper API (e.g., 'https://us.zuperpro.com/api')
                  If not provided, defaults to US region.
        timeout: Request timeout in seconds (default: 30)
        max_retries: Maximum number of retries for failed requests (default: 3)
    """

    DEFAULT_BASE_URL = "https://us.zuperpro.com/api"

    def __init__(
        self,
        api_key: str,
        base_url: Optional[str] = None,
        timeout: int = 30,
        max_retries: int = 3,
    ):
        self.api_key = api_key
        self.base_url = (base_url or self.DEFAULT_BASE_URL).rstrip("/")
        self.timeout = timeout
        self.max_retries = max_retries
        self.session = requests.Session()
        self.session.headers.update(
            {
                "x-api-key": self.api_key,
                "Content-Type": "application/json",
                "Accept": "application/json",
            }
        )

    def _request(
        self,
        method: str,
        endpoint: str,
        params: Optional[Dict[str, Any]] = None,
        json_data: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Make an HTTP request to the Zuper API with retry logic.

        Args:
            method: HTTP method (GET, POST, PUT, DELETE)
            endpoint: API endpoint (e.g., '/jobs')
            params: Query parameters
            json_data: JSON body for POST/PUT requests

        Returns:
            Response JSON as a dictionary

        Raises:
            ZuperAuthError: If authentication fails
            ZuperRateLimitError: If rate limit is exceeded
            ZuperNotFoundError: If resource is not found
            ZuperAPIError: For other API errors
        """
        url = f"{self.base_url}{endpoint}"

        for attempt in range(self.max_retries):
            try:
                response = self.session.request(
                    method=method,
                    url=url,
                    params=params,
                    json=json_data,
                    timeout=self.timeout,
                )

                # Handle different HTTP status codes
                if response.status_code == 200:
                    return response.json()
                elif response.status_code == 401:
                    raise ZuperAuthError(
                        "Authentication failed. Check your API key.",
                        status_code=401,
                        response=self._safe_json(response),
                    )
                elif response.status_code == 403:
                    raise ZuperAuthError(
                        "Access forbidden. Check your API key permissions.",
                        status_code=403,
                        response=self._safe_json(response),
                    )
                elif response.status_code == 404:
                    raise ZuperNotFoundError(
                        f"Resource not found: {endpoint}",
                        status_code=404,
                        response=self._safe_json(response),
                    )
                elif response.status_code == 429:
                    if attempt < self.max_retries - 1:
                        # Exponential backoff for rate limiting
                        wait_time = 2 ** (attempt + 1)
                        time.sleep(wait_time)
                        continue
                    raise ZuperRateLimitError(
                        "Rate limit exceeded",
                        status_code=429,
                        response=self._safe_json(response),
                    )
                else:
                    response.raise_for_status()

            except requests.exceptions.Timeout:
                if attempt < self.max_retries - 1:
                    wait_time = 2 ** (attempt + 1)
                    time.sleep(wait_time)
                    continue
                raise ZuperAPIError(f"Request timed out after {self.timeout} seconds")

            except requests.exceptions.ConnectionError:
                if attempt < self.max_retries - 1:
                    wait_time = 2 ** (attempt + 1)
                    time.sleep(wait_time)
                    continue
                raise ZuperAPIError("Connection error. Check your network connection.")

            except requests.exceptions.HTTPError as e:
                raise ZuperAPIError(
                    f"HTTP error: {str(e)}",
                    status_code=response.status_code if response else None,
                    response=self._safe_json(response) if response else None,
                )

        raise ZuperAPIError("Max retries exceeded")

    @staticmethod
    def _safe_json(response: requests.Response) -> Optional[Dict]:
        """Safely parse JSON from response."""
        try:
            return response.json()
        except (ValueError, TypeError):
            return None

    def get_all_jobs(
        self,
        page: int = 1,
        limit: int = 100,
        sort: str = "DESC",
        sort_by: str = "created_at",
        from_date: Optional[str] = None,
        to_date: Optional[str] = None,
        status: Optional[str] = None,
        customer_uid: Optional[str] = None,
        user_uid: Optional[str] = None,
        job_category: Optional[str] = None,
        **kwargs,
    ) -> Dict[str, Any]:
        """
        Get all jobs with pagination and filtering.

        Args:
            page: Page number (default: 1)
            limit: Number of results per page (default: 100, max varies by plan)
            sort: Sort direction - 'ASC' or 'DESC' (default: 'DESC')
            sort_by: Field to sort by (default: 'created_at')
            from_date: Start date filter (ISO 8601 format: 'YYYY-MM-DD')
            to_date: End date filter (ISO 8601 format: 'YYYY-MM-DD')
            status: Filter by job status
            customer_uid: Filter by customer UID
            user_uid: Filter by assigned user UID
            job_category: Filter by job category
            **kwargs: Additional query parameters

        Returns:
            Dictionary containing jobs data and pagination info
        """
        params = {
            "page": page,
            "limit": limit,
            "sort": sort,
            "sort_by": sort_by,
        }

        # Add optional filters
        if from_date:
            params["date"] = from_date
        if to_date:
            params["to_date"] = to_date
        if status:
            params["status"] = status
        if customer_uid:
            params["customer_uid"] = customer_uid
        if user_uid:
            params["user_uid"] = user_uid
        if job_category:
            params["job_category"] = job_category

        # Add any additional parameters
        params.update(kwargs)

        return self._request("GET", "/jobs", params=params)

    def iter_all_jobs(
        self,
        limit: int = 100,
        sort: str = "DESC",
        sort_by: str = "created_at",
        from_date: Optional[str] = None,
        to_date: Optional[str] = None,
        **kwargs,
    ) -> Iterator[Dict[str, Any]]:
        """
        Iterate over all jobs, automatically handling pagination.

        This is a generator that yields individual job records.

        Args:
            limit: Number of results per page (default: 100)
            sort: Sort direction - 'ASC' or 'DESC' (default: 'DESC')
            sort_by: Field to sort by (default: 'created_at')
            from_date: Start date filter (ISO 8601 format)
            to_date: End date filter (ISO 8601 format)
            **kwargs: Additional query parameters

        Yields:
            Individual job dictionaries
        """
        page = 1
        while True:
            response = self.get_all_jobs(
                page=page,
                limit=limit,
                sort=sort,
                sort_by=sort_by,
                from_date=from_date,
                to_date=to_date,
                **kwargs,
            )

            jobs = response.get("data", [])
            if not jobs:
                break

            for job in jobs:
                yield job

            # Check if there are more pages
            pagination = response.get("pagination", {})
            total_pages = pagination.get("total_pages", 1)
            if page >= total_pages:
                break

            page += 1

    def get_job_details(self, job_uid: str) -> Dict[str, Any]:
        """
        Get details for a specific job.

        Args:
            job_uid: The unique identifier of the job

        Returns:
            Dictionary containing the job details

        Raises:
            ZuperNotFoundError: If job is not found
        """
        return self._request("GET", f"/jobs/{job_uid}")

    def get_recurring_jobs(
        self,
        page: int = 1,
        limit: int = 100,
        sort: str = "DESC",
        sort_by: str = "created_at",
        **kwargs,
    ) -> Dict[str, Any]:
        """
        Get all recurring jobs with pagination.

        Args:
            page: Page number (default: 1)
            limit: Number of results per page (default: 100)
            sort: Sort direction - 'ASC' or 'DESC' (default: 'DESC')
            sort_by: Field to sort by (default: 'created_at')
            **kwargs: Additional query parameters

        Returns:
            Dictionary containing recurring jobs data and pagination info
        """
        params = {
            "page": page,
            "limit": limit,
            "sort": sort,
            "sort_by": sort_by,
        }
        params.update(kwargs)

        return self._request("GET", "/recurring_jobs", params=params)

    def get_customers(
        self,
        page: int = 1,
        limit: int = 100,
        **kwargs,
    ) -> Dict[str, Any]:
        """
        Get all customers with pagination.

        Args:
            page: Page number (default: 1)
            limit: Number of results per page (default: 100)
            **kwargs: Additional query parameters

        Returns:
            Dictionary containing customers data and pagination info
        """
        params = {
            "page": page,
            "limit": limit,
        }
        params.update(kwargs)

        return self._request("GET", "/customers", params=params)

    def get_users(
        self,
        page: int = 1,
        limit: int = 100,
        **kwargs,
    ) -> Dict[str, Any]:
        """
        Get all users (field technicians) with pagination.

        Args:
            page: Page number (default: 1)
            limit: Number of results per page (default: 100)
            **kwargs: Additional query parameters

        Returns:
            Dictionary containing users data and pagination info
        """
        params = {
            "page": page,
            "limit": limit,
        }
        params.update(kwargs)

        return self._request("GET", "/users", params=params)

    # -------------------------------------------------------------------------
    # Custom Fields Methods
    # -------------------------------------------------------------------------

    def get_custom_fields(
        self,
        module: str = "JOB",
        page: int = 1,
        limit: int = 100,
        **kwargs,
    ) -> Dict[str, Any]:
        """
        Get custom field definitions for a module.

        Args:
            module: The module type - 'JOB', 'CUSTOMER', 'USER', 'ASSET', etc.
                    (default: 'JOB')
            page: Page number (default: 1)
            limit: Number of results per page (default: 100)
            **kwargs: Additional query parameters

        Returns:
            Dictionary containing custom field definitions
        """
        params = {
            "page": page,
            "limit": limit,
            "module": module,
        }
        params.update(kwargs)

        return self._request("GET", "/custom_fields", params=params)

    def get_job_custom_fields(self, job_uid: str) -> Dict[str, Any]:
        """
        Get custom field values for a specific job.

        Args:
            job_uid: The unique identifier of the job

        Returns:
            Dictionary containing the job's custom field values
        """
        job_details = self.get_job_details(job_uid)
        return job_details.get("data", {}).get("custom_fields", {})

    def update_custom_fields(
        self,
        module_name: str,
        module_uid: str,
        custom_fields: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """
        Update custom field values for any module (job, customer, property, organization).

        Args:
            module_name: The module type - 'JOB', 'CUSTOMER', 'PROPERTY', 'ORGANIZATION'
            module_uid: The unique identifier of the entity
            custom_fields: List of custom field updates, each containing:
                - label (required): The custom field label/name
                - value (required): The new value for the field
                - type (optional): Field type
                - ref_uid (optional): Reference UID
                - group_name (optional): Group name for the field
                - group_uid (optional): Group UID

        Returns:
            Dictionary containing the API response

        Example:
            client.update_custom_fields(
                module_name="JOB",
                module_uid="abc123",
                custom_fields=[
                    {"label": "Equipment Type", "value": "Tractor"},
                    {"label": "Serial Number", "value": "SN-12345"},
                ]
            )
        """
        payload = {
            "module_name": module_name,
            "module_uid": module_uid,
            "custom_fields": custom_fields,
        }
        return self._request("PATCH", "/custom_fields", json_data=payload)

    def update_job_custom_fields(
        self,
        job_uid: str,
        custom_fields: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """
        Update custom field values for a job.

        Args:
            job_uid: The unique identifier of the job
            custom_fields: List of custom field updates, each containing:
                - label (required): The custom field label/name
                - value (required): The new value for the field
                - type (optional): Field type
                - group_name (optional): Group name for the field

        Returns:
            Dictionary containing the API response

        Example:
            client.update_job_custom_fields(
                job_uid="abc123",
                custom_fields=[
                    {"label": "Equipment Type", "value": "Tractor"},
                    {"label": "Serial Number", "value": "SN-12345"},
                ]
            )
        """
        return self.update_custom_fields("JOB", job_uid, custom_fields)

    def get_customer_custom_fields(self, customer_uid: str) -> Dict[str, Any]:
        """
        Get custom field values for a specific customer.

        Args:
            customer_uid: The unique identifier of the customer

        Returns:
            Dictionary containing the customer's custom field values
        """
        customer_details = self._request("GET", f"/customers/{customer_uid}")
        return customer_details.get("data", {}).get("custom_fields", {})

    def update_customer_custom_fields(
        self,
        customer_uid: str,
        custom_fields: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """
        Update custom field values for a customer.

        Args:
            customer_uid: The unique identifier of the customer
            custom_fields: List of custom field updates, each containing:
                - label (required): The custom field label/name
                - value (required): The new value for the field

        Returns:
            Dictionary containing the API response

        Example:
            client.update_customer_custom_fields(
                customer_uid="abc123",
                custom_fields=[
                    {"label": "Account Manager", "value": "John Doe"},
                    {"label": "Contract Type", "value": "Premium"},
                ]
            )
        """
        return self.update_custom_fields("CUSTOMER", customer_uid, custom_fields)

    def update_property_custom_fields(
        self,
        property_uid: str,
        custom_fields: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """
        Update custom field values for a property.

        Args:
            property_uid: The unique identifier of the property
            custom_fields: List of custom field updates, each containing:
                - label (required): The custom field label/name
                - value (required): The new value for the field

        Returns:
            Dictionary containing the API response
        """
        return self.update_custom_fields("PROPERTY", property_uid, custom_fields)

    def update_organization_custom_fields(
        self,
        organization_uid: str,
        custom_fields: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """
        Update custom field values for an organization.

        Args:
            organization_uid: The unique identifier of the organization
            custom_fields: List of custom field updates, each containing:
                - label (required): The custom field label/name
                - value (required): The new value for the field

        Returns:
            Dictionary containing the API response
        """
        return self.update_custom_fields("ORGANIZATION", organization_uid, custom_fields)

    def get_asset_custom_fields(self, asset_uid: str) -> Dict[str, Any]:
        """
        Get custom field values for a specific asset.

        Args:
            asset_uid: The unique identifier of the asset

        Returns:
            Dictionary containing the asset's custom field values
        """
        asset_details = self._request("GET", f"/assets/{asset_uid}")
        return asset_details.get("data", {}).get("custom_fields", {})

    def update_asset_custom_fields(
        self,
        asset_uid: str,
        custom_fields: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """
        Update custom field values for an asset.

        Note: Assets may use 'PROPERTY' module type in Zuper's API.
        If this doesn't work, try update_property_custom_fields() instead.

        Args:
            asset_uid: The unique identifier of the asset
            custom_fields: List of custom field updates, each containing:
                - label (required): The custom field label/name
                - value (required): The new value for the field

        Returns:
            Dictionary containing the API response
        """
        # Try ASSET first, but Zuper may use PROPERTY for assets
        payload = {
            "module_name": "ASSET",
            "module_uid": asset_uid,
            "custom_fields": custom_fields,
        }
        return self._request("PATCH", "/custom_fields", json_data=payload)

    def close(self):
        """Close the session."""
        self.session.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
