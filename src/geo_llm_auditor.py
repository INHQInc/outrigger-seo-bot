"""
GEO/LLM Visibility Auditor Module
Analyzes pages for AI/LLM search visibility optimization
(Generative Engine Optimization)
"""
import requests
import json
import re
from bs4 import BeautifulSoup
from typing import List, Dict, Optional
from urllib.parse import urlparse

from config import (
    REQUEST_TIMEOUT,
    REQUEST_HEADERS,
    SEVERITY,
    CATEGORIES,
)


class GEOIssue:
    """Represents a GEO/LLM visibility issue"""

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


class GEOLLMAuditor:
    """
    Audits pages for GEO (Generative Engine Optimization) and LLM visibility.

    GEO focuses on optimizing content for AI-powered search engines like:
    - Google AI Overviews (formerly SGE)
    - Bing Chat / Copilot
    - Perplexity AI
    - ChatGPT with browsing

    Key factors for LLM visibility:
    1. Structured Data (Schema.org)
    2. Entity clarity and disambiguation
    3. FAQ and How-To content formats
    4. Natural language query matching
    5. Content authority signals
    6. Freshness indicators
    7. Citation-worthy content structure
    """

    # Schema types important for hospitality/travel industry
    HOSPITALITY_SCHEMAS = [
        'Hotel',
        'LodgingBusiness',
        'Resort',
        'LocalBusiness',
        'Organization',
        'WebSite',
        'WebPage',
        'BreadcrumbList',
        'FAQPage',
        'HowTo',
        'Review',
        'AggregateRating',
        'Offer',
        'Place',
        'TouristAttraction',
        'TouristDestination',
    ]

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update(REQUEST_HEADERS)

    def fetch_page(self, url: str) -> Optional[str]:
        """Fetch page content"""
        try:
            response = self.session.get(url, timeout=REQUEST_TIMEOUT)
            response.raise_for_status()
            return response.text
        except requests.RequestException as e:
            print(f"Error fetching {url}: {e}")
            return None

    def audit_page(self, url: str) -> List[GEOIssue]:
        """Perform GEO/LLM visibility audit on a single page"""
        issues = []

        html_content = self.fetch_page(url)
        if not html_content:
            issues.append(GEOIssue(
                url=url,
                issue_type="page_fetch_error",
                category=CATEGORIES['geo_llm'],
                severity=SEVERITY['critical'],
                title="Page Not Accessible for GEO Audit",
                description="Could not fetch page content for GEO analysis",
                recommendation="Ensure page is accessible",
            ))
            return issues

        soup = BeautifulSoup(html_content, 'lxml')

        # Run all GEO/LLM checks
        issues.extend(self._check_schema_markup(url, soup, html_content))
        issues.extend(self._check_entity_clarity(url, soup))
        issues.extend(self._check_faq_content(url, soup, html_content))
        issues.extend(self._check_how_to_content(url, soup, html_content))
        issues.extend(self._check_local_business_schema(url, html_content))
        issues.extend(self._check_breadcrumb_schema(url, html_content))
        issues.extend(self._check_content_structure(url, soup))
        issues.extend(self._check_natural_language_optimization(url, soup))
        issues.extend(self._check_citation_worthiness(url, soup))
        issues.extend(self._check_speakable_content(url, html_content))
        issues.extend(self._check_ai_crawler_access(url, soup))

        return issues

    def _extract_json_ld(self, html_content: str) -> List[Dict]:
        """Extract all JSON-LD structured data from page"""
        schemas = []
        soup = BeautifulSoup(html_content, 'lxml')

        for script in soup.find_all('script', type='application/ld+json'):
            try:
                data = json.loads(script.string)
                if isinstance(data, list):
                    schemas.extend(data)
                else:
                    schemas.append(data)
            except (json.JSONDecodeError, TypeError):
                continue

        return schemas

    def _check_schema_markup(self, url: str, soup: BeautifulSoup, html_content: str) -> List[GEOIssue]:
        """Check for structured data (Schema.org) markup"""
        issues = []
        schemas = self._extract_json_ld(html_content)

        if not schemas:
            # Also check for microdata
            has_microdata = soup.find(attrs={'itemtype': True})
            if not has_microdata:
                issues.append(GEOIssue(
                    url=url,
                    issue_type="missing_schema",
                    category=CATEGORIES['schema'],
                    severity=SEVERITY['high'],
                    title="No Structured Data Found",
                    description="Page has no JSON-LD or microdata structured data",
                    recommendation="Add Schema.org structured data (JSON-LD recommended) for better AI/LLM understanding",
                ))
                return issues

        # Check for essential schema types
        schema_types = set()
        for schema in schemas:
            if '@type' in schema:
                schema_type = schema['@type']
                if isinstance(schema_type, list):
                    schema_types.update(schema_type)
                else:
                    schema_types.add(schema_type)

        # Check for WebPage or WebSite schema
        if not schema_types.intersection({'WebPage', 'WebSite'}):
            issues.append(GEOIssue(
                url=url,
                issue_type="missing_webpage_schema",
                category=CATEGORIES['schema'],
                severity=SEVERITY['medium'],
                title="Missing WebPage/WebSite Schema",
                description="Page lacks WebPage or WebSite schema type",
                recommendation="Add WebPage schema to help LLMs understand page purpose and hierarchy",
            ))

        # Check for Organization schema (important for brand recognition)
        if not schema_types.intersection({'Organization', 'Corporation', 'Hotel', 'LodgingBusiness'}):
            issues.append(GEOIssue(
                url=url,
                issue_type="missing_organization_schema",
                category=CATEGORIES['schema'],
                severity=SEVERITY['medium'],
                title="Missing Organization Schema",
                description="No Organization or business-type schema found",
                recommendation="Add Organization schema for brand entity recognition by AI systems",
            ))

        return issues

    def _check_entity_clarity(self, url: str, soup: BeautifulSoup) -> List[GEOIssue]:
        """Check for clear entity identification (who, what, where)"""
        issues = []

        # Check for clear business/brand name in prominent positions
        h1 = soup.find('h1')
        title = soup.find('title')

        # Look for contact/about information
        contact_indicators = ['contact', 'about', 'address', 'phone', 'email']
        has_contact_section = any(
            soup.find(string=re.compile(indicator, re.I))
            for indicator in contact_indicators
        )

        # Check for author/organization attribution
        author_meta = soup.find('meta', attrs={'name': 'author'})
        publisher_schema = soup.find('script', string=re.compile('"publisher"', re.I)) if soup.find('script', type='application/ld+json') else None

        if not author_meta and not publisher_schema:
            issues.append(GEOIssue(
                url=url,
                issue_type="unclear_entity_attribution",
                category=CATEGORIES['geo_llm'],
                severity=SEVERITY['medium'],
                title="Unclear Content Attribution",
                description="Page lacks clear author or publisher attribution",
                recommendation="Add author meta tag or publisher schema for LLM trust signals",
            ))

        return issues

    def _check_faq_content(self, url: str, soup: BeautifulSoup, html_content: str) -> List[GEOIssue]:
        """Check for FAQ content structure (highly valued by LLMs)"""
        issues = []

        # Check for FAQ schema
        schemas = self._extract_json_ld(html_content)
        has_faq_schema = any(
            schema.get('@type') == 'FAQPage' or
            (isinstance(schema.get('@type'), list) and 'FAQPage' in schema.get('@type', []))
            for schema in schemas
        )

        # Check for FAQ-like content patterns
        faq_patterns = [
            r'frequently\s+asked\s+questions?',
            r'\bfaq\b',
            r'questions?\s*(and|&)\s*answers?',
            r'q\s*(&|and)\s*a\b',
        ]

        has_faq_content = any(
            soup.find(string=re.compile(pattern, re.I))
            for pattern in faq_patterns
        )

        # Check for question-answer structure
        questions = soup.find_all(string=re.compile(r'^(what|how|why|when|where|who|can|do|does|is|are|will|should)\s+.+\?$', re.I))

        if has_faq_content and not has_faq_schema:
            issues.append(GEOIssue(
                url=url,
                issue_type="faq_missing_schema",
                category=CATEGORIES['schema'],
                severity=SEVERITY['high'],
                title="FAQ Content Without Schema",
                description="Page has FAQ-style content but lacks FAQPage schema",
                recommendation="Add FAQPage structured data to make FAQ content eligible for rich results and AI citations",
            ))

        # Suggest adding FAQ if it's a key page without one
        if not has_faq_content and not has_faq_schema:
            # Check if this is a page that would benefit from FAQs
            page_path = urlparse(url).path.lower()
            faq_worthy_pages = ['hotel', 'resort', 'room', 'booking', 'reservation', 'amenities', 'location']
            if any(keyword in page_path for keyword in faq_worthy_pages):
                issues.append(GEOIssue(
                    url=url,
                    issue_type="missing_faq_opportunity",
                    category=CATEGORIES['geo_llm'],
                    severity=SEVERITY['low'],
                    title="FAQ Content Opportunity",
                    description="This page type would benefit from FAQ content for LLM visibility",
                    recommendation="Consider adding an FAQ section with FAQPage schema to capture question-based AI queries",
                ))

        return issues

    def _check_how_to_content(self, url: str, soup: BeautifulSoup, html_content: str) -> List[GEOIssue]:
        """Check for How-To content structure"""
        issues = []

        schemas = self._extract_json_ld(html_content)
        has_howto_schema = any(
            schema.get('@type') == 'HowTo'
            for schema in schemas
        )

        # Check for how-to style content
        howto_patterns = [
            r'how\s+to\s+\w+',
            r'step\s+\d+',
            r'guide\s+to',
            r'instructions?\s+for',
        ]

        has_howto_content = any(
            soup.find(string=re.compile(pattern, re.I))
            for pattern in howto_patterns
        )

        # Check for ordered lists (potential how-to steps)
        ordered_lists = soup.find_all('ol')
        has_step_lists = len(ordered_lists) > 0

        if (has_howto_content or has_step_lists) and not has_howto_schema:
            issues.append(GEOIssue(
                url=url,
                issue_type="howto_missing_schema",
                category=CATEGORIES['schema'],
                severity=SEVERITY['medium'],
                title="How-To Content Without Schema",
                description="Page has instructional content but lacks HowTo schema",
                recommendation="Add HowTo structured data for step-by-step content to improve AI visibility",
            ))

        return issues

    def _check_local_business_schema(self, url: str, html_content: str) -> List[GEOIssue]:
        """Check for LocalBusiness/Hotel schema (critical for hospitality)"""
        issues = []

        schemas = self._extract_json_ld(html_content)
        business_types = {'LocalBusiness', 'Hotel', 'LodgingBusiness', 'Resort', 'Motel', 'Hostel'}

        has_business_schema = any(
            schema.get('@type') in business_types or
            (isinstance(schema.get('@type'), list) and business_types.intersection(set(schema.get('@type', []))))
            for schema in schemas
        )

        if not has_business_schema:
            # Check if this appears to be a hotel/property page
            page_indicators = ['hotel', 'resort', 'property', 'location', 'stay']
            url_lower = url.lower()
            if any(indicator in url_lower for indicator in page_indicators):
                issues.append(GEOIssue(
                    url=url,
                    issue_type="missing_hotel_schema",
                    category=CATEGORIES['schema'],
                    severity=SEVERITY['high'],
                    title="Missing Hotel/Business Schema",
                    description="Property page lacks Hotel or LodgingBusiness schema",
                    recommendation="Add Hotel schema with address, amenities, and priceRange for local search and AI visibility",
                ))

        # Check for required properties in hotel schema
        for schema in schemas:
            if schema.get('@type') in business_types:
                missing_props = []
                required_props = ['name', 'address', 'telephone', 'image']
                recommended_props = ['priceRange', 'amenityFeature', 'checkinTime', 'checkoutTime', 'numberOfRooms']

                for prop in required_props:
                    if prop not in schema:
                        missing_props.append(prop)

                if missing_props:
                    issues.append(GEOIssue(
                        url=url,
                        issue_type="incomplete_hotel_schema",
                        category=CATEGORIES['schema'],
                        severity=SEVERITY['medium'],
                        title="Incomplete Hotel Schema",
                        description=f"Hotel schema missing: {', '.join(missing_props)}",
                        recommendation="Add missing required properties for complete hotel information",
                        current_value=f"Missing: {', '.join(missing_props)}",
                    ))

        return issues

    def _check_breadcrumb_schema(self, url: str, html_content: str) -> List[GEOIssue]:
        """Check for BreadcrumbList schema"""
        issues = []

        schemas = self._extract_json_ld(html_content)
        has_breadcrumb = any(
            schema.get('@type') == 'BreadcrumbList'
            for schema in schemas
        )

        soup = BeautifulSoup(html_content, 'lxml')

        # Check if page has visual breadcrumbs
        breadcrumb_patterns = ['breadcrumb', 'crumb', 'nav-path']
        has_visual_breadcrumbs = any(
            soup.find(class_=re.compile(pattern, re.I)) or
            soup.find(id=re.compile(pattern, re.I))
            for pattern in breadcrumb_patterns
        )

        # Check for aria-label breadcrumb
        has_aria_breadcrumb = soup.find(attrs={'aria-label': re.compile('breadcrumb', re.I)})

        if (has_visual_breadcrumbs or has_aria_breadcrumb) and not has_breadcrumb:
            issues.append(GEOIssue(
                url=url,
                issue_type="breadcrumb_missing_schema",
                category=CATEGORIES['schema'],
                severity=SEVERITY['medium'],
                title="Breadcrumbs Without Schema",
                description="Page has breadcrumb navigation but lacks BreadcrumbList schema",
                recommendation="Add BreadcrumbList schema for site hierarchy signals to AI systems",
            ))

        if not has_visual_breadcrumbs and not has_breadcrumb:
            # Not homepage
            if urlparse(url).path not in ['/', '']:
                issues.append(GEOIssue(
                    url=url,
                    issue_type="missing_breadcrumbs",
                    category=CATEGORIES['structure'],
                    severity=SEVERITY['low'],
                    title="No Breadcrumb Navigation",
                    description="Page lacks breadcrumb navigation for hierarchy context",
                    recommendation="Add breadcrumb navigation with BreadcrumbList schema",
                ))

        return issues

    def _check_content_structure(self, url: str, soup: BeautifulSoup) -> List[GEOIssue]:
        """Check content structure for LLM-friendly patterns"""
        issues = []

        # Check for clear paragraph structure
        paragraphs = soup.find_all('p')
        long_paragraphs = [p for p in paragraphs if len(p.get_text(strip=True)) > 500]

        if long_paragraphs:
            issues.append(GEOIssue(
                url=url,
                issue_type="long_paragraphs",
                category=CATEGORIES['geo_llm'],
                severity=SEVERITY['low'],
                title="Long Paragraphs",
                description=f"{len(long_paragraphs)} paragraphs exceed 500 characters",
                recommendation="Break long paragraphs into shorter, scannable sections for better LLM extraction",
            ))

        # Check for bulleted/numbered lists (LLMs love structured content)
        lists = soup.find_all(['ul', 'ol'])
        if len(lists) < 2:
            issues.append(GEOIssue(
                url=url,
                issue_type="few_lists",
                category=CATEGORIES['geo_llm'],
                severity=SEVERITY['low'],
                title="Limited List Content",
                description="Page has few bullet or numbered lists",
                recommendation="Add more structured lists to help LLMs extract and cite key information",
            ))

        # Check for definition-style content (LLMs extract definitions well)
        has_definitions = soup.find('dl') or soup.find(class_=re.compile('definition', re.I))

        # Check for tables (structured data that LLMs can parse)
        tables = soup.find_all('table')
        tables_with_headers = [t for t in tables if t.find('th')]

        if tables and not tables_with_headers:
            issues.append(GEOIssue(
                url=url,
                issue_type="tables_without_headers",
                category=CATEGORIES['geo_llm'],
                severity=SEVERITY['low'],
                title="Tables Without Headers",
                description="Data tables lack header rows",
                recommendation="Add <th> elements to tables for better LLM data comprehension",
            ))

        return issues

    def _check_natural_language_optimization(self, url: str, soup: BeautifulSoup) -> List[GEOIssue]:
        """Check for natural language query optimization"""
        issues = []

        # Get page text
        text = soup.get_text(separator=' ', strip=True).lower()

        # Check for question-answer patterns (highly valuable for LLMs)
        question_words = ['what', 'how', 'why', 'when', 'where', 'who', 'which', 'can', 'does', 'is']
        question_count = sum(1 for word in question_words if f'{word} ' in text)

        # Check for conversational phrases
        conversational_patterns = [
            r'you can',
            r'we offer',
            r'you\'ll find',
            r'looking for',
            r'perfect for',
            r'ideal for',
        ]
        conversational_count = sum(
            1 for pattern in conversational_patterns
            if re.search(pattern, text)
        )

        if conversational_count < 2:
            issues.append(GEOIssue(
                url=url,
                issue_type="low_conversational_content",
                category=CATEGORIES['geo_llm'],
                severity=SEVERITY['low'],
                title="Limited Conversational Language",
                description="Content lacks natural, conversational phrasing",
                recommendation="Add conversational language that matches how users ask AI assistants questions",
            ))

        return issues

    def _check_citation_worthiness(self, url: str, soup: BeautifulSoup) -> List[GEOIssue]:
        """Check if content is structured for AI citations"""
        issues = []

        # Check for statistics/data points (LLMs often cite specific data)
        text = soup.get_text()
        has_statistics = bool(re.search(r'\d+%|\d+\s*(rooms?|guests?|years?|miles?|km|sq\s*ft)', text, re.I))

        # Check for quotable statements (short, definitive statements)
        sentences = re.split(r'[.!?]', text)
        short_declarative = [s for s in sentences if 20 < len(s.strip()) < 100]

        # Check for unique value propositions
        unique_patterns = ['only', 'first', 'exclusive', 'unique', 'award-winning', 'best']
        has_unique_claims = any(pattern in text.lower() for pattern in unique_patterns)

        # Check for dates/freshness signals
        date_pattern = r'(202[4-6]|january|february|march|april|may|june|july|august|september|october|november|december)\s+\d{1,2}'
        has_dates = bool(re.search(date_pattern, text, re.I))

        if not has_dates:
            issues.append(GEOIssue(
                url=url,
                issue_type="no_freshness_signals",
                category=CATEGORIES['geo_llm'],
                severity=SEVERITY['low'],
                title="No Content Freshness Signals",
                description="Content lacks visible dates or freshness indicators",
                recommendation="Add publication/update dates to signal content freshness to AI systems",
            ))

        return issues

    def _check_speakable_content(self, url: str, html_content: str) -> List[GEOIssue]:
        """Check for speakable schema (for voice assistants)"""
        issues = []

        schemas = self._extract_json_ld(html_content)

        # Check if any schema has speakable property
        has_speakable = any(
            'speakable' in schema
            for schema in schemas
        )

        if not has_speakable:
            issues.append(GEOIssue(
                url=url,
                issue_type="missing_speakable",
                category=CATEGORIES['geo_llm'],
                severity=SEVERITY['low'],
                title="No Speakable Content Markup",
                description="Page lacks speakable schema for voice assistant optimization",
                recommendation="Add speakable property to schema for voice search and smart speaker compatibility",
            ))

        return issues

    def _check_ai_crawler_access(self, url: str, soup: BeautifulSoup) -> List[GEOIssue]:
        """Check for AI crawler accessibility signals"""
        issues = []

        # Check for robots meta that might block AI crawlers
        robots = soup.find('meta', attrs={'name': 'robots'})
        if robots:
            content = robots.get('content', '').lower()
            # Some sites specifically block AI crawlers
            ai_blocking_patterns = ['noai', 'noimageai', 'gptbot', 'ccbot']
            for pattern in ai_blocking_patterns:
                if pattern in content:
                    issues.append(GEOIssue(
                        url=url,
                        issue_type="ai_crawler_blocked",
                        category=CATEGORIES['geo_llm'],
                        severity=SEVERITY['high'],
                        title="AI Crawlers May Be Blocked",
                        description=f"Robots meta contains '{pattern}' which may block AI crawlers",
                        recommendation="Review AI crawler blocking policies if you want LLM visibility",
                        current_value=content,
                    ))

        return issues


def main():
    """Test the GEO/LLM auditor"""
    auditor = GEOLLMAuditor()
    issues = auditor.audit_page("https://www.outrigger.com")

    print(f"\nFound {len(issues)} GEO/LLM issues:")
    for issue in issues:
        print(f"  [{issue.severity}] {issue.title}: {issue.description}")


if __name__ == "__main__":
    main()
