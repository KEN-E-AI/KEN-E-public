import { useState } from "react";
import { Plug } from "lucide-react";
import { PRODUCT_INTEGRATIONS } from "@/data/productIntegrationsWithLogos";

type IntegrationIconProps = {
  /** Display name (matched case-insensitively against PRODUCT_INTEGRATIONS). */
  name: string;
  className?: string;
};

/**
 * Renders an integration's logo with a Lucide icon fallback on load error,
 * resolving the asset from the shared PRODUCT_INTEGRATIONS registry — the same
 * img+fallback convention used by ProductIntegrationsEditor.
 */
export function IntegrationIcon({
  name,
  className = "size-10",
}: IntegrationIconProps) {
  const [hasImageError, setHasImageError] = useState(false);
  const integration = PRODUCT_INTEGRATIONS.find(
    (i) => i.name.toLowerCase() === name.toLowerCase(),
  );
  const FallbackIcon = integration?.icon ?? Plug;

  if (integration?.logo && !hasImageError) {
    return (
      <img
        src={integration.logo}
        alt={`${name} logo`}
        className={`${className} object-contain`}
        onError={() => setHasImageError(true)}
      />
    );
  }

  return (
    <div
      className={`${className} rounded bg-brand-light-blue/20 flex items-center justify-center`}
    >
      <FallbackIcon className="h-4 w-4 text-brand-medium-blue" />
    </div>
  );
}
