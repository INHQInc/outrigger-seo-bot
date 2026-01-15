"""
Configuration settings for Outrigger SEO/GEO Audit
"""
import os
from datetime import timedelta

# Target website
SITE_URL = "https://www.outrigger.com"
SITEMAP_URL = f"{SITE_URL}/sitemap.xml"

# Monday.com settings
MONDAY_API_URL = "https://api.monday.com/v2"
MONDAY_API_TOKEN = os.environ.get("MONDAY_API_TOKEN")
MONDAY_BOARD_ID = "18395774522"

# Monday.com group IDs (will be populated on first run)
MONDAY_GROUPS = {
    "new_issues": "new_group",  # For newly discovered issues
    "in_progress": "group_title",  # Being worked on
    "completed": "completed",  # Fixed and verified
    "wont_fix": "wont_fix",  # Acknowledged but won't fix
}

# Audit settings
DAYS_TO_CHECK = 7  # Check pages updated in last 7 days
AUDIT_DAY = "thursday"  # Run audit every Thursday

# SEO Issue Severity Levels
SEVERITY = {
    "critical": "Critical",
    "high": "High",
    "medium": "Medium",
    "low": "Low",
}

# SEO Issue Categories
CATEGORIES = {
    "meta": "Meta Tags",
    "content": "Content",
    "technical": "Technical SEO",
    "structure": "Site Structure",
    "performance": "Performance",
    "geo_llm": "GEO/LLM Visibility",
    "schema": "Structured Data",
}

# GEO/LLM specific checks
GEO_LLM_CHECKS = [
    "schema_markup",
    "entity_clarity",
    "faq_content",
    "how_to_content",
    "local_business_schema",
    "breadcrumb_schema",
    "content_freshness",
    "topic_authority",
    "natural_language_queries",
]

# Request settings
REQUEST_TIMEOUT = 30
REQUEST_HEADERS = {
    "User-Agent": "OutriggerSEOBot/1.0 (SEO Audit Tool)",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
}

# Rate limiting
REQUESTS_PER_SECOND = 2
DELAY_BETWEEN_REQUESTS = 1 / REQUESTS_PER_SECOND
