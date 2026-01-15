#!/bin/bash

# =============================================================================
# Outrigger SEO/GEO Audit - Google Cloud Deployment Script
# =============================================================================
#
# This script sets up the complete Google Cloud infrastructure for the
# SEO/GEO audit system including:
# - Secret Manager for API tokens
# - Cloud Run service
# - Cloud Scheduler for weekly Thursday runs
# - IAM permissions
#
# Prerequisites:
# - Google Cloud SDK (gcloud) installed and authenticated
# - A Google Cloud project with billing enabled
# - Monday.com API token
#
# Usage:
#   ./deploy.sh <PROJECT_ID> <MONDAY_API_TOKEN>
#
# =============================================================================

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Configuration
PROJECT_ID=${1:-""}
MONDAY_API_TOKEN=${2:-""}
REGION="us-central1"
SERVICE_NAME="outrigger-seo-audit"
SCHEDULER_NAME="outrigger-seo-audit-weekly"
SECRET_NAME="monday-api-token"
MONDAY_BOARD_ID="18395774522"

# Validate inputs
if [ -z "$PROJECT_ID" ]; then
    echo -e "${RED}Error: PROJECT_ID is required${NC}"
    echo "Usage: ./deploy.sh <PROJECT_ID> <MONDAY_API_TOKEN>"
    exit 1
fi

if [ -z "$MONDAY_API_TOKEN" ]; then
    echo -e "${RED}Error: MONDAY_API_TOKEN is required${NC}"
    echo "Usage: ./deploy.sh <PROJECT_ID> <MONDAY_API_TOKEN>"
    exit 1
fi

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}Outrigger SEO/GEO Audit Deployment${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo "Project ID: $PROJECT_ID"
echo "Region: $REGION"
echo "Service: $SERVICE_NAME"
echo ""

# Set project
echo -e "${YELLOW}[1/8] Setting Google Cloud project...${NC}"
gcloud config set project $PROJECT_ID

# Enable required APIs
echo -e "${YELLOW}[2/8] Enabling required APIs...${NC}"
gcloud services enable \
    cloudbuild.googleapis.com \
    run.googleapis.com \
    cloudscheduler.googleapis.com \
    secretmanager.googleapis.com \
    containerregistry.googleapis.com

# Create secret for Monday.com API token
echo -e "${YELLOW}[3/8] Creating/updating secret for Monday.com API token...${NC}"
if gcloud secrets describe $SECRET_NAME --project=$PROJECT_ID &>/dev/null; then
    echo "Secret exists, adding new version..."
    echo -n "$MONDAY_API_TOKEN" | gcloud secrets versions add $SECRET_NAME --data-file=-
else
    echo "Creating new secret..."
    echo -n "$MONDAY_API_TOKEN" | gcloud secrets create $SECRET_NAME \
        --replication-policy="automatic" \
        --data-file=-
fi

# Build the container
echo -e "${YELLOW}[4/8] Building container image...${NC}"
gcloud builds submit \
    --tag gcr.io/$PROJECT_ID/$SERVICE_NAME:latest \
    .

# Deploy to Cloud Run
echo -e "${YELLOW}[5/8] Deploying to Cloud Run...${NC}"
gcloud run deploy $SERVICE_NAME \
    --image gcr.io/$PROJECT_ID/$SERVICE_NAME:latest \
    --region $REGION \
    --platform managed \
    --allow-unauthenticated \
    --memory 1Gi \
    --timeout 540s \
    --set-env-vars "MONDAY_BOARD_ID=$MONDAY_BOARD_ID" \
    --set-secrets "MONDAY_API_TOKEN=${SECRET_NAME}:latest"

# Get the service URL
SERVICE_URL=$(gcloud run services describe $SERVICE_NAME \
    --region $REGION \
    --format 'value(status.url)')

echo -e "${GREEN}Service deployed at: $SERVICE_URL${NC}"

# Create Cloud Scheduler job for weekly Thursday runs
echo -e "${YELLOW}[6/8] Setting up Cloud Scheduler for weekly Thursday runs...${NC}"

# Delete existing scheduler if it exists
gcloud scheduler jobs delete $SCHEDULER_NAME \
    --location=$REGION \
    --quiet 2>/dev/null || true

# Create new scheduler job
# Runs every Thursday at 9:00 AM UTC (adjust timezone as needed)
gcloud scheduler jobs create http $SCHEDULER_NAME \
    --location=$REGION \
    --schedule="0 9 * * 4" \
    --uri="${SERVICE_URL}" \
    --http-method=POST \
    --headers="Content-Type=application/json" \
    --message-body='{}' \
    --time-zone="America/Los_Angeles" \
    --description="Weekly SEO/GEO audit for Outrigger.com - runs every Thursday"

# Grant Cloud Run invoker permission to scheduler
echo -e "${YELLOW}[7/8] Setting up IAM permissions...${NC}"
# Get the compute service account
PROJECT_NUMBER=$(gcloud projects describe $PROJECT_ID --format='value(projectNumber)')
COMPUTE_SA="${PROJECT_NUMBER}-compute@developer.gserviceaccount.com"

# Grant secret accessor role to Cloud Run service account
gcloud secrets add-iam-policy-binding $SECRET_NAME \
    --member="serviceAccount:${COMPUTE_SA}" \
    --role="roles/secretmanager.secretAccessor" \
    --project=$PROJECT_ID

echo -e "${YELLOW}[8/8] Verifying deployment...${NC}"

# Test the health endpoint
echo "Testing health endpoint..."
HEALTH_RESPONSE=$(curl -s "${SERVICE_URL}")
echo "Response: $HEALTH_RESPONSE"

echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}Deployment Complete!${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo "Service URL: $SERVICE_URL"
echo ""
echo "The audit will run automatically every Thursday at 9:00 AM Pacific."
echo ""
echo "Manual trigger options:"
echo "  - HTTP POST: curl -X POST $SERVICE_URL"
echo "  - Console: https://console.cloud.google.com/run?project=$PROJECT_ID"
echo "  - Scheduler: https://console.cloud.google.com/cloudscheduler?project=$PROJECT_ID"
echo ""
echo "View logs:"
echo "  gcloud logging read 'resource.type=cloud_run_revision AND resource.labels.service_name=$SERVICE_NAME' --limit=50"
echo ""
