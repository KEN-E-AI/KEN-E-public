import { useMemo } from 'react';
import { useNavigate } from 'react-router';
import { Settings2, Clock, Calendar as CalendarIcon, PlayCircle } from 'lucide-react';
import { Button } from './ui/button';
import { mockWorkflows } from '../data/mockData';
import { scheduleOccurrencesInRange } from '../lib/scheduleOccurrences';

type Props = {
  rangeStart: Date;
  rangeEnd: Date;
};

function formatDate(d: Date): string {
  return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
}

export function ProjectsInRangePanel({ rangeStart, rangeEnd }: Props) {
  const navigate = useNavigate();

  const startMs = rangeStart.getTime();
  const endMs = rangeEnd.getTime();
  const inRange = useMemo(() => {
    const start = new Date(startMs);
    const end = new Date(endMs);
    return mockWorkflows
      .filter(w => w.type === 'freeform')
      .map(w => ({
        workflow: w,
        occurrences: scheduleOccurrencesInRange(w.schedule, start, end),
      }))
      .filter(entry => entry.occurrences.length > 0)
      .sort((a, b) => a.occurrences[0].getTime() - b.occurrences[0].getTime());
  }, [startMs, endMs]);

  return (
    <div className="rounded-[var(--radius-md)] border border-[var(--color-border-default)] bg-[var(--color-bg-elevated)]">
      <div className="flex items-center justify-between px-4 py-3 border-b border-[var(--color-border-default)]">
        <div className="flex items-center gap-2">
          <CalendarIcon className="size-4 text-[var(--color-violet-500)]" />
          <h3 className="text-sm">Projects in view</h3>
          <span className="text-[0.625rem] text-muted-foreground">
            {formatDate(rangeStart)} – {formatDate(rangeEnd)}
          </span>
        </div>
        <span className="text-xs text-muted-foreground">{inRange.length} scheduled</span>
      </div>

      {inRange.length === 0 ? (
        <div className="px-4 py-6 text-center text-xs text-muted-foreground">
          No projects scheduled in this range.
        </div>
      ) : (
        <ul className="divide-y divide-[var(--color-border-default)]">
          {inRange.map(({ workflow: wf, occurrences }) => (
            <li
              key={`${wf.id}-${rangeStart.getTime()}-${rangeEnd.getTime()}`}
              className="flex items-start gap-3 px-4 py-3"
            >
              <PlayCircle className="size-4 text-[var(--color-violet-500)] shrink-0 mt-0.5" />
              <div className="flex-1 min-w-0">
                <p className="text-sm truncate">{wf.name}</p>
                <div className="flex items-center gap-3 mt-0.5 text-[0.6875rem] text-muted-foreground">
                  <span className="flex items-center gap-1">
                    <Clock className="size-3" />
                    {wf.schedule}
                  </span>
                  <span>{occurrences.length} run{occurrences.length === 1 ? '' : 's'} in view</span>
                </div>
                <div className="flex flex-wrap gap-1 mt-1.5">
                  {occurrences.map((occ, i) => (
                    <span
                      key={`${occ.getTime()}-${i}`}
                      className="text-[0.625rem] px-1.5 py-0.5 rounded-full bg-[var(--color-violet-100)] text-[var(--color-violet-600)] border border-[var(--color-violet-200)]"
                    >
                      {formatDate(occ)}
                    </span>
                  ))}
                </div>
              </div>
              <Button
                variant="outline"
                size="sm"
                onClick={() => navigate(`/workflows/automations/${wf.id}`)}
                className="gap-1.5 shrink-0"
              >
                <Settings2 className="size-3.5" />
                Configure
              </Button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
