#!/usr/bin/env python3
"""
Test script to debug Monday.com API field population
Run with: python test_monday.py
"""

import os
import json
import requests

# Configuration
MONDAY_API_TOKEN = os.environ.get('MONDAY_API_TOKEN', '')
MONDAY_BOARD_ID = '18395774522'
API_URL = "https://api.monday.com/v2"

def get_headers():
    return {
        "Authorization": MONDAY_API_TOKEN,
        "Content-Type": "application/json",
        "API-Version": "2024-01"
    }

def fetch_columns():
    """Fetch and display all columns from the board"""
    query = '''query ($board_id: [ID!]!) {
        boards(ids: $board_id) {
            columns { id title type }
        }
    }'''
    variables = {"board_id": [MONDAY_BOARD_ID]}

    resp = requests.post(API_URL, json={"query": query, "variables": variables},
                        headers=get_headers(), timeout=30)
    data = resp.json()

    print("=" * 60)
    print("BOARD COLUMNS")
    print("=" * 60)

    columns = {}
    if 'data' in data and data['data']['boards']:
        for col in data['data']['boards'][0]['columns']:
            print(f"  Title: {col['title']:20} | ID: {col['id']:15} | Type: {col['type']}")
            col_key = col['title'].lower().replace(' ', '_')
            columns[col_key] = {'id': col['id'], 'type': col['type'], 'title': col['title']}
    else:
        print(f"Error: {data}")

    print()
    return columns

def create_test_item(columns):
    """Create a test item with all fields populated"""

    print("=" * 60)
    print("CREATING TEST ITEM")
    print("=" * 60)

    # Build column values based on what we found
    column_values = {}

    # Find each column and set appropriate test value
    for col_key, col_info in columns.items():
        col_id = col_info['id']
        col_type = col_info['type']
        col_title = col_info['title']

        # Skip the name/task column
        if col_type == 'name':
            continue

        print(f"\nProcessing: {col_title} (id={col_id}, type={col_type})")

        if 'url' in col_key.lower() or col_type == 'link':
            # Link/URL column
            value = {"url": "https://www.outrigger.com/test-page", "text": "Test Page URL"}
            column_values[col_id] = value
            print(f"  -> Setting as link: {value}")

        elif 'description' in col_key.lower() or col_type == 'long_text':
            # Long text column
            value = {"text": "This is a test description for debugging purposes."}
            column_values[col_id] = value
            print(f"  -> Setting as long_text: {value}")

        elif 'type' in col_key.lower() and col_type == 'text':
            # Text column for issue type
            value = "Test Issue Type"
            column_values[col_id] = value
            print(f"  -> Setting as text: {value}")

        elif 'date' in col_key.lower() or col_type == 'date':
            # Date column
            value = {"date": "2026-01-16"}
            column_values[col_id] = value
            print(f"  -> Setting as date: {value}")

        elif col_type == 'status' or col_type == 'color':
            # Status column
            value = {"label": "Open"}
            column_values[col_id] = value
            print(f"  -> Setting as status: {value}")

        elif col_type == 'text':
            # Generic text
            value = f"Test value for {col_title}"
            column_values[col_id] = value
            print(f"  -> Setting as text: {value}")
        else:
            print(f"  -> Skipping (unknown type)")

    print("\n" + "-" * 60)
    print("COLUMN VALUES TO SEND:")
    print(json.dumps(column_values, indent=2))
    print("-" * 60)

    # Create the item
    query = '''mutation ($board_id: ID!, $item_name: String!, $column_values: JSON!) {
        create_item (board_id: $board_id, item_name: $item_name, column_values: $column_values) {
            id
            column_values {
                id
                text
                value
            }
        }
    }'''

    variables = {
        "board_id": MONDAY_BOARD_ID,
        "item_name": "TEST ITEM - Delete Me",
        "column_values": json.dumps(column_values)
    }

    print("\nSending request to Monday.com...")
    resp = requests.post(API_URL, json={"query": query, "variables": variables},
                        headers=get_headers(), timeout=30)
    data = resp.json()

    print("\n" + "=" * 60)
    print("MONDAY.COM RESPONSE")
    print("=" * 60)
    print(json.dumps(data, indent=2))

    if 'data' in data and data['data'].get('create_item'):
        print("\n✅ SUCCESS! Item created with ID:", data['data']['create_item']['id'])
        print("\nColumn values after creation:")
        for cv in data['data']['create_item'].get('column_values', []):
            print(f"  {cv['id']}: {cv['text']}")
    elif 'errors' in data:
        print("\n❌ ERROR!")
        for err in data['errors']:
            print(f"  - {err.get('message', err)}")

    return data

def main():
    if not MONDAY_API_TOKEN:
        print("ERROR: MONDAY_API_TOKEN environment variable not set!")
        print("Run: export MONDAY_API_TOKEN='your-token-here'")
        return

    print("\n🔍 Testing Monday.com API Integration\n")

    # Step 1: Fetch columns
    columns = fetch_columns()

    if not columns:
        print("Failed to fetch columns!")
        return

    # Step 2: Create test item
    create_test_item(columns)

    print("\n" + "=" * 60)
    print("TEST COMPLETE")
    print("=" * 60)
    print("\nCheck your Monday.com board for 'TEST ITEM - Delete Me'")
    print("If fields are populated, the API is working correctly.")
    print("Delete the test item when done.")

if __name__ == "__main__":
    main()
