"""
SEO Auditor Module
Performs comprehensive SEO analysis on web pages
"""
import requests
import re
import time
from bs4 import BeautifulSoup
from typing import List, Dict, Optional, Tuple
from urllib.parse import urlparse, urljoin
from collections import Counter

from config import (
    REQUEST_TIMEOUT,
    REQUEST_HEADERS,
    DELAY_BETWEEN_REQUESTS,
    SEVERITY,
    CATEGORIES,
)


class SEOIssue:
    """Represents an SEO issue found during audit"""

    def __init__(
        self,
        url: str,
        issue_type: str,
        category: str,
        severity: str,
        title: str,
        description: str,
        recommendation: str,
        current_value: str = None,
        expected_value: str = None,
    ):
        self.url = url
        self.issue_type = issue_type
        self.category = category
        self.severity = severity
        self.title = title
        self.description = description
        self.recommendation = recommendation
        self.current_value = current_value
        self.expected_value = expected_value

    def to_dict(self) -> Dict:
        return {
            'url': self.url,
            'issue_type': self.issue_type,
            'category': self.category,
            'severity': self.severity,
            'title': self.title,
            'description': self.description,
            'recommendation': self.recommendation,
            'current_value': self.current_value,
            'expected_value': self.expected_value,
        }


class SEOAuditor:
    """Performs SEO audits on web pages"""

    # Optimal ranges for various SEO elements
    TITLE_MIN_LENGTH = 30
    TITLE_MAX_LENGTH = 60
    META_DESC_MIN_LENGTH = 120
    META_DESC_MAX_LENGTH = 160
    H1_MAX_COUNT = 1
    MIN_WORD_COUNT = 300
    MAX_URL_LENGTH = 75
    MIN_INTERNAL_LINKS = 3
    MIN_EXTERNAL_LINKS = 1

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update(REQUEST_HEADERS)

    def fetch_page(self, url: str) -> Optional[Tuple[str, int]]:
        """Fetch page content and return HTML with status code"""
        try:
            response = self.session.get(url, timeout=REQUEST_TIMEOUT)
            return response.text, response.status_code
        except requests.RequestException as e:
            print(f"Error fetching {url}: {e}")
            return None, 0

    def audit_page(self, url: str) -> List[SEOIssue]:
        """Perform full SEO audit on a single page"""
        issues = []

        # Fetch page
        result = self.fetch_page(url)
        if result[0] is None:
            issues.append(SEOIssue(
                url=url,
                issue_type="page_fetch_error",
                category=CATEGORIES['technical'],
                severity=SEVERITY['critical'],
                title="Page Not Accessible",
                description="Could not fetch the page content",
                recommendation="Verify the page is accessible and returns a 200 status code",
            ))
            return issues

        html_content, status_code = result

        # Check status code
        if status_code != 200:
            issues.append(SEOIssue(
                url=url,
                issue_type="http_status",
                category=CATEGORIES['technical'],
                severity=SEVERITY['critical'],
                title=f"HTTP Status {status_code}",
                description=f"Page returned HTTP status {status_code} instead of 200",
                recommendation="Fix server configuration to return proper 200 status",
                current_value=str(status_code),
                expected_value="200",
            ))

        # Parse HTML
        soup = BeautifulSoup(html_content, 'lxml')

        # Run all audit checks
        issues.extend(self._check_title(url, soup))
        issues.extend(self._check_meta_description(url, soup))
        issues.extend(self._check_headings(url, soup))
        issues.extend(self._check_images(url, soup))
        issues.extend(self._check_links(url, soup))
        issues.extend(self._check_url_structure(url))
        issues.extend(self._check_content(url, soup))
        issues.extend(self._check_canonical(url, soup))
        issues.extend(self._check_robots_meta(url, soup))
        issues.extend(self._check_open_graph(url, soup))
        issues.extend(self._check_twitter_cards(url, soup))
        issues.extend(self._check_hreflang(url, soup))
        issues.extend(self._check_mobile_meta(url, soup))

        return issues

    def _check_title(self, url: str, soup: BeautifulSoup) -> List[SEOIssue]:
        """Check page title tag"""
        issues = []
        title_tag = soup.find('title')

        if not title_tag or not title_tag.string:
            issues.append(SEOIssue(
                url=url,
                issue_type="missing_title",
                category=CATEGORIES['meta'],
                severity=SEVERITY['critical'],
                title="Missing Title Tag",
                description="Page is missing a title tag",
                recommendation="Add a unique, descriptive title tag between 30-60 characters",
            ))
            return issues

        title = title_tag.string.strip()
        title_length = len(title)

        if title_length < self.TITLE_MIN_LENGTH:
            issues.append(SEOIssue(
                url=url,
                issue_type="title_too_short",
                category=CATEGORIES['meta'],
                severity=SEVERITY['medium'],
                title="Title Too Short",
                description=f"Title is {title_length} characters, should be at least {self.TITLE_MIN_LENGTH}",
                recommendation=f"Expand title to {self.TITLE_MIN_LENGTH}-{self.TITLE_MAX_LENGTH} characters",
                current_value=str(title_length),
                expected_value=f"{self.TITLE_MIN_LENGTH}-{self.TITLE_MAX_LENGTH}",
            ))

        if title_length > self.TITLE_MAX_LENGTH:
            issues.append(SEOIssue(
                url=url,
                issue_type="title_too_long",
                category=CATEGORIES['meta'],
                severity=SEVERITY['medium'],
                title="Title Too Long",
                description=f"Title is {title_length} characters, may be truncated in search results",
                recommendation=f"Shorten title to {self.TITLE_MAX_LENGTH} characters or less",
                current_value=str(title_length),
                expected_value=f"<= {self.TITLE_MAX_LENGTH}",
            ))

        return issues

    def _check_meta_description(self, url: str, soup: BeautifulSoup) -> List[SEOIssue]:
        """Check meta description"""
        issues = []
        meta_desc = soup.find('meta', attrs={'name': 'description'})

        if not meta_desc or not meta_desc.get('content'):
            issues.append(SEOIssue(
                url=url,
                issue_type="missing_meta_description",
                category=CATEGORIES['meta'],
                severity=SEVERITY['high'],
                title="Missing Meta Description",
                description="Page is missing a meta description",
                recommendation=f"Add a compelling meta description between {self.META_DESC_MIN_LENGTH}-{self.META_DESC_MAX_LENGTH} characters",
            ))
            return issues

        desc = meta_desc.get('content', '').strip()
        desc_length = len(desc)

        if desc_length < self.META_DESC_MIN_LENGTH:
            issues.append(SEOIssue(
                url=url,
                issue_type="meta_description_too_short",
                category=CATEGORIES['meta'],
                severity=SEVERITY['medium'],
                title="Meta Description Too Short",
                description=f"Meta description is {desc_length} characters",
                recommendation=f"Expand to {self.META_DESC_MIN_LENGTH}-{self.META_DESC_MAX_LENGTH} characters",
                current_value=str(desc_length),
                expected_value=f"{self.META_DESC_MIN_LENGTH}-{self.META_DESC_MAX_LENGTH}",
            ))

        if desc_length > self.META_DESC_MAX_LENGTH:
            issues.append(SEOIssue(
                url=url,
                issue_type="meta_description_too_long",
                category=CATEGORIES['meta'],
                severity=SEVERITY['low'],
                title="Meta Description Too Long",
                description=f"Meta description is {desc_length} characters, may be truncated",
                recommendation=f"Shorten to {self.META_DESC_MAX_LENGTH} characters or less",
                current_value=str(desc_length),
                expected_value=f"<= {self.META_DESC_MAX_LENGTH}",
            ))

        return issues

    def _check_headings(self, url: str, soup: BeautifulSoup) -> List[SEOIssue]:
        """Check heading structure (H1-H6)"""
        issues = []

        h1_tags = soup.find_all('h1')

        if len(h1_tags) == 0:
            issues.append(SEOIssue(
                url=url,
                issue_type="missing_h1",
                category=CATEGORIES['content'],
                severity=SEVERITY['high'],
                title="Missing H1 Tag",
                description="Page does not have an H1 heading",
                recommendation="Add a single, descriptive H1 tag that includes primary keywords",
            ))

        if len(h1_tags) > self.H1_MAX_COUNT:
            issues.append(SEOIssue(
                url=url,
                issue_type="multiple_h1",
                category=CATEGORIES['content'],
                severity=SEVERITY['medium'],
                title="Multiple H1 Tags",
                description=f"Page has {len(h1_tags)} H1 tags, should have only 1",
                recommendation="Consolidate to a single H1 tag and use H2-H6 for subheadings",
                current_value=str(len(h1_tags)),
                expected_value="1",
            ))

        # Check heading hierarchy
        headings = []
        for i in range(1, 7):
            for h in soup.find_all(f'h{i}'):
                headings.append((i, h.get_text(strip=True)))

        # Check for skipped heading levels
        if headings:
            levels_used = sorted(set(h[0] for h in headings))
            for i in range(len(levels_used) - 1):
                if levels_used[i + 1] - levels_used[i] > 1:
                    issues.append(SEOIssue(
                        url=url,
                        issue_type="heading_hierarchy_skip",
                        category=CATEGORIES['structure'],
                        severity=SEVERITY['low'],
                        title="Heading Hierarchy Skip",
                        description=f"Heading levels jump from H{levels_used[i]} to H{levels_used[i + 1]}",
                        recommendation="Maintain proper heading hierarchy without skipping levels",
                    ))
                    break

        return issues

    def _check_images(self, url: str, soup: BeautifulSoup) -> List[SEOIssue]:
        """Check image optimization"""
        issues = []
        images = soup.find_all('img')

        images_without_alt = []
        images_without_src = []

        for img in images:
            src = img.get('src', '')
            alt = img.get('alt')

            if not src:
                images_without_src.append(img)

            if alt is None or alt.strip() == '':
                # Get some identifier for the image
                img_id = src[:50] if src else 'unknown'
                images_without_alt.append(img_id)

        if images_without_alt:
            issues.append(SEOIssue(
                url=url,
                issue_type="images_missing_alt",
                category=CATEGORIES['content'],
                severity=SEVERITY['medium'],
                title="Images Missing Alt Text",
                description=f"{len(images_without_alt)} images are missing alt attributes",
                recommendation="Add descriptive alt text to all images for accessibility and SEO",
                current_value=str(len(images_without_alt)),
                expected_value="0",
            ))

        return issues

    def _check_links(self, url: str, soup: BeautifulSoup) -> List[SEOIssue]:
        """Check internal and external links"""
        issues = []
        parsed_url = urlparse(url)
        base_domain = parsed_url.netloc

        links = soup.find_all('a', href=True)
        internal_links = []
        external_links = []
        broken_anchors = []

        for link in links:
            href = link.get('href', '')

            if not href or href.startswith('#'):
                if href.startswith('#') and len(href) > 1:
                    # Check if anchor target exists
                    anchor_id = href[1:]
                    if not soup.find(id=anchor_id) and not soup.find(attrs={'name': anchor_id}):
                        broken_anchors.append(href)
                continue

            # Resolve relative URLs
            full_url = urljoin(url, href)
            parsed_href = urlparse(full_url)

            if parsed_href.netloc == base_domain:
                internal_links.append(full_url)
            elif parsed_href.scheme in ('http', 'https'):
                external_links.append(full_url)

        if len(internal_links) < self.MIN_INTERNAL_LINKS:
            issues.append(SEOIssue(
                url=url,
                issue_type="few_internal_links",
                category=CATEGORIES['structure'],
                severity=SEVERITY['medium'],
                title="Few Internal Links",
                description=f"Page has only {len(internal_links)} internal links",
                recommendation=f"Add more internal links (at least {self.MIN_INTERNAL_LINKS}) to improve site navigation and SEO",
                current_value=str(len(internal_links)),
                expected_value=f">= {self.MIN_INTERNAL_LINKS}",
            ))

        return issues

    def _check_url_structure(self, url: str) -> List[SEOIssue]:
        """Check URL structure and length"""
        issues = []
        parsed = urlparse(url)
        path = parsed.path

        if len(url) > self.MAX_URL_LENGTH:
            issues.append(SEOIssue(
                url=url,
                issue_type="url_too_long",
                category=CATEGORIES['technical'],
                severity=SEVERITY['low'],
                title="URL Too Long",
                description=f"URL is {len(url)} characters",
                recommendation=f"Keep URLs under {self.MAX_URL_LENGTH} characters for better usability",
                current_value=str(len(url)),
                expected_value=f"<= {self.MAX_URL_LENGTH}",
            ))

        # Check for underscores (hyphens preferred)
        if '_' in path:
            issues.append(SEOIssue(
                url=url,
                issue_type="url_underscores",
                category=CATEGORIES['technical'],
                severity=SEVERITY['low'],
                title="URL Contains Underscores",
                description="URL path contains underscores instead of hyphens",
                recommendation="Use hyphens (-) instead of underscores (_) in URLs",
            ))

        # Check for uppercase characters
        if path != path.lower():
            issues.append(SEOIssue(
                url=url,
                issue_type="url_uppercase",
                category=CATEGORIES['technical'],
                severity=SEVERITY['low'],
                title="URL Contains Uppercase",
                description="URL path contains uppercase characters",
                recommendation="Use lowercase characters in URLs for consistency",
            ))

        return issues

    def _check_content(self, url: str, soup: BeautifulSoup) -> List[SEOIssue]:
        """Check content quality indicators"""
        issues = []

        # Get text content (excluding scripts and styles)
        for element in soup(['script', 'style', 'nav', 'footer', 'header']):
            element.decompose()

        text = soup.get_text(separator=' ', strip=True)
        words = text.split()
        word_count = len(words)

        if word_count < self.MIN_WORD_COUNT:
            issues.append(SEOIssue(
                url=url,
                issue_type="thin_content",
                category=CATEGORIES['content'],
                severity=SEVERITY['high'],
                title="Thin Content",
                description=f"Page has only {word_count} words of content",
                recommendation=f"Add more valuable content (at least {self.MIN_WORD_COUNT} words)",
                current_value=str(word_count),
                expected_value=f">= {self.MIN_WORD_COUNT}",
            ))

        return issues

    def _check_canonical(self, url: str, soup: BeautifulSoup) -> List[SEOIssue]:
        """Check canonical URL"""
        issues = []
        canonical = soup.find('link', rel='canonical')

        if not canonical or not canonical.get('href'):
            issues.append(SEOIssue(
                url=url,
                issue_type="missing_canonical",
                category=CATEGORIES['technical'],
                severity=SEVERITY['medium'],
                title="Missing Canonical Tag",
                description="Page does not have a canonical URL specified",
                recommendation="Add a canonical tag to prevent duplicate content issues",
            ))

        return issues

    def _check_robots_meta(self, url: str, soup: BeautifulSoup) -> List[SEOIssue]:
        """Check robots meta tag"""
        issues = []
        robots = soup.find('meta', attrs={'name': 'robots'})

        if robots:
            content = robots.get('content', '').lower()
            if 'noindex' in content:
                issues.append(SEOIssue(
                    url=url,
                    issue_type="noindex_tag",
                    category=CATEGORIES['technical'],
                    severity=SEVERITY['critical'],
                    title="Page Set to NoIndex",
                    description="Page has noindex directive and won't appear in search results",
                    recommendation="Remove noindex if this page should be indexed",
                    current_value=content,
                ))

        return issues

    def _check_open_graph(self, url: str, soup: BeautifulSoup) -> List[SEOIssue]:
        """Check Open Graph tags for social sharing"""
        issues = []
        required_og = ['og:title', 'og:description', 'og:image', 'og:url']
        missing_og = []

        for og_prop in required_og:
            og_tag = soup.find('meta', property=og_prop)
            if not og_tag or not og_tag.get('content'):
                missing_og.append(og_prop)

        if missing_og:
            issues.append(SEOIssue(
                url=url,
                issue_type="missing_open_graph",
                category=CATEGORIES['meta'],
                severity=SEVERITY['medium'],
                title="Missing Open Graph Tags",
                description=f"Missing Open Graph tags: {', '.join(missing_og)}",
                recommendation="Add Open Graph tags for better social media sharing",
                current_value=', '.join(missing_og),
            ))

        return issues

    def _check_twitter_cards(self, url: str, soup: BeautifulSoup) -> List[SEOIssue]:
        """Check Twitter Card tags"""
        issues = []
        twitter_card = soup.find('meta', attrs={'name': 'twitter:card'})

        if not twitter_card:
            issues.append(SEOIssue(
                url=url,
                issue_type="missing_twitter_card",
                category=CATEGORIES['meta'],
                severity=SEVERITY['low'],
                title="Missing Twitter Card",
                description="Page does not have Twitter Card meta tags",
                recommendation="Add Twitter Card tags for better Twitter sharing",
            ))

        return issues

    def _check_hreflang(self, url: str, soup: BeautifulSoup) -> List[SEOIssue]:
        """Check hreflang tags for international SEO"""
        issues = []
        # This is informational - only flag if partial implementation
        hreflang_tags = soup.find_all('link', rel='alternate', hreflang=True)

        if hreflang_tags:
            # Check for x-default
            has_xdefault = any(tag.get('hreflang') == 'x-default' for tag in hreflang_tags)
            if not has_xdefault:
                issues.append(SEOIssue(
                    url=url,
                    issue_type="missing_hreflang_xdefault",
                    category=CATEGORIES['technical'],
                    severity=SEVERITY['low'],
                    title="Missing hreflang x-default",
                    description="hreflang tags present but missing x-default fallback",
                    recommendation="Add x-default hreflang for users outside targeted regions",
                ))

        return issues

    def _check_mobile_meta(self, url: str, soup: BeautifulSoup) -> List[SEOIssue]:
        """Check mobile-specific meta tags"""
        issues = []
        viewport = soup.find('meta', attrs={'name': 'viewport'})

        if not viewport:
            issues.append(SEOIssue(
                url=url,
                issue_type="missing_viewport",
                category=CATEGORIES['technical'],
                severity=SEVERITY['high'],
                title="Missing Viewport Meta Tag",
                description="Page does not have a viewport meta tag for mobile responsiveness",
                recommendation="Add <meta name='viewport' content='width=device-width, initial-scale=1'>",
            ))

        return issues

    def audit_pages(self, urls: List[Dict]) -> List[SEOIssue]:
        """Audit multiple pages with rate limiting"""
        all_issues = []

        for i, url_data in enumerate(urls):
            url = url_data['url']
            print(f"Auditing ({i + 1}/{len(urls)}): {url}")

            issues = self.audit_page(url)
            all_issues.extend(issues)

            # Rate limiting
            if i < len(urls) - 1:
                time.sleep(DELAY_BETWEEN_REQUESTS)

        return all_issues


def main():
    """Test the SEO auditor"""
    auditor = SEOAuditor()
    issues = auditor.audit_page("https://www.outrigger.com")

    print(f"\nFound {len(issues)} issues:")
    for issue in issues:
        print(f"  [{issue.severity}] {issue.title}: {issue.description}")


if __name__ == "__main__":
    main()
