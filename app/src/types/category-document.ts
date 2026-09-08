export type CategorySummary = {
  code: string;
  label: string;
  documentCount: number;
  extraFields: PortalExtraField[];
};

export type PortalExtraField = {
  key: string;
  label: string;
  fieldType: "email" | "text" | string;
  required: boolean;
  placeholder?: string;
  helpText?: string;
};

export type CategoryDocument = {
  id: string;
  category: string;
  originalFilename: string;
  byteSize: number;
  uploadedBy: string;
  uploadedByName: string;
  createdAt: string;
};
