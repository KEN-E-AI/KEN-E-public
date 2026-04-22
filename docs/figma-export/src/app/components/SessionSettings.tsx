import { useState } from 'react';
import {
  Pencil,
  FileText,
  FileSpreadsheet,
  FileImage,
  FileCode,
  Upload,
  Bot,
  CheckCircle2,
  Circle,
  ChevronDown,
  ChevronRight,
  Plus,
  X,
  Shield,
  Wrench,
  Clock,
  Sparkles,
} from 'lucide-react';
import { Card, CardContent } from './ui/card';
import { Input } from './ui/input';
import { Textarea } from './ui/textarea';
import { Badge } from './ui/badge';
import { Button } from './ui/button';
import { Progress } from './ui/progress';
import { Checkbox } from './ui/checkbox';
import { ScrollArea } from './ui/scroll-area';
import { cn } from './ui/utils';
import { sessionCategories } from '../data/mockData';

// --- Mock data for session settings ---

interface SessionDocument {
  id: string;
  name: string;
  type: 'pdf' | 'spreadsheet' | 'image' | 'code' | 'text';
  source: 'user' | 'ken-e';
  addedAt: Date;
  size: string;
}

interface TodoItem {
  id: string;
  text: string;
  completed: boolean;
}

interface TodoList {
  id: string;
  title: string;
  createdAt: Date;
  isCurrent: boolean;
  items: TodoItem[];
}

interface Permission {
  id: string;
  name: string;
  description: string;
  grantedAt: Date;
}

interface LoadedTool {
  id: string;
  name: string;
  description: string;
  authenticated: boolean;
  lastUsed?: Date;
}

const mockDocuments: SessionDocument[] = [
  { id: '1', name: 'Q3 Campaign Brief.pdf', type: 'pdf', source: 'user', addedAt: new Date(2026, 1, 13, 10, 0), size: '2.4 MB' },
  { id: '2', name: 'Channel Performance Report.xlsx', type: 'spreadsheet', source: 'ken-e', addedAt: new Date(2026, 1, 13, 11, 30), size: '1.1 MB' },
  { id: '3', name: 'Brand Guidelines 2026.pdf', type: 'pdf', source: 'user', addedAt: new Date(2026, 1, 12, 9, 0), size: '8.7 MB' },
  { id: '4', name: 'Social Media Calendar Draft.xlsx', type: 'spreadsheet', source: 'ken-e', addedAt: new Date(2026, 1, 13, 14, 20), size: '540 KB' },
  { id: '5', name: 'Hero Banner Mockup.png', type: 'image', source: 'ken-e', addedAt: new Date(2026, 1, 13, 15, 0), size: '3.2 MB' },
  { id: '6', name: 'Email Template Code.html', type: 'code', source: 'ken-e', addedAt: new Date(2026, 1, 14, 8, 45), size: '24 KB' },
  { id: '7', name: 'Competitor Analysis Notes.txt', type: 'text', source: 'user', addedAt: new Date(2026, 1, 14, 10, 15), size: '12 KB' },
];

const mockTodoLists: TodoList[] = [
  {
    id: '1',
    title: 'Current: Q3 Calendar Build',
    createdAt: new Date(2026, 1, 15, 9, 0),
    isCurrent: true,
    items: [
      { id: '1a', text: 'Finalize email campaign dates for July', completed: true },
      { id: '1b', text: 'Schedule LinkedIn ad flights for August', completed: true },
      { id: '1c', text: 'Add webinar series to September calendar', completed: false },
      { id: '1d', text: 'Coordinate social media content with design team', completed: false },
      { id: '1e', text: 'Set up budget allocation per channel', completed: false },
      { id: '1f', text: 'Review and approve final calendar with stakeholders', completed: false },
    ],
  },
  {
    id: '2',
    title: 'Previous: Initial Research Phase',
    createdAt: new Date(2026, 1, 13, 14, 0),
    isCurrent: false,
    items: [
      { id: '2a', text: 'Gather Q2 performance data from all channels', completed: true },
      { id: '2b', text: 'Identify top-performing campaign types', completed: true },
      { id: '2c', text: 'Analyze competitor marketing calendars', completed: true },
      { id: '2d', text: 'Draft initial Q3 strategy recommendations', completed: true },
    ],
  },
  {
    id: '3',
    title: 'Previous: Asset Collection',
    createdAt: new Date(2026, 1, 12, 10, 0),
    isCurrent: false,
    items: [
      { id: '3a', text: 'Collect brand guidelines from design team', completed: true },
      { id: '3b', text: 'Upload campaign brief document', completed: true },
      { id: '3c', text: 'Request budget figures from finance', completed: true },
    ],
  },
];

const mockPermissions: Permission[] = [
  { id: '1', name: 'Read Calendar Data', description: 'Access marketing calendar events and schedules', grantedAt: new Date(2026, 1, 13, 10, 0) },
  { id: '2', name: 'Write Calendar Events', description: 'Create and modify calendar events', grantedAt: new Date(2026, 1, 13, 10, 0) },
  { id: '3', name: 'Access Analytics', description: 'Read campaign performance metrics', grantedAt: new Date(2026, 1, 13, 10, 5) },
  { id: '4', name: 'Generate Reports', description: 'Create performance reports and exports', grantedAt: new Date(2026, 1, 13, 11, 30) },
  { id: '5', name: 'Manage Budget Data', description: 'View and suggest budget allocations', grantedAt: new Date(2026, 1, 14, 9, 0) },
];

const mockTools: LoadedTool[] = [
  { id: '1', name: 'Google Ads API', description: 'Campaign management and reporting', authenticated: true, lastUsed: new Date(2026, 1, 15, 8, 30) },
  { id: '2', name: 'HubSpot CRM', description: 'Contact and deal management', authenticated: true, lastUsed: new Date(2026, 1, 15, 9, 15) },
  { id: '3', name: 'Meta Ads Manager', description: 'Facebook and Instagram advertising', authenticated: true, lastUsed: new Date(2026, 1, 14, 16, 0) },
  { id: '4', name: 'Salesforce', description: 'CRM data and lead management', authenticated: false },
  { id: '5', name: 'LinkedIn Campaign Manager', description: 'LinkedIn advertising platform', authenticated: true, lastUsed: new Date(2026, 1, 15, 7, 45) },
  { id: '6', name: 'Mailchimp', description: 'Email marketing automation', authenticated: false },
  { id: '7', name: 'Google Analytics 4', description: 'Website traffic and conversion tracking', authenticated: true, lastUsed: new Date(2026, 1, 15, 10, 0) },
  { id: '8', name: 'Canva Design API', description: 'Asset generation and design tools', authenticated: true, lastUsed: new Date(2026, 1, 13, 14, 20) },
];

// --- Component ---

const docIcons: Record<SessionDocument['type'], typeof FileText> = {
  pdf: FileText,
  spreadsheet: FileSpreadsheet,
  image: FileImage,
  code: FileCode,
  text: FileText,
};

const docColors: Record<SessionDocument['type'], string> = {
  pdf: 'var(--color-error)',
  spreadsheet: 'var(--color-success)',
  image: 'var(--color-violet-500)',
  code: 'var(--color-blue-500)',
  text: 'var(--color-slate-500)',
};

export function SessionSettings() {
  const [sessionName, setSessionName] = useState('Building Q3 calendar');
  const [sessionCategory, setSessionCategory] = useState('Campaign Planning');
  const [categories, setCategories] = useState(['Uncategorized', ...sessionCategories]);
  const [newCategory, setNewCategory] = useState('');
  const [showNewCategory, setShowNewCategory] = useState(false);
  const [sessionSummary, setSessionSummary] = useState(
    'This session focuses on building the Q3 marketing calendar. KEN-E analyzed Q2 performance data across all channels, identified top-performing campaign types (email nurture sequences and LinkedIn sponsored content), and is now constructing a comprehensive Q3 calendar. Key milestones include July email campaigns, August LinkedIn ad flights, and a September webinar series. Budget allocation recommendations have been generated based on Q2 ROI data. The session has produced a channel performance report and social media calendar draft as artifacts.'
  );
  const [expandedTodoLists, setExpandedTodoLists] = useState<string[]>(['1']);

  const contextWindowUsed = 67;
  const contextWindowMax = 128000;
  const tokensUsedInput = 84320;
  const tokensUsedOutput = 42150;
  const totalTokens = tokensUsedInput + tokensUsedOutput;

  const toggleTodoList = (id: string) => {
    setExpandedTodoLists(prev =>
      prev.includes(id) ? prev.filter(i => i !== id) : [...prev, id]
    );
  };

  const handleAddCategory = () => {
    if (newCategory.trim() && !categories.includes(newCategory.trim())) {
      const trimmed = newCategory.trim();
      setCategories(prev => [...prev, trimmed]);
      setSessionCategory(trimmed);
      setNewCategory('');
      setShowNewCategory(false);
    }
  };

  return (
    <ScrollArea className="h-full">
      <div className="p-6 space-y-6 max-w-4xl">
        {/* 1. Session Name + 2. Session Category */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          <Card className="p-5" accentColor="var(--color-accent-slot-1)">
            <div className="flex items-center gap-2 mb-3">
              <Pencil className="size-4 text-[var(--color-violet-500)]" />
              <h3
                className="text-[var(--text-heading-sm)]"
                style={{ fontFamily: 'var(--font-display)' }}
              >
                Session Name
              </h3>
            </div>
            <Input
              value={sessionName}
              onChange={(e) => setSessionName(e.target.value)}
              placeholder="Enter session name..."
            />
          </Card>

          <Card className="p-5" accentColor="var(--color-accent-slot-2)">
            <div className="flex items-center gap-2 mb-3">
              <span className="text-[var(--color-blue-500)]">#</span>
              <h3
                className="text-[var(--text-heading-sm)]"
                style={{ fontFamily: 'var(--font-display)' }}
              >
                Session Category
              </h3>
              <Badge variant="neutral">Optional</Badge>
            </div>
            <div className="flex gap-3">
              <select
                value={sessionCategory}
                onChange={(e) => setSessionCategory(e.target.value)}
                className="flex-1 px-3 py-2 rounded-[var(--radius-md)] border-2 border-[var(--color-border-default)] bg-[var(--color-bg-elevated)] text-[var(--text-body-md)] focus:outline-none focus:border-[var(--color-violet-500)] focus:shadow-[0_0_0_3px_var(--color-violet-100)]"
                style={{
                  transitionTimingFunction: 'var(--ease-default)',
                  transitionDuration: 'var(--duration-fast)',
                }}
              >
                {categories.map(cat => (
                  <option key={cat} value={cat}>{cat}</option>
                ))}
              </select>
              <Button
                variant="outline"
                size="sm"
                onClick={() => setShowNewCategory(!showNewCategory)}
              >
                <Plus className="size-4" />
                New
              </Button>
            </div>
            {showNewCategory && (
              <div className="flex gap-2 mt-3">
                <Input
                  value={newCategory}
                  onChange={(e) => setNewCategory(e.target.value)}
                  placeholder="New category name..."
                  onKeyDown={(e) => e.key === 'Enter' && handleAddCategory()}
                  className="flex-1"
                />
                <Button size="sm" onClick={handleAddCategory}>Add</Button>
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => { setShowNewCategory(false); setNewCategory(''); }}
                >
                  <X className="size-4" />
                </Button>
              </div>
            )}
          </Card>
        </div>

        {/* 3. Session Summary */}
        <Card className="p-5" accentColor="var(--color-accent-slot-3)">
          <div className="flex items-center gap-2 mb-1">
            <Sparkles className="size-4 text-[var(--color-teal-500)]" />
            <h3
              className="text-[var(--text-heading-sm)]"
              style={{ fontFamily: 'var(--font-display)' }}
            >
              Session Summary
            </h3>
          </div>
          <p className="text-[var(--text-caption)] text-[var(--color-text-tertiary)] mb-3">
            Auto-generated during compaction. You can edit this summary.
          </p>
          <Textarea
            value={sessionSummary}
            onChange={(e) => setSessionSummary(e.target.value)}
            className="min-h-[120px]"
          />
        </Card>

        {/* 4. Documents */}
        <Card className="p-5" accentColor="var(--color-accent-slot-4)">
          <div className="flex items-center justify-between mb-4">
            <div className="flex items-center gap-2">
              <FileText className="size-4 text-[var(--color-amber-500)]" />
              <h3
                className="text-[var(--text-heading-sm)]"
                style={{ fontFamily: 'var(--font-display)' }}
              >
                Documents
              </h3>
              <Badge variant="neutral">{mockDocuments.length}</Badge>
            </div>
          </div>
          <div className="space-y-2">
            {mockDocuments.map(doc => {
              const Icon = docIcons[doc.type];
              return (
                <div
                  key={doc.id}
                  className="flex items-center gap-3 p-2.5 rounded-[var(--radius-md)] border-2 border-[var(--color-border-default)] bg-[var(--color-bg-primary)] hover:border-[var(--color-violet-300)] transition-all"
                  style={{
                    transitionTimingFunction: 'var(--ease-default)',
                    transitionDuration: 'var(--duration-fast)',
                  }}
                >
                  <div
                    className="size-8 rounded-[var(--radius-sm)] flex items-center justify-center shrink-0"
                    style={{
                      backgroundColor: `color-mix(in srgb, ${docColors[doc.type]} 12%, transparent)`,
                      color: docColors[doc.type],
                    }}
                  >
                    <Icon className="size-4" />
                  </div>
                  <div className="flex-1 min-w-0">
                    <p className="text-[var(--text-body-sm)] font-medium truncate">
                      {doc.name}
                    </p>
                    <p className="text-[var(--text-caption)] text-[var(--color-text-tertiary)]">
                      {doc.size}
                    </p>
                  </div>
                  <Badge variant={doc.source === 'user' ? 'outline' : 'default'}>
                    {doc.source === 'user' ? (
                      <span className="flex items-center gap-1"><Upload className="size-3" />Uploaded</span>
                    ) : (
                      <span className="flex items-center gap-1"><Bot className="size-3" />KEN-E</span>
                    )}
                  </Badge>
                </div>
              );
            })}
          </div>
        </Card>

        {/* 5. To Do Lists */}
        <Card className="p-5" accentColor="var(--color-accent-slot-5)">
          <div className="flex items-center gap-2 mb-1">
            <CheckCircle2 className="size-4 text-[var(--color-violet-500)]" />
            <h3
              className="text-[var(--text-heading-sm)]"
              style={{ fontFamily: 'var(--font-display)' }}
            >
              To Do Lists
            </h3>
          </div>
          <p className="text-[var(--text-caption)] text-[var(--color-text-tertiary)] mb-4">
            Tracks long tasks to ensure details are preserved during compaction.
          </p>
          <div className="space-y-3">
            {mockTodoLists.map(list => {
              const isExpanded = expandedTodoLists.includes(list.id);
              const completedCount = list.items.filter(i => i.completed).length;
              return (
                <div
                  key={list.id}
                  className={cn(
                    "rounded-[var(--radius-md)] border-2 transition-all overflow-hidden",
                    list.isCurrent
                      ? "border-[var(--color-violet-300)] bg-[var(--color-bg-primary)]"
                      : "border-[var(--color-border-default)] bg-[var(--color-bg-primary)]"
                  )}
                >
                  <button
                    onClick={() => toggleTodoList(list.id)}
                    className="w-full flex items-center gap-2 p-3 hover:bg-[var(--color-accent)] transition-all text-left"
                    style={{
                      transitionTimingFunction: 'var(--ease-default)',
                      transitionDuration: 'var(--duration-fast)',
                    }}
                  >
                    {isExpanded ? (
                      <ChevronDown className="size-4 text-[var(--color-text-tertiary)] shrink-0" />
                    ) : (
                      <ChevronRight className="size-4 text-[var(--color-text-tertiary)] shrink-0" />
                    )}
                    <span className="text-[var(--text-body-sm)] font-medium flex-1 min-w-0 truncate">
                      {list.title}
                    </span>
                    {list.isCurrent && <Badge variant="info">Active</Badge>}
                    <span className="text-[var(--text-caption)] text-[var(--color-text-tertiary)] shrink-0">
                      {completedCount}/{list.items.length}
                    </span>
                  </button>
                  {isExpanded && (
                    <div className="px-3 pb-3 space-y-2 border-t-2 border-dashed border-[var(--color-border-default)] pt-3">
                      {list.items.map(item => (
                        <div key={item.id} className="flex items-start gap-2.5">
                          <Checkbox
                            checked={item.completed}
                            className="mt-0.5"
                            disabled
                          />
                          <span
                            className={cn(
                              "text-[var(--text-body-sm)]",
                              item.completed && "line-through text-[var(--color-text-tertiary)]"
                            )}
                          >
                            {item.text}
                          </span>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        </Card>

        {/* 6. Context Window + 7. Tokens Used */}
        <Card className="p-5" accentColor="var(--color-accent-slot-6)">
          <div className="flex items-center gap-2 mb-4">
            <Clock className="size-4 text-[var(--color-blue-500)]" />
            <h3
              className="text-[var(--text-heading-sm)]"
              style={{ fontFamily: 'var(--font-display)' }}
            >
              Context &amp; Token Usage
            </h3>
          </div>

          {/* Context Window Progress Bar */}
          <div className="mb-5">
            <div className="flex items-center justify-between mb-2">
              <span className="text-[var(--text-body-sm)] text-[var(--color-text-secondary)]">
                Context Window
              </span>
              <span className="text-[var(--text-body-sm)] font-medium">
                {contextWindowUsed}% used
              </span>
            </div>
            <div className="relative">
              <Progress value={contextWindowUsed} className="h-3 bg-[var(--color-surface-muted)]" />
            </div>
            <div className="flex items-center justify-between mt-1.5">
              <span className="text-[var(--text-caption)] text-[var(--color-text-tertiary)]">
                ~{Math.round(contextWindowMax * contextWindowUsed / 100).toLocaleString()} / {contextWindowMax.toLocaleString()} tokens
              </span>
              <Badge variant={contextWindowUsed > 80 ? 'warning' : contextWindowUsed > 60 ? 'info' : 'success'}>
                {contextWindowUsed > 80 ? 'Near limit' : contextWindowUsed > 60 ? 'Moderate' : 'Healthy'}
              </Badge>
            </div>
          </div>

          {/* Tokens Used */}
          <div
            className="border-t-2 border-dashed border-[var(--color-border-default)] pt-4"
          >
            <span className="text-[var(--text-body-sm)] text-[var(--color-text-secondary)] block mb-3">
              Tokens Used This Session
            </span>
            <div className="grid grid-cols-3 gap-4">
              <div className="text-center p-3 rounded-[var(--radius-md)] bg-[var(--color-bg-primary)] border-2 border-[var(--color-border-default)]">
                <p className="text-[var(--text-heading-md)] font-bold text-[var(--color-blue-500)]" style={{ fontFamily: 'var(--font-display)' }}>
                  {tokensUsedInput.toLocaleString()}
                </p>
                <p className="text-[var(--text-caption)] text-[var(--color-text-tertiary)] mt-1">Input</p>
              </div>
              <div className="text-center p-3 rounded-[var(--radius-md)] bg-[var(--color-bg-primary)] border-2 border-[var(--color-border-default)]">
                <p className="text-[var(--text-heading-md)] font-bold text-[var(--color-violet-500)]" style={{ fontFamily: 'var(--font-display)' }}>
                  {tokensUsedOutput.toLocaleString()}
                </p>
                <p className="text-[var(--text-caption)] text-[var(--color-text-tertiary)] mt-1">Output</p>
              </div>
              <div className="text-center p-3 rounded-[var(--radius-md)] bg-[var(--color-bg-primary)] border-2 border-[var(--color-border-default)]">
                <p className="text-[var(--text-heading-md)] font-bold text-[var(--color-text-primary)]" style={{ fontFamily: 'var(--font-display)' }}>
                  {totalTokens.toLocaleString()}
                </p>
                <p className="text-[var(--text-caption)] text-[var(--color-text-tertiary)] mt-1">Total</p>
              </div>
            </div>
          </div>
        </Card>

        {/* 8. Permissions */}
        <Card className="p-5" accentColor="var(--color-accent-slot-1)">
          <div className="flex items-center gap-2 mb-4">
            <Shield className="size-4 text-[var(--color-teal-500)]" />
            <h3
              className="text-[var(--text-heading-sm)]"
              style={{ fontFamily: 'var(--font-display)' }}
            >
              Permissions Approved
            </h3>
            <Badge variant="neutral">{mockPermissions.length}</Badge>
          </div>
          <div className="space-y-2">
            {mockPermissions.map(perm => (
              <div
                key={perm.id}
                className="flex items-center gap-3 p-2.5 rounded-[var(--radius-md)] border-2 border-[var(--color-border-default)] bg-[var(--color-bg-primary)]"
              >
                <div
                  className="size-2.5 rounded-full bg-[var(--color-success)] shrink-0"
                  style={{ boxShadow: '0 0 4px rgba(16, 185, 129, 0.5)' }}
                />
                <div className="flex-1 min-w-0">
                  <p className="text-[var(--text-body-sm)] font-medium">
                    {perm.name}
                  </p>
                  <p className="text-[var(--text-caption)] text-[var(--color-text-tertiary)]">
                    {perm.description}
                  </p>
                </div>
                <span className="text-[var(--text-caption)] text-[var(--color-text-tertiary)] shrink-0">
                  {perm.grantedAt.toLocaleDateString('en-US', { month: 'short', day: 'numeric' })}
                </span>
              </div>
            ))}
          </div>
        </Card>

        {/* 9. Tools Loaded */}
        <Card className="p-5" accentColor="var(--color-accent-slot-3)">
          <div className="flex items-center gap-2 mb-4">
            <Wrench className="size-4 text-[var(--color-violet-500)]" />
            <h3
              className="text-[var(--text-heading-sm)]"
              style={{ fontFamily: 'var(--font-display)' }}
            >
              Loaded Tools
            </h3>
            <Badge variant="success">
              {mockTools.filter(t => t.authenticated).length}/{mockTools.length} connected
            </Badge>
          </div>
          <div className="space-y-2">
            {mockTools.map(tool => (
              <div
                key={tool.id}
                className="flex items-center gap-3 p-2.5 rounded-[var(--radius-md)] border-2 border-[var(--color-border-default)] bg-[var(--color-bg-primary)] hover:border-[var(--color-violet-300)] transition-all"
                style={{
                  transitionTimingFunction: 'var(--ease-default)',
                  transitionDuration: 'var(--duration-fast)',
                }}
              >
                <div
                  className={cn(
                    "size-2.5 rounded-full shrink-0",
                    tool.authenticated
                      ? "bg-[var(--color-success)]"
                      : "bg-[var(--color-error)]"
                  )}
                  style={{
                    boxShadow: tool.authenticated
                      ? '0 0 4px rgba(16, 185, 129, 0.5)'
                      : '0 0 4px rgba(239, 68, 68, 0.5)',
                  }}
                />
                <div className="flex-1 min-w-0">
                  <p className="text-[var(--text-body-sm)] font-medium">
                    {tool.name}
                  </p>
                  <p className="text-[var(--text-caption)] text-[var(--color-text-tertiary)]">
                    {tool.description}
                  </p>
                </div>
                <Badge variant={tool.authenticated ? 'success' : 'error'}>
                  {tool.authenticated ? 'Authenticated' : 'Disconnected'}
                </Badge>
              </div>
            ))}
          </div>
        </Card>
      </div>
    </ScrollArea>
  );
}