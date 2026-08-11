import { Badge } from "@/components/ui/badge";
import { useBackendStatus } from "@/hooks/use-backend-status";

function formatTaskApiStatus(
  status: ReturnType<typeof useBackendStatus>["taskApiStatus"]
): string {
  if (status === "connected") {
    return "Connected";
  }
  if (status === "checking") {
    return "Checking";
  }
  return "Disconnected";
}

export function BackendStatusBadges() {
  const { authStatus, taskApiStatus, isRemote } = useBackendStatus();

  if (!isRemote) {
    return null;
  }

  return (
    <div className="hidden items-center gap-1.5 md:flex">
      <Badge
        className="font-normal text-xs"
        variant={authStatus === "logged-in" ? "default" : "destructive"}
      >
        Auth: {authStatus === "logged-in" ? "Logged in" : "Expired"}
      </Badge>
      <Badge
        className="font-normal text-xs"
        variant={taskApiStatus === "connected" ? "default" : "secondary"}
      >
        Task API: {formatTaskApiStatus(taskApiStatus)}
      </Badge>
    </div>
  );
}
