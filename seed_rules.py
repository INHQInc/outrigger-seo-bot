#!/usr/bin/env python3
"""
Seed Firestore with recommended SEO/GEO audit rules.
Run this once to pre-populate the admin dashboard with all recommended checks.
"""

from google.cloud import firestore

FIRESTORE_PROJECT_ID = 'project-85d26db5-f70f-487e-b0e'

# All the SEO/GEO rules to pre-populate
# Rules with 'prompt' field use LLM-based evaluation
# Rules with only 'checkType' use legacy hardcoded checks
SEO_RULES = [
    # ============ TIER 1: CRITICAL (LLM-POWERED) ============
    {
        'name': 'Title Tag Check',
        'checkType': 'title',
        'description': 'Checks for missing or too-short title tags. Title should be 50-60 characters and include primary keywords.',
        'prompt': '''Check if this page has a proper <title> tag. The rule FAILS if:
1. The page is missing a <title> tag entirely, OR
2. The title is empty or contains only whitespace, OR
3. The title is less than 30 characters (too short to be descriptive), OR
4. The title is generic like "Home" or "Page" without context

For a hotel/hospitality site, a good title should include the property name, location, and ideally brand.
Example of a good title: "Beachfront Resort in Waikiki | Outrigger Hotels Hawaii"''',
        'enabled': True,
        'severity': 'Critical',
        'tier': 1
    },
    {
        'name': 'Meta Description Check',
        'checkType': 'meta',
        'description': 'Checks for missing or too-short meta descriptions. Should be 150-160 characters with compelling copy and call-to-action.',
        'prompt': '''Check if this page has a proper meta description. The rule FAILS if:
1. The page is missing a <meta name="description"> tag, OR
2. The meta description content is empty, OR
3. The meta description is less than 120 characters (too short), OR
4. The meta description is over 160 characters (will be truncated in search results)

For a hotel site, meta descriptions should be compelling and include a call-to-action like "Book now" or "Learn more".
Example: "Experience paradise at our oceanfront Waikiki resort. Stunning views, world-class amenities, and authentic Hawaiian hospitality. Book direct for best rates."''',
        'enabled': True,
        'severity': 'Critical',
        'tier': 1
    },
    {
        'name': 'H1 Tag Check',
        'checkType': 'h1',
        'description': 'Checks for missing H1 tags or multiple H1s. Each page should have exactly one H1 describing the main topic.',
        'prompt': '''Check if this page has proper H1 heading structure. The rule FAILS if:
1. The page has NO <h1> tag at all, OR
2. The page has MORE than one <h1> tag (should have exactly one), OR
3. The H1 is empty or contains only whitespace

Best practice: Each page should have exactly one H1 that clearly describes the main topic of the page.
For hotel pages, H1 should typically be the property or room name.''',
        'enabled': True,
        'severity': 'Critical',
        'tier': 1
    },
    {
        'name': 'Canonical Tag Check',
        'checkType': 'canonical',
        'description': 'Checks for missing canonical URLs. Canonical tags prevent duplicate content issues and consolidate ranking signals.',
        'prompt': '''Check if this page has a canonical tag. The rule FAILS if:
1. The page is missing a <link rel="canonical"> tag, OR
2. The canonical tag exists but has no href value, OR
3. The canonical href is empty or invalid

A canonical tag tells search engines which version of a page is the "master" copy, preventing duplicate content issues.
Example: <link rel="canonical" href="https://www.outrigger.com/hotels-resorts/hawaii">''',
        'enabled': True,
        'severity': 'Critical',
        'tier': 1
    },

    # ============ TIER 2: HIGH PRIORITY (Schema/GEO) - LLM-POWERED ============
    {
        'name': 'Schema/Structured Data Check',
        'checkType': 'schema',
        'description': 'Comprehensive schema.org checks including Hotel, LocalBusiness, Organization, FAQ, Review, Offer, Breadcrumb, and Speakable schemas. Critical for AI/LLM visibility.',
        'prompt': '''Check if this page has appropriate JSON-LD structured data (schema.org markup). The rule FAILS if:
1. The page has NO <script type="application/ld+json"> tags at all, OR
2. For hotel/resort pages (URL contains /hotel, /resort, /room): Missing Hotel, LodgingBusiness, or LocalBusiness schema, OR
3. For any page: Missing Organization or WebSite schema for brand identity, OR
4. Schema exists but is missing critical properties like name, address, or description

Look for JSON-LD scripts and check their @type values. Hotels should have:
- Hotel or LodgingBusiness with address, amenities, priceRange
- AggregateRating for reviews
- Offer for pricing information

This is CRITICAL for AI/LLM visibility - ChatGPT and Google AI pull from structured data.''',
        'enabled': True,
        'severity': 'High',
        'tier': 2
    },
    {
        'name': 'Thin Content Check',
        'checkType': 'content',
        'description': 'Flags pages with less than 300 words of content. Thin pages rank poorly and provide insufficient information for AI assistants.',
        'prompt': '''Analyze the main content of this page (excluding navigation, headers, footers, and boilerplate). The rule FAILS if:
1. The page has less than approximately 300 words of actual content, OR
2. The content is mostly duplicated/boilerplate text, OR
3. The main content area appears empty or contains only images without supporting text

For hotel pages, there should be substantial descriptive content about:
- Property features and amenities
- Room descriptions
- Location highlights
- Guest experiences

Thin content hurts both SEO rankings and AI assistant recommendations.''',
        'enabled': True,
        'severity': 'High',
        'tier': 2
    },
    {
        'name': 'Geo Meta Tags Check',
        'checkType': 'geo',
        'description': 'Checks for geo.region and geo.placename meta tags. Important for location-based searches and AI travel recommendations.',
        'prompt': '''Check if this page has geographic meta tags for location-based SEO. The rule FAILS if:
1. The page is missing BOTH geo.region and geo.placename meta tags, OR
2. For a location-specific page (hotels, destinations): Missing geo coordinates

Look for these tags:
- <meta name="geo.region" content="US-HI">
- <meta name="geo.placename" content="Honolulu">
- <meta name="geo.position" content="21.2769;-157.8268">

These help AI travel assistants understand location context for "hotels near me" queries.''',
        'enabled': True,
        'severity': 'High',
        'tier': 2
    },
    {
        'name': 'Open Graph Tags Check',
        'checkType': 'og',
        'description': 'Checks for og:image, og:title, and og:description. Essential for social sharing - posts with images get 2-3x more engagement.',
        'prompt': '''Check if this page has proper Open Graph tags for social sharing. The rule FAILS if:
1. Missing og:image tag (critical - posts without images get much less engagement), OR
2. Missing og:title tag, OR
3. Missing og:description tag, OR
4. og:image exists but the URL appears invalid or points to a placeholder

Look for these meta tags with property attribute:
- <meta property="og:image" content="...">
- <meta property="og:title" content="...">
- <meta property="og:description" content="...">

For hotels, og:image should show the property, beach, or destination - not a generic logo.''',
        'enabled': True,
        'severity': 'High',
        'tier': 2
    },

    # ============ TIER 3: MEDIUM PRIORITY - LLM-POWERED ============
    {
        'name': 'Image Alt Tags Check',
        'checkType': 'alt',
        'description': 'Checks for missing alt text on images. Required for ADA accessibility compliance and helps images appear in search results.',
        'prompt': '''Check if images on this page have proper alt text for accessibility. The rule FAILS if:
1. Multiple <img> tags are missing the alt attribute entirely, OR
2. Images have empty alt="" attributes (unless they are truly decorative), OR
3. Alt text is generic like "image" or "photo" instead of descriptive

For accessibility (ADA compliance) and SEO, all meaningful images should have descriptive alt text.
Example: alt="Guests relaxing on Waikiki Beach at sunset with Diamond Head in background"

Note: A few missing alt tags on decorative images is acceptable. Flag this as failed only if there's a significant pattern of missing alt text on content images.''',
        'enabled': True,
        'severity': 'Medium',
        'tier': 3
    },
    {
        'name': 'Robots Meta Tag Check',
        'checkType': 'robots',
        'description': 'Checks for presence of robots meta tag. Good practice to explicitly declare indexing instructions.',
        'prompt': '''Check if this page has a robots meta tag. The rule FAILS if:
1. The page is missing a <meta name="robots"> tag

While not strictly required (defaults to index,follow), it's good practice to explicitly declare indexing instructions.
Example: <meta name="robots" content="index, follow">

This is a LOW priority check - only flag if completely missing.''',
        'enabled': False,  # Optional - disabled by default
        'severity': 'Low',
        'tier': 3
    },
]

# Voice & Tone guidelines
VOICE_RULES = [
    {
        'name': 'Warm & Welcoming',
        'category': 'tone',
        'description': 'Content should convey genuine Hawaiian hospitality - warm, welcoming, and relaxed. Avoid corporate jargon.',
        'enabled': True
    },
    {
        'name': 'Adventure & Discovery',
        'category': 'tone',
        'description': 'Inspire a sense of adventure and discovery. Highlight unique experiences and hidden gems.',
        'enabled': True
    },
    {
        'name': 'Authentic Local Voice',
        'category': 'language',
        'description': 'Use authentic Hawaiian and local terms appropriately (aloha, mahalo, ohana). Include cultural context.',
        'enabled': True
    },
    {
        'name': 'Sensory Language',
        'category': 'language',
        'description': 'Use vivid sensory language - describe sounds of waves, smell of plumeria, feel of warm sand.',
        'enabled': True
    },
]

# Brand Standards
BRAND_STANDARDS = [
    {
        'name': 'Brand Name Usage',
        'standardType': 'terminology',
        'description': 'Always use "Outrigger" not "OUTRIGGER" or "outrigger". Full name is "Outrigger Hotels & Resorts".',
        'enabled': True
    },
    {
        'name': 'Property Names',
        'standardType': 'terminology',
        'description': 'Use official property names exactly as registered. Include location identifiers (e.g., "Outrigger Reef Waikiki Beach Resort").',
        'enabled': True
    },
    {
        'name': 'Color Palette',
        'standardType': 'visual',
        'description': 'Primary: Teal (#006272), Gold (#c4a35a), Sunset Orange (#e07c3e). Use consistently across all materials.',
        'enabled': True
    },
    {
        'name': 'Image Standards',
        'standardType': 'visual',
        'description': 'Images should be high-resolution, authentic (not stock), and showcase real guest experiences and destinations.',
        'enabled': True
    },
]


def seed_firestore():
    """Seed Firestore with all recommended rules."""
    print(f"Connecting to Firestore project: {FIRESTORE_PROJECT_ID}")
    db = firestore.Client(project=FIRESTORE_PROJECT_ID)

    # Seed SEO Rules
    print("\n--- Seeding SEO Rules ---")
    seo_collection = db.collection('seoRules')
    for rule in SEO_RULES:
        # Check if rule with this checkType already exists
        existing = seo_collection.where('checkType', '==', rule['checkType']).limit(1).get()
        if len(list(existing)) > 0:
            print(f"  Skipping '{rule['name']}' - already exists")
            continue

        doc_ref = seo_collection.add(rule)
        print(f"  Added: {rule['name']} (checkType: {rule['checkType']})")

    # Seed Voice Rules
    print("\n--- Seeding Voice Rules ---")
    voice_collection = db.collection('voiceRules')
    for rule in VOICE_RULES:
        # Check if rule with this name already exists
        existing = voice_collection.where('name', '==', rule['name']).limit(1).get()
        if len(list(existing)) > 0:
            print(f"  Skipping '{rule['name']}' - already exists")
            continue

        doc_ref = voice_collection.add(rule)
        print(f"  Added: {rule['name']}")

    # Seed Brand Standards
    print("\n--- Seeding Brand Standards ---")
    brand_collection = db.collection('brandStandards')
    for standard in BRAND_STANDARDS:
        # Check if standard with this name already exists
        existing = brand_collection.where('name', '==', standard['name']).limit(1).get()
        if len(list(existing)) > 0:
            print(f"  Skipping '{standard['name']}' - already exists")
            continue

        doc_ref = brand_collection.add(standard)
        print(f"  Added: {standard['name']}")

    print("\n✅ Seeding complete!")
    print("\nView rules at: https://storage.googleapis.com/outrigger-audit-admin/index.html")


if __name__ == '__main__':
    seed_firestore()
