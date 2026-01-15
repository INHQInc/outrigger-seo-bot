"""
Monday.com API Client Module
Handles all interactions with Monday.com board
"""
import requests
import json
from typing import List, Dict, Optional, Any
from datetime import datetime

from config import (
    MONDAY_API_URL,
    MONDAY_API_TOKEN,
    MONDAY_BOARD_ID,
    MONDAY_GROUPS,
)


class MondayClient:
    """Client for Monday.com GraphQL API"""

    def __init__(self, api_token: str = None, board_id: str = None):
        self.api_token = api_token or MONDAY_API_TOKEN
        self.board_id = board_id or MONDAY_BOARD_ID
        self.headers = {
            "Authorization": self.api_token,
            "Content-Type": "application/json",
            "API-Version": "2024-01",
        }
        self._columns_cache = None
        self._groups_cache = None

    def _execute_query(self, query: str, variables: Dict = None) -> Dict:
        """Execute a GraphQL query against Monday.com API"""
        payload = {"query": query}
        if variables:
            payload["variables"] = variables

        try:
            response = requests.post(
                MONDAY_API_URL,
                headers=self.headers,
                json=payload,
                timeout=30
            )
            response.raise_for_status()
            result = response.json()

            if "errors" in result:
                print(f"GraphQL errors: {result['errors']}")
                return None

            return result.get("data")
        except requests.RequestException as e:
            print(f"Monday.com API error: {e}")
            return None

    def get_board_info(self) -> Optional[Dict]:
        """Get board information including columns and groups"""
        query = """
        query ($boardId: [ID!]) {
            boards(ids: $boardId) {
                id
                name
                description
                columns {
                    id
                    title
                    type
                    settings_str
                }
                groups {
                    id
                    title
                    color
                }
            }
        }
        """
        variables = {"boardId": [self.board_id]}
        result = self._execute_query(query, variables)

        if result and result.get("boards"):
            board = result["boards"][0]
            self._columns_cache = {col["id"]: col for col in board.get("columns", [])}
            self._groups_cache = {grp["id"]: grp for grp in board.get("groups", [])}
            return board
        return None

    def get_columns(self) -> Dict:
        """Get board columns (cached)"""
        if not self._columns_cache:
            self.get_board_info()
        return self._columns_cache or {}

    def get_groups(self) -> Dict:
        """Get board groups (cached)"""
        if not self._groups_cache:
            self.get_board_info()
        return self._groups_cache or {}

    def find_group_id(self, group_name: str) -> Optional[str]:
        """Find group ID by name (case-insensitive)"""
        groups = self.get_groups()
        group_name_lower = group_name.lower()

        for group_id, group in groups.items():
            if group["title"].lower() == group_name_lower:
                return group_id

        return None

    def create_group(self, group_name: str) -> Optional[str]:
        """Create a new group on the board"""
        query = """
        mutation ($boardId: ID!, $groupName: String!) {
            create_group(board_id: $boardId, group_name: $groupName) {
                id
            }
        }
        """
        variables = {
            "boardId": self.board_id,
            "groupName": group_name
        }
        result = self._execute_query(query, variables)

        if result and result.get("create_group"):
            # Invalidate cache
            self._groups_cache = None
            return result["create_group"]["id"]
        return None

    def ensure_groups_exist(self) -> Dict[str, str]:
        """Ensure all required groups exist, create if missing"""
        required_groups = {
            "New Issues": "new_issues",
            "In Progress": "in_progress",
            "Completed": "completed",
            "Won't Fix": "wont_fix",
        }

        group_ids = {}
        for group_name, key in required_groups.items():
            group_id = self.find_group_id(group_name)
            if not group_id:
                print(f"Creating group: {group_name}")
                group_id = self.create_group(group_name)
            group_ids[key] = group_id

        return group_ids

    def get_items(self, group_id: str = None, limit: int = 500) -> List[Dict]:
        """Get items from the board, optionally filtered by group"""
        query = """
        query ($boardId: [ID!], $limit: Int!) {
            boards(ids: $boardId) {
                items_page(limit: $limit) {
                    items {
                        id
                        name
                        group {
                            id
                            title
                        }
                        column_values {
                            id
                            text
                            value
                        }
                    }
                }
            }
        }
        """
        variables = {
            "boardId": [self.board_id],
            "limit": limit
        }
        result = self._execute_query(query, variables)

        if result and result.get("boards"):
            items = result["boards"][0].get("items_page", {}).get("items", [])
            if group_id:
                items = [item for item in items if item.get("group", {}).get("id") == group_id]
            return items
        return []

    def create_item(
        self,
        name: str,
        group_id: str,
        column_values: Dict[str, Any] = None
    ) -> Optional[str]:
        """Create a new item on the board"""
        query = """
        mutation ($boardId: ID!, $groupId: String!, $itemName: String!, $columnValues: JSON) {
            create_item(
                board_id: $boardId,
                group_id: $groupId,
                item_name: $itemName,
                column_values: $columnValues
            ) {
                id
            }
        }
        """
        variables = {
            "boardId": self.board_id,
            "groupId": group_id,
            "itemName": name,
            "columnValues": json.dumps(column_values) if column_values else None
        }
        result = self._execute_query(query, variables)

        if result and result.get("create_item"):
            return result["create_item"]["id"]
        return None

    def update_item(self, item_id: str, column_values: Dict[str, Any]) -> bool:
        """Update an item's column values"""
        query = """
        mutation ($boardId: ID!, $itemId: ID!, $columnValues: JSON!) {
            change_multiple_column_values(
                board_id: $boardId,
                item_id: $itemId,
                column_values: $columnValues
            ) {
                id
            }
        }
        """
        variables = {
            "boardId": self.board_id,
            "itemId": item_id,
            "columnValues": json.dumps(column_values)
        }
        result = self._execute_query(query, variables)
        return result is not None

    def move_item_to_group(self, item_id: str, group_id: str) -> bool:
        """Move an item to a different group"""
        query = """
        mutation ($itemId: ID!, $groupId: String!) {
            move_item_to_group(item_id: $itemId, group_id: $groupId) {
                id
            }
        }
        """
        variables = {
            "itemId": item_id,
            "groupId": group_id
        }
        result = self._execute_query(query, variables)
        return result is not None

    def find_item_by_url_and_issue(self, url: str, issue_type: str) -> Optional[Dict]:
        """Find an existing item by URL and issue type"""
        items = self.get_items()

        for item in items:
            item_url = None
            item_issue_type = None

            for col in item.get("column_values", []):
                if col["id"] == "text" or col["id"] == "url":  # Adjust based on your column IDs
                    item_url = col.get("text")
                if col["id"] == "text0" or col["id"] == "issue_type":  # Adjust based on your column IDs
                    item_issue_type = col.get("text")

            # Also check item name for URL
            if url in item.get("name", "") and issue_type in item.get("name", ""):
                return item

        return None

    def delete_item(self, item_id: str) -> bool:
        """Delete an item from the board"""
        query = """
        mutation ($itemId: ID!) {
            delete_item(item_id: $itemId) {
                id
            }
        }
        """
        variables = {"itemId": item_id}
        result = self._execute_query(query, variables)
        return result is not None


class MondayTaskManager:
    """High-level manager for SEO audit tasks on Monday.com"""

    def __init__(self, api_token: str = None, board_id: str = None):
        self.client = MondayClient(api_token, board_id)
        self.group_ids = {}

    def initialize(self) -> bool:
        """Initialize the task manager and ensure board is ready"""
        board_info = self.client.get_board_info()
        if not board_info:
            print("Failed to get board info")
            return False

        print(f"Connected to board: {board_info['name']}")

        # Ensure required groups exist
        self.group_ids = self.client.ensure_groups_exist()
        print(f"Groups configured: {self.group_ids}")

        return True

    def create_issue_task(self, issue: Dict) -> Optional[str]:
        """Create a Monday.com task from an SEO/GEO issue"""
        # Build task name
        task_name = f"[{issue['severity']}] {issue['title']} - {issue['url'][:50]}"

        # Build column values (adjust IDs based on your board's columns)
        column_values = {}

        # Get board columns to map properly
        columns = self.client.get_columns()

        for col_id, col_info in columns.items():
            col_title_lower = col_info["title"].lower()

            # Map issue fields to columns
            if "url" in col_title_lower or "link" in col_title_lower:
                if col_info["type"] == "link":
                    column_values[col_id] = {"url": issue["url"], "text": issue["url"]}
                else:
                    column_values[col_id] = issue["url"]

            elif "severity" in col_title_lower or "priority" in col_title_lower:
                column_values[col_id] = {"label": issue["severity"]}

            elif "category" in col_title_lower or "type" in col_title_lower:
                column_values[col_id] = issue.get("category", "")

            elif "description" in col_title_lower:
                column_values[col_id] = issue.get("description", "")[:2000]

            elif "recommendation" in col_title_lower or "action" in col_title_lower:
                column_values[col_id] = issue.get("recommendation", "")[:2000]

            elif "status" in col_title_lower:
                column_values[col_id] = {"label": "New"}

            elif "date" in col_title_lower or "found" in col_title_lower:
                column_values[col_id] = {"date": datetime.now().strftime("%Y-%m-%d")}

        # Create the item
        group_id = self.group_ids.get("new_issues")
        if not group_id:
            print("No 'New Issues' group found")
            return None

        item_id = self.client.create_item(
            name=task_name,
            group_id=group_id,
            column_values=column_values if column_values else None
        )

        if item_id:
            print(f"Created task: {task_name}")
        else:
            print(f"Failed to create task: {task_name}")

        return item_id

    def create_issues_batch(self, issues: List[Dict]) -> List[str]:
        """Create multiple issue tasks"""
        created_ids = []

        for issue in issues:
            # Check if issue already exists
            existing = self.client.find_item_by_url_and_issue(
                issue["url"],
                issue["issue_type"]
            )

            if existing:
                print(f"Issue already exists: {issue['title']} for {issue['url']}")
                continue

            item_id = self.create_issue_task(issue)
            if item_id:
                created_ids.append(item_id)

        return created_ids

    def mark_issue_fixed(self, item_id: str) -> bool:
        """Move an issue to the completed group"""
        completed_group = self.group_ids.get("completed")
        if not completed_group:
            print("No 'Completed' group found")
            return False

        return self.client.move_item_to_group(item_id, completed_group)

    def get_in_progress_items(self) -> List[Dict]:
        """Get all items currently being worked on"""
        in_progress_group = self.group_ids.get("in_progress")
        if not in_progress_group:
            return []
        return self.client.get_items(group_id=in_progress_group)

    def get_items_to_verify(self) -> List[Dict]:
        """Get items that have been marked as done but need verification"""
        # This would typically look for items with a specific status
        # Adjust based on your workflow
        items = self.client.get_items()
        to_verify = []

        for item in items:
            for col in item.get("column_values", []):
                if col["id"] == "status":  # Adjust column ID
                    status_text = col.get("text", "").lower()
                    if status_text in ["ready for review", "done", "fixed"]:
                        to_verify.append(item)
                        break

        return to_verify


def main():
    """Test the Monday.com client"""
    manager = MondayTaskManager()

    if not manager.initialize():
        print("Failed to initialize")
        return

    # Test creating an issue
    test_issue = {
        "url": "https://www.outrigger.com/test",
        "issue_type": "missing_meta_description",
        "category": "Meta Tags",
        "severity": "High",
        "title": "Missing Meta Description",
        "description": "Test issue - page is missing a meta description",
        "recommendation": "Add a compelling meta description",
    }

    # item_id = manager.create_issue_task(test_issue)
    # print(f"Created item: {item_id}")


if __name__ == "__main__":
    main()
