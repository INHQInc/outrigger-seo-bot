#!/usr/bin/env python3
"""
Seed Firestore with recommended SEO/GEO audit rules.
Run this once to pre-populate the admin dashboard with all recommended checks.
"""

from google.cloud import firestore

FIRESTORE_PROJECT_ID = 'project-85d26db5-f70f-487e-b0e'

# All the SEO/GEO rules to pre-populate
SEO_RULES = [
    # ============ TIER 1: CRITICAL ============
    {
        'name': 'Title Tag Check',
        'checkType': 'title',
        'description': 'Checks for missing or too-short title tags. Title should be 50-60 characters and include primary keywords.',
        'enabled': True,
        'severity': 'Critical',
        'tier': 1
    },
    {
        'name': 'Meta Description Check',
        'checkType': 'meta',
        'description': 'Checks for missing or too-short meta descriptions. Should be 150-160 characters with compelling copy and call-to-action.',
        'enabled': True,
        'severity': 'Critical',
        'tier': 1
    },
    {
        'name': 'H1 Tag Check',
        'checkType': 'h1',
        'description': 'Checks for missing H1 tags or multiple H1s. Each page should have exactly one H1 describing the main topic.',
        'enabled': True,
        'severity': 'Critical',
        'tier': 1
    },
    {
        'name': 'Canonical Tag Check',
        'checkType': 'canonical',
        'description': 'Checks for missing canonical URLs. Canonical tags prevent duplicate content issues and consolidate ranking signals.',
        'enabled': True,
        'severity': 'Critical',
        'tier': 1
    },

    # ============ TIER 2: HIGH PRIORITY (Schema/GEO) ============
    {
        'name': 'Schema/Structured Data Check',
        'checkType': 'schema',
        'description': 'Comprehensive schema.org checks including Hotel, LocalBusiness, Organization, FAQ, Review, Offer, Breadcrumb, and Speakable schemas. Critical for AI/LLM visibility.',
        'enabled': True,
        'severity': 'High',
        'tier': 2
    },
    {
        'name': 'Thin Content Check',
        'checkType': 'content',
        'description': 'Flags pages with less than 300 words of content. Thin pages rank poorly and provide insufficient information for AI assistants.',
        'enabled': True,
        'severity': 'High',
        'tier': 2
    },
    {
        'name': 'Geo Meta Tags Check',
        'checkType': 'geo',
        'description': 'Checks for geo.region and geo.placename meta tags. Important for location-based searches and AI travel recommendations.',
        'enabled': True,
        'severity': 'High',
        'tier': 2
    },
    {
        'name': 'Open Graph Tags Check',
        'checkType': 'og',
        'description': 'Checks for og:image, og:title, and og:description. Essential for social sharing - posts with images get 2-3x more engagement.',
        'enabled': True,
        'severity': 'High',
        'tier': 2
    },

    # ============ TIER 3: MEDIUM PRIORITY ============
    {
        'name': 'Image Alt Tags Check',
        'checkType': 'alt',
        'description': 'Checks for missing alt text on images. Required for ADA accessibility compliance and helps images appear in search results.',
        'enabled': True,
        'severity': 'Medium',
        'tier': 3
    },
    {
        'name': 'Robots Meta Tag Check',
        'checkType': 'robots',
        'description': 'Checks for presence of robots meta tag. Good practice to explicitly declare indexing instructions.',
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
