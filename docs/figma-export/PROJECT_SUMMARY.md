# MER-E - Marketing Campaign Management Platform

A modern, AI-powered marketing campaign management platform built with React 18, TailwindCSS, and Radix UI components.

## Overview

MER-E is a comprehensive marketing platform that uses an AI chat interface as the primary control surface. Users can interact with the platform through natural language, manage campaigns across multiple channels, analyze performance, and run simulations.

## Key Features

### 🤖 AI Chat Interface
- Primary control surface for the entire platform
- Support for 2-3 concurrent AI sessions
- Session status indicators (working, idle, complete)
- Context-aware responses and quick actions

### 📅 Marketing Calendar
- Month/week/day view toggles
- Color-coded activities by channel (email, paid search, social, content, events, SEO)
- Drag-and-drop scheduling capability
- Today indicator and visual activity overview

### 🔄 Workflows & Automation
- Two types: Freeform automations and Dashboard refresh schedules
- Visual workflow cards with status indicators
- Last run timestamps and schedule information
- Dashboard previews for reporting workflows

### 📊 Performance Analytics
- Real-time key metric tracking with trend visualizations
- AI-generated optimization recommendations
- Accept/dismiss recommendation actions
- Scheduled automated analyses
- Impact categorization (high/medium/low)

### 🧪 Simulations
- **Focus Groups**: AI-generated panels of 100 agents matching ICP
  - Submit questions and view aggregated feedback
  - Sentiment breakdowns and insights
  - Response distribution visualization
  
- **Campaign Forecasting**: Scenario modeling with before/after comparisons
  - Budget allocation optimization
  - Projected impact analysis
  - Multiple scenario management

### ⚙️ Settings & Integrations
- Martech integration hub with connection status
- Team member management
- Notification preferences
- Account and workspace settings

## Layout Options

MER-E offers three distinct layout approaches to suit different workflows:

### Layout A: Chat-Dominant Split View
- Chat takes 50-60% of screen on left
- Active section rendered in right panel
- Icon-only collapsible sidebar on far left
- Resizable panels
- **Best for**: Power users, large screens, multitasking

### Layout B: Chat as Overlay/Drawer
- Full-width section views
- Floating chat button (bottom-right)
- Slide-over drawer for chat
- Session indicators in top bar
- **Best for**: Content-focused workflows, cleaner interface

### Layout C: Hub-and-Spoke Dashboard
- Chat is the home/hub screen
- Persistent top navigation bar
- Collapsible bottom chat widget across all sections
- Full-screen section views
- **Best for**: Clean, minimal preference, mobile-like experience

## Design System

### Colors
- **Primary Accent**: Violet (#8b5cf6 light, #a78bfa dark)
- **Backgrounds**: White light mode, #0a0a0a dark mode (deep charcoal, not pure black)
- **Channel Colors**: 
  - Email: #f59e0b
  - Paid Search: #3b82f6
  - Social: #8b5cf6
  - Content: #10b981
  - Events: #ef4444
  - SEO: #06b6d4

### Typography
- Clean sans-serif (Inter/Geist)
- Clear hierarchy with minimal weight variations
- Default: 16px base, 500 medium weight, 400 normal weight

### Components
- Rounded corners: 8px default (0.5rem)
- Subtle borders and soft shadows
- Consistent with Radix UI / shadcn/ui patterns
- Responsive and touch-friendly

### Dark Mode
- System preference support
- Smooth transitions
- Optimized contrast ratios
- Deep charcoal (#0a0a0a) instead of pure black

## Mobile Experience

- Bottom tab navigation (6 tabs)
- Full-screen section views
- Touch-optimized interactions
- Responsive component sizing
- Mobile header with current page indicator
- Active session count display

## Technical Stack

- **Frontend**: React 18
- **Styling**: TailwindCSS v4
- **UI Components**: Radix UI primitives
- **Icons**: Lucide React
- **Charts**: Recharts
- **Routing**: React Router v7 (Data Mode)
- **Theme**: next-themes
- **Animations**: Motion (formerly Framer Motion)

## Project Structure

```
/src/app/
├── components/
│   ├── ui/              # Radix UI components
│   ├── ChatInterface.tsx
│   ├── SessionIndicator.tsx
│   ├── EmptyState.tsx
│   ├── ThemeToggle.tsx
│   ├── ThemeProvider.tsx
│   ├── LayoutSelector.tsx
│   ├── WelcomeDialog.tsx
│   └── FeatureShowcase.tsx
├── layouts/
│   ├── LayoutA.tsx      # Split view
│   ├── LayoutB.tsx      # Drawer
│   ├── LayoutC.tsx      # Hub-and-spoke
│   └── MobileLayout.tsx
├── pages/
│   ├── ChatPage.tsx
│   ├── CalendarPage.tsx
│   ├── WorkflowsPage.tsx
│   ├── PerformancePage.tsx
│   ├── SimulationsPage.tsx
│   ├── SettingsPage.tsx
│   └── NotFoundPage.tsx
├── data/
│   └── mockData.ts
├── routes.ts
└── App.tsx
```

## Getting Started

1. The app loads with a welcome dialog to choose your preferred layout
2. Default view is the AI Chat interface with session indicators
3. Navigate between sections using the sidebar/top nav
4. Use the "Platform Overview" tab on the Chat page to see all features
5. Change layouts anytime using the "Switch Layout" button on the Chat page
6. Toggle dark/light mode using the theme switcher

## Mock Data

The application includes comprehensive mock data for demonstration:
- 3 AI sessions with different statuses
- 5 marketing activities across multiple channels
- 4 workflows (mix of freeform and dashboard types)
- 4 performance metrics with trends
- 3 AI recommendations with different impact levels
- 6 integrations with various connection states

## Notes

- Layout choice persists in localStorage
- Welcome dialog shows only on first visit
- Mobile layout auto-activates on screens < 768px
- All sections include empty states with AI chat prompts
- Session indicators are visible across all layouts
- Responsive design adapts to all screen sizes
