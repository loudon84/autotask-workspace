import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ArtifactPreview } from "@/components/business/artifact-preview";
import type { Artifact } from "@/types/artifact";

const { downloadFileMock, useArtifactDownloadUrlMock } = vi.hoisted(() => ({
  downloadFileMock: vi.fn(),
  useArtifactDownloadUrlMock: vi.fn(),
}));

vi.mock("@/actions/shell", () => ({
  downloadFile: downloadFileMock,
}));

vi.mock("@/features/artifacts/api/use-artifacts", () => ({
  useArtifactDownloadUrl: (...args: unknown[]) =>
    useArtifactDownloadUrlMock(...args),
}));

const downloadUrl = "http://127.0.0.1:4520/signed/artifact-screenshot-1";

const screenshot: Artifact = {
  id: "artifact-screenshot-1",
  taskId: "task-1",
  runId: "run-1",
  name: "login-success.png",
  type: "screenshot",
  filePath: "runs/run-1/login-success.png",
  sizeText: "128 KB",
  mimeType: "image/png",
  createdAt: "2026-07-27T10:00:00Z",
};

const spreadsheet: Artifact = {
  ...screenshot,
  id: "artifact-xlsx-1",
  name: "order.xlsx",
  type: "download",
  filePath: "runs/run-1/order.xlsx",
  mimeType: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
};

describe("ArtifactPreview", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    downloadFileMock.mockResolvedValue(undefined);
    useArtifactDownloadUrlMock.mockReturnValue({
      data: downloadUrl,
      isError: false,
      isFetching: false,
      isLoading: false,
      isSuccess: true,
      refetch: vi.fn().mockResolvedValue({ data: downloadUrl }),
    });
  });

  it("loads and renders a screenshot in the evidence dialog", () => {
    render(<ArtifactPreview artifact={screenshot} loadScreenshot />);

    expect(useArtifactDownloadUrlMock).toHaveBeenCalledWith(
      "artifact-screenshot-1",
      true
    );
    expect(
      screen.getByRole("img", { name: "login-success.png" })
    ).toHaveAttribute("src", downloadUrl);
  });

  it("does not request an image while rendering a normal artifact list", () => {
    render(<ArtifactPreview artifact={screenshot} />);

    expect(useArtifactDownloadUrlMock).toHaveBeenCalledWith(
      "artifact-screenshot-1",
      false
    );
    expect(screen.queryByRole("img")).not.toBeInTheDocument();
    expect(screen.getByText("截图占位预览")).toBeInTheDocument();
  });

  it("downloads an XLSX artifact through the Electron download handler", async () => {
    const user = userEvent.setup();
    render(<ArtifactPreview allowDownload artifact={spreadsheet} />);

    await user.click(screen.getByRole("button", { name: "下载 order.xlsx" }));

    expect(useArtifactDownloadUrlMock).toHaveBeenCalledWith(
      "artifact-xlsx-1",
      false
    );
    expect(downloadFileMock).toHaveBeenCalledWith(downloadUrl);
  });
});
