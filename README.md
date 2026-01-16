# Outrigger SEO & GEO Audit System

Automated SEO and GEO (Generative Engine Optimization) auditing system for outrigger.com that identifies issues and creates tasks in Monday.com for tracking and resolution.

## Overview

This system consists of:
1. **Cloud Run Function** - Parses sitemap, audits pages, creates Monday.com tasks
2. **Admin Dashboard** - Web-based configuration interface hosted on Cloud Storage
3. **Firestore Database** - Stores configuration rules from admin dashboard

## Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                         OUTRIGGER SEO AUDIT                          │
├─────────────────────────────────────────────────────────────────────┤
│                                                                       │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────────┐       │
│  │   Admin      │    │   Cloud Run  │    │    Monday.com    │       │
│  │  Dashboard   │───▶│   Function   │───▶│      Board       │       │
│  │  (Storage)   │    │  (Auditor)   │    │   (Issues)       │       │
│  └──────────────┘    └──────────────┘    └──────────────────┘       │
│         │                   │                                        │
│         │                   │                                        │
│         ▼                   ▼                                        │
│  ┌──────────────┐    ┌──────────────┐                               │
│  │  Firestore   │    │  ScraperAPI  │                               │
│  │  (Config)    │    │ (Cloudflare) │                               │
│  └──────────────┘    └──────────────┘                               │
│                                                                       │
└─────────────────────────────────────────────────────────────────────┘
```

## Components

### 1. Cloud Run Function (`main.py`)
The core audit function that:
- Parses the Outrigger sitemap for recently modified pages
- Performs 18+ SEO/GEO checks on each page
- Creates issues in Monday.com with detailed descriptions
- Loads configuration from Firestore admin dashboard

### 2. Admin Dashboard (`admin/index.html`)
A web-based configuration interface hosted on Google Cloud Storage:
- **SEO/GEO Rules**: Configure which checks to enable/disable
- **Voice & Tone**: Set guidelines for content analysis
- **Brand Standards**: Define brand consistency rules

**URL**: https://storage.googleapis.com/outrigger-audit-admin/index.html

### 3. Firestore Database
Stores configuration from the admin dashboard:
- `seoRules` collection - SEO check configurations
- `voiceRules` collection - Voice/tone guidelines
- `brandStandards` collection - Brand standards

## SEO/GEO Checks Performed

### Tier 1: Critical
| Check | Severity | Description |
|-------|----------|-------------|
| Missing page title | Critical | Page has no `<title>` tag |
| Title too short | High | Title is less than 30 characters |
| Missing meta description | Critical | No meta description tag |
| Meta description too short | High | Meta description under 120 characters |
| Missing H1 tag | Critical | Page has no H1 heading |
| Missing canonical tag | Critical | No canonical URL specified |
| Missing Hotel/LocalBusiness schema | Critical | No Hotel or LocalBusiness structured data |
| Missing address in schema | Critical | Schema exists but no address/location |

### Tier 2: High Priority (GEO/LLM)
| Check | Severity | Description |
|-------|----------|-------------|
| Missing Organization schema | High | No Organization/Corporation schema |
| Missing FAQ schema | High | FAQ content without FAQPage schema |
| Missing Review/Rating schema | High | No AggregateRating or Review schema |
| Thin content | High | Page has less than 300 words |
| Missing geo meta tags | High | No geo.region or geo.placename tags |
| Missing Open Graph image | High | No og:image for social sharing |

### Tier 3: Medium Priority
| Check | Severity | Description |
|-------|----------|-------------|
| Missing alt tags | Medium | Images without alt text |
| Missing BreadcrumbList schema | Medium | No breadcrumb structured data |
| Multiple H1 tags | Low | Page has more than one H1 |
| Missing robots meta tag | Low | No robots directive |
| Missing Speakable schema | Medium | No voice search optimization |

## URLs

| Resource | URL |
|----------|-----|
| Admin Dashboard | https://storage.googleapis.com/outrigger-audit-admin/index.html |
| Cloud Run Service | https://outrigger-seo-audit-22338575803.us-central1.run.app |
| Config Endpoint | https://outrigger-seo-audit-22338575803.us-central1.run.app?config=true |
| Test Endpoint | https://outrigger-seo-audit-22338575803.us-central1.run.app?test=true |

## API Endpoints

### GET /
Health check and status
```json
{
  "status": "healthy",
  "service": "outrigger-seo-audit",
  "scraper_api_configured": true,
  "firestore_connected": true
}
```

### GET /?config=true
View loaded configuration from Firestore
```json
{
  "status": "config",
  "firestore_connected": true,
  "seo_rules": 3,
  "voice_rules": 0,
  "brand_standards": 0,
  "rules_detail": {...}
}
```

### GET /?test=true
Test Monday.com column detection and create a test item

### POST /
Run the full SEO audit
```json
{
  "status": "success",
  "results": {
    "pages": 20,
    "issues": 45,
    "tasks_created": 42,
    "duplicates_skipped": 3,
    "config_loaded": true,
    "rules_used": {"seo": 3, "voice": 0, "brand": 0}
  }
}
```

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `MONDAY_API_TOKEN` | Yes | Monday.com API token for authentication |
| `MONDAY_BOARD_ID` | No | Monday.com board ID (defaults to 18395774522) |
| `SCRAPER_API_KEY` | Yes | ScraperAPI key for bypassing Cloudflare |
| `FIRESTORE_PROJECT_ID` | No | Firebase project ID (defaults to project-85d26db5-f70f-487e-b0e) |

## Deployment

### Cloud Run (Auto-deployed via Cloud Build)
Pushing to the `main` branch triggers automatic deployment:
```bash
git add . && git commit -m "Your message" && git push origin main
```

### Admin Dashboard (Manual upload)
```bash
gsutil cp admin/index.html gs://outrigger-audit-admin/index.html
```

### Cloud Scheduler (Weekly Run)
- **Job Name**: `outrigger-seo-audit-weekly`
- **Schedule**: `0 9 * * 4` (Every Thursday at 9:00 AM)
- **Timezone**: America/Los_Angeles

## Project Structure

```
outrigger-seo-audit/
├── main.py              # Main Cloud Run function
├── requirements.txt     # Python dependencies
├── Dockerfile          # Container configuration
├── cloudbuild.yaml     # Cloud Build CI/CD configuration
├── admin/
│   └── index.html      # Admin dashboard (hosted on Cloud Storage)
└── README.md           # This file
```

## Firebase/Firestore Setup

The Cloud Run service account needs `Cloud Datastore User` role to access Firestore:

1. Go to IAM & Admin in GCP Console
2. Find the compute service account: `22338575803-compute@developer.gserviceaccount.com`
3. Grant the `Cloud Datastore User` role

## Monday.com Board Columns

| Column | Type | Content |
|--------|------|---------|
| Task | Name | Issue title |
| Page URL | Link | Full URL of the affected page |
| Issue Description | Long Text | Detailed explanation and fix instructions |
| Severity | Status | Critical, High, Medium, or Low |

## Brand Colors

The admin dashboard uses Outrigger brand colors:
- **Teal**: #006272
- **Gold**: #c4a35a
- **Sunset Orange**: #e07c3e

## Version History

- **v1.0** (Jan 15, 2026): Initial release with basic SEO checks
- **v2.0** (Jan 16, 2026): Added ScraperAPI integration for Cloudflare bypass
- **v3.0** (Jan 16, 2026): Comprehensive SEO/GEO checks (18+), duplicate detection
- **v4.0** (Jan 16, 2026): Admin dashboard with Firestore integration

## Troubleshooting

### Firestore Permission Error (403)
Grant `Cloud Datastore User` role to the compute service account in IAM.

### Cloudflare Challenge Page
Check ScraperAPI key is configured and has credits.

### Columns Not Populating
Check column names match expected patterns in Monday.com board.

### Viewing Logs
```bash
gcloud logging read "resource.type=cloud_run_revision AND resource.labels.service_name=outrigger-seo-audit" --limit=100
```

Or in Cloud Console: Cloud Run > outrigger-seo-audit > Logs

## License

Proprietary - Outrigger Hotels & Resorts
