import ExternalLink from "@/components/external-link";
import { useSdmsBaseUrl } from "@/features/processes/api/use-sdms-base-url";
import { buildSdmsDpViewUrl } from "@/types/endpoint-config";

function display(value: unknown): string {
  const text = String(value ?? "").trim();
  return text || "—";
}

export function SdmsDeliveryPlanLabel({
  headerId,
  docNo,
  labeled = true,
}: {
  headerId?: unknown;
  docNo?: unknown;
  labeled?: boolean;
}) {
  const baseUrl = useSdmsBaseUrl();
  const label = display(docNo);
  const id = String(headerId ?? "").trim();
  const href = id ? buildSdmsDpViewUrl(baseUrl, id) : null;
  const value = href ? (
    <ExternalLink className="text-primary" href={href} type="button">
      {label}
    </ExternalLink>
  ) : (
    label
  );

  if (!labeled) {
    return value;
  }

  return (
    <span>
      交货计划：
      {value}
    </span>
  );
}
