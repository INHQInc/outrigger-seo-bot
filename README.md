# Outrigger SEO & GEO Audit System

Automated SEO and GEO auditing system for outrigger.com that runs weekly, identifies issues, and creates tasks in Monday.com for tracking and resolution.

## Overview

This Cloud Run function:
1. Parses the outrigger.com sitemap for pages updated in the last 7 days
2. Audits each page for 18+ SEO/GEO issues
3. Creates tasks in Monday.com with detailed issue information
4. Runs automatically every Thursday at 9 AM via Cloud Scheduler

## SEO/GEO Checks Performed

### Basic SEO (6 checks)
| Check | Severity | Description |
|-------|----------|-------------|
| Missing page title | High | Page has no `<title>` tag |
| Title too short | Medium | Title is less than 30 characters |
| Missing meta description | High | No meta description tag |
| Meta description too short | Medium | Meta description under 120 characters |
| Missing H1 tag | Medium | Page has no H1 heading |
| Multiple H1 tags | Low | Page has more than one H1 |

### Technical SEO (2 checks)
| Check | Severity | Description |
|-------|----------|-------------|
| Missing canonical tag | Medium | No canonical URL specified |
| Missing robots meta tag | Low | No robots directive |

### Open Graph / Social (3 checks)
| Check | Severity | Description |
|-------|----------|-------------|
| Missing og:title | Medium | No Open Graph title for social sharing |
| Missing og:description | Medium | No Open Graph description |
| Missing og:image | Medium | No Open Graph image |

### Image Accessibility (1 check)
| Check | Severity | Description |
|-------|----------|-------------|
| Missing alt tags | Medium | Images without alt text (lists individual filenames, up to 5 per page) |

### Schema/Structured Data (6 checks)
| Check | Severity | Description |
|-------|----------|-------------|
| No JSON-LD structured data | High | Page has no schema markup |
| Missing Organization schema | Medium | No Organization/Corporation schema |
| Missing LocalBusiness/Hotel schema | High | No LocalBusiness or Hotel schema (critical for hotels) |
| Missing BreadcrumbList schema | Low | No breadcrumb structured data |
| Missing Hotel schema on hotel pages | High | Hotel/room pages without Hotel/LodgingBusiness schema |
| Missing address in schema | Medium | Schema exists but no address/location |

### GEO/Local SEO (1 check)
| Check | Severity | Description |
|-------|----------|-------------|
| Missing geo meta tags | Low | No geo.region or geo.placename tags |

### Conditional Checks
| Check | Severity | Description |
|-------|----------|-------------|
| FAQ content without FAQPage schema | Low | Page has FAQ elements but no FAQ schema |

## Architecture

```
┌─────────────────────┐     ┌──────────────────┐     ┌─────────────────┐
│  Cloud Scheduler    │────▶│  Cloud Run       │────▶│  Monday.com     │
│  (Weekly Thursday)  │     │  Function        │     │  Board          │
└─────────────────────┘     └──────────────────┘     └─────────────────┘
                                    │
                                    ▼
                            ┌──────────────────┐
                            │  ScraperAPI      │
                            │  (Cloudflare     │
                            │   bypass)        │
                            └──────────────────┘
                                    │
                                    ▼
                            ┌──────────────────┐
                            │  outrigger.com   │
                            │  sitemap.xml     │
                            └──────────────────┘
```

## Monday.com Board Columns

The system populates these columns in your Monday.com board:

| Column | Type | Content |
|--------|------|---------|
| Task | Name | Issue title + page identifier |
| Issue Description | Long Text | Detailed explanation of the issue and how to fix it |
| Issue Type | Text | Category of the issue (e.g., "Missing Meta", "Missing Alt Tags") |
| Page URL | Link/Text | Full URL of the affected page |
| Date Found | Date | Date the issue was detected |
| Status | Status | Set to "Open" by default |
| Person | People | Left empty for manual assignment |

## Deployment Details

### Google Cloud Project
- **Project ID**: `project-85d26db5-f70f-487e-b0e`
- **Region**: us-central1 (Iowa)

### Cloud Run Function
- **Service URL**: `https://outrigger-seo-audit-22338575803.us-central1.run.app`
- **Entry Point**: `hello_http`
- **Runtime**: Python 3.11
- **Memory**: 256 MB
- **Timeout**: 60 seconds

### Cloud Scheduler
- **Job Name**: `outrigger-seo-audit-weekly`
- **Schedule**: `0 9 * * 4` (Every Thursday at 9:00 AM)
- **Timezone**: America/Los_Angeles
- **HTTP Method**: POST

### Monday.com Integration
- **Board ID**: `18395774522`
- **Board Name**: SEO & GEO Weekly Audit

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `MONDAY_API_TOKEN` | Yes | Monday.com API token for authentication |
| `MONDAY_BOARD_ID` | No | Monday.com board ID (defaults to 18395774522) |
| `SCRAPER_API_KEY` | Yes | ScraperAPI key for bypassing Cloudflare protection |

## Features

### Duplicate Detection
The system checks for existing items in Monday.com before creating new tasks. If an issue with the same title already exists, it's skipped to prevent duplicate entries.

### Cloudflare Bypass
Uses ScraperAPI to bypass Cloudflare protection on outrigger.com, ensuring reliable page fetching.

### Dynamic Column Mapping
Automatically detects Monday.com board column IDs and types, adapting to different column configurations.

### Individual Image Tracking
When images are missing alt tags, each image filename is listed individually (up to 5 per page), making it easy to identify and fix specific images.

### Severity Levels
Issues are categorized by severity:
- **High**: Critical SEO issues that significantly impact rankings
- **Medium**: Important issues that should be addressed
- **Low**: Minor issues or best practice recommendations

## File Structure

```
outrigger-seo-audit/
├── main.py              # Main Cloud Function code
├── requirements.txt     # Python dependencies
├── Dockerfile          # Container configuration
├── cloudbuild.yaml     # CI/CD configuration
├── deploy.sh           # Deployment script
├── README.md           # This file
├── .gitignore          # Git ignore rules
├── .gcloudignore       # Cloud ignore rules
├── config/             # Configuration files
├── src/                # Additional source files
└── tests/              # Test files
```

## API Endpoints

### GET /
Health check endpoint.

**Response:**
```json
{
  "status": "healthy",
  "service": "outrigger-seo-audit",
  "scraper_api_configured": true
}
```

### POST /
Trigger an audit run.

**Response:**
```json
{
  "status": "success",
  "results": {
    "pages": 20,
    "issues": 45,
    "tasks_created": 42,
    "duplicates_skipped": 3
  }
}
```

## Deployment Commands

### Deploy to Cloud Run
```bash
gcloud functions deploy outrigger-seo-audit \
  --gen2 \
  --runtime=python311 \
  --region=us-central1 \
  --source=. \
  --entry-point=hello_http \
  --trigger-http \
  --allow-unauthenticated \
  --set-env-vars MONDAY_API_TOKEN=your-token-here,SCRAPER_API_KEY=your-key-here
```

### Create Cloud Scheduler Job
```bash
gcloud scheduler jobs create http outrigger-seo-audit-weekly \
  --location=us-central1 \
  --schedule="0 9 * * 4" \
  --time-zone="America/Los_Angeles" \
  --uri="https://outrigger-seo-audit-22338575803.us-central1.run.app" \
  --http-method=POST
```

### Test the Function (Force Run)
```bash
curl -X POST https://outrigger-seo-audit-22338575803.us-central1.run.app
```

## Dependencies

```
requests>=2.31.0
beautifulsoup4>=4.12.0
lxml>=4.9.0
html5lib>=1.1
gql>=3.5.0
requests-toolbelt>=1.0.0
functions-framework>=3.5.0
google-cloud-secret-manager>=2.18.0
python-dateutil>=2.8.2
pytz>=2024.1
aiohttp>=3.9.0
google-cloud-logging>=3.9.0
```

## Troubleshooting

### Common Issues

1. **"Not authenticated" from Monday.com**
   - Regenerate your Monday.com API token
   - Ensure the token has write permissions
   - Update the `MONDAY_API_TOKEN` environment variable

2. **"Cloudflare challenge page" in logs**
   - Check ScraperAPI key is configured
   - Verify ScraperAPI account has credits
   - Check the `SCRAPER_API_KEY` environment variable

3. **Columns not populating**
   - Check column names match expected patterns
   - Review logs for "Found columns:" message
   - Ensure column types are compatible (text, long_text, link, date, status)

4. **No pages found in sitemap**
   - Verify sitemap URL is accessible
   - Check if pages have been updated in the last 7 days
   - Review logs for sitemap parsing errors

### Viewing Logs

**Via Google Cloud Console:**
Cloud Run > outrigger-seo-audit > Observability > Logs

**Via CLI:**
```bash
gcloud logging read "resource.type=cloud_run_revision AND resource.labels.service_name=outrigger-seo-audit" --limit=100
```

## Monitoring

- **Cloud Run Logs**: Google Cloud Console > Cloud Run > outrigger-seo-audit > Logs
- **Scheduler Logs**: Google Cloud Console > Cloud Scheduler > outrigger-seo-audit-weekly
- **Monday.com Board**: Check board ID 18395774522 for created tasks

## Issue Descriptions

The system provides detailed descriptions for each issue type to help developers understand and fix the problems:

| Issue Type | Description |
|------------|-------------|
| missing_title | The page is missing a `<title>` tag. This is critical for SEO as the title appears in search results and browser tabs. |
| short_title | The page title is less than 30 characters. Titles should be 50-60 characters for optimal SEO. |
| missing_meta | The page is missing a meta description. This description appears in search results and affects click-through rates. |
| short_meta | The meta description is less than 120 characters. Optimal length is 150-160 characters for search results. |
| missing_canonical | The page is missing a canonical tag. This helps prevent duplicate content issues and consolidates ranking signals. |
| missing_og_title | The page is missing an Open Graph title (og:title). This affects how the page appears when shared on social media. |
| missing_og_image | The page is missing an Open Graph image (og:image). Social shares without images get significantly less engagement. |
| missing_alt_tags | Images on this page are missing alt tags. Alt tags are important for accessibility and image SEO. |
| missing_schema | The page has no JSON-LD structured data. Schema markup helps search engines understand page content. |
| missing_localbusiness_schema | The page is missing LocalBusiness schema. This is critical for local SEO and Google Maps visibility. |
| missing_hotel_schema | The page is missing Hotel or LodgingBusiness schema. This is essential for hotel/resort pages. |

## Version History

- **v1.0** (Jan 15, 2026): Initial release with basic SEO checks
- **v2.0** (Jan 16, 2026): Added ScraperAPI integration for Cloudflare bypass
- **v3.0** (Jan 16, 2026): Added comprehensive SEO/GEO checks (18+ checks), duplicate detection, dynamic column mapping, individual image alt tag tracking

## License

Proprietary - Outrigger Hotels & Resorts

## Support

Contact the development team for support or feature requests.
