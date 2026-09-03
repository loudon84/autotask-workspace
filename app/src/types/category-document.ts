export type CategorySummary = {
  code: string;
  label: string;
  documentCount: number;
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
