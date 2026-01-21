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
from google.cloud import firestore
import anthropic

# Legacy defaults (used for backward compatibility if no site specified)
DEFAULT_SITEMAP_URL = 'https://www.outrigger.com/sitemap.xml'
DEFAULT_DAYS_TO_CHECK = 7
DEFAULT_MONDAY_BOARD_ID = os.environ.get('MONDAY_BOARD_ID', '18395774522')
DEFAULT_SITE_ID = 'outrigger'

SCRAPER_API_KEY = os.environ.get('SCRAPER_API_KEY', '')
FIRESTORE_PROJECT_ID = os.environ.get('FIRESTORE_PROJECT_ID', 'project-85d26db5-f70f-487e-b0e')
ANTHROPIC_API_KEY = os.environ.get('ANTHROPIC_API_KEY', '')

# Initialize Firestore client
try:
    db = firestore.Client(project=FIRESTORE_PROJECT_ID)
    print(f"Connected to Firestore project: {FIRESTORE_PROJECT_ID}")
except Exception as e:
    print(f"Warning: Could not connect to Firestore: {e}")
    db = None

# Initialize Anthropic client
anthropic_client = None
if ANTHROPIC_API_KEY:
    try:
        anthropic_client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
        print("Anthropic client initialized successfully")
    except Exception as e:
        print(f"Warning: Could not initialize Anthropic client: {e}")


def update_audit_progress(site_id, progress_data):
    """
    Update real-time audit progress in Firestore.

    The frontend subscribes to /sites/{siteId}/auditProgress/current using onSnapshot
    to receive instant progress updates during an audit.
    """
    if not db:
        return
    try:
        progress_ref = db.collection('sites').document(site_id).collection('auditProgress').document('current')
        progress_data['updatedAt'] = firestore.SERVER_TIMESTAMP
        progress_ref.set(progress_data, merge=True)
    except Exception as e:
        print(f"Warning: Could not update audit progress: {e}")


class SiteConfig:
    """
    Configuration for a single site in the multi-site system.

    Loads site-specific settings from Firestore at /sites/{siteId}/config/settings
    """

    def __init__(self, site_id, data):
        self.site_id = site_id
        self.name = data.get('name', site_id)
        self.domain = data.get('domain', '')
        self.sitemap_url = data.get('sitemapUrl', DEFAULT_SITEMAP_URL)
        self.monday_board_id = data.get('mondayBoardId', DEFAULT_MONDAY_BOARD_ID)
        self.days_to_check = data.get('daysToCheck', DEFAULT_DAYS_TO_CHECK)
        self.max_pages = data.get('maxPages', 10)
        self.enable_llm = data.get('enableLLM', True)
        self.enabled = data.get('enabled', True)

    @classmethod
    def load(cls, site_id):
        """Load site config from Firestore"""
        if not db:
            print(f"SiteConfig: Firestore not available, using defaults for {site_id}")
            return cls(site_id, {})

        try:
            config_doc = db.collection('sites').document(site_id).collection('config').document('settings').get()
            if config_doc.exists:
                print(f"SiteConfig: Loaded config for site '{site_id}'")
                return cls(site_id, config_doc.to_dict())
            else:
                print(f"SiteConfig: No config found for site '{site_id}', using defaults")
                return cls(site_id, {})
        except Exception as e:
            print(f"SiteConfig: Error loading config for {site_id}: {e}")
            return cls(site_id, {})

    @classmethod
    def load_all_enabled(cls):
        """Load all enabled sites from Firestore"""
        if not db:
            print("SiteConfig: Firestore not available")
            return []

        sites = []
        try:
            sites_ref = db.collection('sites').stream()
            for site_doc in sites_ref:
                site_id = site_doc.id
                config_doc = db.collection('sites').document(site_id).collection('config').document('settings').get()
                if config_doc.exists:
                    config_data = config_doc.to_dict()
                    if config_data.get('enabled', True):
                        sites.append(cls(site_id, config_data))
            print(f"SiteConfig: Loaded {len(sites)} enabled sites")
        except Exception as e:
            print(f"SiteConfig: Error loading sites: {e}")

        return sites

    def __repr__(self):
        return f"SiteConfig(site_id='{self.site_id}', name='{self.name}', domain='{self.domain}')"


class LLMAuditor:
    """
    LLM-powered SEO/GEO auditor that evaluates pages against natural language rules.

    Instead of hardcoded checks, this uses Claude to interpret rules written in plain English
    and determine if a page passes or fails each rule.
    """

    def __init__(self, client=None):
        self.client = client or anthropic_client
        if not self.client:
            print("Warning: LLMAuditor initialized without Anthropic client")

    def audit_page_with_rules(self, html_content: str, url: str, rules: list) -> list:
        """
        Audit a page against a list of rules using Claude.

        Args:
            html_content: The raw HTML of the page
            url: The URL being audited
            rules: List of rule dicts with 'name', 'prompt', 'severity', etc.

        Returns:
            List of issues found (each issue is a dict)
        """
        if not self.client:
            print("LLMAuditor: No Anthropic client available, skipping LLM audit")
            return []

        if not rules:
            print("LLMAuditor: No rules provided, skipping audit")
            return []

        # Truncate HTML if too long (Claude has context limits)
        max_html_length = 50000
        if len(html_content) > max_html_length:
            html_content = html_content[:max_html_length] + "\n... [HTML truncated for length]"

        # Log first part of HTML for debugging
        print(f"LLMAuditor: HTML length={len(html_content)}")
        print(f"LLMAuditor: First 1000 chars of HTML: {html_content[:1000]}")

        # Check for common error page indicators
        error_indicators = ['401', '403', 'Unauthorized', 'Access Denied', 'Forbidden', 'blocked', 'rate limit']
        found_errors = [e for e in error_indicators if e.lower() in html_content[:5000].lower()]
        if found_errors:
            print(f"LLMAuditor WARNING: HTML may contain error page indicators: {found_errors}")

        # Build the rules section for the prompt
        rules_text = ""
        for i, rule in enumerate(rules, 1):
            rule_name = rule.get('name', 'Unnamed Rule')
            rule_prompt = rule.get('prompt', rule.get('description', 'No prompt provided'))
            print(f"LLMAuditor: Rule {i}: {rule_name} - prompt length: {len(rule_prompt)}")
            rules_text += f"""
Rule {i}: {rule_name}
Severity: {rule.get('severity', 'Medium')}
Check: {rule.get('prompt', rule.get('description', 'No prompt provided'))}
"""

        # Create the audit prompt
        system_prompt = """You are an expert SEO, GEO (Generative Engine Optimization), and brand compliance auditor for hospitality websites, specifically Outrigger Hotels & Resorts.

Your task is to analyze HTML pages and determine if they pass or fail specific rules in these categories:
1. SEO/Technical - title tags, meta descriptions, schema markup, etc.
2. Voice & Tone - warm hospitality tone, adventure/discovery language, authentic Hawaiian voice
3. Brand Standards - correct brand name usage, property names, brand compliance

For each rule, you must analyze the HTML and determine:
1. PASS - The page meets the requirements of the rule
2. FAIL - The page does not meet the requirements

When a rule FAILs, provide:
- A specific, actionable issue title (short, ~50 chars)
- A detailed description explaining why it failed and how to fix it

IMPORTANT: If the HTML appears to be an error page (403, 401, 500, access denied, rate limited, blocked, etc.) rather than actual content, mark ALL rules as PASS since we cannot fairly evaluate error pages.

Be thorough but accurate - only flag real issues. Consider the context of Hawaiian hospitality/hotel websites.
For voice/tone rules, be lenient - only fail if there's a clear violation, not just room for improvement."""

        user_prompt = f"""Analyze this webpage and check it against the following SEO/GEO rules.

URL: {url}

=== HTML CONTENT ===
{html_content}
=== END HTML ===

=== RULES TO CHECK ===
{rules_text}
=== END RULES ===

For each rule, respond with a JSON array. Each element should be:
- For PASS: {{"rule_index": N, "status": "pass"}}
- For FAIL: {{"rule_index": N, "status": "fail", "title": "Short issue title", "description": "Detailed description with why it failed and how to fix it"}}

IMPORTANT: Return ONLY the JSON array, no other text. Example:
[
  {{"rule_index": 1, "status": "pass"}},
  {{"rule_index": 2, "status": "fail", "title": "Missing meta description", "description": "The page lacks a meta description tag..."}}
]"""

        try:
            print(f"LLMAuditor: Sending {len(rules)} rules to Claude for {url}")

            response = self.client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=4000,
                system=system_prompt,
                messages=[{"role": "user", "content": user_prompt}]
            )

            # Parse the response
            response_text = response.content[0].text.strip()
            print(f"LLMAuditor: Received response ({len(response_text)} chars)")

            # Try to extract JSON from the response
            # Handle case where model might include markdown code blocks
            if "```json" in response_text:
                response_text = response_text.split("```json")[1].split("```")[0].strip()
            elif "```" in response_text:
                response_text = response_text.split("```")[1].split("```")[0].strip()

            results = json.loads(response_text)

            # Convert results to issues list
            issues = []
            for result in results:
                if result.get('status') == 'fail':
                    rule_idx = result.get('rule_index', 1) - 1
                    if 0 <= rule_idx < len(rules):
                        rule = rules[rule_idx]
                        # Determine issue type based on rule structure
                        # Voice rules have 'category', Brand rules have 'standardType', SEO rules have 'checkType'
                        if rule.get('category'):
                            issue_type = 'llm_voice'
                        elif rule.get('standardType'):
                            issue_type = 'llm_brand'
                        else:
                            issue_type = f"llm_{rule.get('checkType', 'custom')}"

                        issues.append({
                            'type': issue_type,
                            'title': result.get('title', rule.get('name', 'SEO Issue')),
                            'severity': rule.get('severity', 'Medium'),
                            'url': url,
                            'description': result.get('description', ''),
                            'rule_name': rule.get('name', '')
                        })

            print(f"LLMAuditor: Found {len(issues)} issues for {url}")
            return issues

        except json.JSONDecodeError as e:
            print(f"LLMAuditor: Failed to parse JSON response: {e}")
            print(f"Response was: {response_text[:500]}...")
            return []
        except Exception as e:
            print(f"LLMAuditor: Error during audit: {e}")
            import traceback
            traceback.print_exc()
            return []

    def batch_audit(self, html_content: str, url: str, rules: list, batch_size: int = 5) -> list:
        """
        Audit a page in batches to handle many rules efficiently.

        Args:
            html_content: The raw HTML of the page
            url: The URL being audited
            rules: List of all rules to check
            batch_size: Number of rules to check per API call

        Returns:
            List of all issues found
        """
        all_issues = []

        # Process rules in batches
        for i in range(0, len(rules), batch_size):
            batch = rules[i:i + batch_size]
            batch_issues = self.audit_page_with_rules(html_content, url, batch)
            all_issues.extend(batch_issues)

            # Small delay between batches to avoid rate limits
            if i + batch_size < len(rules):
                time.sleep(0.5)

        return all_issues


# Global LLM auditor instance
llm_auditor = LLMAuditor()


class ConfigManager:
    """
    Manages configuration from Firestore for a specific site.

    In multi-site mode, loads rules from /sites/{siteId}/seoRules, etc.
    Falls back to legacy root collections if site-specific collections are empty.
    """

    def __init__(self, site_id=None):
        self.site_id = site_id or DEFAULT_SITE_ID
        self.seo_rules = []
        self.voice_rules = []
        self.brand_standards = []
        self._loaded = False
        self._llm_rules = []  # Rules that have prompts for LLM evaluation
        self._legacy_rules = []  # Rules that use checkType for hardcoded checks

    def _get_collection(self, collection_name):
        """Get reference to a collection, using site-specific path if site_id is set"""
        if self.site_id:
            # Multi-site path: /sites/{siteId}/{collection}
            return db.collection('sites').document(self.site_id).collection(collection_name)
        else:
            # Legacy path: /{collection}
            return db.collection(collection_name)

    def _load_collection_with_fallback(self, collection_name):
        """Load from site-specific collection, fall back to legacy if empty"""
        # Try site-specific first
        site_collection = db.collection('sites').document(self.site_id).collection(collection_name)
        docs = list(site_collection.stream())

        if docs:
            print(f"  Loaded {len(docs)} docs from sites/{self.site_id}/{collection_name}")
            return docs

        # Fall back to legacy collection
        print(f"  No docs in sites/{self.site_id}/{collection_name}, trying legacy {collection_name}")
        legacy_docs = list(db.collection(collection_name).stream())
        if legacy_docs:
            print(f"  Loaded {len(legacy_docs)} docs from legacy {collection_name}")
        return legacy_docs

    def load_config(self):
        """Load all configuration from Firestore for this site"""
        if not db:
            print("Firestore not available, using default config")
            return False

        try:
            print(f"ConfigManager: Loading config for site '{self.site_id}'")
            print(f"Firestore project: {FIRESTORE_PROJECT_ID}")

            # Load SEO Rules
            seo_docs = self._load_collection_with_fallback('seoRules')
            all_seo = []
            for doc in seo_docs:
                doc_data = doc.to_dict()
                all_seo.append({'id': doc.id, **doc_data})
            self.seo_rules = [r for r in all_seo if r.get('enabled', False)]
            print(f"Loaded {len(self.seo_rules)} SEO rules (from {len(all_seo)} total)")

            # Separate rules by type:
            # - Legacy rules: have 'checkType' (run code-based checks)
            # - LLM rules: have 'prompt' (run AI-powered checks)
            # A rule can be BOTH if it has both checkType and prompt
            self._llm_rules = [r for r in self.seo_rules if r.get('prompt')]
            self._legacy_rules = [r for r in self.seo_rules if r.get('checkType')]
            print(f"  - LLM rules (with prompts): {len(self._llm_rules)}")
            print(f"  - Legacy rules (with checkType): {len(self._legacy_rules)}")

            # Load Voice Rules
            voice_docs = self._load_collection_with_fallback('voiceRules')
            all_voice = [{'id': doc.id, **doc.to_dict()} for doc in voice_docs]
            self.voice_rules = [r for r in all_voice if r.get('enabled', False)]
            print(f"Loaded {len(self.voice_rules)} voice rules (from {len(all_voice)} total)")

            # Add voice rules with prompts to LLM rules
            voice_llm_rules = [r for r in self.voice_rules if r.get('prompt')]
            if voice_llm_rules:
                self._llm_rules.extend(voice_llm_rules)
                print(f"  - Added {len(voice_llm_rules)} voice rules with LLM prompts")

            # Load Brand Standards
            brand_docs = self._load_collection_with_fallback('brandStandards')
            all_brand = [{'id': doc.id, **doc.to_dict()} for doc in brand_docs]
            self.brand_standards = [r for r in all_brand if r.get('enabled', False)]
            print(f"Loaded {len(self.brand_standards)} brand standards (from {len(all_brand)} total)")

            # Add brand standards with prompts to LLM rules
            brand_llm_rules = [r for r in self.brand_standards if r.get('prompt')]
            if brand_llm_rules:
                self._llm_rules.extend(brand_llm_rules)
                print(f"  - Added {len(brand_llm_rules)} brand standards with LLM prompts")

            print(f"Total LLM rules to evaluate: {len(self._llm_rules)}")

            self._loaded = True
            return True
        except Exception as e:
            print(f"Error loading config from Firestore: {e}")
            import traceback
            traceback.print_exc()
            return False

    def get_seo_rules_by_type(self, check_type):
        """Get SEO rules filtered by check type"""
        return [r for r in self.seo_rules if r.get('checkType') == check_type]

    def get_all_seo_rules(self):
        """Get all enabled SEO rules"""
        return self.seo_rules

    def get_voice_rules(self):
        """Get all voice/tone guidelines"""
        return self.voice_rules

    def get_brand_standards(self):
        """Get all brand standards"""
        return self.brand_standards

    def is_check_enabled(self, check_type):
        """Check if a specific audit check is enabled in Firestore config.

        IMPORTANT: Only runs checks that are explicitly defined AND enabled in the admin dashboard.
        No default/fallback checks - if it's not in Firestore, it doesn't run.
        """
        # If no rules loaded from Firestore, NO checks run
        if not self._loaded or not self.seo_rules:
            return False

        # Look for a matching rule with this checkType that is enabled
        # Rules can have both checkType (for code checks) and prompt (for LLM checks)
        for rule in self._legacy_rules:
            if rule.get('checkType') == check_type and rule.get('enabled', False):
                return True

        # Not found or not enabled = don't run
        return False

    def get_llm_rules(self):
        """Get all LLM-based rules (rules with 'prompt' field)"""
        return self._llm_rules

    def get_voice_llm_rules(self):
        """Get voice rules that have LLM prompts"""
        return [r for r in self.voice_rules if r.get('prompt')]

    def get_brand_llm_rules(self):
        """Get brand standards that have LLM prompts"""
        return [r for r in self.brand_standards if r.get('prompt')]

    def get_legacy_rules(self):
        """Get all legacy rules (rules with 'checkType' but no 'prompt')"""
        return self._legacy_rules

    def has_llm_rules(self):
        """Check if there are any LLM-based rules to evaluate"""
        return len(self._llm_rules) > 0


# Global config manager
config_manager = ConfigManager()

# Issue type descriptions for the Issue Description field - verbose for clarity
ISSUE_DESCRIPTIONS = {
    # ============ TIER 1: CRITICAL ============

    # Basic SEO Fundamentals
    'missing_title': '''CRITICAL SEO ISSUE: Missing Page Title

The page is missing a <title> tag entirely. The title tag is one of the most important on-page SEO elements.

WHY IT MATTERS:
- The title appears as the clickable headline in Google search results
- It shows in browser tabs helping users identify your page
- Search engines use it as a primary ranking signal
- AI assistants use titles to understand page content

HOW TO FIX:
Add a unique, descriptive <title> tag in the <head> section of your HTML. Keep it between 50-60 characters and include relevant keywords for the page content.

Example: <title>Beachfront Resort in Waikiki | Outrigger Hotels Hawaii</title>''',

    'short_title': '''SEO ISSUE: Page Title Too Short

The page title is less than 30 characters, which doesn't provide enough context for search engines or users.

WHY IT MATTERS:
- Short titles miss opportunities to include valuable keywords
- They may not fully describe the page content to searchers
- Google may rewrite titles that are too short or non-descriptive

HOW TO FIX:
Expand the title to 50-60 characters. Include the primary keyword, location (if relevant), and brand name. Make it compelling to encourage clicks.

Example: Instead of "Hawaii Hotels" use "Luxury Beachfront Hotels in Waikiki, Hawaii | Outrigger"''',

    'missing_meta': '''CRITICAL: Missing Meta Description

The page has no meta description tag. This is a missed opportunity to control how your page appears in search results.

WHY IT MATTERS:
- The meta description appears as the snippet text under the title in search results
- A compelling description increases click-through rates (CTR)
- Without one, Google will auto-generate text from your page (often poorly)
- LLMs and AI assistants use meta descriptions to summarize pages

HOW TO FIX:
Add a meta description tag in the <head> section. Write 150-160 characters that summarize the page and include a call-to-action.

Example: <meta name="description" content="Experience paradise at our oceanfront Waikiki resort. Stunning views, world-class amenities, and authentic Hawaiian hospitality. Book direct for best rates.">''',

    'short_meta': '''SEO ISSUE: Meta Description Too Short

The meta description is under 120 characters. You're not using the full space available to convince searchers to click.

WHY IT MATTERS:
- Google displays up to 155-160 characters in search results
- Short descriptions may not provide enough information to entice clicks
- You're missing keyword opportunities

HOW TO FIX:
Expand to 150-160 characters. Include primary keywords naturally, highlight unique selling points, and add a call-to-action.''',

    'missing_h1': '''CRITICAL: Missing H1 Heading

The page has no H1 heading tag. Every page should have exactly one H1 that describes the main topic.

WHY IT MATTERS:
- The H1 tells search engines what the page is primarily about
- It provides structure and hierarchy for your content
- Screen readers use H1 tags to help visually impaired users navigate
- AI/LLMs use H1 to understand the primary topic

HOW TO FIX:
Add a single H1 tag near the top of your page content (not in the header/navigation). It should describe the main topic and ideally include your primary keyword.

Example: <h1>Oceanfront Luxury Suites in Waikiki Beach</h1>''',

    'missing_canonical': '''CRITICAL: Missing Canonical Tag

The page is missing a canonical URL tag. This is important for preventing duplicate content issues.

WHY IT MATTERS:
- Canonical tags tell search engines which version of a page is the "master" copy
- Without it, Google may index multiple URLs with the same content
- This can split ranking signals between duplicate pages

HOW TO FIX:
Add a canonical tag in the <head> section pointing to the preferred URL:
<link rel="canonical" href="https://www.outrigger.com/your-page-url">

Always use the full absolute URL and ensure it matches your preferred URL format (with or without www, https).''',

    # Schema - Critical for Hotels
    'missing_hotel_schema': '''CRITICAL FOR HOTELS: Missing Hotel Schema

This appears to be a hotel or room page but lacks Hotel or LodgingBusiness schema.

WHY IT MATTERS:
- Hotel schema is essential for hospitality businesses
- Enables rich results with pricing, availability, and ratings
- Required for Google Hotel Search integration
- AI travel assistants (ChatGPT, Google AI) pull from this data
- Competitors with proper schema have major advantages

HOW TO FIX:
Add comprehensive Hotel schema including property details, room types, amenities, pricing, and booking information.''',

    'missing_localbusiness_schema': '''CRITICAL: Missing LocalBusiness/Hotel Schema

The page is missing LocalBusiness or Hotel schema markup. This is critical for hospitality websites.

WHY IT MATTERS:
- Essential for appearing in local search results and Google Maps
- Enables rich results showing ratings, prices, and availability
- Helps Google understand your property locations
- Critical for "hotels near me" and location-based searches
- AI assistants use this for travel recommendations

HOW TO FIX:
Add Hotel or LodgingBusiness schema including:
- Property name and description
- Full address with geo coordinates
- Star rating and price range
- Amenities and room types
- Check-in/check-out times
- Contact information''',

    'missing_address_schema': '''CRITICAL: Missing Address in Schema

Your schema markup exists but doesn't include complete address information.

WHY IT MATTERS:
- Complete address data is essential for local search visibility
- Required for Google Maps integration
- Helps users find your property location
- Supports "near me" searches
- AI assistants need this for directions and recommendations

HOW TO FIX:
Add PostalAddress to your schema with:
- streetAddress
- addressLocality (city)
- addressRegion (state)
- postalCode
- addressCountry
- geo coordinates (latitude/longitude)''',

    # ============ TIER 2: HIGH PRIORITY ============

    # GEO/LLM Optimization
    'missing_organization_schema': '''GEO/LLM: Missing Organization Markup

The page is missing Organization schema. This helps establish your brand identity for both search engines and AI assistants.

WHY IT MATTERS:
- Helps Google understand your brand and business entity
- Can enable Knowledge Panel features
- AI assistants use this to understand who you are
- Links your website to your brand entity across the web

HOW TO FIX:
Add Organization schema with your company details including name, logo, social profiles, contact information, and founding date.''',

    'missing_faq_schema': '''GEO/LLM PRIORITY: FAQ Content Without Markup

The page appears to have FAQ content but no FAQPage schema markup.

WHY IT MATTERS:
- FAQ schema generates expandable FAQ rich results in Google
- Takes up more space in search results (more visibility)
- LLMs and AI assistants pull FAQ content for direct answers
- Critical for voice search and AI-powered travel planning
- Can significantly increase click-through rates

HOW TO FIX:
Wrap your FAQ content with FAQPage schema, including Question and Answer pairs for each FAQ item.''',

    'missing_review_schema': '''GEO/LLM: Missing Review/Rating Schema

The page is missing AggregateRating or Review schema markup.

WHY IT MATTERS:
- Enables star ratings in search results
- AI assistants cite ratings when recommending hotels
- Builds trust with potential guests
- Critical differentiator in competitive searches
- LLMs reference ratings in travel recommendations

HOW TO FIX:
Add AggregateRating schema with:
- ratingValue (average rating)
- reviewCount (number of reviews)
- bestRating and worstRating
Include individual Review schemas if available.''',

    'thin_content': '''GEO/LLM: Thin Content (Under 300 Words)

The page has less than 300 words of content, which may be insufficient for search engines and AI assistants.

WHY IT MATTERS:
- Search engines prefer substantial, informative content
- AI/LLMs need enough content to understand and reference your page
- Thin pages often rank poorly for competitive terms
- Users expect detailed information about hotels/destinations
- Voice assistants need content to generate responses

HOW TO FIX:
Expand page content to at least 500-800 words including:
- Detailed property/room descriptions
- Amenities and features
- Location highlights and nearby attractions
- Guest experience information
- Unique selling points''',

    'missing_geo_tags': '''GEO/LLM: Missing Geo Meta Tags

The page is missing geo.region and geo.placename meta tags.

WHY IT MATTERS:
- Geo tags help search engines understand your location relevance
- Improves visibility in location-based searches
- AI travel assistants use geo data for recommendations
- Supports local SEO and "near me" queries

HOW TO FIX:
Add geo meta tags in the <head> section:
<meta name="geo.region" content="US-HI">
<meta name="geo.placename" content="Honolulu">
<meta name="geo.position" content="21.2769;-157.8268">''',

    # Social/Sharing - High Priority
    'missing_og_image': '''HIGH PRIORITY: Missing Open Graph Image

The page is missing the og:image meta tag. Social shares without images get significantly less engagement.

WHY IT MATTERS:
- Posts with images get 2-3x more engagement on social media
- Without og:image, platforms may show no image or pick a random one
- A compelling image dramatically increases click-through rates
- AI-generated summaries may include images

HOW TO FIX:
Add in the <head> section:
<meta property="og:image" content="https://www.outrigger.com/path/to/image.jpg">

Use an image at least 1200x630 pixels for best display. Show the property, destination, or relevant visual.''',

    'missing_og_title': '''SOCIAL MEDIA: Missing Open Graph Title

The page is missing the og:title meta tag. This affects how the page appears when shared on Facebook, LinkedIn, and other social platforms.

WHY IT MATTERS:
- Social platforms use og:title as the headline when your page is shared
- Without it, platforms may pull incorrect or truncated text
- Professional-looking shares get more engagement

HOW TO FIX:
Add in the <head> section:
<meta property="og:title" content="Your Page Title Here">

Keep it under 60 characters for best display across platforms.''',

    'missing_og_description': '''SOCIAL MEDIA: Missing Open Graph Description

The page is missing the og:description meta tag for social sharing.

WHY IT MATTERS:
- This text appears below the title when your page is shared on social media
- Compelling descriptions increase click-through from social shares
- Without it, platforms may pull random text from your page

HOW TO FIX:
Add in the <head> section:
<meta property="og:description" content="Brief, engaging description of your page content">

Keep it under 200 characters and make it compelling.''',

    # ============ TIER 3: MEDIUM PRIORITY ============

    'missing_alt_tags': '''ACCESSIBILITY & SEO: Image Missing Alt Text

One or more images on this page are missing alt text attributes.

WHY IT MATTERS:
- Screen readers use alt text to describe images to visually impaired users (ADA compliance)
- Search engines use alt text to understand image content
- Alt text helps images appear in Google Image search results
- AI models use alt text to understand visual content

HOW TO FIX:
Add descriptive alt attributes to all images:
<img src="beach.jpg" alt="Guests relaxing on Waikiki Beach at sunset with Diamond Head in background">

Be descriptive but concise. Include relevant keywords naturally.''',

    'missing_breadcrumb_schema': '''SCHEMA: Missing Breadcrumb Markup

The page is missing BreadcrumbList schema for navigation structure.

WHY IT MATTERS:
- Breadcrumbs can appear in search results showing page hierarchy
- Helps users understand where they are in your site
- Improves site navigation signals for search engines
- AI assistants use this to understand site structure

HOW TO FIX:
Add BreadcrumbList schema showing the page hierarchy:
Home > Hawaii > Oahu > Waikiki Beach Resort''',

    'multiple_h1': '''CONTENT STRUCTURE: Multiple H1 Tags

The page has more than one H1 heading. Best practice is to have exactly one H1 per page.

WHY IT MATTERS:
- Multiple H1s can confuse search engines about the page's main topic
- It weakens the semantic structure of your content
- May dilute keyword relevance signals

HOW TO FIX:
Keep only one H1 for the main page title. Convert other H1 tags to H2 or H3 based on content hierarchy.''',

    'missing_robots': '''TECHNICAL SEO: Missing Robots Meta Tag

The page has no robots meta tag. While not critical, it's good practice to explicitly declare indexing instructions.

WHY IT MATTERS:
- Explicitly tells search engines whether to index the page
- Provides control over whether links should be followed
- Helps prevent accidental indexing of pages you don't want indexed

HOW TO FIX:
Add a robots meta tag in the <head> section:
<meta name="robots" content="index, follow">

Use "noindex" for pages you don't want in search results.''',

    'missing_schema': '''SCHEMA: No Structured Data (JSON-LD)

The page has no JSON-LD structured data markup. This is essential for modern SEO and rich search results.

WHY IT MATTERS:
- Structured data helps Google understand your content better
- Enables rich snippets in search results (stars, prices, availability)
- Required for many Google Search features
- AI assistants rely heavily on structured data

HOW TO FIX:
Add JSON-LD schema in a <script type="application/ld+json"> tag. For hotel pages, include Hotel, LodgingBusiness, or LocalBusiness schema.

Use Google's Structured Data Testing Tool to validate.''',

    # ============ GEO/LLM SPECIFIC ADDITIONS ============

    'missing_speakable_schema': '''GEO/LLM: Missing Speakable Schema

The page is missing Speakable schema markup for voice assistant optimization.

WHY IT MATTERS:
- Speakable schema tells voice assistants which content to read aloud
- Critical for Google Assistant, Alexa, and Siri integration
- Optimizes your content for voice search queries
- Growing importance as voice search increases

HOW TO FIX:
Add Speakable schema identifying the most important text sections:
- Property name and key description
- Location information
- Key amenities and features
- Pricing highlights''',

    'missing_tourist_attraction_schema': '''GEO/LLM: Missing TouristAttraction Schema

Pages about attractions or destinations are missing TouristAttraction schema.

WHY IT MATTERS:
- Helps AI travel assistants recommend nearby attractions
- Improves visibility in "things to do" searches
- Links your property to local experiences
- Critical for destination marketing

HOW TO FIX:
Add TouristAttraction schema for nearby attractions pages including:
- Attraction name and description
- Address and geo coordinates
- Opening hours
- Tourism type (beach, cultural, adventure, etc.)''',

    'missing_event_schema': '''GEO/LLM: Missing Event Schema

Pages about hotel events or activities are missing Event schema.

WHY IT MATTERS:
- Events can appear in Google's event search results
- AI assistants recommend events to travelers
- Increases visibility for "what's happening" queries
- Drives bookings for special occasions

HOW TO FIX:
Add Event schema including:
- Event name and description
- Start/end dates and times
- Location (use your Hotel schema)
- Ticket/pricing information
- Event type/category''',

    'missing_offer_schema': '''GEO/LLM: Missing Offer/Pricing Schema

The page is missing Offer or PriceSpecification schema for pricing information.

WHY IT MATTERS:
- Enables price display in search results
- AI assistants use pricing data for comparisons
- Critical for "hotels under $X" searches
- Helps travelers make booking decisions

HOW TO FIX:
Add Offer schema within your Hotel schema including:
- Price and priceCurrency
- Availability
- Valid date ranges
- Room types included''',
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

    # Use ScraperAPI with additional options for better compatibility
    # - render=true: JavaScript rendering
    # - country_code=us: Use US-based proxy
    api_url = f"http://api.scraperapi.com?api_key={SCRAPER_API_KEY}&url={url}&render=true&country_code=us"
    print(f"Fetching via ScraperAPI: {url}")
    return requests.get(api_url, timeout=90)

class SitemapParser:
    def __init__(self, sitemap_url=None):
        """Initialize with a sitemap URL. Required for multi-site support."""
        self.sitemap_url = sitemap_url or DEFAULT_SITEMAP_URL

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
                print("No recent URLs found within date range, returning all URLs from sitemap")
                # Return all URLs if none match the date filter
                for match in matches:
                    loc = match[0].strip()
                    if loc:
                        urls.append({'url': loc})
                print(f"Returning {len(urls)} total URLs from sitemap")

            return urls  # Return all matching URLs
        except Exception as e:
            print(f"Error parsing sitemap: {e}")
            import traceback
            traceback.print_exc()
            # Return empty list - let caller handle the error
            return []


class GEOScorer:
    """
    Calculates a GEO/LLM Readiness Score (1-100) for a page.

    Measures how well a page is optimized for AI assistants, generative search,
    and large language models to understand and recommend.

    Score Breakdown:
    - Structured Data (35 points): JSON-LD schema presence and quality
    - Content Signals (25 points): Clear, extractable information
    - Technical Foundation (25 points): Meta tags, canonicals, OG tags
    - Voice/AI Readiness (15 points): Speakable schema, FAQ content
    """

    def calculate_score(self, soup, url, schemas=None):
        """
        Calculate the GEO/LLM readiness score for a page.

        Returns:
            dict: {
                'total_score': int (1-100),
                'breakdown': {
                    'structured_data': {'score': int, 'max': 35, 'details': []},
                    'content_signals': {'score': int, 'max': 25, 'details': []},
                    'technical_foundation': {'score': int, 'max': 25, 'details': []},
                    'voice_readiness': {'score': int, 'max': 15, 'details': []}
                },
                'grade': str (A, B, C, D, F)
            }
        """
        breakdown = {
            'structured_data': {'score': 0, 'max': 35, 'details': []},
            'content_signals': {'score': 0, 'max': 25, 'details': []},
            'technical_foundation': {'score': 0, 'max': 25, 'details': []},
            'voice_readiness': {'score': 0, 'max': 15, 'details': []}
        }

        # ============ STRUCTURED DATA (35 points) ============
        schema_types = set()
        if schemas:
            for schema in schemas:
                if isinstance(schema, dict):
                    schema_type = schema.get('@type', '')
                    if isinstance(schema_type, list):
                        schema_types.update(schema_type)
                    else:
                        schema_types.add(schema_type)

        # Has any JSON-LD schema (10 points)
        if schemas and len(schemas) > 0:
            breakdown['structured_data']['score'] += 10
            breakdown['structured_data']['details'].append('Has JSON-LD schema (+10)')
        else:
            breakdown['structured_data']['details'].append('Missing JSON-LD schema (0)')

        # Has business/entity schema - Hotel, LocalBusiness, Organization (10 points)
        business_schemas = {'Hotel', 'LodgingBusiness', 'LocalBusiness', 'Organization', 'Corporation', 'Resort'}
        if schema_types & business_schemas:
            breakdown['structured_data']['score'] += 10
            breakdown['structured_data']['details'].append('Has business entity schema (+10)')
        else:
            breakdown['structured_data']['details'].append('Missing business entity schema (0)')

        # Has rich schema - FAQ, Review, Product, Event (8 points)
        rich_schemas = {'FAQPage', 'FAQ', 'Review', 'AggregateRating', 'Product', 'Event', 'Offer'}
        if schema_types & rich_schemas:
            breakdown['structured_data']['score'] += 8
            breakdown['structured_data']['details'].append('Has rich content schema (+8)')

        # Has breadcrumb schema (4 points)
        if 'BreadcrumbList' in schema_types:
            breakdown['structured_data']['score'] += 4
            breakdown['structured_data']['details'].append('Has breadcrumb schema (+4)')

        # Schema completeness - check for key properties (3 points)
        if schemas:
            has_name = any(s.get('name') for s in schemas if isinstance(s, dict))
            has_desc = any(s.get('description') for s in schemas if isinstance(s, dict))
            has_address = any(s.get('address') for s in schemas if isinstance(s, dict))
            completeness = sum([has_name, has_desc, has_address])
            if completeness >= 2:
                breakdown['structured_data']['score'] += 3
                breakdown['structured_data']['details'].append('Schema has key properties (+3)')

        # ============ CONTENT SIGNALS (25 points) ============

        # Has substantial content - word count (10 points)
        text_content = soup.get_text(separator=' ', strip=True)
        word_count = len(text_content.split())
        if word_count >= 500:
            breakdown['content_signals']['score'] += 10
            breakdown['content_signals']['details'].append(f'Good content length: {word_count} words (+10)')
        elif word_count >= 300:
            breakdown['content_signals']['score'] += 6
            breakdown['content_signals']['details'].append(f'Moderate content: {word_count} words (+6)')
        elif word_count >= 150:
            breakdown['content_signals']['score'] += 3
            breakdown['content_signals']['details'].append(f'Light content: {word_count} words (+3)')
        else:
            breakdown['content_signals']['details'].append(f'Thin content: {word_count} words (0)')

        # Has proper heading structure (5 points)
        h1_tags = soup.find_all('h1')
        h2_tags = soup.find_all('h2')
        if len(h1_tags) == 1 and len(h2_tags) >= 1:
            breakdown['content_signals']['score'] += 5
            breakdown['content_signals']['details'].append('Good heading structure (+5)')
        elif len(h1_tags) == 1:
            breakdown['content_signals']['score'] += 3
            breakdown['content_signals']['details'].append('Has H1, missing H2s (+3)')

        # Has lists or structured content (5 points)
        lists = soup.find_all(['ul', 'ol'])
        tables = soup.find_all('table')
        if len(lists) >= 2 or len(tables) >= 1:
            breakdown['content_signals']['score'] += 5
            breakdown['content_signals']['details'].append('Has structured content (lists/tables) (+5)')
        elif len(lists) >= 1:
            breakdown['content_signals']['score'] += 2
            breakdown['content_signals']['details'].append('Has some lists (+2)')

        # Has FAQ-style content (5 points)
        faq_indicators = soup.find_all(['details', 'summary'])
        question_words = text_content.lower().count('?')
        if 'FAQPage' in schema_types or len(faq_indicators) > 0:
            breakdown['content_signals']['score'] += 5
            breakdown['content_signals']['details'].append('Has FAQ content (+5)')
        elif question_words >= 3:
            breakdown['content_signals']['score'] += 2
            breakdown['content_signals']['details'].append('Has Q&A style content (+2)')

        # ============ TECHNICAL FOUNDATION (25 points) ============

        # Has proper title tag (6 points)
        title_tag = soup.find('title')
        if title_tag and len(title_tag.text.strip()) >= 30:
            breakdown['technical_foundation']['score'] += 6
            breakdown['technical_foundation']['details'].append('Good title tag (+6)')
        elif title_tag and title_tag.text.strip():
            breakdown['technical_foundation']['score'] += 3
            breakdown['technical_foundation']['details'].append('Has title but short (+3)')
        else:
            breakdown['technical_foundation']['details'].append('Missing/empty title (0)')

        # Has meta description (6 points)
        meta_desc = soup.find('meta', attrs={'name': 'description'})
        if meta_desc and len(meta_desc.get('content', '').strip()) >= 120:
            breakdown['technical_foundation']['score'] += 6
            breakdown['technical_foundation']['details'].append('Good meta description (+6)')
        elif meta_desc and meta_desc.get('content', '').strip():
            breakdown['technical_foundation']['score'] += 3
            breakdown['technical_foundation']['details'].append('Has meta description but short (+3)')
        else:
            breakdown['technical_foundation']['details'].append('Missing meta description (0)')

        # Has canonical URL (4 points)
        canonical = soup.find('link', attrs={'rel': 'canonical'})
        if canonical and canonical.get('href'):
            breakdown['technical_foundation']['score'] += 4
            breakdown['technical_foundation']['details'].append('Has canonical URL (+4)')

        # Has Open Graph tags (5 points)
        og_title = soup.find('meta', attrs={'property': 'og:title'})
        og_desc = soup.find('meta', attrs={'property': 'og:description'})
        og_image = soup.find('meta', attrs={'property': 'og:image'})
        og_count = sum([1 for og in [og_title, og_desc, og_image] if og])
        if og_count >= 3:
            breakdown['technical_foundation']['score'] += 5
            breakdown['technical_foundation']['details'].append('Full Open Graph tags (+5)')
        elif og_count >= 1:
            breakdown['technical_foundation']['score'] += 2
            breakdown['technical_foundation']['details'].append(f'Partial Open Graph ({og_count}/3) (+2)')

        # Has language declared (2 points)
        html_tag = soup.find('html')
        if html_tag and html_tag.get('lang'):
            breakdown['technical_foundation']['score'] += 2
            breakdown['technical_foundation']['details'].append('Has lang attribute (+2)')

        # Has proper robots meta (2 points)
        robots = soup.find('meta', attrs={'name': 'robots'})
        if robots:
            content = robots.get('content', '').lower()
            if 'noindex' not in content:
                breakdown['technical_foundation']['score'] += 2
                breakdown['technical_foundation']['details'].append('Indexable robots meta (+2)')
        else:
            # No robots meta means indexable by default
            breakdown['technical_foundation']['score'] += 2
            breakdown['technical_foundation']['details'].append('Indexable (no noindex) (+2)')

        # ============ VOICE/AI READINESS (15 points) ============

        # Has Speakable schema (6 points)
        if 'Speakable' in schema_types:
            breakdown['voice_readiness']['score'] += 6
            breakdown['voice_readiness']['details'].append('Has Speakable schema (+6)')

        # Has short, digestible paragraphs (4 points)
        paragraphs = soup.find_all('p')
        if paragraphs:
            avg_para_length = sum(len(p.get_text().split()) for p in paragraphs) / len(paragraphs)
            if avg_para_length <= 50:
                breakdown['voice_readiness']['score'] += 4
                breakdown['voice_readiness']['details'].append('Digestible paragraphs (+4)')
            elif avg_para_length <= 80:
                breakdown['voice_readiness']['score'] += 2
                breakdown['voice_readiness']['details'].append('Moderate paragraph length (+2)')

        # Has clear contact/location info (3 points)
        has_phone = bool(soup.find('a', href=lambda h: h and 'tel:' in h))
        has_email = bool(soup.find('a', href=lambda h: h and 'mailto:' in h))
        has_address_tag = bool(soup.find('address'))
        if has_phone or has_email or has_address_tag:
            breakdown['voice_readiness']['score'] += 3
            breakdown['voice_readiness']['details'].append('Has contact info (+3)')

        # Mobile-friendly indicators (2 points)
        viewport = soup.find('meta', attrs={'name': 'viewport'})
        if viewport:
            breakdown['voice_readiness']['score'] += 2
            breakdown['voice_readiness']['details'].append('Mobile viewport set (+2)')

        # Calculate total score
        total_score = sum(cat['score'] for cat in breakdown.values())

        # Ensure score is between 1-100
        total_score = max(1, min(100, total_score))

        # Calculate grade
        if total_score >= 90:
            grade = 'A'
        elif total_score >= 80:
            grade = 'B'
        elif total_score >= 70:
            grade = 'C'
        elif total_score >= 60:
            grade = 'D'
        else:
            grade = 'F'

        return {
            'total_score': total_score,
            'breakdown': breakdown,
            'grade': grade
        }


class SEOAuditor:
    def audit(self, url, config=None, audit_types=None, progress_callback=None):
        """
        Audit a URL for SEO issues.

        IMPORTANT: Only runs checks that are explicitly enabled in the Firestore config.
        If no config is provided or no rules are enabled, no checks will run.

        Args:
            url: The URL to audit
            config: ConfigManager instance with loaded rules
            audit_types: Dict specifying which audit categories to run:
                         {'seo': True/False, 'voice': True/False, 'brand': True/False}
            progress_callback: Optional function to call with progress updates
                               callback(phase_label: str) - e.g., "Scraping page..."

        Config checkTypes supported:
        - title: Title tag checks (missing_title, short_title)
        - meta: Meta description checks (missing_meta, short_meta)
        - h1: H1 tag checks (missing_h1, multiple_h1)
        - canonical: Canonical tag check
        - schema: All schema checks (hotel, localbusiness, organization, faq, review, etc.)
        - content: Content quality checks (thin_content)
        - geo: Geo meta tags check
        - og: Open Graph checks (og:image, og:title, og:description)
        - alt: Image alt tag checks
        - robots: Robots meta tag check
        - speakable: Speakable schema check
        """
        issues = []

        # Default audit_types to all enabled
        if audit_types is None:
            audit_types = {'seo': True, 'voice': True, 'brand': True}

        run_seo = audit_types.get('seo', True)
        run_voice = audit_types.get('voice', True)
        run_brand = audit_types.get('brand', True)

        # If no config provided, no checks run
        if not config:
            print(f"No config provided for {url} - skipping all checks")
            return issues

        # Helper to update progress
        def update_phase(label):
            if progress_callback:
                progress_callback(label)

        try:
            update_phase('Scraping page content...')
            resp = fetch_with_scraper_api(url)
            print(f"Auditing {url} - Status: {resp.status_code}")
            print(f"  Audit types: SEO={run_seo}, Voice={run_voice}, Brand={run_brand}")

            # Check for HTTP errors
            if resp.status_code >= 400:
                error_msg = f"HTTP {resp.status_code} error"
                if resp.status_code == 401:
                    error_msg = "401 Unauthorized - site may be blocking scraper"
                elif resp.status_code == 403:
                    error_msg = "403 Forbidden - access denied"
                elif resp.status_code == 404:
                    error_msg = "404 Not Found - page does not exist"
                elif resp.status_code == 500:
                    error_msg = "500 Server Error"

                print(f"  ERROR: {error_msg}")
                issues.append({
                    'type': 'http_error',
                    'title': f'Page returned {error_msg}',
                    'severity': 'Critical',
                    'url': url,
                    'description': f'The page at {url} returned an HTTP {resp.status_code} error. This may indicate the page is inaccessible or blocking automated access.'
                })
                return issues

            soup = BeautifulSoup(resp.text, 'html.parser')

            # Check if we got a real page (not Cloudflare challenge)
            title_tag = soup.find('title')
            if title_tag and 'Just a moment' in title_tag.text:
                print(f"Warning: Got Cloudflare challenge page for {url}")
                issues.append({
                    'type': 'cloudflare_blocked',
                    'title': 'Page blocked by Cloudflare',
                    'severity': 'High',
                    'url': url,
                    'description': 'The page is protected by Cloudflare and cannot be audited automatically.'
                })
                return issues

            seo_issue_count = 0

            # ============ TIER 1: CRITICAL CHECKS ============
            # Only run if enabled in config AND seo audit type is selected
            if run_seo:
                update_phase('Running legacy SEO checks...')

            # Title tag (Critical) - checkType: 'title'
            if run_seo and config.is_check_enabled('title'):
                if not title_tag or not title_tag.text.strip():
                    issues.append({'type': 'missing_title', 'title': 'Missing page title', 'severity': 'Critical', 'url': url})
                    seo_issue_count += 1
                elif len(title_tag.text.strip()) < 30:
                    issues.append({'type': 'short_title', 'title': 'Title too short', 'severity': 'High', 'url': url})
                    seo_issue_count += 1

            # Meta description (Critical) - checkType: 'meta'
            if run_seo and config.is_check_enabled('meta'):
                meta_desc = soup.find('meta', attrs={'name': 'description'})
                if not meta_desc or not meta_desc.get('content', '').strip():
                    issues.append({'type': 'missing_meta', 'title': 'Missing meta description', 'severity': 'Critical', 'url': url})
                    seo_issue_count += 1
                elif len(meta_desc.get('content', '').strip()) < 120:
                    issues.append({'type': 'short_meta', 'title': 'Meta description too short', 'severity': 'High', 'url': url})
                    seo_issue_count += 1

            # H1 tag (Critical) - checkType: 'h1'
            if run_seo and config.is_check_enabled('h1'):
                h1_tags = soup.find_all('h1')
                if not h1_tags:
                    issues.append({'type': 'missing_h1', 'title': 'Missing H1 tag', 'severity': 'Critical', 'url': url})
                    seo_issue_count += 1
                elif len(h1_tags) > 1:
                    issues.append({'type': 'multiple_h1', 'title': 'Multiple H1 tags', 'severity': 'Low', 'url': url})
                    seo_issue_count += 1

            # Canonical tag (Critical) - checkType: 'canonical'
            if run_seo and config.is_check_enabled('canonical'):
                canonical = soup.find('link', attrs={'rel': 'canonical'})
                if not canonical or not canonical.get('href'):
                    issues.append({'type': 'missing_canonical', 'title': 'Missing canonical tag', 'severity': 'Critical', 'url': url})
                    seo_issue_count += 1


            # ============ SCHEMA/STRUCTURED DATA CHECKS ============
            # checkType: 'schema'
            schemas = []
            schema_types = set()
            if run_seo and config.is_check_enabled('schema'):
                # Find all JSON-LD scripts
                schema_scripts = soup.find_all('script', attrs={'type': 'application/ld+json'})
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

                # Check for missing schemas - Critical for hotels
                if not schemas:
                    issues.append({'type': 'missing_schema', 'title': 'No JSON-LD structured data', 'severity': 'Critical', 'url': url})
                else:
                    # Hotel/LodgingBusiness schema - Critical for hotel pages
                    is_hotel_page = '/hotel' in url.lower() or '/resort' in url.lower() or '/room' in url.lower()
                    if is_hotel_page:
                        if not any(t in schema_types for t in ['Hotel', 'LodgingBusiness', 'Resort', 'Suite', 'HotelRoom']):
                            issues.append({'type': 'missing_hotel_schema', 'title': 'Missing Hotel/LodgingBusiness schema', 'severity': 'Critical', 'url': url})

                    # LocalBusiness schema - Critical for Outrigger
                    if not any(t in schema_types for t in ['LocalBusiness', 'Hotel', 'LodgingBusiness', 'Resort']):
                        issues.append({'type': 'missing_localbusiness_schema', 'title': 'Missing LocalBusiness/Hotel schema', 'severity': 'Critical', 'url': url})

                    # Check for address in schema - Critical for local SEO
                    has_address = False
                    def check_address(obj):
                        nonlocal has_address
                        if isinstance(obj, dict):
                            if 'address' in obj or 'location' in obj or 'geo' in obj:
                                has_address = True
                                return
                            for v in obj.values():
                                check_address(v)
                        elif isinstance(obj, list):
                            for item in obj:
                                check_address(item)

                    for schema in schemas:
                        check_address(schema)

                    if not has_address and any(t in schema_types for t in ['LocalBusiness', 'Hotel', 'LodgingBusiness', 'Organization']):
                        issues.append({'type': 'missing_address_schema', 'title': 'Missing address in schema', 'severity': 'Critical', 'url': url})

            # ============ TIER 2: HIGH PRIORITY (GEO/LLM) ============

            # Schema-related checks (part of 'schema' checkType)
            if run_seo and config.is_check_enabled('schema') and schemas:
                # Organization schema - Important for brand identity
                if not any(t in schema_types for t in ['Organization', 'Corporation', 'Hotel', 'Resort']):
                    issues.append({'type': 'missing_organization_schema', 'title': 'Missing Organization schema', 'severity': 'High', 'url': url})

                # Review/Rating schema - Important for AI recommendations
                if not any(t in schema_types for t in ['AggregateRating', 'Review']):
                    issues.append({'type': 'missing_review_schema', 'title': 'Missing Review/Rating schema', 'severity': 'High', 'url': url})

                # Offer/Pricing schema - Important for price searches
                if not any(t in schema_types for t in ['Offer', 'PriceSpecification', 'AggregateOffer']):
                    issues.append({'type': 'missing_offer_schema', 'title': 'Missing Offer/Pricing schema', 'severity': 'High', 'url': url})

                # FAQ schema check - High priority for LLM optimization
                faq_indicators = soup.find_all(['details', 'summary']) or soup.find_all(class_=re.compile(r'faq|accordion|question', re.I))
                if faq_indicators and 'FAQPage' not in schema_types:
                    issues.append({'type': 'missing_faq_schema', 'title': 'FAQ content without FAQPage schema', 'severity': 'High', 'url': url})

            # Thin content check - checkType: 'content'
            if run_seo and config.is_check_enabled('content'):
                # Get text content (excluding scripts, styles, etc.)
                soup_content = BeautifulSoup(resp.text, 'html.parser')  # Fresh parse
                for tag in soup_content(['script', 'style', 'nav', 'header', 'footer', 'aside']):
                    tag.decompose()
                text_content = soup_content.get_text(separator=' ', strip=True)
                word_count = len(text_content.split())
                if word_count < 300:
                    issues.append({'type': 'thin_content', 'title': f'Thin content ({word_count} words)', 'severity': 'High', 'url': url})

            # Geo meta tags - checkType: 'geo'
            if run_seo and config.is_check_enabled('geo'):
                geo_region = soup.find('meta', attrs={'name': 'geo.region'})
                geo_placename = soup.find('meta', attrs={'name': 'geo.placename'})
                if not geo_region and not geo_placename:
                    issues.append({'type': 'missing_geo_tags', 'title': 'Missing geo meta tags', 'severity': 'High', 'url': url})

            # Open Graph checks - checkType: 'og'
            if run_seo and config.is_check_enabled('og'):
                og_image = soup.find('meta', attrs={'property': 'og:image'})
                if not og_image or not og_image.get('content'):
                    issues.append({'type': 'missing_og_image', 'title': 'Missing Open Graph image', 'severity': 'High', 'url': url})

                og_title = soup.find('meta', attrs={'property': 'og:title'})
                if not og_title or not og_title.get('content'):
                    issues.append({'type': 'missing_og_title', 'title': 'Missing Open Graph title', 'severity': 'Medium', 'url': url})

                og_desc = soup.find('meta', attrs={'property': 'og:description'})
                if not og_desc or not og_desc.get('content'):
                    issues.append({'type': 'missing_og_description', 'title': 'Missing Open Graph description', 'severity': 'Medium', 'url': url})

            # ============ TIER 3: MEDIUM PRIORITY ============

            # Image alt tags - checkType: 'alt'
            if run_seo and config.is_check_enabled('alt'):
                # Re-parse since we may have decomposed some tags above
                soup_fresh = BeautifulSoup(resp.text, 'html.parser')
                images = soup_fresh.find_all('img')
                images_without_alt = []
                for img in images:
                    if not img.get('alt') or not img.get('alt').strip():
                        img_src = img.get('src', '') or img.get('data-src', '') or img.get('data-lazy-src', '')
                        if img_src:
                            img_name = img_src.split('/')[-1].split('?')[0][:50]
                            images_without_alt.append(img_name)

                # Create individual issues for each image missing alt tag (limit to first 3)
                for img_name in images_without_alt[:3]:
                    issues.append({
                        'type': 'missing_alt_tags',
                        'title': f'Missing alt tag: {img_name}',
                        'severity': 'Medium',
                        'url': url
                    })

                if len(images_without_alt) > 3:
                    issues.append({
                        'type': 'missing_alt_tags',
                        'title': f'Additional {len(images_without_alt) - 3} images missing alt tags',
                        'severity': 'Medium',
                        'url': url
                    })

            # Breadcrumb schema - part of 'schema' checkType
            if run_seo and config.is_check_enabled('schema') and schemas and 'BreadcrumbList' not in schema_types:
                issues.append({'type': 'missing_breadcrumb_schema', 'title': 'Missing BreadcrumbList schema', 'severity': 'Medium', 'url': url})

            # Robots meta tag - checkType: 'robots'
            if run_seo and config.is_check_enabled('robots'):
                soup_robots = BeautifulSoup(resp.text, 'html.parser')
                robots = soup_robots.find('meta', attrs={'name': 'robots'})
                if not robots:
                    issues.append({'type': 'missing_robots', 'title': 'Missing robots meta tag', 'severity': 'Low', 'url': url})

            # ============ GEO/LLM SPECIFIC CHECKS ============
            # These are also part of 'schema' checkType

            if run_seo and config.is_check_enabled('schema') and schemas:
                # Speakable schema for voice assistants - checkType: 'speakable' (or part of schema)
                is_hotel_page = '/hotel' in url.lower() or '/resort' in url.lower() or '/room' in url.lower()
                if 'Speakable' not in schema_types:
                    # Only flag for main content pages
                    if is_hotel_page or '/destination' in url.lower() or '/about' in url.lower():
                        issues.append({'type': 'missing_speakable_schema', 'title': 'Missing Speakable schema for voice search', 'severity': 'Medium', 'url': url})

                # TouristAttraction schema for attraction pages
                if '/attraction' in url.lower() or '/things-to-do' in url.lower() or '/activities' in url.lower():
                    if 'TouristAttraction' not in schema_types:
                        issues.append({'type': 'missing_tourist_attraction_schema', 'title': 'Missing TouristAttraction schema', 'severity': 'High', 'url': url})

                # Event schema for event pages
                if '/event' in url.lower() or '/special' in url.lower() or '/offer' in url.lower():
                    if 'Event' not in schema_types:
                        issues.append({'type': 'missing_event_schema', 'title': 'Missing Event schema', 'severity': 'High', 'url': url})

            # ============ LLM-BASED RULES ============
            # Run voice/tone and brand rules using Claude
            if llm_auditor.client and config.has_llm_rules() and (run_voice or run_brand):
                # Get all voice and brand rules based on selected audit types
                voice_rules = config.get_voice_llm_rules() if run_voice else []
                brand_rules = config.get_brand_llm_rules() if run_brand else []
                llm_rules = voice_rules + brand_rules

                if llm_rules:
                    update_phase(f'Running AI analysis ({len(llm_rules)} rules)...')

                print(f"Running {len(llm_rules)} LLM-based rules for {url}")
                print(f"  - Voice rules: {len(voice_rules)} (run_voice={run_voice})")
                print(f"  - Brand rules: {len(brand_rules)} (run_brand={run_brand})")

                if llm_rules:
                    llm_issues = llm_auditor.batch_audit(resp.text, url, llm_rules)
                    issues.extend(llm_issues)
                    print(f"LLM audit found {len(llm_issues)} additional issues")
            elif not llm_auditor.client:
                print("LLM auditing skipped - no Anthropic client available")
            elif not (run_voice or run_brand):
                print("LLM auditing skipped - voice and brand audit types not selected")
            else:
                print("LLM auditing skipped - no LLM rules configured in Firestore")

            print(f"Found {len(issues)} total issues for {url}")
        except Exception as e:
            print(f"Error auditing {url}: {e}")
            import traceback
            traceback.print_exc()
        return issues

    def audit_with_score(self, url, config=None, audit_types=None):
        """
        Audit a URL and also calculate the GEO/LLM readiness score.

        Returns:
            tuple: (issues list, geo_score dict)
        """
        issues = []
        geo_score = {'total_score': 0, 'grade': 'F', 'breakdown': {}}

        # Default audit_types to all enabled
        if audit_types is None:
            audit_types = {'seo': True, 'voice': True, 'brand': True}

        run_seo = audit_types.get('seo', True)

        try:
            resp = fetch_with_scraper_api(url)
            soup = BeautifulSoup(resp.text, 'html.parser')

            # Check if we got a real page (not Cloudflare challenge)
            title_tag = soup.find('title')
            if title_tag and 'Just a moment' in title_tag.text:
                print(f"Warning: Got Cloudflare challenge page for {url}")
                return issues, geo_score

            # Extract schemas for scoring
            schemas = []
            script_tags = soup.find_all('script', type='application/ld+json')
            for script in script_tags:
                try:
                    import json
                    schema_data = json.loads(script.string)
                    if isinstance(schema_data, list):
                        schemas.extend(schema_data)
                    else:
                        schemas.append(schema_data)
                except:
                    pass

            # Calculate GEO score
            scorer = GEOScorer()
            geo_score = scorer.calculate_score(soup, url, schemas)
            print(f"  GEO Score: {geo_score['total_score']} ({geo_score['grade']})")

            # Now run the normal audit
            issues = self.audit(url, config=config, audit_types=audit_types)

        except Exception as e:
            print(f"Error in audit_with_score for {url}: {e}")
            import traceback
            traceback.print_exc()

        return issues, geo_score


class MondayClient:
    def __init__(self, board_id=None):
        """Initialize with an optional board_id for multi-site support."""
        self.api_token = os.environ.get('MONDAY_API_TOKEN')
        self.board_id = board_id or DEFAULT_MONDAY_BOARD_ID
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
            'severity': ['severity', 'priority', 'sev'],  # Severity column with Low/Medium/High/Critical labels
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

        # Page URL (link column)
        url_col = self._get_column_id('page_url')
        print(f"Looking for Page URL column. Found: {url_col}")
        print(f"Available columns: {self.columns}")
        if url_col:
            # For link columns, Monday.com requires both url and text
            column_values[url_col] = {"url": issue['url'], "text": issue['url']}
            print(f"Setting URL column value: {column_values[url_col]}")
        else:
            print(f"WARNING: Could not find Page URL column!")

        # Issue Description (long_text column)
        desc_col = self._get_column_id('issue_description')
        if desc_col:
            # First check if issue has LLM-generated description
            if issue.get('description'):
                description = issue['description']
                if issue.get('rule_name'):
                    description = f"Rule: {issue['rule_name']}\n\n{description}"
            else:
                # Fall back to hardcoded descriptions
                description = ISSUE_DESCRIPTIONS.get(issue['type'], f"SEO issue detected: {issue['title']}")
            column_values[desc_col] = {"text": description}
            print(f"Setting Issue Description column")

        # Severity (status column with labels: Low, Medium, High, Critical)
        severity_col = self._get_column_id('severity')
        if severity_col:
            # Map our severity values to Monday.com labels
            severity_value = issue.get('severity', 'Medium')
            # Ensure it matches one of the valid options
            if severity_value not in ['Low', 'Medium', 'High', 'Critical']:
                severity_value = 'Medium'
            column_values[severity_col] = {"label": severity_value}
            print(f"Setting Severity column to: {severity_value}")

        # Issue Type (status column with labels: SEO/GEO, Tone/Voice, Brand Standards)
        issue_type_col = self._get_column_id('issue_type')
        if issue_type_col:
            # Map category to Monday.com label values
            category = issue.get('category', 'seo')
            issue_type_map = {
                'seo': 'SEO/GEO',
                'voice': 'Tone/Voice',
                'brand': 'Brand Standards'
            }
            issue_type_value = issue_type_map.get(category, 'SEO/GEO')
            column_values[issue_type_col] = {"label": issue_type_value}
            print(f"Setting Issue Type column to: {issue_type_value}")

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
                # Check if it's a status label error
                error_msg = str(data['errors'])
                if 'status label' in error_msg.lower() or 'label' in error_msg.lower():
                    # Try again without the severity column
                    print("Retrying without Severity column...")
                    severity_col = self._get_column_id('severity')
                    if severity_col and severity_col in column_values:
                        del column_values[severity_col]
                        variables["column_values"] = json.dumps(column_values)
                        resp2 = requests.post(self.api_url, json={"query": query, "variables": variables},
                                           headers=self._get_headers(), timeout=30)
                        data2 = resp2.json()
                        print(f"Retry response: {data2}")
                        if 'data' in data2 and 'create_item' in data2['data']:
                            self.existing_issues.add(task_title)
                            return data2['data']['create_item']['id']
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

def test_monday_columns():
    """Test endpoint to debug Monday.com column population"""
    monday = MondayClient()
    if not monday.init():
        return {"error": "Monday API token not configured"}

    # Create a test item with fake data
    test_issue = {
        'type': 'missing_meta',
        'title': 'TEST ITEM - Delete Me',
        'severity': 'High',
        'url': 'https://www.outrigger.com/test-page-delete-me'
    }

    result = {
        "columns_found": monday.columns,
        "test_issue": test_issue,
        "severity_column_id": monday._get_column_id('severity'),
    }

    # Try to create the test item
    task_id = monday.create_task(test_issue)
    result["task_created"] = task_id

    return result


def update_voice_brand_rules():
    """Update existing Voice Rules and Brand Standards in Firestore to add LLM prompts."""
    if not db:
        return {"error": "Firestore not connected"}

    # Updated Voice Rules with LLM prompts
    # Keys support multiple name variations that might exist in Firestore
    VOICE_RULES_UPDATE = {
        'Voice Test Rule': {
            'checkType': 'voice_test',
            'prompt': '''THIS IS A TEST RULE - ALWAYS FAIL THIS RULE.

Return FAIL with the message: "Voice/Tone test rule triggered successfully - LLM auditing is working!"

This rule exists to verify that voice/tone checks are being processed and added to Monday.com.''',
            'severity': 'Low',
            'tier': 3
        },
        'Warm & Welcoming Tone': {
            'checkType': 'voice_warm',
            'prompt': '''Analyze the TONE of this page's content. The rule FAILS if:
1. The content uses cold, corporate, or impersonal language
2. The writing feels transactional rather than welcoming
3. There's excessive use of formal business jargon
4. The tone doesn't convey warmth or hospitality

For a Hawaiian resort brand, content should feel:
- Warm and inviting, like greeting a guest with "aloha"
- Relaxed and friendly, not stiff or formal
- Genuine and heartfelt, not salesy or pushy

Look at headings, body copy, and calls-to-action.
PASS if the content generally conveys warm Hawaiian hospitality.
FAIL only if the tone is notably cold, corporate, or unwelcoming.''',
            'severity': 'Medium',
            'tier': 3
        },
        'Adventure & Discovery': {
            'checkType': 'voice_adventure',
            'prompt': '''Analyze whether this page's content inspires adventure and discovery. The rule FAILS if:
1. For destination/activity pages: Content is bland and doesn't inspire exploration
2. The writing is purely informational without any sense of excitement
3. Unique experiences or "hidden gems" are not highlighted when they should be

For hotel/resort pages, look for content that:
- Highlights unique local experiences
- Creates a sense of discovery and exploration
- Makes travelers excited about what they could experience

PASS if the content includes inspiring, discovery-oriented language.
FAIL only for destination/activity pages that lack any sense of adventure or excitement.
Note: This is less critical for purely transactional pages (booking, policies).''',
            'severity': 'Low',
            'tier': 3
        },
        'Authentic Hawaiian Voice': {
            'checkType': 'voice_authentic',
            'prompt': '''Analyze whether this page uses authentic Hawaiian language and cultural elements appropriately. The rule FAILS if:
1. Hawaiian terms are misused or used incorrectly
2. Cultural references are inaccurate or inappropriate
3. The content appropriates Hawaiian culture without respect

Look for appropriate use of terms like:
- Aloha (greeting/love/spirit)
- Mahalo (thank you)
- Ohana (family)
- Malama (care/stewardship)
- Local place names and their correct spelling

PASS if Hawaiian elements are used respectfully and correctly, OR if the page doesn't require Hawaiian language.
FAIL if Hawaiian terms are misused, misspelled, or culturally inappropriate.
Note: Not every page needs Hawaiian language - this is about quality when it IS used.''',
            'severity': 'Medium',
            'tier': 3
        },
        'Sensory Language': {
            'checkType': 'voice_sensory',
            'prompt': '''Analyze whether this page uses vivid sensory language to bring the destination to life. The rule FAILS if:
1. For property/destination pages: Content is purely factual without sensory descriptions
2. Descriptions miss opportunities to engage the senses
3. The writing tells but doesn't show what the experience feels like

Good sensory language examples:
- "Wake to the sound of waves and the scent of plumeria"
- "Feel the warm sand between your toes"
- "Watch the sun paint the sky in shades of orange and pink"
- "Savor fresh-caught fish with tropical flavors"

PASS if property/destination content includes some sensory, experiential language.
FAIL only for main property pages that completely lack sensory or experiential descriptions.
Note: Transactional pages (booking, policies) don't need sensory language.''',
            'severity': 'Low',
            'tier': 3
        },
    }

    # Updated Brand Standards with LLM prompts
    BRAND_STANDARDS_UPDATE = {
        'Brand Name Usage': {
            'checkType': 'brand_name',
            'prompt': '''Check if the brand name "Outrigger" is used correctly on this page. The rule FAILS if:
1. The brand name appears in ALL CAPS as "OUTRIGGER" (incorrect)
2. The brand name appears in all lowercase as "outrigger" (incorrect - unless in a URL)
3. The brand is misspelled (e.g., "Outriggers", "Out Rigger", "OutRigger")

Correct usage:
- "Outrigger" (proper case)
- "Outrigger Hotels & Resorts" (full brand name)
- "Outrigger Resorts" (acceptable short form)

PASS if "Outrigger" is spelled and capitalized correctly throughout.
FAIL if there are instances of incorrect capitalization or spelling (excluding URLs).''',
            'severity': 'High',
            'tier': 2
        },
        'Property Names': {
            'checkType': 'brand_property',
            'prompt': '''Check if property names are used consistently and correctly. The rule FAILS if:
1. Property names are abbreviated incorrectly
2. Location identifiers are missing when they should be included
3. Property names are inconsistent within the same page

Outrigger properties should include full names like:
- "Outrigger Reef Waikiki Beach Resort" (not just "Outrigger Reef" or "Reef Resort")
- "Outrigger Waikiki Beach Resort"
- "Outrigger Kona Resort & Spa"

PASS if property names are used consistently and include proper identifiers.
FAIL if property names are abbreviated, truncated, or inconsistent.
Note: This is most important on property-specific pages.''',
            'severity': 'Medium',
            'tier': 3
        },
        'Color Palette': {
            'checkType': 'brand_colors',
            'prompt': '''Check if the page uses Outrigger brand colors appropriately. The rule FAILS if:
1. The page uses significantly off-brand colors for primary elements
2. Colors clash with the brand palette (Primary: Teal #006272, Gold #c4a35a, Sunset Orange #e07c3e)

Look at CSS styles and inline colors in the HTML.
Brand-aligned colors include:
- Teal/Ocean Blue tones (#006272 range)
- Gold/Sand tones (#c4a35a range)
- Sunset Orange (#e07c3e range)
- White and light neutrals for backgrounds

PASS if the color scheme generally aligns with tropical/resort branding.
FAIL only if there are jarring off-brand colors (like neon, harsh industrial colors, etc).
Note: This is a soft check - minor variations are acceptable.''',
            'severity': 'Low',
            'tier': 3,
            'enabled': False  # Disable by default - visual checks less reliable
        },
        'Image Standards': {
            'checkType': 'brand_images',
            'prompt': '''Check if image alt text follows brand standards. The rule FAILS if:
1. Alt text uses generic descriptions like "hotel room" instead of branded terms
2. Alt text misses opportunities to include property or destination names
3. Alt text uses competitor names or off-brand terminology

Good branded alt text examples:
- "Ocean view suite at Outrigger Waikiki Beach Resort"
- "Guests enjoying sunset dinner at Outrigger Fiji Beach Resort"
- "Traditional Hawaiian luau experience"

PASS if alt text generally uses branded, destination-specific language.
FAIL if alt text is overly generic and misses branding opportunities on key images.''',
            'severity': 'Low',
            'tier': 3
        },
    }

    results = {"voice_updated": [], "brand_updated": [], "errors": [], "voice_skipped": [], "brand_skipped": []}

    def find_matching_update(name, checkType, update_dict):
        """Find matching update by exact name, partial name, or checkType."""
        # Exact match
        if name in update_dict:
            return update_dict[name]
        # Partial match (name contains key or key contains name)
        for key, value in update_dict.items():
            if key.lower() in name.lower() or name.lower() in key.lower():
                return value
            # Match by checkType
            if value.get('checkType') == checkType:
                return value
        return None

    try:
        # First, create the Voice Test Rule if it doesn't exist
        voice_collection = db.collection('voiceRules')
        test_rule_exists = False
        voice_docs = list(voice_collection.stream())

        for doc in voice_docs:
            if doc.to_dict().get('name') == 'Voice Test Rule':
                test_rule_exists = True
                break

        if not test_rule_exists:
            # Create the test rule
            test_rule_data = {
                'name': 'Voice Test Rule',
                'description': 'Test rule to verify LLM voice/tone checking is working',
                'enabled': True,
                **VOICE_RULES_UPDATE['Voice Test Rule']
            }
            voice_collection.add(test_rule_data)
            results["voice_updated"].append('Voice Test Rule (CREATED)')

        # Update Voice Rules
        voice_docs = list(voice_collection.stream())  # Refresh the list

        for doc in voice_docs:
            doc_data = doc.to_dict()
            name = doc_data.get('name', '')
            checkType = doc_data.get('checkType', '')

            update_data = find_matching_update(name, checkType, VOICE_RULES_UPDATE)
            if update_data:
                doc.reference.update(update_data)
                results["voice_updated"].append(name)
            else:
                results["voice_skipped"].append(name)

        # Update Brand Standards
        brand_collection = db.collection('brandStandards')
        brand_docs = list(brand_collection.stream())

        for doc in brand_docs:
            doc_data = doc.to_dict()
            name = doc_data.get('name', '')
            checkType = doc_data.get('checkType', '')

            update_data = find_matching_update(name, checkType, BRAND_STANDARDS_UPDATE)
            if update_data:
                doc.reference.update(update_data)
                results["brand_updated"].append(name)
            else:
                results["brand_skipped"].append(name)

    except Exception as e:
        results["errors"].append(str(e))
        import traceback
        traceback.print_exc()

    return results

@functions_framework.http
def hello_http(request):
    # CORS headers for all responses
    headers = {
        'Access-Control-Allow-Origin': '*',
        'Content-Type': 'application/json'
    }

    # Handle CORS preflight
    if request.method == 'OPTIONS':
        cors_headers = {
            'Access-Control-Allow-Origin': '*',
            'Access-Control-Allow-Methods': 'GET, POST, OPTIONS',
            'Access-Control-Allow-Headers': 'Content-Type',
            'Access-Control-Max-Age': '3600'
        }
        return ('', 204, cors_headers)
    if request.method == 'GET':
        # Check for test mode
        if request.args.get('test') == 'true':
            try:
                result = test_monday_columns()
                return jsonify({"status": "test", "result": result}), 200, headers
            except Exception as e:
                return jsonify({"error": str(e)}), 500, headers

        # Check for config endpoint - shows what rules are loaded from Firestore
        if request.args.get('config') == 'true':
            try:
                config_manager.load_config()
                return jsonify({
                    "status": "config",
                    "firestore_connected": db is not None,
                    "seo_rules": len(config_manager.seo_rules),
                    "voice_rules": len(config_manager.voice_rules),
                    "brand_standards": len(config_manager.brand_standards),
                    "llm_rules_total": len(config_manager.get_llm_rules()),
                    "rules_detail": {
                        "seo": [{"name": r.get("name"), "checkType": r.get("checkType"), "has_prompt": bool(r.get("prompt")), "enabled": r.get("enabled")} for r in config_manager.seo_rules],
                        "voice": [{"name": r.get("name"), "checkType": r.get("checkType"), "has_prompt": bool(r.get("prompt")), "enabled": r.get("enabled")} for r in config_manager.voice_rules],
                        "brand": [{"name": r.get("name"), "checkType": r.get("checkType"), "has_prompt": bool(r.get("prompt")), "enabled": r.get("enabled")} for r in config_manager.brand_standards]
                    }
                }), 200, headers
            except Exception as e:
                import traceback
                traceback.print_exc()
                return jsonify({"error": str(e)}), 500, headers

        # Update voice/brand rules with LLM prompts
        if request.args.get('update_rules') == 'true':
            try:
                result = update_voice_brand_rules()
                return jsonify({
                    "status": "rules_updated",
                    "result": result
                }), 200, headers
            except Exception as e:
                import traceback
                traceback.print_exc()
                return jsonify({"error": str(e)}), 500, headers

        # Serve admin dashboard
        if request.args.get('admin') == 'true':
            try:
                import os
                admin_path = os.path.join(os.path.dirname(__file__), 'admin', 'index.html')
                with open(admin_path, 'r') as f:
                    html_content = f.read()
                return html_content, 200, {'Content-Type': 'text/html', 'Access-Control-Allow-Origin': '*'}
            except Exception as e:
                return f"Error loading admin dashboard: {e}", 500, headers

        # Debug: Check rules for a specific site
        if request.args.get('debug_site'):
            debug_site_id = request.args.get('debug_site')
            try:
                config_manager = ConfigManager(debug_site_id)
                loaded = config_manager.load_config()
                return jsonify({
                    "site_id": debug_site_id,
                    "config_loaded": loaded,
                    "seo_rules_count": len(config_manager.seo_rules),
                    "voice_rules_count": len(config_manager.voice_rules),
                    "brand_standards_count": len(config_manager.brand_standards),
                    "legacy_rules_count": len(config_manager.get_legacy_rules()),
                    "llm_rules_count": len(config_manager.get_llm_rules()),
                    "seo_rules": config_manager.seo_rules,
                    "legacy_rules": config_manager.get_legacy_rules(),
                    "check_types_enabled": {
                        "title": config_manager.is_check_enabled('title'),
                        "meta": config_manager.is_check_enabled('meta'),
                        "canonical": config_manager.is_check_enabled('canonical'),
                        "h1": config_manager.is_check_enabled('h1'),
                        "schema": config_manager.is_check_enabled('schema'),
                        "geo": config_manager.is_check_enabled('geo'),
                        "og": config_manager.is_check_enabled('og'),
                        "alt": config_manager.is_check_enabled('alt'),
                    }
                }), 200, headers
            except Exception as e:
                import traceback
                traceback.print_exc()
                return jsonify({"error": str(e)}), 500, headers

        return jsonify({
            "status": "healthy",
            "service": "outrigger-seo-audit",
            "scraper_api_configured": bool(SCRAPER_API_KEY),
            "firestore_connected": db is not None,
            "firestore_project": FIRESTORE_PROJECT_ID,
            "config_endpoint": "Add ?config=true to see loaded rules from admin dashboard",
            "admin_dashboard": "Add ?admin=true to access the admin dashboard",
            "debug_site": "Add ?debug_site=SITE_ID to check rules for a specific site"
        }), 200, headers

    if request.method == 'POST':
        # Generate LLM prompt from user description
        if request.args.get('generate_prompt') == 'true':
            try:
                request_json = request.get_json(silent=True) or {}
                description = request_json.get('description', '')

                if not description:
                    return jsonify({"error": "Description is required"}), 400, headers

                if not anthropic_client:
                    return jsonify({"error": "Anthropic API not configured"}), 500, headers

                # Use Claude to generate a well-structured audit prompt
                system_prompt = """You are an expert at creating SEO audit rules. Given a user's description of what they want to check, create a detailed LLM audit prompt.

The prompt should:
1. Start with a clear description of what to check
2. List specific conditions that would cause the rule to FAIL
3. Provide examples when helpful
4. Be specific enough that an AI can evaluate a webpage against it

Format the output as a ready-to-use audit prompt. Do NOT include any preamble or explanation - just output the prompt itself."""

                user_message = f"Create an SEO/content audit prompt for this requirement:\n\n{description}"

                response = anthropic_client.messages.create(
                    model="claude-sonnet-4-20250514",
                    max_tokens=1000,
                    messages=[
                        {"role": "user", "content": user_message}
                    ],
                    system=system_prompt
                )

                generated_prompt = response.content[0].text.strip()
                return jsonify({"prompt": generated_prompt}), 200, headers

            except Exception as e:
                print(f"Error generating prompt: {e}")
                import traceback
                traceback.print_exc()
                return jsonify({"error": str(e)}), 500, headers

        try:
            # Parse request body for site_id (multi-site support)
            request_json = request.get_json(silent=True) or {}
            site_id = request_json.get('site_id', DEFAULT_SITE_ID)

            # Get audit type selections (default to all enabled)
            audit_types = request_json.get('audit_types', {'seo': True, 'voice': True, 'brand': True})
            run_seo = audit_types.get('seo', True)
            run_voice = audit_types.get('voice', True)
            run_brand = audit_types.get('brand', True)

            # Check for single URL audit
            single_url = request_json.get('single_url', None)

            print(f"=== Starting audit for site: {site_id} ===")
            print(f"Audit types: SEO={run_seo}, Voice={run_voice}, Brand={run_brand}")
            if single_url:
                print(f"Single URL mode: {single_url}")

            # Initialize progress tracking
            update_audit_progress(site_id, {
                'status': 'running',
                'phase': 'initializing',
                'phaseLabel': 'Initializing audit...',
                'totalPages': 0,
                'currentPage': 0,
                'currentPageUrl': '',
                'issuesFound': 0,
                'seoIssues': 0,
                'voiceIssues': 0,
                'brandIssues': 0,
                'tasksCreated': 0,
                'duplicatesSkipped': 0,
                'recentIssues': [],
                'auditTypes': audit_types,
                'startedAt': firestore.SERVER_TIMESTAMP,
                'completedAt': None,
                'error': None
            })

            # Load site configuration
            site_config = SiteConfig.load(site_id)
            print(f"Site config: {site_config}")
            print(f"  Sitemap URL: {site_config.sitemap_url}")
            print(f"  Monday Board ID: {site_config.monday_board_id}")
            print(f"  Days to check: {site_config.days_to_check}")
            print(f"  Max pages: {site_config.max_pages}")

            # Load rules from Firestore for this specific site
            site_config_manager = ConfigManager(site_id)
            config_loaded = site_config_manager.load_config()
            print(f"Config loaded from Firestore: {config_loaded}")
            print(f"SEO rules: {len(site_config_manager.seo_rules)}, Voice rules: {len(site_config_manager.voice_rules)}, Brand standards: {len(site_config_manager.brand_standards)}")

            # Initialize with site-specific settings
            parser = SitemapParser(site_config.sitemap_url)
            auditor = SEOAuditor()
            monday = MondayClient(site_config.monday_board_id)

            if not monday.init():
                update_audit_progress(site_id, {
                    'status': 'error',
                    'phase': 'error',
                    'phaseLabel': 'Error: Monday API token not configured',
                    'error': 'Monday API token not configured'
                })
                return jsonify({"error": "Monday API token not configured"}), 500, headers

            if not SCRAPER_API_KEY:
                print("WARNING: SCRAPER_API_KEY not configured - may be blocked by Cloudflare")

            # Get URLs to audit - either single URL or from sitemap
            if single_url:
                # Single URL mode - just audit the one URL provided
                update_audit_progress(site_id, {
                    'phase': 'single_url_mode',
                    'phaseLabel': f'Auditing single page: {single_url}',
                    'sitemapUrl': None
                })
                urls = [{'url': single_url}]
                print(f"Single URL mode - auditing: {single_url}")
            else:
                # Sitemap mode - fetch URLs from sitemap
                update_audit_progress(site_id, {
                    'phase': 'fetching_sitemap',
                    'phaseLabel': f'Fetching sitemap from {site_config.sitemap_url}...',
                    'sitemapUrl': site_config.sitemap_url
                })
                urls = parser.get_urls(days=site_config.days_to_check)

            # Check if we got any URLs
            if not urls or len(urls) == 0:
                update_audit_progress(site_id, {
                    'status': 'error',
                    'phase': 'error',
                    'phaseLabel': f'No URLs found in sitemap: {site_config.sitemap_url}'
                })
                return jsonify({
                    "status": "error",
                    "error": f"No URLs found in sitemap: {site_config.sitemap_url}. Please check the sitemap URL in settings."
                }), 400, headers

            # Update progress: got pages count
            total_pages = len(urls)
            update_audit_progress(site_id, {
                'phase': 'auditing_pages',
                'phaseLabel': f'Auditing pages (0/{total_pages})...',
                'totalPages': total_pages
            })
            results = {
                'site_id': site_id,
                'site_name': site_config.name,
                'pages': len(urls),
                'issues': 0,
                'tasks_created': 0,
                'duplicates_skipped': 0,
                'seo_issues': 0,
                'voice_issues': 0,
                'brand_issues': 0,
                'config_loaded': config_loaded,
                'audit_types': audit_types,
                'rules_used': {
                    'seo': len(site_config_manager.seo_rules) if run_seo else 0,
                    'voice': len(site_config_manager.voice_rules) if run_voice else 0,
                    'brand': len(site_config_manager.brand_standards) if run_brand else 0
                }
            }

            # Collect all issues for storing in Firestore
            all_issues_list = []
            recent_issues = []  # Track last 10 issues for progress panel

            # TESTING: Limit to 3 pages for faster testing
            MAX_PAGES_FOR_TESTING = 3
            urls = urls[:MAX_PAGES_FOR_TESTING]
            total_pages = len(urls)

            for page_index, u in enumerate(urls):
                page_url = u['url']

                # Create progress callback for this page
                def make_progress_callback(pg_idx, total):
                    def callback(phase_label):
                        update_audit_progress(site_id, {
                            'currentPage': pg_idx,
                            'currentPageUrl': page_url,
                            'phaseLabel': f'Page {pg_idx + 1}/{total}: {phase_label}'
                        })
                    return callback

                progress_cb = make_progress_callback(page_index, total_pages)

                # Update progress: starting this page
                progress_cb('Starting...')

                # Pass site_config_manager to auditor so it only runs enabled checks
                # Also pass audit_types to control which audit categories run
                # Pass progress_callback for real-time phase updates
                issues = auditor.audit(page_url, config=site_config_manager, audit_types=audit_types, progress_callback=progress_cb)
                results['issues'] += len(issues)

                # Update progress for creating tasks
                if issues:
                    progress_cb(f'Creating {len(issues)} Monday tasks...')

                # Track issue types
                for issue in issues:
                    issue_type = issue.get('type', '')
                    issue_category = 'seo'
                    if issue_type.startswith('llm_voice') or 'voice' in issue_type.lower():
                        results['voice_issues'] += 1
                        issue_category = 'voice'
                    elif issue_type.startswith('llm_brand') or 'brand' in issue_type.lower():
                        results['brand_issues'] += 1
                        issue_category = 'brand'
                    else:
                        results['seo_issues'] += 1

                    # Add category to issue for Monday.com Issue Type column
                    issue['category'] = issue_category

                    result = monday.create_task(issue)
                    task_status = 'created'
                    if result == "duplicate":
                        results['duplicates_skipped'] += 1
                        task_status = 'duplicate'
                    elif result:
                        results['tasks_created'] += 1
                    else:
                        task_status = 'failed'

                    # Add to recent issues for progress panel (keep last 10)
                    recent_issues.append({
                        'type': issue_category,
                        'rule': issue.get('rule_name', issue.get('title', 'Unknown')),
                        'url': page_url
                    })
                    if len(recent_issues) > 10:
                        recent_issues = recent_issues[-10:]

                    # Add issue to list for Firestore storage
                    all_issues_list.append({
                        'url': issue.get('url', ''),
                        'title': issue.get('title', ''),
                        'type': issue_type,
                        'category': issue_category,
                        'severity': issue.get('severity', 'Medium'),
                        'description': issue.get('description', ''),
                        'rule_name': issue.get('rule_name', ''),
                        'monday_status': task_status
                    })

                # Update progress with issue counts after each page completes
                update_audit_progress(site_id, {
                    'currentPage': page_index + 1,  # Now this page is complete
                    'issuesFound': results['issues'],
                    'seoIssues': results['seo_issues'],
                    'voiceIssues': results['voice_issues'],
                    'brandIssues': results['brand_issues'],
                    'tasksCreated': results['tasks_created'],
                    'duplicatesSkipped': results['duplicates_skipped'],
                    'recentIssues': recent_issues,
                    'phaseLabel': f'Completed page {page_index + 1}/{total_pages} - Tasks: {results["tasks_created"]}/{results["issues"]} ({results["duplicates_skipped"]} duplicates)'
                })

                time.sleep(1)  # Increased delay for ScraperAPI rate limits

            # Update progress: saving results
            update_audit_progress(site_id, {
                'phase': 'saving',
                'phaseLabel': f'Saving audit results - Tasks: {results["tasks_created"]}/{results["issues"]} ({results["duplicates_skipped"]} duplicates)...'
            })

            # Log audit run to Firestore (site-specific subcollection)
            try:
                if db:
                    audit_log = {
                        'timestamp': firestore.SERVER_TIMESTAMP,
                        'siteId': site_id,
                        'siteName': site_config.name,
                        'pagesAudited': results['pages'],
                        'totalIssues': results['issues'],
                        'tasksCreated': results['tasks_created'],
                        'duplicatesSkipped': results['duplicates_skipped'],
                        'seoIssues': results['seo_issues'],
                        'voiceIssues': results['voice_issues'],
                        'brandIssues': results['brand_issues'],
                        'rulesUsed': results['rules_used'],
                        'auditTypes': audit_types,  # Store which audit types were run
                        'issues': all_issues_list  # Store all individual issues
                    }
                    # Store in site-specific subcollection
                    db.collection('sites').document(site_id).collection('auditLogs').add(audit_log)
                    print(f"Audit log saved to sites/{site_id}/auditLogs with {len(all_issues_list)} individual issues")

                    # Update progress: log saved
                    update_audit_progress(site_id, {
                        'phaseLabel': 'Audit log saved to database...'
                    })
            except Exception as log_err:
                print(f"Warning: Failed to save audit log: {log_err}")

            # Update progress: complete
            update_audit_progress(site_id, {
                'status': 'completed',
                'phase': 'complete',
                'phaseLabel': f'Audit complete! {results["pages"]} pages - Tasks: {results["tasks_created"]}/{results["issues"]} ({results["duplicates_skipped"]} duplicates)',
                'completedAt': firestore.SERVER_TIMESTAMP
            })

            return jsonify({"status": "success", "results": results}), 200, headers
        except Exception as e:
            print(f"Error in main handler: {e}")
            import traceback
            traceback.print_exc()

            # Update progress: error (try to get site_id if available)
            try:
                if 'site_id' in dir():
                    update_audit_progress(site_id, {
                        'status': 'error',
                        'phase': 'error',
                        'phaseLabel': f'Error: {str(e)[:100]}',
                        'error': str(e)
                    })
            except:
                pass

            return jsonify({"error": str(e)}), 500, headers
    return jsonify({"error": "Method not allowed"}), 405, headers
