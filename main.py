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
