import { ChevronDown } from "lucide-react";
import { useState } from "react";
import { Button } from "@/components/ui/button";
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@/components/ui/collapsible";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import type { AutoTaskEndpointConfig } from "@/types/endpoint-config";
import { defaultAutoTaskEndpointConfig } from "@/types/endpoint-config";

interface EndpointConfigPanelProps {
  config: AutoTaskEndpointConfig;
  onChange: (config: AutoTaskEndpointConfig) => void;
}

export function EndpointConfigPanel({
  config,
  onChange,
}: EndpointConfigPanelProps) {
  const [open, setOpen] = useState(false);

  const update = (patch: Partial<AutoTaskEndpointConfig>) => {
    onChange({ ...config, ...patch });
  };

  return (
    <Collapsible onOpenChange={setOpen} open={open}>
      <CollapsibleTrigger asChild>
        <Button className="w-full gap-2" size="sm" variant="ghost">
          <ChevronDown
            className={`h-4 w-4 transition-transform ${open ? "rotate-180" : ""}`}
          />
          高级：Endpoint 配置
        </Button>
      </CollapsibleTrigger>
      <CollapsibleContent className="space-y-3 pt-2">
        <div className="space-y-2">
          <Label htmlFor="authBackendUrl">Auth Backend URL</Label>
          <Input
            id="authBackendUrl"
            onChange={(e) => update({ authBackendUrl: e.target.value })}
            placeholder={defaultAutoTaskEndpointConfig.authBackendUrl}
            value={config.authBackendUrl}
          />
        </div>
        <div className="space-y-2">
          <Label htmlFor="authPrefix">Auth Prefix</Label>
          <Input
            id="authPrefix"
            onChange={(e) => update({ authPrefix: e.target.value })}
            value={config.authPrefix}
          />
        </div>
        <div className="space-y-2">
          <Label htmlFor="taskBackendUrl">Task Backend URL</Label>
          <Input
            id="taskBackendUrl"
            onChange={(e) => update({ taskBackendUrl: e.target.value })}
            placeholder={defaultAutoTaskEndpointConfig.taskBackendUrl}
            value={config.taskBackendUrl}
          />
        </div>
        <div className="space-y-2">
          <Label htmlFor="taskPrefix">Task Prefix</Label>
          <Input
            id="taskPrefix"
            onChange={(e) => update({ taskPrefix: e.target.value })}
            value={config.taskPrefix}
          />
        </div>
        <div className="space-y-2">
          <Label htmlFor="rpaEngineUrl">RPA Engine URL</Label>
          <Input
            id="rpaEngineUrl"
            onChange={(e) => update({ rpaEngineUrl: e.target.value })}
            placeholder={defaultAutoTaskEndpointConfig.rpaEngineUrl}
            value={config.rpaEngineUrl}
          />
        </div>
        <div className="space-y-2">
          <Label htmlFor="sdmsWebBaseUrl">SDMS Web Base URL</Label>
          <Input
            id="sdmsWebBaseUrl"
            onChange={(e) => update({ sdmsWebBaseUrl: e.target.value })}
            placeholder={defaultAutoTaskEndpointConfig.sdmsWebBaseUrl}
            value={config.sdmsWebBaseUrl ?? ""}
          />
        </div>
      </CollapsibleContent>
    </Collapsible>
  );
}
