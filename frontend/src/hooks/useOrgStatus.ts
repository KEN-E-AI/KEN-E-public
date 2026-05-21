// Stub — BL-PRD-04 will replace the body. Do not change the return-shape
// contract without Billing review.

export type OrgStatus = {
  status:
    | "active"
    | "inactive_overage"
    | "inactive_past_due"
    | "inactive_canceled"
    | "approaching_limit";
  reason_message: string | null;
  cta_url: string | null;
  refetch: () => Promise<void>;
};

export function useOrgStatus(): OrgStatus {
  return {
    status: "active",
    reason_message: null,
    cta_url: null,
    refetch: () => Promise.resolve(),
  };
}
