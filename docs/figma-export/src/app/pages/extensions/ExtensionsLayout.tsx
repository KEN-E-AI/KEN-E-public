import { Outlet, useLocation, Link } from 'react-router';
import { ArrowLeft, Puzzle } from 'lucide-react';
import { Button } from '../../components/ui/button';
import { getExtensionBySlug } from '../../data/extensionRegistry';

export function ExtensionsLayout() {
  const location = useLocation();
  const isIndex = location.pathname === '/extensions';

  // Extract extension slug from path like /extensions/dashboard-creator
  const segments = location.pathname.split('/');
  const extensionSlug = segments.length >= 3 ? segments[2] : null;
  const extension = extensionSlug ? getExtensionBySlug(extensionSlug) : null;

  return (
    <div className="flex flex-col h-full">
      {/* Page Header */}
      <div className="px-6 pt-6 pb-4">
        {isIndex ? (
          <div className="mb-4">
            <div className="flex items-center gap-3 mb-1">
              <div
                className="size-9 rounded-[var(--radius-md)] bg-[var(--color-violet-500)] flex items-center justify-center -rotate-2"
                style={{ boxShadow: 'var(--shadow-color-violet)' }}
              >
                <Puzzle className="size-4 text-[var(--color-text-inverse)]" />
              </div>
              <div>
                <h1 className="mb-0">Extensions</h1>
                <p className="text-sm text-muted-foreground">
                  Extend KEN-E with optional features and tools
                </p>
              </div>
            </div>
          </div>
        ) : (
          <div>
            <Link to="/extensions">
              <Button
                variant="ghost"
                size="sm"
                className="gap-2 mb-3 -ml-2 text-muted-foreground hover:text-foreground"
              >
                <ArrowLeft className="size-4" />
                Back to Extensions
              </Button>
            </Link>
            {extension && (
              <div className="flex items-center gap-3 mb-2">
                <div
                  className={`size-9 rounded-[var(--radius-md)] flex items-center justify-center ${extension.rotation}`}
                  style={{ backgroundColor: extension.color, boxShadow: extension.shadow }}
                >
                  <extension.icon className="size-4 text-[var(--color-text-inverse)]" />
                </div>
                <div>
                  <h1 className="mb-0">{extension.name}</h1>
                  <p className="text-sm text-muted-foreground">{extension.description}</p>
                </div>
              </div>
            )}
          </div>
        )}
      </div>

      {/* Content */}
      <div className="flex-1 overflow-auto">
        <Outlet />
      </div>
    </div>
  );
}
