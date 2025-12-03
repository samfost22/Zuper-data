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
response = client.get_all_jobs(page=1, limit=10)
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
    limit=100,
    sort="DESC",
    sort_by="created_at",
    from_date="2024-01-01",
    to_date="2024-12-31",
    status="completed",
)
```

**Parameters:**
- `page` (int): Page number (default: 1)
- `limit` (int): Results per page (default: 100)
- `sort` (str): Sort direction - 'ASC' or 'DESC'
- `sort_by` (str): Field to sort by
- `from_date` (str): Start date filter (YYYY-MM-DD)
- `to_date` (str): End date filter (YYYY-MM-DD)
- `status` (str): Filter by job status
- `customer_uid` (str): Filter by customer
- `user_uid` (str): Filter by assigned user

### `iter_all_jobs()`

Generator that iterates through all jobs, handling pagination automatically.

```python
for job in client.iter_all_jobs(limit=100):
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
