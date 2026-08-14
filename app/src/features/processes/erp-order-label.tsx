import { useEffect, useState } from "react";
import ExternalLink from "@/components/external-link";
import { getAuthEndpointConfig } from "@/actions/auth";
import {
  buildSdmsOmViewUrl,
  defaultAutoTaskEndpointConfig,
} from "@/types/endpoint-config";

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
  const [baseUrl, setBaseUrl] = useState(
    defaultAutoTaskEndpointConfig.sdmsWebBaseUrl
  );
  const label = display(orderNumber);
  const id = String(headerId ?? "").trim();
  const href = id ? buildSdmsOmViewUrl(baseUrl, id) : null;

  useEffect(() => {
    let cancelled = false;
    void getAuthEndpointConfig()
      .then((config) => {
        if (!cancelled && config.sdmsWebBaseUrl) {
          setBaseUrl(config.sdmsWebBaseUrl);
        }
      })
      .catch(() => {
        /* keep default */
      });
    return () => {
      cancelled = true;
    };
  }, []);

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
