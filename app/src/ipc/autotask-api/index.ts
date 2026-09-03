import {
  downloadCategoryDocument,
  request,
  uploadCategoryDocuments,
  uploadInvoiceFiles,
} from "./handlers";

export const autotaskApi = {
  request,
  uploadInvoiceFiles,
  uploadCategoryDocuments,
  downloadCategoryDocument,
};
