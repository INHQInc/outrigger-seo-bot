"""
Audit Orchestrator
Main entry point that coordinates all audit components
"""
import os
import time
from datetime import datetime, timedelta
from typing import List, Dict, Optional
import pytz

from sitemap_parser import SitemapParser
from seo_auditor import SEOAuditor, SEOIssue
from geo_llm_auditor import GEOLLMAuditor, GEOIssue
from monday_client import MondayTaskManager
from verification_engine import VerificationEngine, VerificationResult
from config import (
    SITEMAP_URL,
    DAYS_TO_CHECK,
    DELAY_BETWEEN_REQUESTS,
    MONDAY_API_TOKEN,
    MONDAY_BOARD_ID,
)


class AuditOrchestrator:
    """
    Coordinates the full SEO/GEO audit workflow:
    1. Parse sitemap and find recently updated pages
    2. Run SEO and GEO audits on those pages
    3. Create tasks in Monday.com for new issues
    4. Verify previously reported issues
    5. Update Monday.com board status
    """

    def __init__(self, api_token: str = None, board_id: str = None):
        self.sitemap_parser = SitemapParser(SITEMAP_URL)
        self.seo_auditor = SEOAuditor()
        self.geo_auditor = GEOLLMAuditor()
        self.verification_engine = VerificationEngine()

        # Initialize Monday.com client
        self.monday_manager = MondayTaskManager(
            api_token=api_token or MONDAY_API_TOKEN,
            board_id=board_id or MONDAY_BOARD_ID
        )

        self.audit_results = {
            "run_timestamp": None,
            "pages_checked": 0,
            "seo_issues_found": 0,
            "geo_issues_found": 0,
            "tasks_created": 0,
            "issues_verified": 0,
            "issues_fixed": 0,
            "errors": [],
        }

    def run_weekly_audit(self) -> Dict:
        """
        Run the full weekly audit workflow.
        This is the main entry point for the scheduled job.
        """
        print("=" * 60)
        print(f"Starting Weekly SEO/GEO Audit - {datetime.now().isoformat()}")
        print("=" * 60)

        self.audit_results["run_timestamp"] = datetime.now().isoformat()

        try:
            # Step 1: Initialize Monday.com connection
            print("\n[1/5] Initializing Monday.com connection...")
            if not self.monday_manager.initialize():
                raise Exception("Failed to initialize Monday.com connection")
            print("Monday.com connection established")

            # Step 2: Get recently updated URLs from sitemap
            print(f"\n[2/5] Fetching URLs updated in the last {DAYS_TO_CHECK} days...")
            urls_to_audit = self.sitemap_parser.get_recently_updated_urls(days=DAYS_TO_CHECK)

            if not urls_to_audit:
                print("No recently updated URLs found. Checking verification only.")
            else:
                print(f"Found {len(urls_to_audit)} URLs to audit")
                self.audit_results["pages_checked"] = len(urls_to_audit)

            # Step 3: Run SEO and GEO audits
            if urls_to_audit:
                print("\n[3/5] Running SEO and GEO audits...")
                all_issues = self._run_audits(urls_to_audit)
                print(f"Total issues found: {len(all_issues)}")

                # Step 4: Create Monday.com tasks for new issues
                print("\n[4/5] Creating tasks in Monday.com...")
                self._create_tasks(all_issues)
            else:
                print("\n[3/5] Skipping audits - no URLs to check")
                print("\n[4/5] Skipping task creation - no new issues")

            # Step 5: Verify previously reported issues
            print("\n[5/5] Verifying previously reported issues...")
            self._verify_existing_issues()

            print("\n" + "=" * 60)
            print("Audit Complete!")
            print("=" * 60)
            self._print_summary()

        except Exception as e:
            error_msg = f"Audit failed: {str(e)}"
            print(f"\nERROR: {error_msg}")
            self.audit_results["errors"].append(error_msg)

        return self.audit_results

    def _run_audits(self, urls: List[Dict]) -> List[Dict]:
        """Run SEO and GEO audits on all URLs"""
        all_issues = []

        for i, url_data in enumerate(urls):
            url = url_data["url"]
            print(f"\nAuditing ({i + 1}/{len(urls)}): {url}")

            try:
                # Run SEO audit
                seo_issues = self.seo_auditor.audit_page(url)
                for issue in seo_issues:
                    all_issues.append(issue.to_dict())
                    self.audit_results["seo_issues_found"] += 1

                # Run GEO audit
                geo_issues = self.geo_auditor.audit_page(url)
                for issue in geo_issues:
                    all_issues.append(issue.to_dict())
                    self.audit_results["geo_issues_found"] += 1

                print(f"  - Found {len(seo_issues)} SEO issues, {len(geo_issues)} GEO issues")

            except Exception as e:
                error_msg = f"Error auditing {url}: {str(e)}"
                print(f"  - ERROR: {error_msg}")
                self.audit_results["errors"].append(error_msg)

            # Rate limiting
            if i < len(urls) - 1:
                time.sleep(DELAY_BETWEEN_REQUESTS)

        return all_issues

    def _create_tasks(self, issues: List[Dict]) -> None:
        """Create Monday.com tasks for issues"""
        created_count = 0

        for issue in issues:
            try:
                # Skip low-severity issues optionally
                # if issue.get('severity') == 'Low':
                #     continue

                item_id = self.monday_manager.create_issue_task(issue)
                if item_id:
                    created_count += 1

            except Exception as e:
                error_msg = f"Error creating task for {issue.get('title')}: {str(e)}"
                print(f"  - ERROR: {error_msg}")
                self.audit_results["errors"].append(error_msg)

        self.audit_results["tasks_created"] = created_count
        print(f"Created {created_count} new tasks in Monday.com")

    def _verify_existing_issues(self) -> None:
        """Verify previously reported issues and update Monday.com"""
        try:
            # Get items that need verification
            items_to_verify = self.monday_manager.get_items_to_verify()
            print(f"Found {len(items_to_verify)} items to verify")

            for item in items_to_verify:
                try:
                    # Extract issue details from Monday.com item
                    issue_data = self._extract_issue_from_item(item)
                    if not issue_data:
                        continue

                    # Verify the fix
                    result = self.verification_engine.verify_issue(issue_data)
                    self.audit_results["issues_verified"] += 1

                    if result.is_fixed:
                        # Move to completed group
                        self.monday_manager.mark_issue_fixed(item["id"])
                        self.audit_results["issues_fixed"] += 1
                        print(f"  - FIXED: {issue_data.get('title', 'Unknown')}")
                    else:
                        print(f"  - NOT FIXED: {issue_data.get('title', 'Unknown')} - {result.details}")

                        # Update item with verification details
                        self._update_verification_status(item["id"], result)

                except Exception as e:
                    error_msg = f"Error verifying item {item.get('id')}: {str(e)}"
                    print(f"  - ERROR: {error_msg}")
                    self.audit_results["errors"].append(error_msg)

        except Exception as e:
            error_msg = f"Error in verification phase: {str(e)}"
            print(f"ERROR: {error_msg}")
            self.audit_results["errors"].append(error_msg)

    def _extract_issue_from_item(self, item: Dict) -> Optional[Dict]:
        """Extract issue details from a Monday.com item for verification"""
        issue_data = {
            "item_id": item["id"],
            "title": item.get("name", ""),
        }

        for col in item.get("column_values", []):
            col_id = col.get("id", "").lower()
            value = col.get("text") or col.get("value")

            if "url" in col_id or "link" in col_id:
                if isinstance(value, str) and value.startswith("http"):
                    issue_data["url"] = value
                elif col.get("text"):
                    issue_data["url"] = col["text"]

            elif "type" in col_id or "issue" in col_id:
                issue_data["issue_type"] = value

            elif "current" in col_id or "value" in col_id:
                issue_data["current_value"] = value

        # Try to extract URL from item name if not found
        if not issue_data.get("url"):
            import re
            url_match = re.search(r'https?://[^\s]+', item.get("name", ""))
            if url_match:
                issue_data["url"] = url_match.group(0)

        # Try to extract issue type from item name
        if not issue_data.get("issue_type"):
            name = item.get("name", "").lower()
            # Map common issue titles to types
            type_mapping = {
                "missing title": "missing_title",
                "title too": "title_too_short",
                "meta description": "missing_meta_description",
                "missing h1": "missing_h1",
                "multiple h1": "multiple_h1",
                "schema": "missing_schema",
                "canonical": "missing_canonical",
                "open graph": "missing_open_graph",
            }
            for keyword, issue_type in type_mapping.items():
                if keyword in name:
                    issue_data["issue_type"] = issue_type
                    break

        return issue_data if issue_data.get("url") and issue_data.get("issue_type") else None

    def _update_verification_status(self, item_id: str, result: VerificationResult) -> None:
        """Update Monday.com item with verification results"""
        columns = self.monday_manager.client.get_columns()

        update_values = {}
        for col_id, col_info in columns.items():
            col_title_lower = col_info["title"].lower()

            if "last verified" in col_title_lower or "verified date" in col_title_lower:
                update_values[col_id] = {"date": datetime.now().strftime("%Y-%m-%d")}

            elif "verification" in col_title_lower and "note" in col_title_lower:
                update_values[col_id] = result.details[:500]

        if update_values:
            self.monday_manager.client.update_item(item_id, update_values)

    def _print_summary(self) -> None:
        """Print audit summary"""
        print(f"\nAudit Summary:")
        print(f"  - Pages checked: {self.audit_results['pages_checked']}")
        print(f"  - SEO issues found: {self.audit_results['seo_issues_found']}")
        print(f"  - GEO issues found: {self.audit_results['geo_issues_found']}")
        print(f"  - Tasks created: {self.audit_results['tasks_created']}")
        print(f"  - Issues verified: {self.audit_results['issues_verified']}")
        print(f"  - Issues confirmed fixed: {self.audit_results['issues_fixed']}")

        if self.audit_results["errors"]:
            print(f"  - Errors encountered: {len(self.audit_results['errors'])}")


def run_audit(api_token: str = None, board_id: str = None) -> Dict:
    """
    Main entry point for running the audit.
    Can be called directly or from Cloud Function.
    """
    orchestrator = AuditOrchestrator(api_token, board_id)
    return orchestrator.run_weekly_audit()


def main():
    """Run audit from command line"""
    results = run_audit()
    print(f"\nResults: {results}")


if __name__ == "__main__":
    main()
