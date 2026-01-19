#!/usr/bin/env python3
"""
Update existing Voice Rules and Brand Standards in Firestore to add LLM prompts.
Run this to enable voice/tone and brand compliance checking via Claude.
"""

from google.cloud import firestore

FIRESTORE_PROJECT_ID = 'project-85d26db5-f70f-487e-b0e'

# Updated Voice Rules with LLM prompts
VOICE_RULES_UPDATE = {
    'Warm & Welcoming': {
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
    'Authentic Local Voice': {
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


def update_firestore():
    """Update existing Firestore rules with LLM prompts."""
    print(f"Connecting to Firestore project: {FIRESTORE_PROJECT_ID}")
    db = firestore.Client(project=FIRESTORE_PROJECT_ID)

    # Update Voice Rules
    print("\n--- Updating Voice Rules ---")
    voice_collection = db.collection('voiceRules')
    voice_docs = voice_collection.stream()

    for doc in voice_docs:
        doc_data = doc.to_dict()
        name = doc_data.get('name', '')

        if name in VOICE_RULES_UPDATE:
            update_data = VOICE_RULES_UPDATE[name]
            print(f"  Updating '{name}' with prompt and checkType...")
            doc.reference.update(update_data)
            print(f"    ✓ Added checkType: {update_data['checkType']}")
        else:
            print(f"  Skipping '{name}' - no update defined")

    # Update Brand Standards
    print("\n--- Updating Brand Standards ---")
    brand_collection = db.collection('brandStandards')
    brand_docs = brand_collection.stream()

    for doc in brand_docs:
        doc_data = doc.to_dict()
        name = doc_data.get('name', '')

        if name in BRAND_STANDARDS_UPDATE:
            update_data = BRAND_STANDARDS_UPDATE[name]
            print(f"  Updating '{name}' with prompt and checkType...")
            doc.reference.update(update_data)
            print(f"    ✓ Added checkType: {update_data['checkType']}")
        else:
            print(f"  Skipping '{name}' - no update defined")

    print("\n✅ Update complete!")
    print("\nVoice/Tone and Brand Standards are now LLM-powered!")
    print("The next audit run will evaluate pages against these rules using Claude.")


if __name__ == '__main__':
    update_firestore()
