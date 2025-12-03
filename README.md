# Zuper Data Connector

A Python connector for the [Zuper](https://www.zuper.co/) Field Service Management API.

## Features

- Fetch all jobs with pagination and filtering
- Get individual job details
- Get recurring jobs
- Get customers and users
- **Custom fields support** - read and update custom fields on jobs, customers, and assets
- Automatic retry with exponential backoff
- Export jobs to CSV

## Installation

```bash
pip install -r requirements.txt
```

## Quick Start

```python
from zuper_connector import ZuperClient

# Initialize the client
client = ZuperClient(api_key="your_api_key_here")

# Get all jobs (first page)
response = client.get_all_jobs(page=1, count=10)
jobs = response.get("data", [])

for job in jobs:
    print(f"Job: {job.get('job_title')} - Status: {job.get('job_status')}")

# Get specific job details
job_details = client.get_job_details("job_uid_here")

# Iterate through all jobs (auto-pagination)
for job in client.iter_all_jobs():
    print(job.get("job_uid"))
```

## Configuration

### API Key

Get your API key from Zuper:
1. Navigate to **Settings** -> **Developer Hub** -> **API Keys**
2. Click "New API Key" and create one

### Base URL

Zuper is hosted in different regions. Set the appropriate base URL:

| Region | Base URL |
|--------|----------|
| US (default) | `https://us.zuperpro.com/api` |
| EU | `https://eu.zuperpro.com/api` |
| Asia Pacific | `https://ap.zuperpro.com/api` |

```python
client = ZuperClient(
    api_key="your_api_key",
    base_url="https://eu.zuperpro.com/api"  # For EU region
)
```

## API Methods

### `get_all_jobs()`

Fetch jobs with pagination and filtering.

```python
response = client.get_all_jobs(
    page=1,
    count=100,
    sort="DESC",
    sort_by="scheduled_start_time",
    from_date="2024-01-01",
    to_date="2024-12-31",
    job_status="COMPLETED",
    priority="HIGH",
)
```

**Parameters:**
- `page` (int): Page number (default: 1)
- `count` (int): Results per page (default: 100, max: 1000)
- `sort` (str): Sort direction - 'ASC' or 'DESC'
- `sort_by` (str): Field to sort by - 'work_order_number', 'job_priority', 'scheduled_start_time', 'due_date'
- `date_type` (str): Date type for filtering - 'scheduled_date', 'created_date', 'current_status_updated_at'
- `priority` (str): Filter by priority - 'URGENT', 'HIGH', 'MEDIUM', 'LOW'
- `customer` (str): Filter by customer UIDs
- `category` (str): Filter by category UIDs
- `keyword` (str): Search keyword
- `job_status` (str): Filter by job status
- `from_date` (str): Filter by scheduled from date
- `to_date` (str): Filter by scheduled to date
- `assigned_to` (str): Filter by assigned user UIDs
- `asset` (str): Filter by asset UIDs
- `custom_field` (str): Filter by custom field
- `job_type` (str): Filter by job type - 'NEW', 'REVISIT'

### `iter_all_jobs()`

Generator that iterates through all jobs, handling pagination automatically.

```python
for job in client.iter_all_jobs(count=100):
    process_job(job)
```

### `get_job_details(job_uid)`

Get details for a specific job.

```python
job = client.get_job_details("abc123-def456")
```

### `get_recurring_jobs()`

Fetch recurring jobs.

```python
recurring = client.get_recurring_jobs(page=1, limit=50)
```

### `get_customers()` / `get_users()`

Fetch customers or field technicians.

```python
customers = client.get_customers(page=1, limit=100)
users = client.get_users(page=1, limit=100)
```

## Custom Fields

Zuper supports custom fields on jobs, customers, properties, and organizations.

### Get Custom Field Definitions

```python
# Get custom field definitions for jobs
job_fields = client.get_custom_fields(module="JOB")

# Get custom field definitions for customers
customer_fields = client.get_custom_fields(module="CUSTOMER")
```

### Get Custom Field Values

```python
# Get custom fields for a specific job
custom_fields = client.get_job_custom_fields("job_uid_here")

# Get custom fields for a specific customer
custom_fields = client.get_customer_custom_fields("customer_uid_here")
```

### Update Custom Fields

```python
# Update custom fields on a job
client.update_job_custom_fields(
    job_uid="abc123",
    custom_fields=[
        {"label": "Equipment Type", "value": "Tractor"},
        {"label": "Serial Number", "value": "SN-12345"},
    ]
)

# Update custom fields on a customer
client.update_customer_custom_fields(
    customer_uid="abc123",
    custom_fields=[
        {"label": "Account Manager", "value": "John Doe"},
        {"label": "Contract Type", "value": "Premium"},
    ]
)

# Generic method for any module type
client.update_custom_fields(
    module_name="JOB",  # JOB, CUSTOMER, PROPERTY, ORGANIZATION
    module_uid="abc123",
    custom_fields=[
        {"label": "Field Name", "value": "Field Value"},
    ]
)
```

## NetSuite Integration Dashboard

A Streamlit dashboard to identify completed jobs with line items that are missing the "NetSuite Saleorder ID" custom field.

### Running the Dashboard

```bash
# Set your API key
export ZUPER_API_KEY="your_api_key_here"

# Optional: Set region if not US
export ZUPER_BASE_URL="https://eu.zuperpro.com/api"

# Run the dashboard
streamlit run dashboard/netsuite_dashboard.py
```

The dashboard shows:
- Summary metrics (total jobs, flagged jobs, compliance rate)
- Table of flagged jobs with work order numbers and links
- CSV export functionality
- Date range filtering (defaults to year-to-date)

## Examples

### Export Jobs to CSV

```bash
python examples/export_to_csv.py output.csv
```

### Fetch and Display Jobs

```bash
python examples/fetch_jobs.py
```

## Environment Variables

You can set these environment variables instead of passing them to the client:

```bash
export ZUPER_API_KEY="your_api_key_here"
export ZUPER_BASE_URL="https://us.zuperpro.com/api"
```

## Error Handling

```python
from zuper_connector import ZuperClient, ZuperAPIError, ZuperAuthError

try:
    client = ZuperClient(api_key="invalid_key")
    jobs = client.get_all_jobs()
except ZuperAuthError as e:
    print(f"Authentication failed: {e}")
except ZuperAPIError as e:
    print(f"API error: {e}")
```

## License

MIT
