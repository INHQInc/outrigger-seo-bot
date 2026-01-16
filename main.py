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
    # Basic SEO
    'missing_title': 'The page is missing a <title> tag. This is critical for SEO as the title appears in search results and browser tabs.',
    'short_title': 'The page title is less than 30 characters. Titles should be 50-60 characters for optimal SEO.',
    'missing_meta': 'The page is missing a meta description. This description appears in search results and affects click-through rates.',
    'short_meta': 'The meta description is less than 120 characters. Optimal length is 150-160 characters for search results.',
    'missing_h1': 'The page is missing an H1 heading tag. Every page should have exactly one H1 for proper content hierarchy.',
    'multiple_h1': 'The page has multiple H1 tags. Best practice is to have exactly one H1 per page.',

    # Technical SEO
    'missing_canonical': 'The page is missing a canonical tag. This helps prevent duplicate content issues and consolidates ranking signals.',
    'missing_robots': 'The page is missing a robots meta tag. This controls how search engines crawl and index the page.',

    # Open Graph
    'missing_og_title': 'The page is missing an Open Graph title (og:title). This affects how the page appears when shared on social media.',
    'missing_og_description': 'The page is missing an Open Graph description (og:description). This affects social media sharing previews.',
    'missing_og_image': 'The page is missing an Open Graph image (og:image). Social shares without images get significantly less engagement.',

    # Images
    'missing_alt_tags': 'Images on this page are missing alt tags. Alt tags are important for accessibility and image SEO.',

    # Schema/Structured Data
    'missing_schema': 'The page has no JSON-LD structured data. Schema markup helps search engines understand page content.',
    'missing_organization_schema': 'The page is missing Organization schema. This helps establish brand identity in search results.',
    'missing_localbusiness_schema': 'The page is missing LocalBusiness schema. This is critical for local SEO and Google Maps visibility.',
    'missing_breadcrumb_schema': 'The page is missing BreadcrumbList schema. Breadcrumbs improve navigation and search result appearance.',
    'missing_faq_schema': 'The page has FAQ content but no FAQPage schema. FAQ schema can generate rich results in search.',
    'missing_hotel_schema': 'The page is missing Hotel or LodgingBusiness schema. This is essential for hotel/resort pages.',

    # GEO/Local SEO
    'missing_geo_tags': 'The page is missing geo meta tags (geo.region, geo.placename). These help with local search visibility.',
    'missing_address_schema': 'The page is missing PostalAddress in schema. Complete address info improves local SEO.',
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
            title_tag = soup.find('title')
            if title_tag and 'Just a moment' in title_tag.text:
                print(f"Warning: Got Cloudflare challenge page for {url}")
                return issues

            # ============ BASIC SEO CHECKS ============

            # Title tag
            if not title_tag or not title_tag.text.strip():
                issues.append({'type': 'missing_title', 'title': 'Missing page title', 'severity': 'High', 'url': url})
            elif len(title_tag.text.strip()) < 30:
                issues.append({'type': 'short_title', 'title': 'Title too short', 'severity': 'Medium', 'url': url})

            # Meta description
            meta_desc = soup.find('meta', attrs={'name': 'description'})
            if not meta_desc or not meta_desc.get('content', '').strip():
                issues.append({'type': 'missing_meta', 'title': 'Missing meta description', 'severity': 'High', 'url': url})
            elif len(meta_desc.get('content', '').strip()) < 120:
                issues.append({'type': 'short_meta', 'title': 'Meta description too short', 'severity': 'Medium', 'url': url})

            # H1 tags
            h1_tags = soup.find_all('h1')
            if not h1_tags:
                issues.append({'type': 'missing_h1', 'title': 'Missing H1 tag', 'severity': 'Medium', 'url': url})
            elif len(h1_tags) > 1:
                issues.append({'type': 'multiple_h1', 'title': 'Multiple H1 tags', 'severity': 'Low', 'url': url})

            # ============ TECHNICAL SEO CHECKS ============

            # Canonical tag
            canonical = soup.find('link', attrs={'rel': 'canonical'})
            if not canonical or not canonical.get('href'):
                issues.append({'type': 'missing_canonical', 'title': 'Missing canonical tag', 'severity': 'Medium', 'url': url})

            # Robots meta tag
            robots = soup.find('meta', attrs={'name': 'robots'})
            if not robots:
                issues.append({'type': 'missing_robots', 'title': 'Missing robots meta tag', 'severity': 'Low', 'url': url})

            # ============ OPEN GRAPH CHECKS ============

            og_title = soup.find('meta', attrs={'property': 'og:title'})
            if not og_title or not og_title.get('content'):
                issues.append({'type': 'missing_og_title', 'title': 'Missing Open Graph title', 'severity': 'Medium', 'url': url})

            og_desc = soup.find('meta', attrs={'property': 'og:description'})
            if not og_desc or not og_desc.get('content'):
                issues.append({'type': 'missing_og_description', 'title': 'Missing Open Graph description', 'severity': 'Medium', 'url': url})

            og_image = soup.find('meta', attrs={'property': 'og:image'})
            if not og_image or not og_image.get('content'):
                issues.append({'type': 'missing_og_image', 'title': 'Missing Open Graph image', 'severity': 'Medium', 'url': url})

            # ============ IMAGE ALT TAG CHECKS ============

            images = soup.find_all('img')
            images_without_alt = []
            for img in images:
                if not img.get('alt') or not img.get('alt').strip():
                    # Get image source/name
                    img_src = img.get('src', '') or img.get('data-src', '') or img.get('data-lazy-src', '')
                    if img_src:
                        # Extract filename from URL
                        img_name = img_src.split('/')[-1].split('?')[0][:50]
                        images_without_alt.append(img_name)

            # Create individual issues for each image missing alt tag (limit to first 5)
            for img_name in images_without_alt[:5]:
                issues.append({
                    'type': 'missing_alt_tags',
                    'title': f'Missing alt tag: {img_name}',
                    'severity': 'Medium',
                    'url': url
                })

            # If more than 5 images missing alt, add a summary
            if len(images_without_alt) > 5:
                issues.append({
                    'type': 'missing_alt_tags',
                    'title': f'Additional {len(images_without_alt) - 5} images missing alt tags',
                    'severity': 'Medium',
                    'url': url
                })

            # ============ SCHEMA/STRUCTURED DATA CHECKS ============

            # Find all JSON-LD scripts
            schema_scripts = soup.find_all('script', attrs={'type': 'application/ld+json'})
            schemas = []
            for script in schema_scripts:
                try:
                    schema_data = json.loads(script.string)
                    if isinstance(schema_data, list):
                        schemas.extend(schema_data)
                    else:
                        schemas.append(schema_data)
                except:
                    pass

            # Get all @type values from schemas
            schema_types = set()
            def extract_types(obj):
                if isinstance(obj, dict):
                    if '@type' in obj:
                        t = obj['@type']
                        if isinstance(t, list):
                            schema_types.update(t)
                        else:
                            schema_types.add(t)
                    for v in obj.values():
                        extract_types(v)
                elif isinstance(obj, list):
                    for item in obj:
                        extract_types(item)

            for schema in schemas:
                extract_types(schema)

            print(f"Found schema types: {schema_types}")

            # Check for missing schemas
            if not schemas:
                issues.append({'type': 'missing_schema', 'title': 'No JSON-LD structured data', 'severity': 'High', 'url': url})
            else:
                # Organization schema
                if not any(t in schema_types for t in ['Organization', 'Corporation', 'Hotel', 'Resort']):
                    issues.append({'type': 'missing_organization_schema', 'title': 'Missing Organization schema', 'severity': 'Medium', 'url': url})

                # LocalBusiness/Hotel schema - important for Outrigger
                if not any(t in schema_types for t in ['LocalBusiness', 'Hotel', 'LodgingBusiness', 'Resort']):
                    issues.append({'type': 'missing_localbusiness_schema', 'title': 'Missing LocalBusiness/Hotel schema', 'severity': 'High', 'url': url})

                # Breadcrumb schema
                if 'BreadcrumbList' not in schema_types:
                    issues.append({'type': 'missing_breadcrumb_schema', 'title': 'Missing BreadcrumbList schema', 'severity': 'Low', 'url': url})

                # Check for Hotel-specific schema on hotel pages
                if '/hotel' in url.lower() or '/resort' in url.lower() or '/room' in url.lower():
                    if not any(t in schema_types for t in ['Hotel', 'LodgingBusiness', 'Resort', 'Suite', 'HotelRoom']):
                        issues.append({'type': 'missing_hotel_schema', 'title': 'Missing Hotel/LodgingBusiness schema', 'severity': 'High', 'url': url})

                # Check for address in schema (for local SEO)
                has_address = False
                for schema in schemas:
                    if isinstance(schema, dict):
                        if 'address' in schema or 'location' in schema:
                            has_address = True
                            break
                if not has_address and any(t in schema_types for t in ['LocalBusiness', 'Hotel', 'LodgingBusiness', 'Organization']):
                    issues.append({'type': 'missing_address_schema', 'title': 'Missing address in schema', 'severity': 'Medium', 'url': url})

            # FAQ schema check - only if page has FAQ content
            faq_indicators = soup.find_all(['details', 'summary']) or soup.find_all(class_=re.compile(r'faq|accordion', re.I))
            if faq_indicators and 'FAQPage' not in schema_types:
                issues.append({'type': 'missing_faq_schema', 'title': 'FAQ content without FAQPage schema', 'severity': 'Low', 'url': url})

            # ============ GEO/LOCAL SEO CHECKS ============

            # Geo meta tags
            geo_region = soup.find('meta', attrs={'name': 'geo.region'})
            geo_placename = soup.find('meta', attrs={'name': 'geo.placename'})
            if not geo_region and not geo_placename:
                issues.append({'type': 'missing_geo_tags', 'title': 'Missing geo meta tags', 'severity': 'Low', 'url': url})

            print(f"Found {len(issues)} issues for {url}")
        except Exception as e:
            print(f"Error auditing {url}: {e}")
            import traceback
            traceback.print_exc()
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
                url_col_id = self._get_column_id('page_url')
                for item in items:
                    name = item.get('name', '')
                    # Try to get the URL from column values for duplicate key
                    url = ''
                    for col in item.get('column_values', []):
                        if col['id'] == url_col_id:
                            # URL might be in text or in value (as JSON)
                            url = col.get('text', '')
                            if not url and col.get('value'):
                                try:
                                    val = json.loads(col['value'])
                                    url = val.get('url', '') if isinstance(val, dict) else ''
                                except:
                                    pass
                            break
                    # Create duplicate key matching the format we use when creating
                    if url:
                        self.existing_issues.add(f"{name}|{url}")
                    # Also add just the name for backward compatibility
                    self.existing_issues.add(name)
                print(f"Found {len(self.existing_issues)} existing items/keys")
        except Exception as e:
            print(f"Error fetching existing items: {e}")

    def _get_column_id(self, field_name):
        """Get column ID by common field name variations"""
        field_mappings = {
            'issue_description': ['issue_description', 'description', 'issue_desc'],
            'issue_type': ['issue_type', 'type', 'issuetype'],
            'status': ['status'],
            'page_url': ['url', 'page_url', 'pageurl', 'link'],  # 'url' first since column is named "URL"
            'date_found': ['date_found', 'datefound', 'date', 'found_date'],
        }
        print(f"Looking for field: {field_name}, mappings: {field_mappings.get(field_name)}")
        print(f"Current columns: {list(self.columns.keys())}")

        # First try exact matches
        for key in field_mappings.get(field_name, [field_name]):
            if key in self.columns:
                print(f"Found exact match: {key} -> {self.columns[key]['id']}")
                return self.columns[key]['id']
        # Then try partial matches (but be more specific)
        for key in field_mappings.get(field_name, [field_name]):
            for col_name in self.columns:
                # For page_url, look for columns containing 'url' but not other fields
                if field_name == 'page_url' and 'url' in col_name:
                    print(f"Found partial match: {col_name} -> {self.columns[col_name]['id']}")
                    return self.columns[col_name]['id']
                elif key in col_name or col_name in key:
                    print(f"Found partial match: {col_name} -> {self.columns[col_name]['id']}")
                    return self.columns[col_name]['id']
        print(f"No match found for {field_name}")
        return None

    def is_duplicate(self, task_title):
        """Check if this issue already exists"""
        return task_title in self.existing_issues

    def create_task(self, issue):
        """Create a task with all column values populated"""
        if not self.api_token:
            return None

        # Task title is ONLY the issue - URL goes in the Page URL column
        task_title = issue['title']

        # For duplicate detection, use title + URL combo
        duplicate_key = f"{issue['title']}|{issue['url']}"
        if duplicate_key in self.existing_issues:
            print(f"Skipping duplicate: {task_title[:60]}...")
            return "duplicate"

        # Build column values JSON
        column_values = {}

        # Issue Description (long_text column)
        desc_col = self._get_column_id('issue_description')
        if desc_col:
            description = ISSUE_DESCRIPTIONS.get(issue['type'], issue['title'])
            col_type = self.columns.get('issue_description', {}).get('type', '')
            if col_type == 'long_text':
                column_values[desc_col] = {"text": description}
            else:
                column_values[desc_col] = description

        # Issue Type (text column)
        type_col = self._get_column_id('issue_type')
        if type_col:
            issue_type_value = issue['type'].replace('_', ' ').title()
            col_type = self.columns.get('issue_type', {}).get('type', '')
            if col_type == 'color':  # status/label column
                column_values[type_col] = {"label": issue_type_value}
            else:
                column_values[type_col] = issue_type_value

        # Page URL (link or text column)
        url_col = self._get_column_id('page_url')
        print(f"Looking for Page URL column. Found: {url_col}")
        print(f"Available columns: {self.columns}")
        if url_col:
            # Find the actual column type by ID
            col_type = None
            for col_name, col_info in self.columns.items():
                if col_info['id'] == url_col:
                    col_type = col_info['type']
                    break
            print(f"Page URL column ID: {url_col}, type: {col_type}, url: {issue['url']}")
            # For link columns, Monday.com requires both url and text
            column_values[url_col] = {"url": issue['url'], "text": issue['url']}
            print(f"Setting URL column value: {column_values[url_col]}")
        else:
            print(f"WARNING: Could not find Page URL column!")

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
