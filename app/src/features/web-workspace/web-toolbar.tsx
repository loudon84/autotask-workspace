import {
  ArrowLeft,
  ArrowRight,
  ExternalLink,
  RefreshCw,
  X,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import type { WebTab } from "@/types/web-tab";
import { WebAddressInput } from "./web-address-input";

type WebToolbarProps = {
  activeTab: WebTab | null;
  addressValue: string;
  onAddressChange: (value: string) => void;
  onNavigate: (url: string) => void;
  onBack: () => void;
  onForward: () => void;
  onReload: () => void;
  onOpenExternal: () => void;
  onClose: () => void;
};

export function WebToolbar({
  activeTab,
  addressValue,
  onAddressChange,
  onNavigate,
  onBack,
  onForward,
  onReload,
  onOpenExternal,
  onClose,
}: WebToolbarProps) {
  return (
    <div className="flex items-center gap-1 border-b px-2 py-1.5">
      <Button
        className="h-8 w-8"
        disabled={!activeTab?.canGoBack}
        onClick={onBack}
        size="icon"
        variant="ghost"
      >
        <ArrowLeft className="h-4 w-4" />
      </Button>
      <Button
        className="h-8 w-8"
        disabled={!activeTab?.canGoForward}
        onClick={onForward}
        size="icon"
        variant="ghost"
      >
        <ArrowRight className="h-4 w-4" />
      </Button>
      <Button
        className="h-8 w-8"
        disabled={!activeTab}
        onClick={onReload}
        size="icon"
        variant="ghost"
      >
        <RefreshCw className="h-4 w-4" />
      </Button>

      <WebAddressInput
        disabled={!activeTab}
        onChange={onAddressChange}
        onNavigate={onNavigate}
        value={addressValue}
      />

      <Button
        className="h-8 w-8"
        disabled={!activeTab}
        onClick={onOpenExternal}
        size="icon"
        variant="ghost"
      >
        <ExternalLink className="h-4 w-4" />
      </Button>
      <Button
        className="h-8 w-8"
        disabled={!activeTab}
        onClick={onClose}
        size="icon"
        variant="ghost"
      >
        <X className="h-4 w-4" />
      </Button>
    </div>
  );
}
