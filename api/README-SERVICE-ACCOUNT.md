# Google Cloud Service Account Setup

## Service Account Key File

The file `google-cloud-service-account-key.json` has been created from the template. 

**IMPORTANT**: 
- This file contains placeholder values and needs to be updated with your actual Google Cloud service account credentials
- This file is automatically ignored by git and will NOT be checked into version control
- Download your actual service account key from Google Cloud Console and replace the placeholder content

## How to get your service account key:

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Navigate to IAM & Admin > Service Accounts
3. Create a new service account or select an existing one
4. Click on the service account name
5. Go to the "Keys" tab
6. Click "Add Key" > "Create new key" 
7. Choose "JSON" format
8. Download the file and replace the content of `google-cloud-service-account-key.json`

## Required permissions:

Your service account needs the following roles:
- Cloud Datastore User (for Firestore access)
- Or custom permissions: `datastore.entities.*`
