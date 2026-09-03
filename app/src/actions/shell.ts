import { ipc } from "@/ipc/manager";

export function openExternalLink(url: string) {
  return ipc.client.shell.openExternalLink({ url });
}

export function downloadFile(url: string) {
  return ipc.client.shell.downloadFile({ url });
}

export function selectInvoiceFiles() {
  return ipc.client.shell.selectInvoiceFiles();
}

export function selectCategoryDocumentFiles() {
  return ipc.client.shell.selectCategoryDocumentFiles();
}
