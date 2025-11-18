import { useMemo } from "react";

/**
 * Hook to detect unsaved changes in forms
 * Compares original and current values, trimming strings for accurate comparison
 *
 * @param original - Original data object
 * @param current - Current form data object
 * @param isEditing - Whether the form is in edit mode
 * @returns Whether there are unsaved changes
 */
export function useUnsavedChanges<T extends Record<string, any>>(
  original: T | null,
  current: T,
  isEditing: boolean,
): boolean {
  return useMemo(() => {
    if (!isEditing || !original) return false;

    // Compare each key in the objects
    for (const key in current) {
      const originalValue = original[key];
      const currentValue = current[key];

      // Handle string comparison with trimming
      if (
        typeof originalValue === "string" &&
        typeof currentValue === "string"
      ) {
        if (originalValue.trim() !== currentValue.trim()) {
          return true;
        }
      }
      // Handle undefined/null/empty string equivalence
      else if (
        (originalValue === undefined ||
          originalValue === null ||
          originalValue === "") &&
        (currentValue === undefined ||
          currentValue === null ||
          currentValue === "")
      ) {
        continue;
      }
      // Direct comparison for other types
      else if (originalValue !== currentValue) {
        return true;
      }
    }

    return false;
  }, [original, current, isEditing]);
}
