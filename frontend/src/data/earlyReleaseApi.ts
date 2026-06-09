import apiPublic from "@/lib/api-public";

export type SignupPolicy = {
  invite_only: boolean;
};

export type ValidateCodeResponse = {
  valid: boolean;
};

export const EARLY_RELEASE_CODE_STORAGE_KEY = "kene_early_release_code";

export async function getSignupPolicy(): Promise<SignupPolicy> {
  try {
    const response = await apiPublic.get<SignupPolicy>(
      "/api/v1/auth/signup-policy",
    );
    return response.data;
  } catch {
    return { invite_only: false };
  }
}

export async function validateAccessCode(
  code: string,
): Promise<ValidateCodeResponse> {
  const response = await apiPublic.post<ValidateCodeResponse>(
    "/api/v1/early-release/validate",
    { code },
  );
  return response.data;
}
