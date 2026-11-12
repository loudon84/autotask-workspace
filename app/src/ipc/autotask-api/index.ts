import {
  downloadCategoryDocument,
  request,
  uploadBoeAttachment,
  uploadCategoryDocuments,
  uploadInvoiceFiles,
} from "./handlers";

export const autotaskApi = {
  request,
  uploadInvoiceFiles,
  uploadBoeAttachment,
  uploadCategoryDocuments,
  downloadCategoryDocument,
};
