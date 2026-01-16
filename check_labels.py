#!/usr/bin/env python3
"""Check the available labels for the Severity column"""

import os
import json
import requests

MONDAY_API_TOKEN = os.environ.get('MONDAY_API_TOKEN', '')
MONDAY_BOARD_ID = '18395774522'
API_URL = "https://api.monday.com/v2"

def get_headers():
    return {
        "Authorization": MONDAY_API_TOKEN,
        "Content-Type": "application/json",
        "API-Version": "2024-01"
    }

def fetch_column_settings():
    """Fetch column settings including status labels"""
    query = '''query ($board_id: [ID!]!) {
        boards(ids: $board_id) {
            columns {
                id
                title
                type
                settings_str
            }
        }
    }'''
    variables = {"board_id": [MONDAY_BOARD_ID]}

    resp = requests.post(API_URL, json={"query": query, "variables": variables},
                        headers=get_headers(), timeout=30)
    data = resp.json()

    if 'data' in data and data['data']['boards']:
        for col in data['data']['boards'][0]['columns']:
            if 'severity' in col['title'].lower():
                print(f"\n=== {col['title']} ===")
                print(f"ID: {col['id']}")
                print(f"Type: {col['type']}")
                settings = json.loads(col['settings_str']) if col['settings_str'] else {}
                print(f"Settings: {json.dumps(settings, indent=2)}")
                if 'labels' in settings:
                    print("\nAvailable Labels:")
                    for label_id, label_name in settings['labels'].items():
                        print(f"  {label_id}: {label_name}")

if __name__ == "__main__":
    if not MONDAY_API_TOKEN:
        print("Set MONDAY_API_TOKEN environment variable")
    else:
        fetch_column_settings()
