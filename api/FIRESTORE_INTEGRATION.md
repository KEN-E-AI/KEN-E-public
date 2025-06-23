# Firestore Integration

This document describes the Google Firestore integration added to the Kene API, providing endpoints for working with Google Cloud Firestore.

## Dependencies

The Firestore integration requires the following packages (already included in pyproject.toml):
- `google-cloud-firestore` - Google Cloud Firestore client library

## Environment Variables

Add the following environment variables to your `.env` file:

```bash
# Google Cloud Firestore Configuration
# Path to Google Cloud service account key JSON file
GOOGLE_APPLICATION_CREDENTIALS=./google-cloud-service-account-key.json
# Google Cloud project ID
GOOGLE_CLOUD_PROJECT_ID=your-google-cloud-project-id
# Firestore database ID (default: "(default)")
FIRESTORE_DATABASE_ID=(default)
```

## Service Account Setup

To use Firestore, you need to set up authentication with a Google Cloud service account:

1. Go to the Google Cloud Console (https://console.cloud.google.com/)
2. Select your project or create a new one
3. Navigate to "IAM & Admin" > "Service Accounts"
4. Create a new service account or use an existing one
5. Add the "Cloud Datastore User" or "Firestore Service Account" role
6. Create and download a JSON key file
7. Save the JSON file as `google-cloud-service-account-key.json` in your project root

## API Endpoints

All Firestore endpoints are available under `/api/v1/firestore/`:

### Document Operations

- **POST** `/api/v1/firestore/documents` - Create a new document
- **GET** `/api/v1/firestore/documents/{collection}/{document_id}` - Get a document by ID
- **PUT** `/api/v1/firestore/documents/{collection}/{document_id}` - Update a document
- **DELETE** `/api/v1/firestore/documents/{collection}/{document_id}` - Delete a document

### Query Operations

- **POST** `/api/v1/firestore/documents/query` - Query documents with filters
- **GET** `/api/v1/firestore/collections/{collection}/documents` - List all documents in a collection

### KPI Settings Operations

- **GET** `/api/v1/firestore/kpi-settings/{account_id}/{kpi_name}` - Get a specific KPI setting
- **PUT** `/api/v1/firestore/kpi-settings` - Update a KPI setting
- **GET** `/api/v1/firestore/kpi-settings/{account_id}` - Get all KPI settings for an account

### Funnel Steps Operations

- **POST** `/api/v1/firestore/funnel-steps` - Create a new funnel step
- **GET** `/api/v1/firestore/funnel-steps/{account_id}/{funnel_type}` - List all funnel steps for a funnel
- **GET** `/api/v1/firestore/funnel-steps/{account_id}/{funnel_type}/{funnel_step_num}` - Get a specific funnel step
- **PUT** `/api/v1/firestore/funnel-steps/{account_id}/{funnel_type}/{funnel_step_num}` - Update a funnel step
- **DELETE** `/api/v1/firestore/funnel-steps/{account_id}/{funnel_type}/{funnel_step_num}` - Delete a funnel step

### Channel Operations

- **POST** `/api/v1/firestore/channels` - Create a new channel within a funnel step
- **GET** `/api/v1/firestore/channels/{channel_name}` - Get a specific channel within a funnel step
- **GET** `/api/v1/firestore/channels` - List all channels within a funnel step
- **PUT** `/api/v1/firestore/channels/{channel_name}` - Update a channel within a funnel step
- **DELETE** `/api/v1/firestore/channels/{channel_name}` - Delete a channel within a funnel step

### Tactic Operations

- **POST** `/api/v1/firestore/tactics` - Create a new tactic within a channel
- **GET** `/api/v1/firestore/tactics/{tactic_name}` - Get a specific tactic within a channel
- **GET** `/api/v1/firestore/tactics` - List all tactics within a channel
- **PUT** `/api/v1/firestore/tactics/{tactic_name}` - Update a tactic within a channel
- **DELETE** `/api/v1/firestore/tactics/{tactic_name}` - Delete a tactic within a channel

### Health Check

- **GET** `/api/v1/firestore/health` - Check Firestore service health

## Usage Examples

### Create a Document

```bash
curl -X POST "http://localhost:8000/api/v1/firestore/documents" \
  -H "Content-Type: application/json" \
  -d '{
    "account_id": "user123",
    "collection": "users",
    "document_id": "user123",
    "data": {
      "name": "John Doe",
      "email": "john@example.com",
      "created_at": "2024-01-01T00:00:00Z"
    }
  }'
```

### Get a Document

```bash
curl "http://localhost:8000/api/v1/firestore/documents/users/user123?account_id=user123"
```

### Query Documents

```bash
curl -X POST "http://localhost:8000/api/v1/firestore/documents/query" \
  -H "Content-Type: application/json" \
  -d '{
    "account_id": "user123",
    "collection": "users",
    "field": "status",
    "operator": "==",
    "value": "active",
    "limit": 10
  }'
```

### Update a Document

```bash
curl -X PUT "http://localhost:8000/api/v1/firestore/documents/users/user123?account_id=user123" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "John Smith",
    "updated_at": "2024-01-02T00:00:00Z"
  }'
```

### Delete a Document

```bash
curl -X DELETE "http://localhost:8000/api/v1/firestore/documents/users/user123?account_id=user123"
```

### Get a Specific KPI Setting

```bash
curl "http://localhost:8000/api/v1/firestore/kpi-settings/account123/income_kpi"
```

### Update a KPI Setting

```bash
curl -X PUT "http://localhost:8000/api/v1/firestore/kpi-settings" \
  -H "Content-Type: application/json" \
  -d '{
    "account_id": "account123",
    "kpi_name": "marketing_cost_kpi",
    "metric_id": "metric456"
  }'
```

### Get All KPI Settings for an Account

```bash
curl "http://localhost:8000/api/v1/firestore/kpi-settings/account123"
```

**Valid KPI Names:**
- `income_kpi`
- `marketing_cost_kpi`
- `net_income_kpi`

## KPI Settings Data Structure

The KPI settings are stored in the `customer-database` Firestore database with the following structure:

- **Database:** `customer-database`
- **Collection:** `organizations`
- **Document ID:** `3RVmprzASztrmfpY0ipE`

The data path for KPI settings is:
```
document.accounts[<account_id>].account_settings.overview_kpis[<kpi_name>] = <metric_id>
```

### Example Document Structure:
```json
{
  "accounts": {
    "account123": {
      "account_settings": {
        "overview_kpis": {
          "income_kpi": "metric456",
          "marketing_cost_kpi": "metric789",
          "net_income_kpi": "metric123"
        }
      }
    }
  }
}
```

## Funnel Steps Data Structure

Funnel steps are stored in the same `customer-database` with the following structure:

### Organization Funnel Path:
```
document.accounts[<account_id>].funnels.organization[<funnel_step_num>]
```

### Big Bet Funnel Path:
```
document.accounts[<account_id>].funnels.big_bets[<big_bet_name>][<funnel_step_num>]
```

### Example Document Structure:
```json
{
  "accounts": {
    "account123": {
      "account_settings": {
        "overview_kpis": {
          "income_kpi": "metric456",
          "marketing_cost_kpi": "metric789",
          "net_income_kpi": "metric123"
        }
      },
      "funnels": {
        "organization": {
          "1": {
            "funnel_step_name": "awareness",
            "effectiveness_kpi": "metric123",
            "efficiency_kpi": "metric456",
            "objective": "Increase brand awareness"
          },
          "2": {
            "funnel_step_name": "consideration",
            "effectiveness_kpi": "metric789",
            "efficiency_kpi": "metric101",
            "objective": "Drive consideration"
          }
        },
        "big_bets": {
          "new_product_launch": {
            "1": {
              "funnel_step_name": "awareness",
              "effectiveness_kpi": "metric555",
              "efficiency_kpi": "metric666",
              "objective": "Create awareness for new product"
            }
          }
        }
      }
    }
  }
}
```

## Channel Operations

### Create a Channel

```bash
curl -X POST "http://localhost:8000/api/v1/firestore/channels?account_id=account123&funnel_type=organization&funnel_step_num=1" \
  -H "Content-Type: application/json" \
  -d '{
    "channel_name": "email_marketing",
    "effectiveness_kpi": "metric123",
    "efficiency_kpi": "metric456",
    "supporting_metrics": ["metric789", "metric101", "metric202"]
  }'
```

### Create a Channel (Big Bet Funnel)

```bash
curl -X POST "http://localhost:8000/api/v1/firestore/channels?account_id=account123&funnel_type=big_bet&funnel_step_num=1&big_bet_name=new_product_launch" \
  -H "Content-Type: application/json" \
  -d '{
    "channel_name": "social_media",
    "effectiveness_kpi": "metric567",
    "efficiency_kpi": "metric890",
    "supporting_metrics": ["metric111", "metric222"]
  }'
```

### List All Channels in a Funnel Step

```bash
# Organization funnel
curl "http://localhost:8000/api/v1/firestore/channels?account_id=account123&funnel_type=organization&funnel_step_num=1"

# Big bet funnel
curl "http://localhost:8000/api/v1/firestore/channels?account_id=account123&funnel_type=big_bet&funnel_step_num=1&big_bet_name=new_product_launch"
```

### Get a Specific Channel

```bash
curl "http://localhost:8000/api/v1/firestore/channels/email_marketing?account_id=account123&funnel_type=organization&funnel_step_num=1"
```

### Update a Channel

```bash
curl -X PUT "http://localhost:8000/api/v1/firestore/channels/email_marketing?account_id=account123&funnel_type=organization&funnel_step_num=1" \
  -H "Content-Type: application/json" \
  -d '{
    "effectiveness_kpi": "metric999",
    "supporting_metrics": ["metric789", "metric101", "metric303"]
  }'
```

### Delete a Channel

```bash
curl -X DELETE "http://localhost:8000/api/v1/firestore/channels/email_marketing?account_id=account123&funnel_type=organization&funnel_step_num=1"
```

## Tactic Operations

### Create a Tactic

```bash
curl -X POST "http://localhost:8000/api/v1/firestore/tactics?account_id=account123&funnel_type=organization&funnel_step_num=1&channel_name=email_marketing" \
  -H "Content-Type: application/json" \
  -d '{
    "tactic_name": "email_campaign",
    "effectiveness_kpi": "metric123",
    "efficiency_kpi": "metric456",
    "supporting_metrics": ["metric789", "metric101", "metric202"]
  }'
```

### Create a Tactic (Big Bet Funnel)

```bash
curl -X POST "http://localhost:8000/api/v1/firestore/tactics?account_id=account123&funnel_type=big_bet&funnel_step_num=1&channel_name=social_media&big_bet_name=new_product_launch" \
  -H "Content-Type: application/json" \
  -d '{
    "tactic_name": "instagram_ads",
    "effectiveness_kpi": "metric567",
    "efficiency_kpi": "metric890",
    "supporting_metrics": ["metric111", "metric222"]
  }'
```

### List All Tactics in a Channel

```bash
# Organization funnel
curl "http://localhost:8000/api/v1/firestore/tactics?account_id=account123&funnel_type=organization&funnel_step_num=1&channel_name=email_marketing"

# Big bet funnel
curl "http://localhost:8000/api/v1/firestore/tactics?account_id=account123&funnel_type=big_bet&funnel_step_num=1&channel_name=social_media&big_bet_name=new_product_launch"
```

### Get a Specific Tactic

```bash
curl "http://localhost:8000/api/v1/firestore/tactics/email_campaign?account_id=account123&funnel_type=organization&funnel_step_num=1&channel_name=email_marketing"
```

### Update a Tactic

```bash
curl -X PUT "http://localhost:8000/api/v1/firestore/tactics/email_campaign?account_id=account123&funnel_type=organization&funnel_step_num=1&channel_name=email_marketing" \
  -H "Content-Type: application/json" \
  -d '{
    "effectiveness_kpi": "metric999",
    "supporting_metrics": ["metric789", "metric101", "metric303"]
  }'
```

### Delete a Tactic

```bash
curl -X DELETE "http://localhost:8000/api/v1/firestore/tactics/email_campaign?account_id=account123&funnel_type=organization&funnel_step_num=1&channel_name=email_marketing"
```

## Data Structure in Firestore

The Firestore data is organized in the following structure:

### Organization Collection Structure
```
organizations/
└── kene_organizations/
    └── accounts/
        └── {account_id}/
            ├── account_settings/
            │   └── overview_kpis/
            │       ├── income_kpi: "metric_id"
            │       ├── marketing_cost_kpi: "metric_id"
            │       └── net_income_kpi: "metric_id"
            └── funnels/
                ├── organization/
                │   └── {funnel_step_num}/
                │       ├── funnel_step_name: "string"
                │       ├── effectiveness_kpi: "metric_id"
                │       ├── efficiency_kpi: "metric_id"
                │       ├── objective: "string"
                │       └── channels/
                │           └── {channel_name}/
                │               ├── effectiveness_kpi: "metric_id"
                │               ├── efficiency_kpi: "metric_id"
                │               ├── supporting_metrics: ["metric_id", ...]
                │               └── tactics/
                │                   └── {tactic_name}/
                │                       ├── effectiveness_kpi: "metric_id"
                │                       ├── efficiency_kpi: "metric_id"
                │                       └── supporting_metrics: ["metric_id", ...]
                └── big_bets/
                    └── {big_bet_name}/
                        └── {funnel_step_num}/
                            ├── funnel_step_name: "string"
                            ├── effectiveness_kpi: "metric_id"
                            ├── efficiency_kpi: "metric_id"
                            ├── objective: "string"
                            └── channels/
                                └── {channel_name}/
                                    ├── effectiveness_kpi: "metric_id"
                                    ├── efficiency_kpi: "metric_id"
                                    ├── supporting_metrics: ["metric_id", ...]
                                    └── tactics/
                                        └── {tactic_name}/
                                            ├── effectiveness_kpi: "metric_id"
                                            ├── efficiency_kpi: "metric_id"
                                            └── supporting_metrics: ["metric_id", ...]
```

### Channel Data Structure

Each channel contains the following fields:
- **effectiveness_kpi** (string): Metric ID for effectiveness calculation within the channel
- **efficiency_kpi** (string): Metric ID for efficiency calculation within the channel and funnel step  
- **supporting_metrics** (array): List of metric IDs for evaluating channel performance

### Tactic Data Structure

Each tactic contains the following fields:
- **effectiveness_kpi** (string): Metric ID for effectiveness calculation within the tactic
- **efficiency_kpi** (string): Metric ID for efficiency calculation within the tactic  
- **supporting_metrics** (array): List of metric IDs for evaluating tactic performance

### Path Examples

**KPI Settings:**
- Organization income KPI: `accounts[account123].account_settings.overview_kpis[income_kpi]`

**Funnel Steps:**
- Organization funnel step 1: `accounts[account123].funnels.organization[1]`
- Big bet funnel step 2: `accounts[account123].funnels.big_bets[new_product_launch][2]`

**Channels:**
- Organization funnel channel: `accounts[account123].funnels.organization[1].channels[email_marketing]`
- Big bet funnel channel: `accounts[account123].funnels.big_bets[new_product_launch][1].channels[social_media]`

**Tactics:**
- Organization funnel tactic: `accounts[account123].funnels.organization[1].channels[email_marketing].tactics[email_campaign]`
- Big bet funnel tactic: `accounts[account123].funnels.big_bets[new_product_launch][1].channels[social_media].tactics[instagram_ads]`
