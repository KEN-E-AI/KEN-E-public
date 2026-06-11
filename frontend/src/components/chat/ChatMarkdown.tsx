import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { cn } from "@/lib/utils";

type ChatMarkdownProps = {
  content: string;
  className?: string;
  flattenHeadings?: boolean;
};

/**
 * Renders chat/agent text as GitHub-flavored markdown.
 *
 * Unlike the home page's `MessageContent`, this stays visually neutral: it does
 * NOT impose `prose`/`prose-invert` colors or a fixed font size — color and size
 * are inherited from the caller's wrapper (the chat's `textSizeClass` + token
 * colors), so a rendered message looks like the surrounding document text, just
 * with bold/lists/headings/tables/code formatted instead of raw `**`/`#`.
 *
 * `flattenHeadings` renders h1–h3 at body size (bold only) for the reasoning
 * stream, where headings should stay quiet/small rather than scale up.
 */
export function ChatMarkdown({
  content,
  className,
  flattenHeadings = false,
}: ChatMarkdownProps) {
  const flatHeading = "text-[1em] font-semibold mt-2 mb-1 first:mt-0";
  return (
    <div className={cn("leading-relaxed", className)}>
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={{
          // `[font-size:inherit]` overrides the base `p { font-size }` element
          // rule so the paragraph honors the caller's wrapper size (11px in the
          // reasoning stream) instead of jumping to --text-body-lg.
          p: ({ children }) => (
            <p className="mb-3 last:mb-0 [font-size:inherit]">{children}</p>
          ),
          h1: ({ children }) => (
            <h1
              className={
                flattenHeadings
                  ? flatHeading
                  : "text-[1.25em] font-semibold mt-4 mb-2 first:mt-0"
              }
            >
              {children}
            </h1>
          ),
          h2: ({ children }) => (
            <h2
              className={
                flattenHeadings
                  ? flatHeading
                  : "text-[1.15em] font-semibold mt-4 mb-2 first:mt-0"
              }
            >
              {children}
            </h2>
          ),
          h3: ({ children }) => (
            <h3
              className={
                flattenHeadings
                  ? flatHeading
                  : "text-[1.05em] font-semibold mt-3 mb-1.5 first:mt-0"
              }
            >
              {children}
            </h3>
          ),
          ul: ({ children }) => (
            <ul className="list-disc pl-5 mb-3 space-y-1">{children}</ul>
          ),
          ol: ({ children }) => (
            <ol className="list-decimal pl-5 mb-3 space-y-1">{children}</ol>
          ),
          li: ({ children }) => <li className="leading-relaxed">{children}</li>,
          strong: ({ children }) => (
            <strong className="font-semibold">{children}</strong>
          ),
          em: ({ children }) => <em className="italic">{children}</em>,
          a: ({ href, children }) => (
            <a
              href={href}
              target="_blank"
              rel="noopener noreferrer"
              className="underline text-[var(--color-violet-500)] hover:opacity-80"
            >
              {children}
            </a>
          ),
          code: ({ className: codeClass, children }) => {
            const isBlock = /language-/.test(codeClass || "");
            return isBlock ? (
              <code className={cn("font-mono text-[0.9em]", codeClass)}>
                {children}
              </code>
            ) : (
              <code className="px-1 py-0.5 rounded bg-[var(--color-bg-elevated)] font-mono text-[0.9em]">
                {children}
              </code>
            );
          },
          pre: ({ children }) => (
            <pre className="p-3 mb-3 rounded-[var(--radius-md)] bg-[var(--color-bg-elevated)] overflow-x-auto text-[0.9em]">
              {children}
            </pre>
          ),
          blockquote: ({ children }) => (
            <blockquote className="border-l-2 border-[var(--color-border-default)] pl-3 my-3 text-[var(--color-text-secondary)]">
              {children}
            </blockquote>
          ),
          table: ({ children }) => (
            <div className="overflow-x-auto mb-3">
              <table className="min-w-full border-collapse text-[0.95em]">
                {children}
              </table>
            </div>
          ),
          th: ({ children }) => (
            <th className="border border-[var(--color-border-default)] px-2 py-1 text-left font-semibold">
              {children}
            </th>
          ),
          td: ({ children }) => (
            <td className="border border-[var(--color-border-default)] px-2 py-1">
              {children}
            </td>
          ),
          hr: () => (
            <hr className="my-4 border-[var(--color-border-default)]" />
          ),
        }}
      >
        {content}
      </ReactMarkdown>
    </div>
  );
}

export default ChatMarkdown;
