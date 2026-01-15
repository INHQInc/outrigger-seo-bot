"""
Sitemap Parser Module
Fetches and parses sitemap.xml, filters pages by last modified date
"""
import requests
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
from typing import List, Dict, Optional
from dateutil import parser as date_parser
import pytz

from config import (
    SITEMAP_URL,
    SITE_URL,
    DAYS_TO_CHECK,
    REQUEST_TIMEOUT,
    REQUEST_HEADERS,
)


class SitemapParser:
    """Parse sitemap.xml and extract URLs with their metadata"""

    # XML namespaces commonly used in sitemaps
    NAMESPACES = {
        'sitemap': 'http://www.sitemaps.org/schemas/sitemap/0.9',
        'xhtml': 'http://www.w3.org/1999/xhtml',
        'image': 'http://www.google.com/schemas/sitemap-image/1.1',
        'video': 'http://www.google.com/schemas/sitemap-video/1.1',
    }

    def __init__(self, sitemap_url: str = SITEMAP_URL):
        self.sitemap_url = sitemap_url
        self.urls: List[Dict] = []

    def fetch_sitemap(self, url: str = None) -> Optional[str]:
        """Fetch sitemap XML content from URL"""
        url = url or self.sitemap_url
        try:
            response = requests.get(
                url,
                headers=REQUEST_HEADERS,
                timeout=REQUEST_TIMEOUT
            )
            response.raise_for_status()
            return response.text
        except requests.RequestException as e:
            print(f"Error fetching sitemap from {url}: {e}")
            return None

    def parse_sitemap(self, xml_content: str) -> List[Dict]:
        """Parse sitemap XML and extract URL entries"""
        urls = []

        try:
            root = ET.fromstring(xml_content)

            # Check if this is a sitemap index (contains other sitemaps)
            sitemap_entries = root.findall('.//sitemap:sitemap', self.NAMESPACES)
            if sitemap_entries:
                # This is a sitemap index, recursively fetch each sitemap
                for sitemap in sitemap_entries:
                    loc = sitemap.find('sitemap:loc', self.NAMESPACES)
                    if loc is not None and loc.text:
                        child_content = self.fetch_sitemap(loc.text)
                        if child_content:
                            urls.extend(self.parse_sitemap(child_content))
            else:
                # This is a regular sitemap with URL entries
                url_entries = root.findall('.//sitemap:url', self.NAMESPACES)

                for url_entry in url_entries:
                    url_data = self._extract_url_data(url_entry)
                    if url_data:
                        urls.append(url_data)

        except ET.ParseError as e:
            print(f"Error parsing sitemap XML: {e}")

        return urls

    def _extract_url_data(self, url_entry: ET.Element) -> Optional[Dict]:
        """Extract data from a single URL entry"""
        loc = url_entry.find('sitemap:loc', self.NAMESPACES)
        if loc is None or not loc.text:
            return None

        url_data = {
            'url': loc.text.strip(),
            'lastmod': None,
            'changefreq': None,
            'priority': None,
        }

        # Extract lastmod (last modified date)
        lastmod = url_entry.find('sitemap:lastmod', self.NAMESPACES)
        if lastmod is not None and lastmod.text:
            try:
                url_data['lastmod'] = date_parser.parse(lastmod.text.strip())
            except (ValueError, TypeError):
                pass

        # Extract changefreq
        changefreq = url_entry.find('sitemap:changefreq', self.NAMESPACES)
        if changefreq is not None and changefreq.text:
            url_data['changefreq'] = changefreq.text.strip()

        # Extract priority
        priority = url_entry.find('sitemap:priority', self.NAMESPACES)
        if priority is not None and priority.text:
            try:
                url_data['priority'] = float(priority.text.strip())
            except ValueError:
                pass

        return url_data

    def get_recently_updated_urls(self, days: int = DAYS_TO_CHECK) -> List[Dict]:
        """Get URLs that were updated within the specified number of days"""
        # Fetch and parse sitemap
        xml_content = self.fetch_sitemap()
        if not xml_content:
            return []

        self.urls = self.parse_sitemap(xml_content)

        # Filter by last modified date
        cutoff_date = datetime.now(pytz.UTC) - timedelta(days=days)

        recently_updated = []
        for url_data in self.urls:
            lastmod = url_data.get('lastmod')
            if lastmod:
                # Ensure lastmod is timezone-aware
                if lastmod.tzinfo is None:
                    lastmod = pytz.UTC.localize(lastmod)

                if lastmod >= cutoff_date:
                    recently_updated.append(url_data)
            else:
                # If no lastmod, include the URL (we can't determine when it was updated)
                # You might want to change this behavior based on your needs
                pass

        print(f"Found {len(recently_updated)} URLs updated in the last {days} days")
        return recently_updated

    def get_all_urls(self) -> List[Dict]:
        """Get all URLs from sitemap (for full audit)"""
        xml_content = self.fetch_sitemap()
        if not xml_content:
            return []

        self.urls = self.parse_sitemap(xml_content)
        print(f"Found {len(self.urls)} total URLs in sitemap")
        return self.urls


def main():
    """Test the sitemap parser"""
    parser = SitemapParser()

    # Get recently updated URLs
    recent_urls = parser.get_recently_updated_urls(days=7)

    print("\nRecently updated URLs:")
    for url_data in recent_urls[:10]:  # Print first 10
        print(f"  - {url_data['url']}")
        if url_data['lastmod']:
            print(f"    Last modified: {url_data['lastmod']}")

    if len(recent_urls) > 10:
        print(f"  ... and {len(recent_urls) - 10} more")


if __name__ == "__main__":
    main()
