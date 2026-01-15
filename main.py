import functions_framework
import os
import json
import time
import requests
import re
import gzip
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
from flask import jsonify

SITEMAP_URL = 'https://www.outrigger.com/sitemap.xml'
DAYS_TO_CHECK = 7
MONDAY_BOARD_ID = os.environ.get('MONDAY_BOARD_ID', '18395774522')
SCRAPER_API_KEY = os.environ.get('SCRAPER_API_KEY', '')

# Issue type descriptions for the Issue Description field
ISSUE_DESCRIPTIONS = {
    'missing_title': 'The page is missing a <title> tag. This is critical for SEO as the title appears in search results and browser tabs.',
    'short_title': 'The page title is less than 30 characters. Titles should be 50-60 characters for optimal SEO.',
    'missing_meta': 'The page is missing a meta description. This description appears in search results and affects click-through rates.',
    'missing_h1': 'The page is missing an H1 heading tag. Every page should have exactly one H1 for proper content hierarchy.',
    'multiple_h1': 'The page has multiple H1 tags. Best practice is to have exactly one H1 per page.'
}

def fetch_with_scraper_api(url):
    """Fetch URL using ScraperAPI to bypass Cloudflare"""
    if not SCRAPER_API_KEY:
        print("No ScraperAPI key configured, using direct request")
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        }
        return requests.get(url, timeout=60, headers=headers)

    # Use ScraperAPI
    api_url = f"http://api.scraperapi.com?api_key={SCRAPER_API_KEY}&url={url}&render=true"
    print(f"Fetching via ScraperAPI: {url}")
    return requests.get(api_url, timeout=60)

class SitemapParser:
    def __init__(self, sitemap_url=SITEMAP_URL):
        self.sitemap_url = sitemap_url

    def get_urls(self, days=7):
        try:
            resp = fetch_with_scraper_api(self.sitemap_url)
            print(f"Response status: {resp.status_code}")
            cutoff = datetime.now() - timedelta(days=days)
            urls = []

            content = resp.text
            print(f"Sitemap size: {len(content)} bytes")
            print(f"First 500 chars: {content[:500]}")

            # Find all <url>...</url> blocks
            url_blocks = re.findall(r'<url>(.*?)</url>', content, re.DOTALL)
            print(f"Found {len(url_blocks)} URL blocks")

            matches = []
            for block in url_blocks:
                loc_match = re.search(r'<loc>([^<]+)</loc>', block)
                lastmod_match = re.search(r'<lastmod>([^<]+)</lastmod>', block)
                if loc_match:
                    loc = loc_match.group(1).strip()
                    lastmod = lastmod_match.group(1).strip() if lastmod_match else None
                    matches.append((loc, lastmod))

            print(f"Found {len(matches)} URL entries with loc tags")

            for match in matches:
                loc = match[0].strip()
                lastmod = match[1].strip() if match[1] else None

                if loc:
                    if lastmod:
                        try:
                            mod_date = datetime.fromisoformat(lastmod.replace('Z', '+00:00'))
                            if mod_date.replace(tzinfo=None) > cutoff:
                                urls.append({'url': loc})
                        except:
                            pass
                    else:
                        urls.append({'url': loc})

            print(f"Found {len(urls)} recent URLs (within {days} days)")

            if len(urls) == 0:
                print("No recent URLs found, using fallback URLs")
                return [
                    {'url': 'https://www.outrigger.com/'},
                    {'url': 'https://www.outrigger.com/hotels-resorts/hawaii'},
                    {'url': 'https://www.outrigger.com/hotels-resorts/fiji'},
                    {'url': 'https://www.outrigger.com/hotels-resorts/thailand'},
                    {'url': 'https://www.outrigger.com/hotels-resorts/mauritius'}
                ]

            return urls[:20]
        except Exception as e:
            print(f"Error parsing sitemap: {e}")
            print("Using fallback URLs due to error")
            return [
                {'url': 'https://www.outrigger.com/'},
                {'url': 'https://www.outrigger.com/hotels-resorts/hawaii'},
                {'url': 'https://www.outrigger.com/hotels-resorts/fiji'},
                {'url': 'https://www.outrigger.com/hotels-resorts/thailand'},
                {'url': 'https://www.outrigger.com/hotels-resorts/mauritius'}
            ]

class SEOAuditor:
    def audit(self, url):
        issues = []
        try:
            resp = fetch_with_scraper_api(url)
            print(f"Auditing {url} - Status: {resp.status_code}")

            soup = BeautifulSoup(resp.text, 'html.parser')

            # Check if we got a real page (not Cloudflare challenge)
            title = soup.find('title')
            if title and 'Just a moment' in title.text:
                print(f"Warning: Got Cloudflare challenge page for {url}")
                return issues

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

            print(f"Found {len(issues)} issues for {url}")
        except Exception as e:
            print(f"Error auditing {url}: {e}")
        return issues

class MondayClient:
    def __init__(self):
        self.api_token = os.environ.get('MONDAY_API_TOKEN')
        self.board_id = MONDAY_BOARD_ID
        self.api_url = "https://api.monday.com/v2"
        self.columns = {}
        self.existing_issues = set()  # Track URL + issue_type combos

    def init(self):
        if not self.api_token:
            return False
        # Fetch column IDs and existing items
        self._fetch_columns()
        self._fetch_existing_items()
        return True

    def _get_headers(self):
        return {
            "Authorization": self.api_token,
            "Content-Type": "application/json",
            "API-Version": "2024-01"
        }

    def _fetch_columns(self):
        """Fetch column IDs from the board"""
        query = '''query ($board_id: [ID!]!) {
            boards(ids: $board_id) {
                columns { id title type }
            }
        }'''
        variables = {"board_id": [self.board_id]}
        try:
            resp = requests.post(self.api_url, json={"query": query, "variables": variables},
                               headers=self._get_headers(), timeout=30)
            data = resp.json()
            print(f"Columns response: {data}")
            if 'data' in data and data['data']['boards']:
                for col in data['data']['boards'][0]['columns']:
                    col_title = col['title'].lower().replace(' ', '_')
                    self.columns[col_title] = {'id': col['id'], 'type': col['type']}
                print(f"Found columns: {list(self.columns.keys())}")
        except Exception as e:
            print(f"Error fetching columns: {e}")

    def _fetch_existing_items(self):
        """Fetch existing items to prevent duplicates"""
        query = '''query ($board_id: [ID!]!) {
            boards(ids: $board_id) {
                items_page(limit: 500) {
                    items {
                        id
                        name
                        column_values { id text value }
                    }
                }
            }
        }'''
        variables = {"board_id": [self.board_id]}
        try:
            resp = requests.post(self.api_url, json={"query": query, "variables": variables},
                               headers=self._get_headers(), timeout=30)
            data = resp.json()
            if 'data' in data and data['data']['boards']:
                items = data['data']['boards'][0].get('items_page', {}).get('items', [])
                for item in items:
                    # Extract URL and issue type from item name or columns
                    name = item.get('name', '')
                    # Create a unique key from the item name (which contains severity, issue, and URL)
                    self.existing_issues.add(name)
                print(f"Found {len(self.existing_issues)} existing items")
        except Exception as e:
            print(f"Error fetching existing items: {e}")

    def _get_column_id(self, field_name):
        """Get column ID by common field name variations"""
        field_mappings = {
            'issue_description': ['issue_description', 'description', 'text'],
            'issue_type': ['issue_type', 'type', 'label'],
            'status': ['status'],
            'page_url': ['page_url', 'url', 'link'],
            'priority': ['priority'],
            'date_found': ['date_found', 'date', 'created'],
        }
        for key in field_mappings.get(field_name, [field_name]):
            if key in self.columns:
                return self.columns[key]['id']
        return None

    def is_duplicate(self, task_title):
        """Check if this issue already exists"""
        return task_title in self.existing_issues

    def create_task(self, issue):
        """Create a task with all column values populated"""
        if not self.api_token:
            return None

        task_title = f"[{issue['severity']}] {issue['title']} - {issue['url'][:50]}"

        # Check for duplicate
        if self.is_duplicate(task_title):
            print(f"Skipping duplicate: {task_title[:60]}...")
            return "duplicate"

        # Build column values JSON
        column_values = {}

        # Issue Description (text column)
        desc_col = self._get_column_id('issue_description')
        if desc_col:
            description = ISSUE_DESCRIPTIONS.get(issue['type'], issue['title'])
            column_values[desc_col] = description

        # Issue Type (text or label column)
        type_col = self._get_column_id('issue_type')
        if type_col:
            column_values[type_col] = issue['type'].replace('_', ' ').title()

        # Page URL (text or link column)
        url_col = self._get_column_id('page_url')
        if url_col:
            # For link columns, use JSON format; for text, use plain string
            if self.columns.get('page_url', {}).get('type') == 'link':
                column_values[url_col] = json.dumps({"url": issue['url'], "text": issue['url'][:50]})
            else:
                column_values[url_col] = issue['url']

        # Priority (status column) - map severity to priority
        priority_col = self._get_column_id('priority')
        if priority_col:
            priority_map = {'High': 'High', 'Medium': 'Medium', 'Low': 'Low'}
            column_values[priority_col] = {"label": priority_map.get(issue['severity'], 'Medium')}

        # Date Found (date column)
        date_col = self._get_column_id('date_found')
        if date_col:
            today = datetime.now().strftime("%Y-%m-%d")
            column_values[date_col] = {"date": today}

        # Status (status column) - set to "Open" or default
        status_col = self._get_column_id('status')
        if status_col:
            column_values[status_col] = {"label": "Open"}

        print(f"Creating task with columns: {list(column_values.keys())}")

        query = '''mutation ($board_id: ID!, $item_name: String!, $column_values: JSON!) {
            create_item (board_id: $board_id, item_name: $item_name, column_values: $column_values) { id }
        }'''
        variables = {
            "board_id": self.board_id,
            "item_name": task_title,
            "column_values": json.dumps(column_values)
        }

        try:
            resp = requests.post(self.api_url, json={"query": query, "variables": variables},
                               headers=self._get_headers(), timeout=30)
            data = resp.json()
            print(f"Monday API response: {data}")
            if 'data' in data and 'create_item' in data['data']:
                # Add to existing issues to prevent duplicates in same run
                self.existing_issues.add(task_title)
                return data['data']['create_item']['id']
            elif 'errors' in data:
                print(f"Monday API errors: {data['errors']}")
                # Try simpler create without column_values if it fails
                return self._create_simple_task(task_title)
        except Exception as e:
            print(f"Error creating Monday task: {e}")
        return None

    def _create_simple_task(self, title):
        """Fallback: create task with just the title"""
        query = '''mutation ($board_id: ID!, $item_name: String!) {
            create_item (board_id: $board_id, item_name: $item_name) { id }
        }'''
        variables = {"board_id": self.board_id, "item_name": title}
        try:
            resp = requests.post(self.api_url, json={"query": query, "variables": variables},
                               headers=self._get_headers(), timeout=30)
            data = resp.json()
            if 'data' in data and 'create_item' in data['data']:
                self.existing_issues.add(title)
                return data['data']['create_item']['id']
        except Exception as e:
            print(f"Error in fallback task creation: {e}")
        return None

@functions_framework.http
def hello_http(request):
    headers = {'Access-Control-Allow-Origin': '*', 'Content-Type': 'application/json'}
    if request.method == 'OPTIONS':
        return ('', 204, headers)
    if request.method == 'GET':
        return jsonify({"status": "healthy", "service": "outrigger-seo-audit", "scraper_api_configured": bool(SCRAPER_API_KEY)}), 200, headers
    if request.method == 'POST':
        try:
            parser = SitemapParser()
            auditor = SEOAuditor()
            monday = MondayClient()

            if not monday.init():
                return jsonify({"error": "Monday API token not configured"}), 500, headers

            if not SCRAPER_API_KEY:
                print("WARNING: SCRAPER_API_KEY not configured - may be blocked by Cloudflare")

            urls = parser.get_urls(days=DAYS_TO_CHECK)
            results = {'pages': len(urls), 'issues': 0, 'tasks_created': 0, 'duplicates_skipped': 0}

            for u in urls:
                issues = auditor.audit(u['url'])
                results['issues'] += len(issues)
                for issue in issues:
                    result = monday.create_task(issue)
                    if result == "duplicate":
                        results['duplicates_skipped'] += 1
                    elif result:
                        results['tasks_created'] += 1
                time.sleep(1)  # Increased delay for ScraperAPI rate limits

            return jsonify({"status": "success", "results": results}), 200, headers
        except Exception as e:
            print(f"Error in main handler: {e}")
            return jsonify({"error": str(e)}), 500, headers
    return jsonify({"error": "Method not allowed"}), 405, headers
