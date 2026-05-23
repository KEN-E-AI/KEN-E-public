import "vitest";
import type { AxeMatchers } from "vitest-axe/matchers";

// vitest-axe 0.1.0 augments `Vi.Assertion`, which vitest 3.x no longer
// exposes — vitest 3 re-exports `Assertion` from `@vitest/expect` directly.
// Bridge the matchers onto the modern interface so `expect(...).toHaveNoViolations()`
// type-checks.
declare module "vitest" {
  interface Assertion extends AxeMatchers {}
  interface AsymmetricMatchersContaining extends AxeMatchers {}
}
