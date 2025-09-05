import { useState, useMemo } from "react";
import { ChevronDown, ChevronRight, Code2 } from "lucide-react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@/components/ui/collapsible";
import { cn } from "@/lib/utils";

interface MessageContentProps {
  content: string;
  className?: string;
  isAssistant?: boolean;
}

interface ParsedContent {
  text: string;
  jsonData?: any;
}

function parseMessageContent(content: string): ParsedContent {
  // Look for patterns that indicate JSON data from agents
  // The format often looks like: {'function_call': {...}}{'function_response': {...}}actual text

  // First try to extract consecutive JSON-like objects at the beginning
  let jsonObjects = [];
  let currentPos = 0;

  // Helper function to find matching bracket
  function findMatchingBracket(str: string, startPos: number): number {
    let depth = 0;
    let inString = false;
    let escapeNext = false;
    let quoteChar = "";

    for (let i = startPos; i < str.length; i++) {
      const char = str[i];

      if (escapeNext) {
        escapeNext = false;
        continue;
      }

      if (char === "\\") {
        escapeNext = true;
        continue;
      }

      if (!inString) {
        if (char === '"' || char === "'") {
          inString = true;
          quoteChar = char;
        } else if (char === "{") {
          depth++;
        } else if (char === "}") {
          depth--;
          if (depth === 0) {
            return i;
          }
        }
      } else {
        if (char === quoteChar) {
          inString = false;
          quoteChar = "";
        }
      }
    }
    return -1;
  }

  // Try to extract Python-style dicts from the beginning
  while (currentPos < content.length) {
    // Skip whitespace
    while (currentPos < content.length && /\s/.test(content[currentPos])) {
      currentPos++;
    }

    // Check if we have a dict starting with {
    if (content[currentPos] === "{") {
      const endPos = findMatchingBracket(content, currentPos);
      if (endPos !== -1) {
        const dictStr = content.substring(currentPos, endPos + 1);
        try {
          // Convert Python dict format to JSON
          // This is a more robust conversion that handles nested quotes
          const jsonStr = dictStr
            .replace(/:\s*'/g, ': "')
            .replace(/'\s*:/g, '":')
            .replace(/,\s*'/g, ', "')
            .replace(/'\s*,/g, '",')
            .replace(/\{\s*'/g, '{"')
            .replace(/'\s*\}/g, '"}')
            .replace(/"\s*:\s*\{/g, '": {')
            .replace(/\}\s*,/g, "},")
            .replace(/'\s*\]/g, '"]')
            .replace(/\[\s*'/g, '["');

          const jsonObj = JSON.parse(jsonStr);

          // Check if it's function/debug data
          if (
            jsonObj.function_call ||
            jsonObj.function_response ||
            jsonObj.tool_calls ||
            jsonObj.type === "function"
          ) {
            jsonObjects.push(jsonObj);
            currentPos = endPos + 1;
            continue;
          }
        } catch (e) {
          // Not valid JSON, stop trying
          break;
        }
      }
    }
    break;
  }

  // If we found JSON objects, separate them from the text
  if (jsonObjects.length > 0) {
    const textPart = content.substring(currentPos).trim();
    // Combine all JSON objects into one for display
    const combinedJson =
      jsonObjects.length === 1 ? jsonObjects[0] : { debug_data: jsonObjects };

    return {
      text: textPart || "",
      jsonData: combinedJson,
    };
  }

  // Also check if content has both text and JSON parts separated by newlines
  const lines = content.split("\n");
  let jsonStartIndex = -1;
  let textPart = "";
  let jsonPart = "";

  // Find where JSON might start
  for (let i = 0; i < lines.length; i++) {
    const line = lines[i].trim();
    if (line.startsWith("{") || line.startsWith("[")) {
      // Found potential JSON start
      jsonStartIndex = i;
      textPart = lines.slice(0, i).join("\n").trim();
      jsonPart = lines.slice(i).join("\n");
      break;
    }
  }

  // If we found a split, try to parse the JSON part
  if (jsonStartIndex >= 0 && jsonPart) {
    try {
      const jsonData = JSON.parse(jsonPart);

      // Check if it's function/tool related JSON (debug data)
      if (
        jsonData.function_call ||
        jsonData.function_response ||
        jsonData.tool_calls ||
        jsonData.type === "function" ||
        jsonData.name ||
        jsonData.arguments
      ) {
        return {
          text: textPart || "", // Use empty string if no text part
          jsonData,
        };
      }
    } catch (e) {
      // Not valid JSON, continue with other patterns
    }
  }

  // Try to find JSON that starts with specific markers
  const jsonPatterns = [
    /```json\n?([\s\S]*?)```/,
    /\{[\s]*"function_call"[\s]*:[\s\S]*\}/,
    /\{[\s]*"function_response"[\s]*:[\s\S]*\}/,
    /\{[\s]*"tool_calls"[\s]*:[\s\S]*\}/,
    /\{[\s]*"type"[\s]*:[\s]*"function"[\s\S]*\}/,
    /\{[\s]*"name"[\s]*:[\s]*"[^"]*"[\s]*,[\s]*"arguments"[\s]*:[\s\S]*\}/,
  ];

  for (const pattern of jsonPatterns) {
    const match = content.match(pattern);
    if (match) {
      try {
        const jsonStr = match[1] || match[0];
        const jsonData = JSON.parse(jsonStr.replace(/```json\n?|```/g, ""));

        // Extract the text portion (everything before and after the JSON)
        const beforeJson = content.substring(0, match.index || 0).trim();
        const afterJson = content
          .substring((match.index || 0) + match[0].length)
          .trim();
        const textParts = [beforeJson, afterJson].filter(Boolean);

        return {
          text: textParts.join("\n").trim(), // Just the extracted text, no default message
          jsonData,
        };
      } catch (e) {
        // If JSON parsing fails, continue to next pattern
        continue;
      }
    }
  }

  // Also check if the entire content is valid JSON
  try {
    const trimmed = content.trim();
    if (trimmed.startsWith("{") || trimmed.startsWith("[")) {
      const jsonData = JSON.parse(trimmed);

      // Check if it's likely debug/function data
      if (
        jsonData.function_call ||
        jsonData.function_response ||
        jsonData.tool_calls ||
        jsonData.type === "function" ||
        jsonData.name ||
        jsonData.arguments
      ) {
        return {
          text: "", // No text part when entire content is JSON
          jsonData,
        };
      }
    }
  } catch (e) {
    // Not JSON, treat as regular text
  }

  return { text: content };
}

function formatJSON(data: any): string {
  return JSON.stringify(data, null, 2);
}

export function MessageContent({
  content,
  className,
  isAssistant = false,
}: MessageContentProps) {
  const [isOpen, setIsOpen] = useState(false);

  const parsedContent = useMemo(() => parseMessageContent(content), [content]);

  // If there's no JSON data, render as markdown
  if (!parsedContent.jsonData) {
    return (
      <div
        className={cn(
          "text-sm leading-relaxed prose prose-sm max-w-none",
          isAssistant ? "prose-invert" : "",
          className,
        )}
      >
        <ReactMarkdown
          remarkPlugins={[remarkGfm]}
          components={{
            // Custom components to ensure consistent styling
            p: ({ children }) => <p className="mb-2 last:mb-0">{children}</p>,
            ul: ({ children }) => (
              <ul className="list-disc pl-4 mb-2">{children}</ul>
            ),
            ol: ({ children }) => (
              <ol className="list-decimal pl-4 mb-2">{children}</ol>
            ),
            li: ({ children }) => <li className="mb-1">{children}</li>,
            strong: ({ children }) => (
              <strong className="font-bold">{children}</strong>
            ),
            code: ({ children }) => (
              <code
                className={cn(
                  "px-1 py-0.5 rounded text-xs font-mono",
                  isAssistant ? "bg-white/20" : "bg-gray-100",
                )}
              >
                {children}
              </code>
            ),
            pre: ({ children }) => (
              <pre
                className={cn(
                  "p-2 rounded overflow-x-auto",
                  isAssistant ? "bg-white/10" : "bg-gray-100",
                )}
              >
                {children}
              </pre>
            ),
            // Table components for proper table rendering
            table: ({ children }) => (
              <table
                className={cn(
                  "min-w-full divide-y mb-4",
                  isAssistant ? "divide-white/20" : "divide-gray-200",
                )}
              >
                {children}
              </table>
            ),
            thead: ({ children }) => (
              <thead className={cn(isAssistant ? "bg-white/10" : "bg-gray-50")}>
                {children}
              </thead>
            ),
            tbody: ({ children }) => (
              <tbody
                className={cn(
                  "divide-y",
                  isAssistant
                    ? "divide-white/10 bg-white/5"
                    : "divide-gray-200 bg-white",
                )}
              >
                {children}
              </tbody>
            ),
            tr: ({ children }) => <tr>{children}</tr>,
            th: ({ children }) => (
              <th
                className={cn(
                  "px-3 py-2 text-left text-xs font-medium uppercase tracking-wider",
                  isAssistant ? "text-white/90" : "text-gray-500",
                )}
              >
                {children}
              </th>
            ),
            td: ({ children }) => (
              <td
                className={cn(
                  "px-3 py-2 whitespace-nowrap text-sm",
                  isAssistant ? "text-white/80" : "text-gray-900",
                )}
              >
                {children}
              </td>
            ),
          }}
        >
          {content}
        </ReactMarkdown>
      </div>
    );
  }

  // Determine button label based on content
  const getButtonLabel = () => {
    if (parsedContent.jsonData.function_call) return "Function Call";
    if (parsedContent.jsonData.function_response) return "Function Response";
    if (parsedContent.jsonData.tool_calls) return "Tool Details";
    return "Details";
  };

  // Handle case where there's only JSON and no text - show a default message
  const displayText =
    parsedContent.text || (parsedContent.jsonData ? "Response received" : "");

  return (
    <div className={cn("space-y-2", className)}>
      {/* Main message text - render as markdown */}
      {displayText && (
        <div
          className={cn(
            "text-sm leading-relaxed prose prose-sm max-w-none",
            isAssistant ? "prose-invert" : "",
          )}
        >
          <ReactMarkdown
            remarkPlugins={[remarkGfm]}
            components={{
              p: ({ children }) => <p className="mb-2 last:mb-0">{children}</p>,
              ul: ({ children }) => (
                <ul className="list-disc pl-4 mb-2">{children}</ul>
              ),
              ol: ({ children }) => (
                <ol className="list-decimal pl-4 mb-2">{children}</ol>
              ),
              li: ({ children }) => <li className="mb-1">{children}</li>,
              strong: ({ children }) => (
                <strong className="font-bold">{children}</strong>
              ),
              code: ({ children }) => (
                <code
                  className={cn(
                    "px-1 py-0.5 rounded text-xs font-mono",
                    isAssistant ? "bg-white/20" : "bg-gray-100",
                  )}
                >
                  {children}
                </code>
              ),
              pre: ({ children }) => (
                <pre
                  className={cn(
                    "p-2 rounded overflow-x-auto",
                    isAssistant ? "bg-white/10" : "bg-gray-100",
                  )}
                >
                  {children}
                </pre>
              ),
              // Table components for proper table rendering
              table: ({ children }) => (
                <table
                  className={cn(
                    "min-w-full divide-y mb-4",
                    isAssistant ? "divide-white/20" : "divide-gray-200",
                  )}
                >
                  {children}
                </table>
              ),
              thead: ({ children }) => (
                <thead
                  className={cn(isAssistant ? "bg-white/10" : "bg-gray-50")}
                >
                  {children}
                </thead>
              ),
              tbody: ({ children }) => (
                <tbody
                  className={cn(
                    "divide-y",
                    isAssistant
                      ? "divide-white/10 bg-white/5"
                      : "divide-gray-200 bg-white",
                  )}
                >
                  {children}
                </tbody>
              ),
              tr: ({ children }) => <tr>{children}</tr>,
              th: ({ children }) => (
                <th
                  className={cn(
                    "px-3 py-2 text-left text-xs font-medium uppercase tracking-wider",
                    isAssistant ? "text-white/90" : "text-gray-500",
                  )}
                >
                  {children}
                </th>
              ),
              td: ({ children }) => (
                <td
                  className={cn(
                    "px-3 py-2 whitespace-nowrap text-sm",
                    isAssistant ? "text-white/80" : "text-gray-900",
                  )}
                >
                  {children}
                </td>
              ),
            }}
          >
            {displayText}
          </ReactMarkdown>
        </div>
      )}

      {/* Collapsible JSON pill */}
      <Collapsible open={isOpen} onOpenChange={setIsOpen}>
        <CollapsibleTrigger asChild>
          <button
            className={cn(
              "inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium transition-all",
              isAssistant
                ? "bg-white/20 text-white/90 hover:bg-white/30 border border-white/20"
                : "bg-dashboard-gray-100 text-dashboard-gray-700 hover:bg-dashboard-gray-200 border border-dashboard-gray-200",
            )}
          >
            {isOpen ? (
              <ChevronDown className="h-3 w-3" />
            ) : (
              <ChevronRight className="h-3 w-3" />
            )}
            <Code2 className="h-3 w-3" />
            <span>{getButtonLabel()}</span>
          </button>
        </CollapsibleTrigger>

        <CollapsibleContent className="mt-2">
          <div
            className={cn(
              "rounded-md p-3 overflow-x-auto",
              isAssistant
                ? "bg-white/10 border border-white/20"
                : "bg-dashboard-gray-50 border border-dashboard-gray-200",
            )}
          >
            <pre
              className={cn(
                "text-xs font-mono",
                isAssistant ? "text-white/90" : "text-dashboard-gray-700",
              )}
            >
              <code>{formatJSON(parsedContent.jsonData)}</code>
            </pre>
          </div>
        </CollapsibleContent>
      </Collapsible>
    </div>
  );
}

export default MessageContent;
