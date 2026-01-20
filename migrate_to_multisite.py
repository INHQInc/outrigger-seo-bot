#!/usr/bin/env python3
"""
Migration script to move existing flat Firestore collections to site-specific subcollections.

This script:
1. Creates a site config document for the existing Outrigger data
2. Copies all documents from root collections to site-specific subcollections
3. Preserves document IDs and all data

Run this script once before deploying the multi-site update.

Usage:
    python migrate_to_multisite.py
"""

import os
from google.cloud import firestore

# Configuration
FIRESTORE_PROJECT_ID = os.environ.get('FIRESTORE_PROJECT_ID', 'project-85d26db5-f70f-487e-b0e')
DEFAULT_SITE_ID = 'outrigger'

# Collections to migrate
COLLECTIONS_TO_MIGRATE = ['seoRules', 'voiceRules', 'brandStandards', 'auditLogs']


def get_firestore_client():
    """Initialize Firestore client"""
    try:
        return firestore.Client(project=FIRESTORE_PROJECT_ID)
    except Exception as e:
        print(f"Error connecting to Firestore: {e}")
        print("Make sure you have GOOGLE_APPLICATION_CREDENTIALS set or are running in GCP")
        return None


def create_site_config(db, site_id):
    """Create the site configuration document"""
    site_config = {
        'name': 'Outrigger Hotels & Resorts',
        'domain': 'outrigger.com',
        'sitemapUrl': 'https://www.outrigger.com/sitemap.xml',
        'mondayBoardId': '18395774522',
        'daysToCheck': 7,
        'maxPages': 10,
        'enableLLM': True,
        'enabled': True,
        'createdAt': firestore.SERVER_TIMESTAMP,
        'updatedAt': firestore.SERVER_TIMESTAMP,
    }

    # Create the config document under sites/{siteId}/config/settings
    config_ref = db.collection('sites').document(site_id).collection('config').document('settings')
    config_ref.set(site_config)
    print(f"Created site config for '{site_id}'")
    print(f"  - Name: {site_config['name']}")
    print(f"  - Domain: {site_config['domain']}")
    print(f"  - Sitemap: {site_config['sitemapUrl']}")
    print(f"  - Monday Board: {site_config['mondayBoardId']}")
    return True


def migrate_collection(db, collection_name, site_id):
    """Copy documents from root collection to site subcollection"""
    source_ref = db.collection(collection_name)
    target_ref = db.collection('sites').document(site_id).collection(collection_name)

    # Get all documents from source
    docs = list(source_ref.stream())

    if not docs:
        print(f"  No documents found in '{collection_name}' - skipping")
        return 0

    count = 0
    batch = db.batch()
    batch_size = 0
    max_batch_size = 400  # Firestore batch limit is 500

    for doc in docs:
        data = doc.to_dict()
        # Preserve the original document ID
        target_doc_ref = target_ref.document(doc.id)
        batch.set(target_doc_ref, data)
        batch_size += 1
        count += 1

        # Commit batch if approaching limit
        if batch_size >= max_batch_size:
            batch.commit()
            batch = db.batch()
            batch_size = 0

    # Commit remaining documents
    if batch_size > 0:
        batch.commit()

    print(f"  Migrated {count} documents from '{collection_name}' to 'sites/{site_id}/{collection_name}'")
    return count


def migrate_settings(db, site_id):
    """Migrate settings/config to site config (merge with existing)"""
    # Check if there's an existing settings document
    settings_ref = db.collection('settings').document('config')
    settings_doc = settings_ref.get()

    if settings_doc.exists:
        settings_data = settings_doc.to_dict()

        # Merge relevant settings into site config
        config_ref = db.collection('sites').document(site_id).collection('config').document('settings')

        update_data = {}
        if settings_data.get('sitemapUrl'):
            update_data['sitemapUrl'] = settings_data['sitemapUrl']
        if settings_data.get('daysToCheck'):
            update_data['daysToCheck'] = settings_data['daysToCheck']
        if settings_data.get('maxPages'):
            update_data['maxPages'] = settings_data['maxPages']
        if settings_data.get('aiModel'):
            update_data['aiModel'] = settings_data['aiModel']
        if settings_data.get('rulesPerBatch'):
            update_data['rulesPerBatch'] = settings_data['rulesPerBatch']
        if 'enableLLM' in settings_data:
            update_data['enableLLM'] = settings_data['enableLLM']

        if update_data:
            update_data['updatedAt'] = firestore.SERVER_TIMESTAMP
            config_ref.update(update_data)
            print(f"  Merged {len(update_data)} settings from 'settings/config' into site config")
        return True
    else:
        print("  No existing settings/config document found - using defaults")
        return False


def verify_migration(db, site_id):
    """Verify the migration was successful"""
    print("\nVerification:")

    # Check site config
    config_ref = db.collection('sites').document(site_id).collection('config').document('settings')
    config_doc = config_ref.get()
    if config_doc.exists:
        print(f"  Site config exists")
    else:
        print(f"  ERROR: Site config not found!")
        return False

    # Check each collection
    for collection_name in COLLECTIONS_TO_MIGRATE:
        source_count = len(list(db.collection(collection_name).stream()))
        target_ref = db.collection('sites').document(site_id).collection(collection_name)
        target_count = len(list(target_ref.stream()))

        status = "OK" if source_count == target_count else "MISMATCH"
        print(f"  {collection_name}: {source_count} source -> {target_count} migrated [{status}]")

        if source_count != target_count:
            return False

    return True


def main():
    print("=" * 60)
    print("Outrigger SEO Bot - Multi-Site Migration Script")
    print("=" * 60)
    print(f"\nFirestore Project: {FIRESTORE_PROJECT_ID}")
    print(f"Target Site ID: {DEFAULT_SITE_ID}")
    print()

    # Connect to Firestore
    db = get_firestore_client()
    if not db:
        return 1

    print("Connected to Firestore\n")

    # Step 1: Create site config
    print("Step 1: Creating site configuration...")
    create_site_config(db, DEFAULT_SITE_ID)
    print()

    # Step 2: Migrate collections
    print("Step 2: Migrating collections...")
    total_migrated = 0
    for collection_name in COLLECTIONS_TO_MIGRATE:
        count = migrate_collection(db, collection_name, DEFAULT_SITE_ID)
        total_migrated += count
    print(f"\n  Total documents migrated: {total_migrated}")
    print()

    # Step 3: Migrate settings
    print("Step 3: Migrating settings...")
    migrate_settings(db, DEFAULT_SITE_ID)
    print()

    # Step 4: Verify
    print("Step 4: Verifying migration...")
    success = verify_migration(db, DEFAULT_SITE_ID)
    print()

    if success:
        print("=" * 60)
        print("MIGRATION COMPLETE!")
        print("=" * 60)
        print(f"\nYour data is now available at: /sites/{DEFAULT_SITE_ID}/")
        print("\nNext steps:")
        print("  1. Deploy the updated main.py and admin/index.html")
        print("  2. Test the admin dashboard with the new site selector")
        print("  3. Keep old collections for 30 days as backup")
        print("  4. Delete old collections after verification period")
        return 0
    else:
        print("=" * 60)
        print("MIGRATION FAILED - Please check errors above")
        print("=" * 60)
        return 1


if __name__ == '__main__':
    exit(main())
