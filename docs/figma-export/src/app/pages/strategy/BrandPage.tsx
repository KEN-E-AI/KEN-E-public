import { Palette, Type, MessageCircle, CheckCircle2, XCircle } from 'lucide-react';
import { Card } from '../../components/ui/card';
import { Badge } from '../../components/ui/badge';
import { Button } from '../../components/ui/button';

const brandColors = [
  { name: 'Primary Blue', hex: '#3B82F6', usage: 'CTAs, links, active states' },
  { name: 'Indigo', hex: '#6366F1', usage: 'Accents, highlights, gradients' },
  { name: 'Teal', hex: '#2EC4B6', usage: 'Success states, secondary actions' },
  { name: 'Slate Dark', hex: '#1E293B', usage: 'Headings, body text' },
  { name: 'Slate Light', hex: '#F1F5F9', usage: 'Backgrounds, dividers' },
];

const voiceAttributes = [
  { trait: 'Confident', description: 'Speak with authority. We know our craft.' },
  { trait: 'Approachable', description: 'Avoid jargon. Write like you\'re explaining to a smart friend.' },
  { trait: 'Forward-looking', description: 'Focus on outcomes and what\'s next, not limitations.' },
  { trait: 'Concise', description: 'Respect the reader\'s time. Every word earns its place.' },
];

const dosDonts = {
  dos: [
    'Use active voice',
    'Lead with benefits',
    'Include specific data points',
    'Address the reader directly',
  ],
  donts: [
    'Use "disruptive" or "innovative" without context',
    'Make unsubstantiated claims',
    'Use ALL CAPS for emphasis',
    'Start sentences with "We"',
  ],
};

export function BrandPage() {
  return (
    <div className="px-6 pb-6 space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="mb-1">Brand Guidelines</h2>
          <p className="text-sm text-muted-foreground">Voice, tone, visual identity, and messaging framework</p>
        </div>
        <Button variant="outline" size="sm">Edit</Button>
      </div>

      {/* Color Palette */}
      <Card className="p-5 space-y-4">
        <h3 className="text-sm flex items-center gap-2">
          <Palette className="size-4 text-[var(--color-violet-500)]" />
          Color Palette
        </h3>
        <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
          {brandColors.map(color => (
            <div key={color.name} className="space-y-2">
              <div
                className="h-16 rounded-[var(--radius-md)] border border-[var(--color-border-default)]"
                style={{ backgroundColor: color.hex }}
              />
              <div>
                <p className="text-xs">{color.name}</p>
                <p className="text-[0.625rem] text-muted-foreground font-mono">{color.hex}</p>
                <p className="text-[0.625rem] text-muted-foreground">{color.usage}</p>
              </div>
            </div>
          ))}
        </div>
      </Card>

      {/* Typography */}
      <Card className="p-5 space-y-4">
        <h3 className="text-sm flex items-center gap-2">
          <Type className="size-4 text-[var(--color-blue-500)]" />
          Typography
        </h3>
        <div className="space-y-3">
          <div className="p-3 rounded-[var(--radius-md)] bg-[var(--color-bg-secondary)]">
            <p className="text-xs text-muted-foreground mb-1">Display / Headings</p>
            <p className="text-lg" style={{ fontFamily: 'var(--font-display)' }}>Plus Jakarta Sans — Bold</p>
          </div>
          <div className="p-3 rounded-[var(--radius-md)] bg-[var(--color-bg-secondary)]">
            <p className="text-xs text-muted-foreground mb-1">Body / UI</p>
            <p className="text-sm" style={{ fontFamily: 'var(--font-body)' }}>Plus Jakarta Sans — Regular / Medium</p>
          </div>
        </div>
      </Card>

      {/* Voice & Tone */}
      <Card className="p-5 space-y-4">
        <h3 className="text-sm flex items-center gap-2">
          <MessageCircle className="size-4 text-[var(--color-teal-500)]" />
          Voice & Tone
        </h3>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          {voiceAttributes.map(attr => (
            <div key={attr.trait} className="p-3 rounded-[var(--radius-md)] bg-[var(--color-bg-secondary)]">
              <Badge variant="outline" className="mb-1.5">{attr.trait}</Badge>
              <p className="text-xs text-muted-foreground">{attr.description}</p>
            </div>
          ))}
        </div>
      </Card>

      {/* Do's & Don'ts */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <Card className="p-5 space-y-3">
          <h3 className="text-sm flex items-center gap-2 text-[var(--color-success)]">
            <CheckCircle2 className="size-4" />
            Do
          </h3>
          <div className="space-y-2">
            {dosDonts.dos.map(item => (
              <div key={item} className="flex items-center gap-2 text-xs p-2 rounded-[var(--radius-sm)] bg-[var(--color-success-bg)] text-[var(--color-success-text)]">
                <CheckCircle2 className="size-3 shrink-0" />
                {item}
              </div>
            ))}
          </div>
        </Card>
        <Card className="p-5 space-y-3">
          <h3 className="text-sm flex items-center gap-2 text-[var(--color-error)]">
            <XCircle className="size-4" />
            Don't
          </h3>
          <div className="space-y-2">
            {dosDonts.donts.map(item => (
              <div key={item} className="flex items-center gap-2 text-xs p-2 rounded-[var(--radius-sm)] bg-[var(--color-error-bg)] text-[var(--color-error-text)]">
                <XCircle className="size-3 shrink-0" />
                {item}
              </div>
            ))}
          </div>
        </Card>
      </div>
    </div>
  );
}
