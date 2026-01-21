# Outrigger SEO/GEO Audit System

A comprehensive, LLM-powered SEO and GEO (Generative Engine Optimization) audit system for Outrigger Hotels & Resorts. This system automatically audits web pages against configurable rules and creates tasks in Monday.com for issues found.

## Table of Contents

1. [System Overview](#system-overview)
2. [Architecture](#architecture)
3. [Components](#components)
4. [Google Cloud Setup](#google-cloud-setup)
5. [Configuration](#configuration)
6. [Admin Dashboard](#admin-dashboard)
7. [Monday.com Integration](#mondaycom-integration)
8. [LLM-Powered Auditing](#llm-powered-auditing)
9. [Deployment](#deployment)
10. [Known Issues & Solutions](#known-issues--solutions)
11. [Troubleshooting](#troubleshooting)
12. [API Reference](#api-reference)
13. [Multi-Site Support](#multi-site-support)
14. [Development Workflow with Claude AI](#development-workflow-with-claude-ai)

---

## System Overview

The Outrigger SEO Audit System is designed to:

1. **Automatically crawl** the Outrigger sitemap to find recently updated pages
2. **Audit pages** against configurable SEO/GEO rules (both hardcoded and AI-powered)
3. **Use Claude AI** to evaluate pages against natural language rules
4. **Create tasks** in Monday.com for any issues found
5. **Prevent duplicates** by tracking existing issues
6. **Run on a schedule** (weekly on Thursdays at 9 AM Pacific)

### Key Features

- **LLM-Powered Auditing**: Uses Claude (claude-sonnet-4-20250514) to interpret natural language audit rules
- **Configurable Rules**: All rules can be managed via a web-based admin dashboard
- **Severity Levels**: Critical, High, Medium, Low
- **Duplicate Prevention**: Tracks existing Monday.com items to avoid duplicates
- **ScraperAPI Integration**: Bypasses Cloudflare protection on outrigger.com
- **Firebase/Firestore**: Stores rules and configuration

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         GOOGLE CLOUD PLATFORM                            │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  ┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐   │
│  │  Cloud Scheduler │────▶│    Cloud Run    │────▶│    Firestore    │   │
│  │  (Weekly Cron)   │     │  (Python App)   │     │  (Rules Store)  │   │
│  └─────────────────┘     └────────┬────────┘     └─────────────────┘   │
│                                   │                                      │
│  ┌─────────────────┐              │              ┌─────────────────┐   │
│  │  Cloud Storage  │              │              │  Secret Manager │   │
│  │ (Admin Dashboard)│              │              │   (API Keys)    │   │
│  └─────────────────┘              │              └─────────────────┘   │
│                                   │                                      │
└───────────────────────────────────┼──────────────────────────────────────┘
                                    │
                    ┌───────────────┼───────────────┐
                    │               │               │
                    ▼               ▼               ▼
           ┌──────────────┐ ┌──────────────┐ ┌──────────────┐
           │  ScraperAPI  │ │ Anthropic API│ │  Monday.com  │
           │ (Web Scrape) │ │ (Claude LLM) │ │  (Task Mgmt) │
           └──────────────┘ └──────────────┘ └──────────────┘
```

### Data Flow

1. **Cloud Scheduler** triggers the Cloud Run service via HTTP POST
2. **Cloud Run** loads rules from **Firestore**
3. **SitemapParser** fetches URLs from Outrigger sitemap via **ScraperAPI**
4. **SEOAuditor** audits each page:
   - Runs legacy hardcoded checks (if no LLM prompt)
   - Sends pages to **Claude** for LLM-based rule evaluation
5. **MondayClient** creates tasks for issues found (with duplicate prevention)

---

## Components

### Main Application (`main.py`)

The core application containing:

| Class | Purpose |
|-------|---------|
| `LLMAuditor` | Handles Claude API calls for AI-powered rule evaluation |
| `ConfigManager` | Loads and manages rules from Firestore |
| `SitemapParser` | Parses Outrigger sitemap to find recent pages |
| `SEOAuditor` | Performs SEO audits (both legacy and LLM-based) |
| `MondayClient` | Creates and manages Monday.com tasks |

### Key Functions

| Function | Purpose |
|----------|---------|
| `hello_http()` | Main HTTP handler for Cloud Run |
| `fetch_with_scraper_api()` | Fetches URLs via ScraperAPI to bypass Cloudflare |
| `test_monday_columns()` | Debug endpoint for Monday.com integration |

### Environment Variables

| Variable | Description | Source |
|----------|-------------|--------|
| `MONDAY_API_TOKEN` | Monday.com API authentication token | Secret Manager |
| `ANTHROPIC_API_KEY` | Claude API key for LLM auditing | Secret Manager |
| `SCRAPER_API_KEY` | ScraperAPI key for web scraping | Secret Manager |
| `MONDAY_BOARD_ID` | Monday.com board ID | Cloud Run env var |
| `FIRESTORE_PROJECT_ID` | Google Cloud project ID | Hardcoded/env var |

---

## Google Cloud Setup

### Project Information

| Item | Value |
|------|-------|
| Project ID | `project-85d26db5-f70f-487e-b0e` |
| Region | `us-central1` |
| Service Account | `22338575803-compute@developer.gserviceaccount.com` |

### Cloud Run Service

- **Name**: `outrigger-seo-audit`
- **URL**: `https://outrigger-seo-audit-22338575803.us-central1.run.app`
- **Memory**: 1 GiB
- **Timeout**: 540 seconds (9 minutes)
- **Authentication**: Allow unauthenticated

### Cloud Scheduler Job

- **Name**: `outrigger-seo-audit-weekly`
- **Schedule**: `0 9 * * 4` (Every Thursday at 9:00 AM)
- **Timezone**: America/Los_Angeles
- **HTTP Target**: POST to Cloud Run URL

### Secret Manager Secrets

| Secret Name | Description |
|-------------|-------------|
| `monday-api-token` | Monday.com API JWT token |
| `anthropic-api-key` | Anthropic/Claude API key |
| `scraper-api-key` | ScraperAPI key |

### Required IAM Roles

The compute service account needs:

1. **Secret Manager Secret Accessor** - To read secrets at runtime
2. **Cloud Run Invoker** - For scheduler to trigger the service
3. **Firestore User** - To read/write rule configuration

### Cloud Storage Bucket

- **Bucket**: `outrigger-audit-admin`
- **File**: `index.html` (Admin Dashboard)
- **URL**: `https://storage.googleapis.com/outrigger-audit-admin/index.html`

---

## Configuration

### Firestore Collections

#### `seoRules` Collection

```javascript
{
  name: "Title Tag Check",           // Display name
  checkType: "title",                // Identifier for legacy checks
  description: "Checks for...",      // Short description
  prompt: "Check if this page...",   // LLM prompt (optional)
  severity: "Critical",              // Critical/High/Medium/Low
  tier: 1,                           // Priority tier
  enabled: true,                     // Active status
  createdAt: Timestamp,
  updatedAt: Timestamp
}
```

#### `voiceRules` Collection

```javascript
{
  name: "Warm & Welcoming",
  category: "tone",                  // tone/language/audience/messaging
  description: "Content should...",
  enabled: true
}
```

#### `brandStandards` Collection

```javascript
{
  name: "Brand Name Usage",
  standardType: "terminology",       // terminology/visual/compliance/accessibility
  description: "Always use...",
  enabled: true
}
```

### Check Types

| checkType | Description | Checks |
|-----------|-------------|--------|
| `title` | Title tag | Missing, too short (<30 chars) |
| `meta` | Meta description | Missing, too short (<120 chars) |
| `h1` | H1 heading | Missing, multiple H1s |
| `canonical` | Canonical URL | Missing tag |
| `schema` | Structured data | Missing JSON-LD, Hotel schema, etc. |
| `content` | Content quality | Thin content (<300 words) |
| `geo` | Geo meta tags | Missing geo.region/geo.placename |
| `og` | Open Graph | Missing og:image, og:title, og:description |
| `alt` | Image alt text | Missing alt attributes |
| `robots` | Robots meta | Missing robots tag |
| `custom` | LLM-only | No legacy check, prompt required |

---

## Admin Dashboard

### URL

```
https://storage.googleapis.com/outrigger-audit-admin/index.html
```

### Features

1. **SEO/GEO Rules Tab**: Manage audit rules with:
   - Name and description
   - Check type (for legacy checks)
   - Severity level
   - LLM prompt (enables AI-powered checking)
   - Enable/disable toggle

2. **Voice & Tone Tab**: Brand voice guidelines

3. **Brand Standards Tab**: Visual and terminology standards

4. **Load Default Rules**: Seeds database with recommended SEO rules

### Firebase Configuration

```javascript
const firebaseConfig = {
  apiKey: "AIzaSyDu4Ka6oFSUOH_7PAZW7k9-2u46SlmbBWE",
  authDomain: "project-85d26db5-f70f-487e-b0e.firebaseapp.com",
  projectId: "project-85d26db5-f70f-487e-b0e",
  storageBucket: "project-85d26db5-f70f-487e-b0e.firebasestorage.app",
  messagingSenderId: "22338575803",
  appId: "1:22338575803:web:58fef3f290892f25c5f89e"
};
```

---

## Monday.com Integration

### Board Configuration

- **Board ID**: `18395774522`

### Required Columns

| Column Name | Type | Purpose |
|-------------|------|---------|
| Name | text | Issue title (auto-populated) |
| URL | link | Page URL where issue was found |
| Issue Description | long_text | Detailed description and fix instructions |
| Severity | status | Low/Medium/High/Critical labels |

### Column Mapping

The system automatically maps columns by name:
- `page_url` / `url` / `link` → URL column
- `issue_description` / `description` → Description column
- `severity` / `priority` → Severity column

### API Authentication

Monday.com uses JWT tokens for authentication:

```
Authorization: <jwt_token>
API-Version: 2024-01
```

### Task Creation

Tasks are created with:
1. **Title**: Short issue description (e.g., "Missing meta description")
2. **URL**: Full page URL
3. **Description**: Detailed explanation from `ISSUE_DESCRIPTIONS` or LLM
4. **Severity**: Mapped to Monday.com status labels

### Duplicate Prevention

The system prevents duplicates by:
1. Fetching existing items on init
2. Creating duplicate key: `{title}|{url}`
3. Skipping if key exists

---

## Rule System Architecture

### Two Types of Checks

The audit system uses two complementary approaches:

| Type | Purpose | Speed | Cost | Example |
|------|---------|-------|------|---------|
| **Legacy (Code-based)** | Simple structural checks | Fast (ms) | Free | Is there a `<title>` tag? |
| **LLM (AI-powered)** | Complex content analysis | Slower | API cost | Is the meta description accurate for THIS page? |

### How Rules Work

Rules can have:
- `checkType`: Triggers legacy code-based checks (e.g., `title`, `meta`, `h1`)
- `prompt`: Triggers LLM evaluation via Claude

A rule with **both** `checkType` and `prompt` will run both checks:
1. Legacy check: "Does the tag exist?"
2. LLM check: "Is the content correct/relevant?"

### System vs Custom Rules

| Attribute | System Rules | Custom Rules |
|-----------|--------------|--------------|
| Created by | Seed defaults | Users |
| `system: true` | ✅ Yes | ❌ No |
| Can delete? | ❌ No (locked) | ✅ Yes |
| Can disable? | ✅ Yes | ✅ Yes |
| Can edit prompt? | ✅ Yes | ✅ Yes |

### Creating New Rules

Users can only create LLM-based rules (no legacy checkType). The workflow:
1. Describe what you want to check in plain English
2. Click "Generate AI Prompt" - Claude creates a structured audit prompt
3. Review/edit the generated prompt
4. Save the rule

---

## LLM-Powered Auditing

### How It Works

1. Rules with a `prompt` field are processed by Claude
2. HTML content is sent along with the rule prompts
3. Claude analyzes and returns pass/fail results
4. Failed rules become issues in Monday.com

### LLMAuditor Class

```python
class LLMAuditor:
    def audit_page_with_rules(self, html_content, url, rules):
        # Sends HTML + rules to Claude
        # Returns list of issues found

    def batch_audit(self, html_content, url, rules, batch_size=5):
        # Processes rules in batches of 5
        # Avoids rate limits and context overflow
```

### Claude Configuration

- **Model**: `claude-sonnet-4-20250514`
- **Max Tokens**: 4000
- **HTML Truncation**: 50,000 characters

### Prompt Structure

```
System: You are an expert SEO and GEO auditor...

User: Analyze this webpage against these rules:
URL: {url}
=== HTML CONTENT ===
{html}
=== END HTML ===
=== RULES TO CHECK ===
Rule 1: {name}
Severity: {severity}
Check: {prompt}
=== END RULES ===

Return JSON array of results...
```

### Response Format

```json
[
  {"rule_index": 1, "status": "pass"},
  {"rule_index": 2, "status": "fail", "title": "...", "description": "..."}
]
```

---

## Deployment

### Cloud Build Configuration (`cloudbuild.yaml`)

```yaml
steps:
  # Upload admin dashboard to Cloud Storage
  - name: 'gcr.io/cloud-builders/gsutil'
    args: ['cp', 'admin/index.html', 'gs://outrigger-audit-admin/index.html']

  # Build container image
  - name: 'gcr.io/cloud-builders/docker'
    args: ['build', '-t', 'gcr.io/$PROJECT_ID/outrigger-seo-audit:$COMMIT_SHA', '.']

  # Push to Container Registry
  - name: 'gcr.io/cloud-builders/docker'
    args: ['push', 'gcr.io/$PROJECT_ID/outrigger-seo-audit:$COMMIT_SHA']

  # Deploy to Cloud Run
  - name: 'gcr.io/google.com/cloudsdktool/cloud-sdk'
    args:
      - 'run'
      - 'deploy'
      - 'outrigger-seo-audit'
      - '--image'
      - 'gcr.io/$PROJECT_ID/outrigger-seo-audit:$COMMIT_SHA'
      - '--region'
      - 'us-central1'
      - '--allow-unauthenticated'
      - '--memory'
      - '1Gi'
      - '--timeout'
      - '540s'
      - '--set-env-vars'
      - 'MONDAY_BOARD_ID=18395774522'
      - '--set-secrets'
      - 'MONDAY_API_TOKEN=monday-api-token:latest,ANTHROPIC_API_KEY=anthropic-api-key:latest,SCRAPER_API_KEY=scraper-api-key:latest'
```

### Dockerfile

```dockerfile
FROM python:3.11-slim
WORKDIR /app
RUN apt-get update && apt-get install -y gcc libxml2-dev libxslt-dev
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY src/ ./src/
COPY main.py .
ENV PYTHONUNBUFFERED=1 PORT=8080
EXPOSE 8080
CMD ["functions-framework", "--target=hello_http", "--port=8080"]
```

### Manual Deployment

```bash
# Build and push image
gcloud builds submit --config=cloudbuild.yaml

# Or deploy directly
gcloud run deploy outrigger-seo-audit \
  --source . \
  --region us-central1 \
  --allow-unauthenticated \
  --memory 1Gi \
  --timeout 540s \
  --set-secrets "MONDAY_API_TOKEN=monday-api-token:latest,ANTHROPIC_API_KEY=anthropic-api-key:latest,SCRAPER_API_KEY=scraper-api-key:latest"
```

### Triggering Manually

```bash
# Force run via Cloud Scheduler
gcloud scheduler jobs run outrigger-seo-audit-weekly --location=us-central1

# Or direct HTTP call
curl -X POST https://outrigger-seo-audit-22338575803.us-central1.run.app/
```

---

## Known Issues & Solutions

### 1. Monday.com "Not Authenticated" Error

**Symptom**: Logs show `Monday API errors: ['Not Authenticated']`

**Cause**: Monday.com API token has expired or is invalid

**Solution**:
1. Go to Monday.com → Profile → Developers → My Access Tokens
2. Generate a new token with `me:write` permission
3. Update Secret Manager:
   - Go to GCP Console → Secret Manager
   - Select `monday-api-token`
   - Click "+ New version"
   - Paste the new JWT token
   - Click "Add new version"
4. **IMPORTANT**: Deploy a new Cloud Run revision to pick up the new secret:
   - Go to Cloud Run → outrigger-seo-audit
   - Click "Edit & deploy new revision"
   - Click "Deploy" (no changes needed)

### 2. Secret Manager Permission Denied

**Symptom**: Build fails with "Permission denied accessing secret"

**Cause**: Service account lacks Secret Manager access

**Solution**:
1. Go to IAM & Admin → IAM
2. Find `22338575803-compute@developer.gserviceaccount.com`
3. Click Edit (pencil icon)
4. Add role: "Secret Manager Secret Accessor"
5. Save

### 3. Cloudflare Blocking Requests

**Symptom**: Pages return "Just a moment" challenge page

**Cause**: Outrigger.com has Cloudflare protection

**Solution**: Ensure `SCRAPER_API_KEY` is configured. ScraperAPI handles Cloudflare bypass.

### 4. Severity Labels Not Working

**Symptom**: Tasks created without severity, or Monday.com errors about labels

**Cause**: Monday.com severity column labels don't match expected values

**Solution**:
1. Go to Monday.com board
2. Check the Severity column labels
3. Ensure labels exist: "Low", "Medium", "High", "Critical"
4. The system falls back to creating tasks without severity if labels fail

### 5. No Rules Loading from Firestore

**Symptom**: Logs show "0 SEO rules loaded" despite rules in admin

**Cause**: Rules not marked as enabled, or Firestore connection issue

**Solution**:
1. Check admin dashboard - ensure rules have "Enabled" toggled ON
2. Verify Firestore project ID matches: `project-85d26db5-f70f-487e-b0e`
3. Check Cloud Run logs for Firestore connection errors

### 6. LLM Audit Not Running

**Symptom**: Only legacy checks run, no AI-powered audits

**Cause**: Rules missing `prompt` field, or Anthropic API key not configured

**Solution**:
1. Check admin dashboard - add LLM prompts to rules
2. Verify `ANTHROPIC_API_KEY` secret exists and is valid
3. Check logs for "LLMAuditor: No Anthropic client available"

---

## Troubleshooting

### Debug Endpoints

| Endpoint | Purpose |
|----------|---------|
| `GET /` | Health check, shows service status |
| `GET /?config=true` | Shows loaded Firestore rules |
| `GET /?test=true` | Creates a test Monday.com task |
| `GET /?debug_site=SITE_ID` | Shows rules loaded for a specific site (useful for debugging multi-site issues) |
| `POST /` | Runs full audit |
| `POST /?generate_prompt=true` | Generate LLM audit prompt from plain English description |

### Checking Logs

```bash
# View Cloud Run logs
gcloud logging read "resource.type=cloud_run_revision AND resource.labels.service_name=outrigger-seo-audit" --limit=100

# Or use Cloud Console
# Go to Cloud Run → outrigger-seo-audit → Logs
```

### Common Log Messages

| Message | Meaning |
|---------|---------|
| `Connected to Firestore project: ...` | Firestore connection successful |
| `Loaded N SEO rules from Firestore` | Rules loaded from admin |
| `LLMAuditor: Sending N rules to Claude` | LLM audit starting |
| `Monday API response: {'data': ...}` | Task created successfully |
| `Monday API errors: [...]` | Task creation failed |
| `Skipping duplicate: ...` | Issue already exists in Monday |

### Testing Locally

```bash
# Set environment variables
export MONDAY_API_TOKEN="your_token"
export ANTHROPIC_API_KEY="your_key"
export SCRAPER_API_KEY="your_key"

# Install dependencies
pip install -r requirements.txt

# Run locally
functions-framework --target=hello_http --port=8080
```

---

## API Reference

### POST / (Run Audit)

Triggers a full SEO audit.

**Response**:
```json
{
  "status": "success",
  "results": {
    "pages": 5,
    "issues": 12,
    "tasks_created": 8,
    "duplicates_skipped": 4,
    "config_loaded": true,
    "rules_used": {
      "seo": 10,
      "voice": 4,
      "brand": 4
    }
  }
}
```

### GET / (Health Check)

Returns service status.

**Response**:
```json
{
  "status": "healthy",
  "service": "outrigger-seo-audit",
  "scraper_api_configured": true,
  "firestore_connected": true,
  "firestore_project": "project-85d26db5-f70f-487e-b0e"
}
```

### GET /?config=true (Show Config)

Returns loaded rules from Firestore.

**Response**:
```json
{
  "status": "config",
  "firestore_connected": true,
  "seo_rules": 10,
  "voice_rules": 4,
  "brand_standards": 4,
  "rules_detail": {
    "seo": [{"name": "...", "type": "...", "enabled": true}],
    "voice": [...],
    "brand": [...]
  }
}
```

---

## File Structure

```
outrigger-seo-audit/
├── main.py                 # Main application
├── Dockerfile              # Container build instructions
├── requirements.txt        # Python dependencies
├── cloudbuild.yaml         # Cloud Build configuration
├── seed_rules.py           # Script to seed Firestore rules
├── admin/
│   └── index.html          # Admin dashboard (deployed to GCS)
├── src/                    # Additional source files (legacy)
│   ├── config.py
│   ├── sitemap_parser.py
│   ├── seo_auditor.py
│   ├── geo_llm_auditor.py
│   ├── monday_client.py
│   └── ...
└── README.md               # This documentation
```

---

## Maintenance Tasks

### Updating Monday.com Token

1. Token expires periodically - watch for auth errors in logs
2. Generate new token from Monday.com developer settings
3. Update Secret Manager with new version
4. Deploy new Cloud Run revision

### Adding New SEO Rules

1. Go to admin dashboard
2. Click "Add Rule"
3. Fill in name, description, check type, severity
4. Add LLM prompt for AI-powered checking
5. Enable the rule
6. Save

### Monitoring

- Check Cloud Run logs weekly
- Monitor Monday.com board for new issues
- Review Anthropic API usage for costs

---

## Support

For issues or questions:
1. Check this documentation
2. Review Cloud Run logs
3. Test with debug endpoints
4. Check Firestore rules in admin dashboard

---

## Multi-Site Support

The system supports managing multiple websites from a single deployment. Each site has its own:
- SEO/GEO rules
- Voice & tone guidelines
- Brand standards
- Audit configuration (sitemap URL, days to check, max pages)
- Monday.com board for task creation
- Audit logs history

### Firestore Structure

```
/sites/{siteId}/
    ├── config/settings     # Site configuration
    ├── seoRules/           # Site-specific SEO rules
    ├── voiceRules/         # Site-specific voice rules
    ├── brandStandards/     # Site-specific brand standards
    └── auditLogs/          # Site-specific audit history
```

### Using the Admin Dashboard

1. **Select a site** from the dropdown in the header
2. All tabs (Rules, Voice, Brand, Logs) show data for the selected site
3. **Add a new site** by clicking "+ Add Site" button
4. **Run audit** for the current site using the "Run" button
5. **View Site ID** in Settings tab - displays the internal site ID for debugging
6. **Delete a site** via the Settings tab (permanently removes all site data)

### Progress Panel

When an audit runs, a real-time progress panel shows:
- Current page being processed
- Issues found (SEO, Voice, Brand counts)
- Tasks created vs duplicates skipped
- Recent issues list

The progress panel **persists across page refreshes** - if you refresh while an audit is running, the panel automatically reappears and continues showing progress.

### Backend API

POST requests to the Cloud Run endpoint accept a `site_id` parameter:

```bash
curl -X POST https://outrigger-seo-audit-22338575803.us-central1.run.app \
  -H "Content-Type: application/json" \
  -d '{"site_id": "outrigger"}'
```

### Migration from Single-Site

Run the migration script to move existing data to the multi-site structure:

```bash
python migrate_to_multisite.py
```

This creates the `/sites/outrigger/` structure and copies existing rules.

---

## Development Workflow with Claude AI

This project is developed collaboratively with Claude AI (Anthropic). This section documents the workflow for future Claude sessions.

### How Claude Connects to This Project

Claude has access to:

1. **Local File System**: Via the Cowork directory mount
   - User grants folder access to the cloned repository
   - Claude can read, edit, and write files directly
   - Path format: `/sessions/[session-id]/mnt/outrigger-seo-bot/`

2. **Git CLI**: Available in the session environment
   - `git` commands can be run via Bash tool
   - Can commit changes locally
   - Push requires user to run `git push` locally (due to auth)

3. **Browser Automation**: Via Claude in Chrome extension
   - Can navigate to Google Cloud Console
   - Can trigger Cloud Builds manually
   - Can access GitHub, Monday.com, Firestore console
   - Approved domains: `console.cloud.google.com`, `shell.cloud.google.com`, `github.com`, `www.outrigger.com`, `monday.com`

### Standard Development Workflow

After every code change:

1. **Claude makes the code changes** in the local repository
2. **Claude commits changes to git** with a clear, descriptive commit message:
   ```bash
   git add -A && git commit -m "description of changes"
   ```
3. **User pushes to GitHub** - Claude cannot push due to auth, so user runs:
   ```bash
   git push
   ```
4. **Cloud Build triggers automatically** - Pushing to `main` branch triggers a Cloud Build that:
   - Builds a new Docker container
   - Deploys to Cloud Run
   - Updates the admin dashboard in Cloud Storage
5. **Wait for deployment** (~2 minutes) - Check build status at:
   https://console.cloud.google.com/cloud-build/builds?project=project-85d26db5-f70f-487e-b0e

**Important**: Code changes require `git push` to deploy. Simply clicking "Deploy" in Cloud Run only redeploys the existing container - it does NOT pick up code changes.

### Commit Message Format

```
<type>: <short description>

<optional detailed description>

Co-Authored-By: Claude <noreply@anthropic.com>
```

Types: `feat`, `fix`, `docs`, `refactor`, `test`, `chore`

### Key URLs

| Resource | URL |
|----------|-----|
| GitHub Repository | https://github.com/INHQInc/outrigger-seo-bot |
| Admin Dashboard | https://storage.googleapis.com/outrigger-audit-admin/index.html |
| Cloud Run Service | https://outrigger-seo-audit-22338575803.us-central1.run.app |
| Cloud Build Triggers | https://console.cloud.google.com/cloud-build/triggers?project=project-85d26db5-f70f-487e-b0e |
| Cloud Run Console | https://console.cloud.google.com/run?project=project-85d26db5-f70f-487e-b0e |

### Git Authentication for Claude

To enable Claude to push directly to GitHub, an SSH key must be set up each session:

1. **Generate SSH key** (Claude runs this):
   ```bash
   ssh-keygen -t ed25519 -C "claude@anthropic.com" -f ~/.ssh/id_ed25519 -N ""
   ```

2. **Add to GitHub**: The public key must be added to GitHub SSH keys:
   - Go to: https://github.com/settings/keys
   - Click "New SSH key"
   - Title: `Claude AI Session`
   - Paste the public key from `~/.ssh/id_ed25519.pub`

3. **Configure git remote** (Claude runs this):
   ```bash
   cd /path/to/outrigger-seo-bot
   git remote set-url origin git@github.com:INHQInc/outrigger-seo-bot.git
   ```

4. **Test connection**:
   ```bash
   ssh -T git@github.com
   ```

**Note**: SSH keys are session-specific. Each new Claude session requires a new key to be generated and added to GitHub. Old session keys can be removed from GitHub settings.

### Starting a New Claude Session

When starting a new session with Claude:

1. **Grant folder access**: Allow Claude to access the local git repository
2. **Pull latest changes**: Run `git pull` locally before starting
3. **Set up SSH key**: Follow the "Git Authentication for Claude" section above
4. **Share context**: Reference this README for project context
5. **Clean up git state**: If there's a stale rebase, run:
   ```bash
   rm -rf .git/rebase-merge
   git rebase --abort
   ```

### File Permissions Note

The mounted directory may have permission restrictions that prevent Claude from:
- Deleting files (use `mcp__cowork__allow_cowork_file_delete` if needed)
- Modifying `.git/` internal files directly

For these operations, the user should run commands locally.

---

### Recent Changes (January 2026)

- **System Rules Protection**: Seeded rules now have `system: true` flag and cannot be deleted (only disabled)
- **AI-Powered Prompt Generation**: Users can describe rules in plain English and click "Generate AI Prompt" to create structured audit prompts using Claude
- **Meta Content Relevance Check**: New SEO rule that catches copy-paste errors where meta tags describe the wrong property
- **All Voice/Brand Rules Run**: Removed the [:1] limit so all enabled Voice and Brand rules are evaluated (not just the first one)
- **LLM-First Rule Creation**: New rules are LLM-only by default; legacy checkType is preserved for system rules
- **Site ID Display**: Settings tab now shows the Site ID and Site Name at the top
- **Progress Panel Persistence**: Progress panel automatically reappears if you refresh while an audit is running
- **Debug Site Endpoint**: Added `?debug_site=SITE_ID` endpoint to diagnose rule loading issues
- **Site Deletion Fix**: Fixed issue where deleting sites with empty subcollections would fail
- **Reset All Rules**: Button now properly deletes existing rules before seeding defaults
- **3-Page Test Limit**: Temporarily limited audits to 3 pages for faster testing (remove `MAX_PAGES_FOR_TESTING` when ready for production)

---

*Last updated: January 2026*
