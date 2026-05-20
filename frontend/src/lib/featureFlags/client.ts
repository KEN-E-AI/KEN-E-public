import type { FlagKey, FlagEvaluation } from "./types";
import api from "@/lib/api";

type EvaluateResponse = {
  evaluations: Record<string, FlagEvaluation>;
};

export async function evaluate(
  flagKeys: FlagKey[],
): Promise<Record<string, FlagEvaluation>> {
  const { data } = await api.post<EvaluateResponse>(
    "/api/v1/feature-flags/evaluate",
    { flag_keys: flagKeys },
  );
  return data.evaluations;
}
