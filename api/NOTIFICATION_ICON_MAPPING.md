# Notification Category Icon Mapping

## Overview
This document describes the mapping between notification categories and their corresponding icons in the KEN-E application.

## Icon Mapping
The following icons are used for each notification category:

| Category | Icon Component | Description |
|----------|---------------|-------------|
| Data Quality Alert | `AlertTriangle` | Triangle with exclamation mark for data quality issues |
| News & Press | `Newspaper` | Newspaper icon for company news and press releases |
| Industry News | `Globe` | Globe icon for industry-wide news and updates |
| Competitor Activities | `Users` | Users icon for competitor-related notifications |
| Scheduled Report Status | `FileText` | File/document icon for report generation updates |
| KPI Performance | `TrendingUp` | Upward trend arrow for KPI alerts |
| New Features | `Sparkles` | Sparkles icon for new feature announcements |

## Implementation Details

### Files Modified

1. **`/frontend/src/components/layout/ContextSidebar.tsx`**
   - Added imports for all notification category icons
   - Created `NOTIFICATION_CATEGORY_ICONS` mapping object
   - Updated notification rendering to use category-based icons instead of the `icon` field
   - Removed dependency on the generic `iconMap`

2. **`/frontend/src/components/layout/ContextSidebar.spec.tsx`**
   - Added comprehensive tests for notification category icons
   - Added tests to verify correct icon background colors for read/unread states

### Key Changes

- The ContextSidebar now uses the notification's `category` field to determine which icon to display
- This ensures consistency with the NotificationPreferences component on the user settings page
- Falls back to `Home` icon if category is not recognized

### Visual States

- **Unread notifications**: Green background (`bg-[#B8E2AF]`) with darker icon color
- **Read notifications**: Gray background (`bg-gray-100`) with muted icon color

## Usage

The icon mapping is automatically applied when notifications are displayed in the ContextSidebar. No additional configuration is needed - simply ensure that notifications have a valid `category` field matching one of the supported categories.