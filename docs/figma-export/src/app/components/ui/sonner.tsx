// Lightweight Toaster placeholder that avoids the `sonner` package's
// module-level DOM manipulation (`document.head.appendChild(style)`)
// which throws in Figma Make's sandboxed iframe.
//
// If toast notifications are needed in the future, implement a custom
// React-based toast system or lazy-load sonner inside a dynamic import.

export function Toaster() {
  return null;
}
