import { useEffect, useState } from "react";
import ExternalLink from "@/components/external-link";
import { getAuthEndpointConfig } from "@/actions/auth";
import {
  buildSdmsCheckViewUrl,
  defaultAutoTaskEndpointConfig,
} from "@/types/endpoint-config";

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
  const [baseUrl, setBaseUrl] = useState(
    defaultAutoTaskEndpointConfig.sdmsWebBaseUrl
  );
  const label = display(checkNum) === "—" ? display(checkHeadId) : display(checkNum);
  const id = String(checkHeadId ?? "").trim();
  const href = id ? buildSdmsCheckViewUrl(baseUrl, id) : null;

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
