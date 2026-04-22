import { createMemoryRouter } from 'react-router';
import { LayoutC } from './layouts/LayoutC';
import { LayoutSettings } from './layouts/LayoutSettings';
import { ChatPage } from './pages/ChatPage';
import { CalendarPage } from './pages/CalendarPage';
import { AccountSettingsPage } from './pages/AccountSettingsPage';
import { NotFoundPage } from './pages/NotFoundPage';
import { PerformancePage } from './pages/PerformancePage';
import { DashboardDetailsPage } from './pages/performance/DashboardDetailsPage';

// Authentication pages
import { SignInPage } from './pages/SignInPage';
import { CreateAccountPage } from './pages/CreateAccountPage';
import { EmailVerificationPage } from './pages/EmailVerificationPage';
import { InvitationAcceptancePage } from './pages/InvitationAcceptancePage';

// Strategy pages
import { StrategyLayout } from './pages/strategy/StrategyLayout';
import { KnowledgeGraphPage } from './pages/strategy/KnowledgeGraphPage';

// Workflows pages
import { WorkflowsLayout } from './pages/workflows/WorkflowsLayout';
import { AgentsPage } from './pages/workflows/AgentsPage';
import { AgentCreatePage } from './pages/workflows/AgentCreatePage';
import { SkillsPage } from './pages/workflows/SkillsPage';
import { AutomationsPage } from './pages/workflows/AutomationsPage';
import { AutomationDetailsPage } from './pages/workflows/AutomationDetailsPage';

// Extensions pages
import { ExtensionsLayout } from './pages/extensions/ExtensionsLayout';
import { ExtensionsIndex } from './pages/extensions/ExtensionsIndex';
import { DashboardCreatorExtension } from './pages/extensions/DashboardCreatorExtension';

// Settings pages
import { OrganizationSettingsPage } from './pages/OrganizationSettingsPage';
import { UserSettingsPage } from './pages/UserSettingsPage';

const routes = [
  // Authentication routes (no layout)
  { path: '/sign-in', Component: SignInPage },
  { path: '/create-account', Component: CreateAccountPage },
  { path: '/verify-email', Component: EmailVerificationPage },
  { path: '/accept-invitation', Component: InvitationAcceptancePage },
  {
    path: '/',
    Component: LayoutC,
    children: [
      { index: true, Component: ChatPage },
      { path: 'performance', Component: PerformancePage },
      { path: 'performance/dashboards/:dashboardId', Component: DashboardDetailsPage },
      {
        path: 'strategy',
        Component: StrategyLayout,
        children: [
          { index: true, Component: KnowledgeGraphPage },
        ],
      },
      { path: 'calendar', Component: CalendarPage },
      {
        path: 'extensions',
        Component: ExtensionsLayout,
        children: [
          { index: true, Component: ExtensionsIndex },
          { path: 'dashboard-creator', Component: DashboardCreatorExtension },
        ],
      },
      {
        path: 'workflows',
        Component: WorkflowsLayout,
        children: [
          { index: true, Component: AgentsPage },
          { path: 'agents/new', Component: AgentCreatePage },
          { path: 'skills', Component: SkillsPage },
          { path: 'automations', Component: AutomationsPage },
          { path: 'automations/:automationId', Component: AutomationDetailsPage },
        ],
      },
      { path: 'settings/account', Component: AccountSettingsPage },
    ],
  },
  {
    path: '/settings',
    Component: LayoutSettings,
    children: [
      { path: 'organization', Component: OrganizationSettingsPage },
      { path: 'user', Component: UserSettingsPage },
    ],
  },
  { path: '*', Component: NotFoundPage },
];

// Use createMemoryRouter to avoid History API access (history.replaceState,
// history.pushState) which can throw SecurityError in sandboxed iframes.
export function createRouter() {
  return createMemoryRouter(routes, {
    initialEntries: ['/'],
  });
}