# Outrigger SEO Audit System

Automated weekly SEO audit system for outrigger.com that creates tasks in Monday.com for any issues found.

## Overview

This system:
1. Parses outrigger.com sitemap to find pages updated in the last 7 days
2. Runs SEO audits checking for title, meta description, and H1 tag issues
3. Creates tasks in Monday.com board for any issues found
4. Runs automatically every Thursday at 9:00 AM (Los Angeles time)

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
- **API Token**: Stored as environment variable `MONDAY_API_TOKEN`

## Environment Variables

| Variable | Description |
|----------|-------------|
| `MONDAY_API_TOKEN` | Monday.com API token for authentication |
| `MONDAY_BOARD_ID` | (Optional) Monday.com board ID, defaults to 18395774522 |

## Files

```
outrigger-seo-audit/
├── main.py              # Cloud Function entry point
├── requirements.txt     # Python dependencies
├── .gitignore          # Git ignore patterns
├── .gcloudignore       # GCloud deploy ignore patterns
└── README.md           # This file
```

## main.py Code

```python
import functions_framework
import os
import json
import time
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
import xml.etree.ElementTree as ET
from flask import jsonify

SITEMAP_URL = 'https://www.outrigger.com/sitemap.xml'
DAYS_TO_CHECK = 7
MONDAY_BOARD_ID = os.environ.get('MONDAY_BOARD_ID', '18395774522')

class SitemapParser:
    def __init__(self, sitemap_url=SITEMAP_URL):
        self.sitemap_url = sitemap_url

    def get_urls(self, days=7):
        try:
            resp = requests.get(self.sitemap_url, timeout=30)
            root = ET.fromstring(resp.content)
            ns = {'sm': 'http://www.sitemaps.org/schemas/sitemap/0.9'}
            cutoff = datetime.now() - timedelta(days=days)
            urls = []
            for url in root.findall('.//sm:url', ns):
                loc = url.find('sm:loc', ns)
                lastmod = url.find('sm:lastmod', ns)
                if loc is not None:
                    url_data = {'url': loc.text}
                    if lastmod is not None:
                        try:
                            mod_date = datetime.fromisoformat(lastmod.text.replace('Z', '+00:00'))
                            if mod_date.replace(tzinfo=None) > cutoff:
                                urls.append(url_data)
                        except:
                            urls.append(url_data)
            return urls[:20]
        except Exception as e:
            print(f"Error parsing sitemap: {e}")
            return []

class SEOAuditor:
    def audit(self, url):
        issues = []
        try:
            resp = requests.get(url, timeout=30)
            soup = BeautifulSoup(resp.text, 'html.parser')
            title = soup.find('title')
            if not title or not title.text.strip():
                issues.append({'type': 'missing_title', 'title': 'Missing page title', 'severity': 'High', 'url': url})
            elif len(title.text.strip()) < 30:
                issues.append({'type': 'short_title', 'title': 'Title too short', 'severity': 'Medium', 'url': url})
            meta_desc = soup.find('meta', attrs={'name': 'description'})
            if not meta_desc or not meta_desc.get('content', '').strip():
                issues.append({'type': 'missing_meta', 'title': 'Missing meta description', 'severity': 'High', 'url': url})
            h1_tags = soup.find_all('h1')
            if not h1_tags:
                issues.append({'type': 'missing_h1', 'title': 'Missing H1 tag', 'severity': 'Medium', 'url': url})
            elif len(h1_tags) > 1:
                issues.append({'type': 'multiple_h1', 'title': 'Multiple H1 tags', 'severity': 'Low', 'url': url})
        except Exception as e:
            print(f"Error auditing {url}: {e}")
        return issues

class MondayClient:
    def __init__(self):
        self.api_token = os.environ.get('MONDAY_API_TOKEN')
        self.board_id = MONDAY_BOARD_ID
        self.api_url = "https://api.monday.com/v2"

    def init(self):
        return self.api_token is not None

    def create_task(self, title):
        if not self.api_token:
            return None
        query = '''mutation ($board_id: ID!, $item_name: String!) {
            create_item (board_id: $board_id, item_name: $item_name) { id }
        }'''
        variables = {"board_id": self.board_id, "item_name": title}
        headers = {"Authorization": self.api_token, "Content-Type": "application/json"}
        try:
            resp = requests.post(self.api_url, json={"query": query, "variables": variables}, headers=headers, timeout=30)
            data = resp.json()
            if 'data' in data and 'create_item' in data['data']:
                return data['data']['create_item']['id']
        except Exception as e:
            print(f"Error creating Monday task: {e}")
        return None

@functions_framework.http
def hello_http(request):
    headers = {'Access-Control-Allow-Origin': '*', 'Content-Type': 'application/json'}
    if request.method == 'OPTIONS':
        return ('', 204, headers)
    if request.method == 'GET':
        return jsonify({"status": "healthy", "service": "outrigger-seo-audit"}), 200, headers
    if request.method == 'POST':
        try:
            parser = SitemapParser()
            auditor = SEOAuditor()
            monday = MondayClient()
            if not monday.init():
                return jsonify({"error": "Monday API token not configured"}), 500, headers
            urls = parser.get_urls(days=DAYS_TO_CHECK)
            results = {'pages': len(urls), 'issues': 0, 'tasks_created': 0}
            for u in urls:
                issues = auditor.audit(u['url'])
                results['issues'] += len(issues)
                for issue in issues:
                    task_title = f"[{issue['severity']}] {issue['title']} - {u['url'][:50]}"
                    if monday.create_task(task_title):
                        results['tasks_created'] += 1
                time.sleep(0.5)
            return jsonify({"status": "success", "results": results}), 200, headers
        except Exception as e:
            return jsonify({"error": str(e)}), 500, headers
    return jsonify({"error": "Method not allowed"}), 405, headers
```

## requirements.txt

```
functions-framework==3.*
requests==2.31.*
beautifulsoup4==4.12.*
lxml==5.1.*
flask==3.0.*
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
  --set-env-vars MONDAY_API_TOKEN=your-token-here
```

### Create Cloud Scheduler Job
```bash
gcloud scheduler jobs create http outrigger-seo-audit-weekly \
  --location=us-central1 \
  --schedule="0 9 * * 4" \
  --time-zone="America/Los_Angeles" \
  --uri="https://outrigger-seo-audit-22338575803.us-central1.run.app" \
  --http-method=POST \
  --oidc-service-account-email=22338575803-compute@developer.gserviceaccount.com
```

### Test the Function
```bash
curl -X POST https://outrigger-seo-audit-22338575803.us-central1.run.app
```

## SEO Checks Performed

| Check | Severity | Description |
|-------|----------|-------------|
| Missing Title | High | Page has no `<title>` tag |
| Short Title | Medium | Title is less than 30 characters |
| Missing Meta Description | High | No meta description tag |
| Missing H1 | Medium | Page has no `<h1>` tag |
| Multiple H1 | Low | Page has more than one `<h1>` tag |

## Monitoring

- **Cloud Run Logs**: Google Cloud Console > Cloud Run > outrigger-seo-audit > Logs
- **Scheduler Logs**: Google Cloud Console > Cloud Scheduler > outrigger-seo-audit-weekly
- **Monday.com Board**: Check board ID 18395774522 for created tasks

## Troubleshooting

1. **Function not running**: Check Cloud Scheduler job status and logs
2. **No tasks created**: Verify MONDAY_API_TOKEN environment variable is set
3. **API errors**: Check Cloud Run logs for detailed error messages

## Created
- **Date**: January 15, 2026
- **By**: Claude Code Assistant
