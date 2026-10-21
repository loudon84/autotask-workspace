import { openExternal, openPortal } from "@/actions/web-workspace";
import { srmOrderDetailUrl } from "@/features/processes/process-model";
import type { ProcessStage } from "@/types/process-instance";
import type { PortalAccount } from "@/types/portal-account";

/** 建单完成后在待回签打开门户自己签。 */
const SRM_SIGN_STAGES = new Set<ProcessStage>(["SIGN_REQUESTED"]);

export function canOpenSrmSign(stage: ProcessStage): boolean {
  return SRM_SIGN_STAGES.has(stage);
}

export async function openSrmOrderSign(
  portal: PortalAccount | undefined,
  poNo: string
): Promise<"external" | "workspace"> {
  const url = srmOrderDetailUrl(portal?.portalUrl ?? "", poNo);
  if (!portal || !url) {
    throw new Error("门户地址缺失，无法打开 SRM");
  }
  if (portal.clientOpenMode === "system_browser") {
    await openExternal(url);
    return "external";
  }
  await openPortal({
    portalId: portal.id,
    url,
    title: `${portal.portalName} ${poNo}`,
    sessionPartition: portal.clientSessionPartition,
    openMode: "webcontents",
  });
  return "workspace";
}
