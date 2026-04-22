/**
 * Knowledge Graph mock data — mirrors a Neo4j property graph model.
 * Schema-agnostic: node types and relationship types can evolve.
 */

export interface KGNodeType {
  id: string;
  label: string;
  color: string;
  bgColor: string;
  icon: string; // Lucide icon name
}

export interface KGNode {
  id: string;
  type: string; // References KGNodeType.id
  label: string;
  properties: Record<string, unknown>;
}

export interface KGRelationshipType {
  id: string;
  label: string;
  color: string;
}

export interface KGRelationship {
  id: string;
  type: string; // References KGRelationshipType.id
  sourceId: string;
  targetId: string;
  properties: Record<string, unknown>;
}

export interface KnowledgeGraph {
  nodeTypes: KGNodeType[];
  relationshipTypes: KGRelationshipType[];
  nodes: KGNode[];
  relationships: KGRelationship[];
}

// ─── Node Types ───

export const nodeTypes: KGNodeType[] = [
  { id: 'Account', label: 'Account', color: '#2EC4B6', bgColor: '#E8F8F6', icon: 'Building2' },
  { id: 'Campaign', label: 'Campaign', color: '#3B82F6', bgColor: '#EFF6FF', icon: 'Megaphone' },
  { id: 'Competitor', label: 'Competitor', color: '#6366F1', bgColor: '#EEF2FF', icon: 'Swords' },
  { id: 'Product', label: 'Product', color: '#F59E0B', bgColor: '#FEF3C7', icon: 'Package' },
  { id: 'Audience', label: 'Audience', color: '#3B82F6', bgColor: '#EFF6FF', icon: 'Users' },
  { id: 'Channel', label: 'Channel', color: '#EC4899', bgColor: '#FDF2F8', icon: 'Radio' },
  { id: 'Content', label: 'Content', color: '#10B981', bgColor: '#D1FAE5', icon: 'FileText' },
  { id: 'Metric', label: 'Metric', color: '#F97316', bgColor: '#FFF7ED', icon: 'Gauge' },
  { id: 'Insight', label: 'Insight', color: '#8B5CF6', bgColor: '#F5F3FF', icon: 'Lightbulb' },
  { id: 'Brand', label: 'Brand', color: '#1E293B', bgColor: '#F1F5F9', icon: 'Palette' },
  { id: 'Strategy', label: 'Strategy', color: '#EF4444', bgColor: '#FEE2E2', icon: 'Target' },
  { id: 'Persona', label: 'Persona', color: '#06B6D4', bgColor: '#ECFEFF', icon: 'CircleUser' },
];

// ─── Relationship Types ───

export const relationshipTypes: KGRelationshipType[] = [
  { id: 'OWNS', label: 'Owns', color: '#94A3B8' },
  { id: 'COMPETES_WITH', label: 'Competes With', color: '#8B5CF6' },
  { id: 'TARGETS', label: 'Targets', color: '#3B82F6' },
  { id: 'USES_CHANNEL', label: 'Uses Channel', color: '#EC4899' },
  { id: 'PRODUCES', label: 'Produces', color: '#10B981' },
  { id: 'MEASURES', label: 'Measures', color: '#F97316' },
  { id: 'GENERATES', label: 'Generates', color: '#8B5CF6' },
  { id: 'PART_OF', label: 'Part Of', color: '#64748B' },
  { id: 'DEPENDS_ON', label: 'Depends On', color: '#EF4444' },
  { id: 'INFORMS', label: 'Informs', color: '#06B6D4' },
  { id: 'REPRESENTS', label: 'Represents', color: '#F59E0B' },
  { id: 'HAS_PERSONA', label: 'Has Persona', color: '#06B6D4' },
  { id: 'EXECUTES', label: 'Executes', color: '#2EC4B6' },
  { id: 'TRACKS', label: 'Tracks', color: '#F97316' },
  { id: 'INFLUENCES', label: 'Influences', color: '#6366F1' },
];

// ─── Nodes ───

export const nodes: KGNode[] = [
  // Account
  { id: 'n1', type: 'Account', label: 'Acme Corp', properties: { industry: 'SaaS', founded: 2018, website: 'https://acmecorp.io', employees: 250, arpu: 89, headquarters: 'San Francisco, CA', description: 'B2B project management platform for remote teams' } },

  // Products
  { id: 'n2', type: 'Product', label: 'Acme Pro', properties: { tier: 'Professional', price: '$49/mo', features: ['Unlimited projects', 'Advanced analytics', 'Priority support'], mrr: 420000, launch_date: '2020-03-15' } },
  { id: 'n3', type: 'Product', label: 'Acme Enterprise', properties: { tier: 'Enterprise', price: '$149/mo', features: ['SSO', 'Audit logs', 'Dedicated CSM', 'Custom integrations'], mrr: 890000, launch_date: '2021-07-01' } },
  { id: 'n4', type: 'Product', label: 'Acme Starter', properties: { tier: 'Starter', price: 'Free', features: ['3 projects', 'Basic reporting'], mrr: 0, launch_date: '2019-01-10' } },

  // Competitors
  { id: 'n5', type: 'Competitor', label: 'RivalPM', properties: { market_share: '22%', strengths: ['Brand recognition', 'Enterprise deals'], weaknesses: ['Slow innovation', 'Complex UI'], founded: 2015 } },
  { id: 'n6', type: 'Competitor', label: 'TaskFlow', properties: { market_share: '15%', strengths: ['Modern UX', 'AI features'], weaknesses: ['Limited integrations', 'Small team'], founded: 2021 } },
  { id: 'n7', type: 'Competitor', label: 'PlanIt', properties: { market_share: '10%', strengths: ['Low price', 'Simplicity'], weaknesses: ['Feature gaps', 'No enterprise tier'], founded: 2019 } },

  // Audiences
  { id: 'n8', type: 'Audience', label: 'SMB Ops Managers', properties: { size: '~45,000', age_range: '28-42', job_titles: ['Operations Manager', 'Project Lead', 'Team Lead'], pain_points: ['Tool sprawl', 'Missed deadlines', 'Poor visibility'] } },
  { id: 'n9', type: 'Audience', label: 'Enterprise IT Buyers', properties: { size: '~12,000', age_range: '35-55', job_titles: ['CTO', 'VP Engineering', 'IT Director'], pain_points: ['Security compliance', 'Vendor consolidation', 'Change management'] } },
  { id: 'n10', type: 'Audience', label: 'Freelance Creatives', properties: { size: '~120,000', age_range: '22-38', job_titles: ['Freelancer', 'Designer', 'Content Creator'], pain_points: ['Client management', 'Time tracking', 'Invoicing'] } },

  // Personas
  { id: 'n11', type: 'Persona', label: 'DevOps Diana', properties: { role: 'DevOps Manager', company_size: '50-200', goals: ['Reduce cycle time', 'Automate workflows'], frustrations: ['Manual deployment tracking', 'Cross-team sync'], preferred_channels: ['LinkedIn', 'Dev blogs'] } },
  { id: 'n12', type: 'Persona', label: 'Startup Sam', properties: { role: 'Startup Founder', company_size: '1-10', goals: ['Ship fast', 'Stay organized'], frustrations: ['Too many tools', 'Expensive software'], preferred_channels: ['Twitter/X', 'ProductHunt', 'Podcasts'] } },

  // Brand
  { id: 'n13', type: 'Brand', label: 'Acme Brand', properties: { voice: 'Confident, approachable, technically sharp', colors: ['#2EC4B6', '#6366F1', '#1E293B'], tagline: 'Ship smarter, together.', tone: ['Professional', 'Empowering', 'Clear'], typography: 'Plus Jakarta Sans' } },

  // Channels
  { id: 'n14', type: 'Channel', label: 'Google Ads', properties: { type: 'Paid Search', monthly_spend: 45000, cpc_avg: 3.20, conversion_rate: '4.2%', status: 'Active' } },
  { id: 'n15', type: 'Channel', label: 'LinkedIn', properties: { type: 'Social / Paid Social', monthly_spend: 28000, followers: 18400, engagement_rate: '3.8%', status: 'Active' } },
  { id: 'n16', type: 'Channel', label: 'Blog', properties: { type: 'Organic Content', monthly_traffic: 85000, posts_per_month: 8, avg_read_time: '4.2 min', status: 'Active' } },
  { id: 'n17', type: 'Channel', label: 'Email', properties: { type: 'Email Marketing', list_size: 42000, open_rate: '28%', click_rate: '4.1%', status: 'Active' } },
  { id: 'n18', type: 'Channel', label: 'YouTube', properties: { type: 'Video', subscribers: 5200, monthly_views: 32000, avg_watch_time: '3:45', status: 'Growing' } },
  { id: 'n19', type: 'Channel', label: 'ProductHunt', properties: { type: 'Launch Platform', launches: 3, total_upvotes: 1240, status: 'Occasional' } },

  // Campaigns
  { id: 'n20', type: 'Campaign', label: 'Q1 Product Launch', properties: { status: 'Completed', start_date: '2026-01-15', end_date: '2026-02-28', budget: 75000, actual_spend: 68500, objective: 'Launch Acme Pro v3', results: { leads: 2400, signups: 890, pipeline: 320000 } } },
  { id: 'n21', type: 'Campaign', label: 'Enterprise Push Q2', properties: { status: 'Active', start_date: '2026-04-01', end_date: '2026-06-30', budget: 120000, objective: 'Grow enterprise pipeline by 40%' } },
  { id: 'n22', type: 'Campaign', label: 'Brand Awareness H1', properties: { status: 'Active', start_date: '2026-01-01', end_date: '2026-06-30', budget: 95000, objective: 'Increase unaided brand recall from 12% to 20%' } },
  { id: 'n23', type: 'Campaign', label: 'Freemium Conversion', properties: { status: 'Planning', start_date: '2026-05-01', budget: 35000, objective: 'Convert 15% of Starter users to Pro' } },
  { id: 'n24', type: 'Campaign', label: 'Competitive Takeout', properties: { status: 'Planning', start_date: '2026-05-15', budget: 50000, objective: 'Win 200 accounts from RivalPM' } },

  // Content
  { id: 'n25', type: 'Content', label: 'Project Mgmt Guide', properties: { format: 'Ebook', status: 'Published', downloads: 3200, word_count: 8500, funnel_stage: 'Top of funnel' } },
  { id: 'n26', type: 'Content', label: 'ROI Calculator', properties: { format: 'Interactive Tool', status: 'Published', monthly_uses: 1800, conversion_rate: '12%', funnel_stage: 'Middle of funnel' } },
  { id: 'n27', type: 'Content', label: 'Enterprise Security Whitepaper', properties: { format: 'Whitepaper', status: 'Published', downloads: 890, word_count: 4200, funnel_stage: 'Bottom of funnel' } },
  { id: 'n28', type: 'Content', label: 'Customer Story: TechStartup', properties: { format: 'Case Study', status: 'Draft', subject: 'How TechStartup saved 20hrs/week', funnel_stage: 'Bottom of funnel' } },
  { id: 'n29', type: 'Content', label: 'Weekly Newsletter', properties: { format: 'Email Series', status: 'Active', subscribers: 42000, frequency: 'Weekly', avg_open_rate: '28%' } },

  // Strategies
  { id: 'n30', type: 'Strategy', label: 'Product-Led Growth', properties: { priority: 'High', description: 'Drive adoption through free tier, in-app upgrades, and viral loops', kpis: ['Free-to-paid conversion', 'Activation rate', 'Viral coefficient'], status: 'Active' } },
  { id: 'n31', type: 'Strategy', label: 'Account-Based Marketing', properties: { priority: 'High', description: 'Targeted campaigns for top 200 enterprise prospects', kpis: ['Pipeline from target accounts', 'Engagement score', 'Meeting rate'], status: 'Active' } },
  { id: 'n32', type: 'Strategy', label: 'Content-Led SEO', properties: { priority: 'Medium', description: 'Build organic traffic through high-value content targeting mid-funnel keywords', kpis: ['Organic traffic', 'Keyword rankings', 'Content-attributed signups'], status: 'Active' } },

  // Metrics
  { id: 'n33', type: 'Metric', label: 'MRR', properties: { value: '$1.31M', trend: 'Up', change: '+8.2% MoM', target: '$1.5M by Q2', category: 'Revenue' } },
  { id: 'n34', type: 'Metric', label: 'CAC', properties: { value: '$185', trend: 'Down', change: '-12% QoQ', target: '<$150', category: 'Efficiency' } },
  { id: 'n35', type: 'Metric', label: 'NPS', properties: { value: 62, trend: 'Stable', benchmark: 'Industry avg: 45', category: 'Customer satisfaction' } },
  { id: 'n36', type: 'Metric', label: 'Trial-to-Paid', properties: { value: '18.5%', trend: 'Up', change: '+2.1pp QoQ', target: '22%', category: 'Conversion' } },
  { id: 'n37', type: 'Metric', label: 'Churn Rate', properties: { value: '3.2%', trend: 'Down', change: '-0.5pp MoM', target: '<2.5%', category: 'Retention' } },
  { id: 'n38', type: 'Metric', label: 'Organic Traffic', properties: { value: '85K/mo', trend: 'Up', change: '+15% MoM', target: '120K/mo', category: 'Acquisition' } },

  // Insights
  { id: 'n39', type: 'Insight', label: 'LinkedIn outperforms Google Ads for enterprise leads', properties: { confidence: 'High', source: 'Q1 Attribution Analysis', impact: 'Reallocate $15K/mo from Google Ads to LinkedIn', date: '2026-03-20', category: 'Channel Optimization' } },
  { id: 'n40', type: 'Insight', label: 'Freemium users who use templates convert 3x more', properties: { confidence: 'High', source: 'Product Analytics', impact: 'Add template onboarding flow', date: '2026-02-14', category: 'Product-Led Growth' } },
  { id: 'n41', type: 'Insight', label: 'Competitor RivalPM losing share in SMB segment', properties: { confidence: 'Medium', source: 'Win/Loss Analysis', impact: 'Launch competitive takeout campaign targeting RivalPM users', date: '2026-03-05', category: 'Competitive Intelligence' } },
  { id: 'n42', type: 'Insight', label: 'Case studies shorten sales cycle by 22%', properties: { confidence: 'High', source: 'Sales Data', impact: 'Produce 4 new case studies in Q2', date: '2026-01-30', category: 'Content Effectiveness' } },

  // Extra nodes for density
  { id: 'n43', type: 'Channel', label: 'Twitter/X', properties: { type: 'Social', followers: 9200, engagement_rate: '1.8%', status: 'Active' } },
  { id: 'n44', type: 'Content', label: 'Webinar: Future of PM', properties: { format: 'Webinar', registrations: 1200, attendance_rate: '45%', status: 'Completed' } },
  { id: 'n45', type: 'Metric', label: 'LTV', properties: { value: '$2,400', trend: 'Up', change: '+5% QoQ', category: 'Revenue' } },
  { id: 'n46', type: 'Audience', label: 'Mid-Market PMOs', properties: { size: '~8,000', job_titles: ['PMO Director', 'Portfolio Manager'], pain_points: ['Resource allocation', 'Portfolio visibility'] } },
  { id: 'n47', type: 'Content', label: 'Comparison: Acme vs RivalPM', properties: { format: 'Landing Page', monthly_visits: 4200, conversion_rate: '8.5%', status: 'Published' } },
  { id: 'n48', type: 'Campaign', label: 'Partner Co-Marketing', properties: { status: 'Active', start_date: '2026-03-01', budget: 25000, objective: 'Generate leads through integration partners' } },
];

// ─── Relationships ───

export const relationships: KGRelationship[] = [
  // Account owns things
  { id: 'r1', type: 'OWNS', sourceId: 'n1', targetId: 'n2', properties: {} },
  { id: 'r2', type: 'OWNS', sourceId: 'n1', targetId: 'n3', properties: {} },
  { id: 'r3', type: 'OWNS', sourceId: 'n1', targetId: 'n4', properties: {} },
  { id: 'r4', type: 'OWNS', sourceId: 'n1', targetId: 'n13', properties: {} },

  // Account competes with
  { id: 'r5', type: 'COMPETES_WITH', sourceId: 'n1', targetId: 'n5', properties: { intensity: 'High', overlap: 'Enterprise + SMB' } },
  { id: 'r6', type: 'COMPETES_WITH', sourceId: 'n1', targetId: 'n6', properties: { intensity: 'Medium', overlap: 'SMB' } },
  { id: 'r7', type: 'COMPETES_WITH', sourceId: 'n1', targetId: 'n7', properties: { intensity: 'Low', overlap: 'Starter tier' } },

  // Campaigns target audiences
  { id: 'r8', type: 'TARGETS', sourceId: 'n20', targetId: 'n8', properties: {} },
  { id: 'r9', type: 'TARGETS', sourceId: 'n21', targetId: 'n9', properties: {} },
  { id: 'r10', type: 'TARGETS', sourceId: 'n22', targetId: 'n8', properties: {} },
  { id: 'r11', type: 'TARGETS', sourceId: 'n22', targetId: 'n10', properties: {} },
  { id: 'r12', type: 'TARGETS', sourceId: 'n23', targetId: 'n10', properties: {} },
  { id: 'r13', type: 'TARGETS', sourceId: 'n24', targetId: 'n8', properties: {} },
  { id: 'r48', type: 'TARGETS', sourceId: 'n48', targetId: 'n46', properties: {} },

  // Campaigns use channels
  { id: 'r14', type: 'USES_CHANNEL', sourceId: 'n20', targetId: 'n14', properties: { budget_allocated: 25000 } },
  { id: 'r15', type: 'USES_CHANNEL', sourceId: 'n20', targetId: 'n15', properties: { budget_allocated: 18000 } },
  { id: 'r16', type: 'USES_CHANNEL', sourceId: 'n20', targetId: 'n17', properties: { budget_allocated: 8000 } },
  { id: 'r17', type: 'USES_CHANNEL', sourceId: 'n21', targetId: 'n15', properties: { budget_allocated: 45000 } },
  { id: 'r18', type: 'USES_CHANNEL', sourceId: 'n22', targetId: 'n16', properties: {} },
  { id: 'r19', type: 'USES_CHANNEL', sourceId: 'n22', targetId: 'n18', properties: {} },
  { id: 'r20', type: 'USES_CHANNEL', sourceId: 'n23', targetId: 'n17', properties: {} },
  { id: 'r41', type: 'USES_CHANNEL', sourceId: 'n22', targetId: 'n43', properties: {} },
  { id: 'r42', type: 'USES_CHANNEL', sourceId: 'n24', targetId: 'n14', properties: { budget_allocated: 20000 } },

  // Campaigns produce content
  { id: 'r21', type: 'PRODUCES', sourceId: 'n20', targetId: 'n25', properties: {} },
  { id: 'r22', type: 'PRODUCES', sourceId: 'n21', targetId: 'n27', properties: {} },
  { id: 'r23', type: 'PRODUCES', sourceId: 'n22', targetId: 'n44', properties: {} },
  { id: 'r24', type: 'PRODUCES', sourceId: 'n23', targetId: 'n26', properties: {} },
  { id: 'r43', type: 'PRODUCES', sourceId: 'n24', targetId: 'n47', properties: {} },

  // Strategies executed by campaigns
  { id: 'r25', type: 'EXECUTES', sourceId: 'n20', targetId: 'n30', properties: {} },
  { id: 'r26', type: 'EXECUTES', sourceId: 'n21', targetId: 'n31', properties: {} },
  { id: 'r27', type: 'EXECUTES', sourceId: 'n22', targetId: 'n32', properties: {} },
  { id: 'r28', type: 'EXECUTES', sourceId: 'n23', targetId: 'n30', properties: {} },

  // Metrics tracked by campaigns/strategies
  { id: 'r29', type: 'TRACKS', sourceId: 'n20', targetId: 'n33', properties: {} },
  { id: 'r30', type: 'TRACKS', sourceId: 'n21', targetId: 'n34', properties: {} },
  { id: 'r31', type: 'TRACKS', sourceId: 'n30', targetId: 'n36', properties: {} },
  { id: 'r32', type: 'TRACKS', sourceId: 'n32', targetId: 'n38', properties: {} },
  { id: 'r44', type: 'TRACKS', sourceId: 'n1', targetId: 'n37', properties: {} },
  { id: 'r45', type: 'TRACKS', sourceId: 'n1', targetId: 'n45', properties: {} },
  { id: 'r46', type: 'TRACKS', sourceId: 'n1', targetId: 'n35', properties: {} },

  // Insights generated
  { id: 'r33', type: 'GENERATES', sourceId: 'n15', targetId: 'n39', properties: {} },
  { id: 'r34', type: 'GENERATES', sourceId: 'n4', targetId: 'n40', properties: {} },
  { id: 'r35', type: 'GENERATES', sourceId: 'n5', targetId: 'n41', properties: {} },
  { id: 'r36', type: 'GENERATES', sourceId: 'n28', targetId: 'n42', properties: {} },

  // Insights inform strategies/campaigns
  { id: 'r37', type: 'INFORMS', sourceId: 'n39', targetId: 'n21', properties: {} },
  { id: 'r38', type: 'INFORMS', sourceId: 'n40', targetId: 'n23', properties: {} },
  { id: 'r39', type: 'INFORMS', sourceId: 'n41', targetId: 'n24', properties: {} },
  { id: 'r47', type: 'INFORMS', sourceId: 'n42', targetId: 'n22', properties: {} },

  // Audiences have personas
  { id: 'r40', type: 'HAS_PERSONA', sourceId: 'n8', targetId: 'n11', properties: {} },
  { id: 'r49', type: 'HAS_PERSONA', sourceId: 'n10', targetId: 'n12', properties: {} },

  // Products part of campaigns
  { id: 'r50', type: 'PART_OF', sourceId: 'n2', targetId: 'n20', properties: {} },
  { id: 'r51', type: 'PART_OF', sourceId: 'n3', targetId: 'n21', properties: {} },
  { id: 'r52', type: 'PART_OF', sourceId: 'n4', targetId: 'n23', properties: {} },

  // Content uses channels
  { id: 'r53', type: 'USES_CHANNEL', sourceId: 'n29', targetId: 'n17', properties: {} },

  // Cross influences
  { id: 'r54', type: 'INFLUENCES', sourceId: 'n30', targetId: 'n32', properties: { description: 'PLG content feeds SEO strategy' } },
  { id: 'r55', type: 'INFLUENCES', sourceId: 'n31', targetId: 'n24', properties: { description: 'ABM targeting informs competitive takeout' } },

  // Depends on
  { id: 'r56', type: 'DEPENDS_ON', sourceId: 'n24', targetId: 'n47', properties: { reason: 'Comparison page needed before campaign launch' } },
  { id: 'r57', type: 'DEPENDS_ON', sourceId: 'n21', targetId: 'n27', properties: { reason: 'Security whitepaper needed for enterprise credibility' } },
];

// ─── Combined export ───

export const knowledgeGraph: KnowledgeGraph = {
  nodeTypes,
  relationshipTypes,
  nodes,
  relationships,
};