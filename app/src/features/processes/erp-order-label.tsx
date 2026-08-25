import ExternalLink from "@/components/external-link";
import { useSdmsBaseUrl } from "@/features/processes/api/use-sdms-base-url";
import { buildSdmsOmViewUrl } from "@/types/endpoint-config";

function display(value: unknown): string {
  const text = String(value ?? "").trim();
  return text || "—";
}

export function ErpOrderLabel({
  headerId,
  orderNumber,
}: {
  headerId?: unknown;
  orderNumber?: unknown;
}) {
  const baseUrl = useSdmsBaseUrl();
  const label = display(orderNumber);
  const id = String(headerId ?? "").trim();
  const href = id ? buildSdmsOmViewUrl(baseUrl, id) : null;

  return (
    <span>
      ERP 订单：
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
