import { apiRequest } from "@/services/api-client";
import { mapListResponse } from "@/services/dto-mappers";
import type {
  CategoryDocument,
  CategorySummary,
} from "@/types/category-document";

export async function listPortalCategories(): Promise<CategorySummary[]> {
  const data = await apiRequest<unknown>({
    method: "GET",
    path: "/portal-categories",
  });
  return mapListResponse<CategorySummary>(data);
}

export async function listCategoryDocuments(
  category: string
): Promise<CategoryDocument[]> {
  const data = await apiRequest<unknown>({
    method: "GET",
    path: `/portal-categories/${category}/documents`,
  });
  return mapListResponse<CategoryDocument>(data);
}

export async function deleteCategoryDocument(
  category: string,
  documentId: string
): Promise<void> {
  await apiRequest<void>({
    method: "DELETE",
    path: `/portal-categories/${category}/documents/${documentId}`,
  });
}
