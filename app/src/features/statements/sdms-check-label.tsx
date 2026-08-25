import ExternalLink from "@/components/external-link";
import { useSdmsBaseUrl } from "@/features/processes/api/use-sdms-base-url";
import { buildSdmsCheckViewUrl } from "@/types/endpoint-config";

function display(value: unknown): string {
  const text = String(value ?? "").trim();
  return text || "—";
}

export function SdmsCheckLabel({
  checkHeadId,
  checkNum,
}: {
  checkHeadId?: unknown;
  checkNum?: unknown;
}) {
  const baseUrl = useSdmsBaseUrl();
  const label = display(checkNum) === "—" ? display(checkHeadId) : display(checkNum);
  const id = String(checkHeadId ?? "").trim();
  const href = id ? buildSdmsCheckViewUrl(baseUrl, id) : null;

  return (
    <span>
      SDMS对账单：
      {href ? (
        <ExternalLink className="text-primary" href={href} type="button">
          {label}
        </ExternalLink>
      ) : (
        label
      )}
    </span>
  );
}
