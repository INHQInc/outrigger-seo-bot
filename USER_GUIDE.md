# Outrigger SEO/GEO Audit System - User Guide

A comprehensive guide for using the SEO/GEO audit dashboard to monitor and improve your website's search engine optimization and AI readiness.

---

## Table of Contents

1. [Getting Started](#getting-started)
2. [Dashboard Overview](#dashboard-overview)
3. [Running Audits](#running-audits)
4. [Managing Rules](#managing-rules)
5. [Understanding Results](#understanding-results)
6. [Monday.com Integration](#mondaycom-integration)
7. [Tips & Best Practices](#tips--best-practices)
8. [Troubleshooting](#troubleshooting)

---

## Getting Started

### Accessing the Dashboard

1. Open your browser and navigate to:
   ```
   https://storage.googleapis.com/outrigger-audit-admin/index.html
   ```

2. Log in with your Google account (must be authorized)

3. Select your site from the dropdown in the header

### First-Time Setup

If this is a new site:

1. Click **"+ Add Site"** in the site dropdown
2. Enter site details:
   - **Site Name**: Display name (e.g., "Outrigger Hotels")
   - **Site ID**: Unique identifier, lowercase, no spaces (e.g., "outrigger")
   - **Sitemap URL**: Full URL to your XML sitemap
   - **Monday.com Board ID**: Your Monday.com board for task tracking
3. Click **Save**
4. Go to **Settings** tab and click **"Reset Rules"** to load default rules

---

## Dashboard Overview

### Navigation Tabs

| Tab | Purpose |
|-----|---------|
| **SEO/GEO Rules** | Manage SEO audit rules (title, meta, schema, etc.) |
| **Voice & Tone** | Manage voice/tone rules for brand consistency |
| **Brand Standards** | Manage brand guideline rules |
| **Audit Logs** | View history of past audits |
| **Settings** | Site configuration and danger zone actions |

### Site Selector

The dropdown in the header lets you switch between sites. Each site has its own:
- Rules configuration
- Audit history
- Monday.com board connection

---

## Running Audits

### Quick Start

1. Click the **"Run"** button in the header
2. Choose your audit source:
   - **Sitemap** - Audit pages from your configured sitemap
   - **Single URL** - Audit one specific page

3. Select audit types:
   - ☑️ **SEO/GEO Rules** - Technical SEO checks
   - ☑️ **Voice & Tone** - Brand voice analysis (AI-powered)
   - ☑️ **Brand Standards** - Brand compliance (AI-powered)

4. Click **"Run Audit"**

### Audit Modes

#### Sitemap Mode
Audits pages from your sitemap based on the configured settings:
- **Days to check**: How far back to look for modified pages
- **Max pages**: Maximum pages to audit per run

**Tip**: Check "Refresh sitemap" to fetch fresh sitemap data, otherwise cached data (up to 24 hours old) is used for faster audits.

#### Single URL Mode
Audit a specific page by entering its full URL.

#### Subfolder Scan Mode
Audit all pages under a specific folder:
1. Enter the folder URL (e.g., `https://example.com/hawaii/oahu`)
2. Check **"Include Subfolders"**
3. The system will find all pages from the sitemap under that path

### Progress Panel

When an audit runs, a real-time progress panel shows:
- Current page being processed
- Phase (Scraping, Running checks, Creating tasks)
- Issues found by category (SEO, Voice, Brand)
- Tasks created vs duplicates skipped
- Recent issues list

The panel persists across page refreshes - if you reload while an audit is running, it will reconnect.

---

## Managing Rules

### Rule Types

#### SEO/GEO Rules (System Rules)
These are **protected system rules** that cannot be deleted:
- Title Tag Check
- Meta Description Check
- H1 Tag Check
- Canonical Tag Check
- Schema/Structured Data Check
- Thin Content Check
- Geo Meta Tags Check
- Open Graph Tags Check
- Image Alt Tags Check
- Meta Content Relevance Check (AI-powered)

**Legacy Rules** (code-based): Fast, free checks that verify if elements exist.
**LLM Rules** (AI-powered): Deep content analysis using Claude AI.

#### Voice & Tone Rules (Example Rules)
Customizable rules for analyzing brand voice. Delete or modify these for your brand.

#### Brand Standards Rules (Example Rules)
Customizable rules for brand compliance. Delete or modify for your guidelines.

### Adding Custom Rules

1. Go to the appropriate tab (SEO, Voice, or Brand)
2. Click **"+ Add Rule"**
3. Fill in the form:
   - **Name**: Short, descriptive name
   - **Description**: What the rule checks (shown in dashboard)
   - **Prompt**: AI instructions for checking (see below)
   - **Severity**: Critical, High, Medium, or Low
4. Click **Save**

### Using AI to Generate Prompts

1. In the "User Description" field, describe what you want to check in plain English:
   ```
   Check if the page mentions specific room amenities like ocean views,
   kitchen facilities, or private balconies
   ```

2. Click **"Generate AI Prompt"**

3. Review and edit the generated structured prompt

4. Save the rule

### Resetting Rules to Defaults

1. Go to **Settings** tab
2. Click **"Reset Rules"**
3. Select which rule types to reset:
   - ☑️ SEO/GEO Rules
   - ☑️ Voice & Tone
   - ☑️ Brand Standards
4. Click **"Reset Selected"**

**Warning**: This replaces selected rules with defaults. Custom rules in those categories will be lost.

---

## Understanding Results

### Issue Severities

| Severity | Meaning | Example |
|----------|---------|---------|
| **Critical** | Must fix immediately | Missing title tag |
| **High** | Fix soon | Missing schema markup |
| **Medium** | Should address | Missing alt tags on images |
| **Low** | Nice to have | Missing robots meta tag |

### Issue Categories

| Category | What It Checks |
|----------|---------------|
| **SEO/GEO** | Technical SEO elements (tags, schema, content) |
| **Voice/Tone** | Brand voice consistency (warmth, tone, language) |
| **Brand Standards** | Brand guideline compliance (naming, CTAs) |

### GEO/LLM Readiness Score

The audit also calculates a **GEO Score (0-100)** measuring how well your page is optimized for AI assistants and generative search:

| Grade | Score | Meaning |
|-------|-------|---------|
| A | 90-100 | Excellent - AI-ready |
| B | 75-89 | Good - Minor improvements needed |
| C | 60-74 | Fair - Some optimization needed |
| D | 40-59 | Poor - Significant work needed |
| F | 0-39 | Failing - Major issues |

---

## Monday.com Integration

### How It Works

When issues are found, the system automatically creates tasks in your Monday.com board:

- **Task Name**: Issue title (e.g., "Missing meta description")
- **Page URL**: Link to the affected page
- **Issue Description**: Details about the issue and how to fix it
- **Severity**: Low, Medium, High, or Critical
- **Issue Type**: SEO/GEO, Tone/Voice, or Brand Standards

### Duplicate Prevention

The system prevents duplicate tasks by:
1. Checking existing tasks in your board
2. Using rule name + URL as the unique identifier
3. Fuzzy matching (75% similarity) to catch LLM title variations

### Required Monday.com Columns

Your board should have these columns:
- **Name** (text) - Task title
- **URL** or **Page URL** (link) - Page link
- **Issue Description** or **Description** (long text) - Issue details
- **Severity** (status) - With labels: Low, Medium, High, Critical
- **Issue Type** (status) - With labels: SEO/GEO, Tone/Voice, Brand Standards

---

## Tips & Best Practices

### For Best Results

1. **Start with defaults**: Use the default rules first to understand what's checked
2. **Run on a few pages first**: Use Single URL mode to test before full sitemap audits
3. **Review AI rules**: LLM rules use AI credits - only enable what you need
4. **Check Monday.com regularly**: Address Critical and High severity issues first

### Rule Writing Tips

When writing custom AI prompts:

✅ **DO**:
- Be specific about what constitutes a failure
- Provide examples of pass and fail scenarios
- Focus on one concept per rule

❌ **DON'T**:
- Make rules too broad or vague
- Combine multiple unrelated checks
- Use subjective criteria without examples

### Example Good Prompt
```
Check if the page has a clear call-to-action. The rule FAILS if:
1. There is no visible "Book Now", "Reserve", or "Contact Us" button
2. CTAs are buried below the fold
3. CTA text is unclear (e.g., just "Click Here")

Look for: prominent buttons, clear action language, above-the-fold placement.
```

---

## Troubleshooting

### Common Issues

#### "No URLs found in sitemap"
- Check that your sitemap URL is correct in Settings
- Verify the sitemap is accessible (not blocked by robots.txt)
- Try the "Refresh sitemap" option

#### "Monday API errors"
- Your Monday.com token may have expired
- Contact your administrator to update the token in Google Cloud Secret Manager

#### "Page blocked by Cloudflare"
- Some pages may have Cloudflare protection
- The system uses ScraperAPI to bypass this, but some pages may still be blocked

#### Issues not appearing in Monday.com
- Check that your board ID is correct in Settings
- Verify the board has the required columns
- Check that column labels match expected values (Low, Medium, High, Critical)

#### Duplicate tasks being created
- This is fixed in the latest version using rule name + fuzzy matching
- If you see duplicates from before this fix, you can manually merge them in Monday.com

### Getting Help

1. Check the **Audit Logs** tab for error details
2. Use the debug endpoint: `?debug_site=YOUR_SITE_ID`
3. Review Cloud Run logs in Google Cloud Console

---

## Quick Reference

### Keyboard Shortcuts

| Action | How To |
|--------|--------|
| Switch sites | Use dropdown in header |
| Run quick audit | Click "Run" button |
| Add new rule | Click "+ Add Rule" in any rules tab |
| View audit history | Go to "Audit Logs" tab |

### URLs

| Resource | URL |
|----------|-----|
| Dashboard | https://storage.googleapis.com/outrigger-audit-admin/index.html |
| API Health Check | https://outrigger-seo-audit-22338575803.us-central1.run.app |

---

*Last updated: January 2026*
