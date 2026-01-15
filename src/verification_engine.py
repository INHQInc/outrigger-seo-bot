"""
Verification Engine Module
Verifies if SEO/GEO fixes have been properly applied
"""
import requests
import json
import re
from bs4 import BeautifulSoup
from typing import List, Dict, Optional, Tuple
from datetime import datetime

from config import (
    REQUEST_TIMEOUT,
    REQUEST_HEADERS,
)


class VerificationResult:
    """Result of a verification check"""

    def __init__(
        self,
        issue_type: str,
        url: str,
        is_fixed: bool,
        details: str,
        previous_value: str = None,
        current_value: str = None,
    ):
        self.issue_type = issue_type
        self.url = url
        self.is_fixed = is_fixed
        self.details = details
        self.previous_value = previous_value
        self.current_value = current_value
        self.verified_at = datetime.now()

    def to_dict(self) -> Dict:
        return {
            "issue_type": self.issue_type,
            "url": self.url,
            "is_fixed": self.is_fixed,
            "details": self.details,
            "previous_value": self.previous_value,
            "current_value": self.current_value,
            "verified_at": self.verified_at.isoformat(),
        }


class VerificationEngine:
    """
    Verifies if SEO/GEO issues have been fixed.
    Runs checks based on the issue type and compares against expected values.
    """

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update(REQUEST_HEADERS)

    def fetch_page(self, url: str) -> Optional[Tuple[str, int]]:
        """Fetch page content"""
        try:
            response = self.session.get(url, timeout=REQUEST_TIMEOUT)
            return response.text, response.status_code
        except requests.RequestException as e:
            print(f"Error fetching {url}: {e}")
            return None, 0

    def verify_issue(self, issue: Dict) -> VerificationResult:
        """
        Verify if a specific issue has been fixed.

        Args:
            issue: Dictionary containing issue details including:
                - url: The page URL
                - issue_type: Type of issue to verify
                - expected_value: What the fixed state should look like (optional)
                - current_value: The value when issue was first found (optional)
        """
        url = issue.get("url")
        issue_type = issue.get("issue_type")
        expected_value = issue.get("expected_value")
        original_value = issue.get("current_value")

        # Fetch the page
        result = self.fetch_page(url)
        if result[0] is None:
            return VerificationResult(
                issue_type=issue_type,
                url=url,
                is_fixed=False,
                details="Could not fetch page to verify fix",
            )

        html_content, status_code = result
        soup = BeautifulSoup(html_content, "lxml")

        # Route to appropriate verification method
        verification_methods = {
            # Meta tag issues
            "missing_title": self._verify_title,
            "title_too_short": self._verify_title_length,
            "title_too_long": self._verify_title_length,
            "missing_meta_description": self._verify_meta_description,
            "meta_description_too_short": self._verify_meta_description_length,
            "meta_description_too_long": self._verify_meta_description_length,

            # Heading issues
            "missing_h1": self._verify_h1,
            "multiple_h1": self._verify_single_h1,
            "heading_hierarchy_skip": self._verify_heading_hierarchy,

            # Image issues
            "images_missing_alt": self._verify_images_alt,

            # Technical issues
            "missing_canonical": self._verify_canonical,
            "noindex_tag": self._verify_no_noindex,
            "missing_viewport": self._verify_viewport,
            "http_status": self._verify_http_status,

            # Social tags
            "missing_open_graph": self._verify_open_graph,
            "missing_twitter_card": self._verify_twitter_card,

            # Content issues
            "thin_content": self._verify_content_length,

            # Schema/GEO issues
            "missing_schema": self._verify_schema_exists,
            "missing_webpage_schema": self._verify_webpage_schema,
            "missing_organization_schema": self._verify_organization_schema,
            "faq_missing_schema": self._verify_faq_schema,
            "howto_missing_schema": self._verify_howto_schema,
            "missing_hotel_schema": self._verify_hotel_schema,
            "breadcrumb_missing_schema": self._verify_breadcrumb_schema,
            "missing_speakable": self._verify_speakable,
        }

        verify_method = verification_methods.get(issue_type)
        if verify_method:
            return verify_method(url, soup, html_content, issue)
        else:
            return VerificationResult(
                issue_type=issue_type,
                url=url,
                is_fixed=False,
                details=f"No verification method for issue type: {issue_type}",
            )

    # ============ Meta Tag Verifications ============

    def _verify_title(self, url: str, soup: BeautifulSoup, html: str, issue: Dict) -> VerificationResult:
        """Verify title tag exists"""
        title = soup.find("title")
        is_fixed = title is not None and title.string and len(title.string.strip()) > 0

        return VerificationResult(
            issue_type="missing_title",
            url=url,
            is_fixed=is_fixed,
            details="Title tag now exists" if is_fixed else "Title tag still missing",
            current_value=title.string.strip() if is_fixed else None,
        )

    def _verify_title_length(self, url: str, soup: BeautifulSoup, html: str, issue: Dict) -> VerificationResult:
        """Verify title length is within optimal range"""
        title = soup.find("title")
        if not title or not title.string:
            return VerificationResult(
                issue_type=issue.get("issue_type"),
                url=url,
                is_fixed=False,
                details="Title tag is missing",
            )

        length = len(title.string.strip())
        is_fixed = 30 <= length <= 60

        return VerificationResult(
            issue_type=issue.get("issue_type"),
            url=url,
            is_fixed=is_fixed,
            details=f"Title length is now {length} characters" + (" (optimal)" if is_fixed else " (needs adjustment)"),
            previous_value=issue.get("current_value"),
            current_value=str(length),
        )

    def _verify_meta_description(self, url: str, soup: BeautifulSoup, html: str, issue: Dict) -> VerificationResult:
        """Verify meta description exists"""
        meta_desc = soup.find("meta", attrs={"name": "description"})
        is_fixed = meta_desc is not None and meta_desc.get("content")

        return VerificationResult(
            issue_type="missing_meta_description",
            url=url,
            is_fixed=is_fixed,
            details="Meta description now exists" if is_fixed else "Meta description still missing",
            current_value=meta_desc.get("content")[:100] if is_fixed else None,
        )

    def _verify_meta_description_length(self, url: str, soup: BeautifulSoup, html: str, issue: Dict) -> VerificationResult:
        """Verify meta description length is within optimal range"""
        meta_desc = soup.find("meta", attrs={"name": "description"})
        if not meta_desc or not meta_desc.get("content"):
            return VerificationResult(
                issue_type=issue.get("issue_type"),
                url=url,
                is_fixed=False,
                details="Meta description is missing",
            )

        length = len(meta_desc.get("content").strip())
        is_fixed = 120 <= length <= 160

        return VerificationResult(
            issue_type=issue.get("issue_type"),
            url=url,
            is_fixed=is_fixed,
            details=f"Meta description length is now {length} characters" + (" (optimal)" if is_fixed else ""),
            previous_value=issue.get("current_value"),
            current_value=str(length),
        )

    # ============ Heading Verifications ============

    def _verify_h1(self, url: str, soup: BeautifulSoup, html: str, issue: Dict) -> VerificationResult:
        """Verify H1 tag exists"""
        h1 = soup.find("h1")
        is_fixed = h1 is not None and h1.get_text(strip=True)

        return VerificationResult(
            issue_type="missing_h1",
            url=url,
            is_fixed=is_fixed,
            details="H1 tag now exists" if is_fixed else "H1 tag still missing",
            current_value=h1.get_text(strip=True)[:50] if is_fixed else None,
        )

    def _verify_single_h1(self, url: str, soup: BeautifulSoup, html: str, issue: Dict) -> VerificationResult:
        """Verify only one H1 tag exists"""
        h1_tags = soup.find_all("h1")
        is_fixed = len(h1_tags) == 1

        return VerificationResult(
            issue_type="multiple_h1",
            url=url,
            is_fixed=is_fixed,
            details=f"Page now has {len(h1_tags)} H1 tag(s)" + (" (correct)" if is_fixed else " (should be 1)"),
            previous_value=issue.get("current_value"),
            current_value=str(len(h1_tags)),
        )

    def _verify_heading_hierarchy(self, url: str, soup: BeautifulSoup, html: str, issue: Dict) -> VerificationResult:
        """Verify heading hierarchy doesn't skip levels"""
        headings = []
        for i in range(1, 7):
            for h in soup.find_all(f"h{i}"):
                headings.append(i)

        if not headings:
            return VerificationResult(
                issue_type="heading_hierarchy_skip",
                url=url,
                is_fixed=True,
                details="No headings found to check hierarchy",
            )

        levels = sorted(set(headings))
        has_skip = False
        for i in range(len(levels) - 1):
            if levels[i + 1] - levels[i] > 1:
                has_skip = True
                break

        return VerificationResult(
            issue_type="heading_hierarchy_skip",
            url=url,
            is_fixed=not has_skip,
            details="Heading hierarchy is now correct" if not has_skip else "Heading hierarchy still has skips",
            current_value=str(levels),
        )

    # ============ Image Verifications ============

    def _verify_images_alt(self, url: str, soup: BeautifulSoup, html: str, issue: Dict) -> VerificationResult:
        """Verify all images have alt text"""
        images = soup.find_all("img")
        missing_alt = [img for img in images if not img.get("alt")]

        is_fixed = len(missing_alt) == 0

        return VerificationResult(
            issue_type="images_missing_alt",
            url=url,
            is_fixed=is_fixed,
            details=f"{len(missing_alt)} images still missing alt text" if not is_fixed else "All images now have alt text",
            previous_value=issue.get("current_value"),
            current_value=str(len(missing_alt)),
        )

    # ============ Technical Verifications ============

    def _verify_canonical(self, url: str, soup: BeautifulSoup, html: str, issue: Dict) -> VerificationResult:
        """Verify canonical tag exists"""
        canonical = soup.find("link", rel="canonical")
        is_fixed = canonical is not None and canonical.get("href")

        return VerificationResult(
            issue_type="missing_canonical",
            url=url,
            is_fixed=is_fixed,
            details="Canonical tag now exists" if is_fixed else "Canonical tag still missing",
            current_value=canonical.get("href") if is_fixed else None,
        )

    def _verify_no_noindex(self, url: str, soup: BeautifulSoup, html: str, issue: Dict) -> VerificationResult:
        """Verify noindex has been removed"""
        robots = soup.find("meta", attrs={"name": "robots"})
        has_noindex = robots and "noindex" in robots.get("content", "").lower()

        return VerificationResult(
            issue_type="noindex_tag",
            url=url,
            is_fixed=not has_noindex,
            details="NoIndex has been removed" if not has_noindex else "NoIndex is still present",
            current_value=robots.get("content") if robots else None,
        )

    def _verify_viewport(self, url: str, soup: BeautifulSoup, html: str, issue: Dict) -> VerificationResult:
        """Verify viewport meta tag exists"""
        viewport = soup.find("meta", attrs={"name": "viewport"})
        is_fixed = viewport is not None

        return VerificationResult(
            issue_type="missing_viewport",
            url=url,
            is_fixed=is_fixed,
            details="Viewport meta tag now exists" if is_fixed else "Viewport meta tag still missing",
        )

    def _verify_http_status(self, url: str, soup: BeautifulSoup, html: str, issue: Dict) -> VerificationResult:
        """Verify page returns 200 status"""
        try:
            response = self.session.head(url, timeout=REQUEST_TIMEOUT)
            is_fixed = response.status_code == 200
            return VerificationResult(
                issue_type="http_status",
                url=url,
                is_fixed=is_fixed,
                details=f"Page now returns {response.status_code}",
                previous_value=issue.get("current_value"),
                current_value=str(response.status_code),
            )
        except:
            return VerificationResult(
                issue_type="http_status",
                url=url,
                is_fixed=False,
                details="Could not check HTTP status",
            )

    # ============ Social Tag Verifications ============

    def _verify_open_graph(self, url: str, soup: BeautifulSoup, html: str, issue: Dict) -> VerificationResult:
        """Verify Open Graph tags exist"""
        required = ["og:title", "og:description", "og:image", "og:url"]
        found = []
        missing = []

        for og in required:
            tag = soup.find("meta", property=og)
            if tag and tag.get("content"):
                found.append(og)
            else:
                missing.append(og)

        is_fixed = len(missing) == 0

        return VerificationResult(
            issue_type="missing_open_graph",
            url=url,
            is_fixed=is_fixed,
            details=f"Open Graph tags complete" if is_fixed else f"Still missing: {', '.join(missing)}",
            current_value=f"Found: {', '.join(found)}" if found else None,
        )

    def _verify_twitter_card(self, url: str, soup: BeautifulSoup, html: str, issue: Dict) -> VerificationResult:
        """Verify Twitter Card exists"""
        twitter_card = soup.find("meta", attrs={"name": "twitter:card"})
        is_fixed = twitter_card is not None

        return VerificationResult(
            issue_type="missing_twitter_card",
            url=url,
            is_fixed=is_fixed,
            details="Twitter Card now exists" if is_fixed else "Twitter Card still missing",
        )

    # ============ Content Verifications ============

    def _verify_content_length(self, url: str, soup: BeautifulSoup, html: str, issue: Dict) -> VerificationResult:
        """Verify content meets minimum word count"""
        for element in soup(["script", "style", "nav", "footer", "header"]):
            element.decompose()

        text = soup.get_text(separator=" ", strip=True)
        word_count = len(text.split())
        is_fixed = word_count >= 300

        return VerificationResult(
            issue_type="thin_content",
            url=url,
            is_fixed=is_fixed,
            details=f"Page now has {word_count} words" + (" (sufficient)" if is_fixed else " (needs more content)"),
            previous_value=issue.get("current_value"),
            current_value=str(word_count),
        )

    # ============ Schema/GEO Verifications ============

    def _extract_json_ld(self, html: str) -> List[Dict]:
        """Extract JSON-LD from HTML"""
        schemas = []
        soup = BeautifulSoup(html, "lxml")

        for script in soup.find_all("script", type="application/ld+json"):
            try:
                data = json.loads(script.string)
                if isinstance(data, list):
                    schemas.extend(data)
                else:
                    schemas.append(data)
            except:
                continue

        return schemas

    def _get_schema_types(self, html: str) -> set:
        """Get all schema types from page"""
        schemas = self._extract_json_ld(html)
        types = set()

        for schema in schemas:
            if "@type" in schema:
                t = schema["@type"]
                if isinstance(t, list):
                    types.update(t)
                else:
                    types.add(t)

        return types

    def _verify_schema_exists(self, url: str, soup: BeautifulSoup, html: str, issue: Dict) -> VerificationResult:
        """Verify structured data exists"""
        schemas = self._extract_json_ld(html)
        is_fixed = len(schemas) > 0

        return VerificationResult(
            issue_type="missing_schema",
            url=url,
            is_fixed=is_fixed,
            details=f"Found {len(schemas)} schema(s)" if is_fixed else "No structured data found",
        )

    def _verify_webpage_schema(self, url: str, soup: BeautifulSoup, html: str, issue: Dict) -> VerificationResult:
        """Verify WebPage or WebSite schema exists"""
        types = self._get_schema_types(html)
        is_fixed = bool(types.intersection({"WebPage", "WebSite"}))

        return VerificationResult(
            issue_type="missing_webpage_schema",
            url=url,
            is_fixed=is_fixed,
            details="WebPage/WebSite schema now exists" if is_fixed else "WebPage/WebSite schema still missing",
            current_value=str(types) if types else None,
        )

    def _verify_organization_schema(self, url: str, soup: BeautifulSoup, html: str, issue: Dict) -> VerificationResult:
        """Verify Organization schema exists"""
        types = self._get_schema_types(html)
        org_types = {"Organization", "Corporation", "Hotel", "LodgingBusiness"}
        is_fixed = bool(types.intersection(org_types))

        return VerificationResult(
            issue_type="missing_organization_schema",
            url=url,
            is_fixed=is_fixed,
            details="Organization schema now exists" if is_fixed else "Organization schema still missing",
            current_value=str(types) if types else None,
        )

    def _verify_faq_schema(self, url: str, soup: BeautifulSoup, html: str, issue: Dict) -> VerificationResult:
        """Verify FAQPage schema exists"""
        types = self._get_schema_types(html)
        is_fixed = "FAQPage" in types

        return VerificationResult(
            issue_type="faq_missing_schema",
            url=url,
            is_fixed=is_fixed,
            details="FAQPage schema now exists" if is_fixed else "FAQPage schema still missing",
        )

    def _verify_howto_schema(self, url: str, soup: BeautifulSoup, html: str, issue: Dict) -> VerificationResult:
        """Verify HowTo schema exists"""
        types = self._get_schema_types(html)
        is_fixed = "HowTo" in types

        return VerificationResult(
            issue_type="howto_missing_schema",
            url=url,
            is_fixed=is_fixed,
            details="HowTo schema now exists" if is_fixed else "HowTo schema still missing",
        )

    def _verify_hotel_schema(self, url: str, soup: BeautifulSoup, html: str, issue: Dict) -> VerificationResult:
        """Verify Hotel/LodgingBusiness schema exists"""
        types = self._get_schema_types(html)
        hotel_types = {"Hotel", "LodgingBusiness", "Resort"}
        is_fixed = bool(types.intersection(hotel_types))

        return VerificationResult(
            issue_type="missing_hotel_schema",
            url=url,
            is_fixed=is_fixed,
            details="Hotel schema now exists" if is_fixed else "Hotel schema still missing",
            current_value=str(types) if types else None,
        )

    def _verify_breadcrumb_schema(self, url: str, soup: BeautifulSoup, html: str, issue: Dict) -> VerificationResult:
        """Verify BreadcrumbList schema exists"""
        types = self._get_schema_types(html)
        is_fixed = "BreadcrumbList" in types

        return VerificationResult(
            issue_type="breadcrumb_missing_schema",
            url=url,
            is_fixed=is_fixed,
            details="BreadcrumbList schema now exists" if is_fixed else "BreadcrumbList schema still missing",
        )

    def _verify_speakable(self, url: str, soup: BeautifulSoup, html: str, issue: Dict) -> VerificationResult:
        """Verify speakable schema property exists"""
        schemas = self._extract_json_ld(html)
        has_speakable = any("speakable" in schema for schema in schemas)

        return VerificationResult(
            issue_type="missing_speakable",
            url=url,
            is_fixed=has_speakable,
            details="Speakable property now exists" if has_speakable else "Speakable property still missing",
        )

    def verify_batch(self, issues: List[Dict]) -> List[VerificationResult]:
        """Verify multiple issues"""
        results = []

        for issue in issues:
            result = self.verify_issue(issue)
            results.append(result)
            print(f"Verified: {issue.get('url')} - {issue.get('issue_type')} - {'FIXED' if result.is_fixed else 'NOT FIXED'}")

        return results


def main():
    """Test the verification engine"""
    engine = VerificationEngine()

    test_issue = {
        "url": "https://www.outrigger.com",
        "issue_type": "missing_meta_description",
    }

    result = engine.verify_issue(test_issue)
    print(f"\nVerification result:")
    print(f"  Fixed: {result.is_fixed}")
    print(f"  Details: {result.details}")


if __name__ == "__main__":
    main()
