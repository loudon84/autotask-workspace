import { ChevronsUpDown } from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";
import { Button } from "@/components/ui/button";
import {
  Command,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
} from "@/components/ui/command";
import { formatOwnerLabel } from "@/features/srm-portals/owner-label";
import type { PortalOwnerCandidate } from "@/types/portal-account";

type OwnerPickerProps = {
  candidates: PortalOwnerCandidate[];
  value: string;
  onChange: (userId: string) => void;
};

export function OwnerPicker({ candidates, value, onChange }: OwnerPickerProps) {
  const [open, setOpen] = useState(false);
  const rootRef = useRef<HTMLDivElement>(null);

  const selected = useMemo(
    () => candidates.find((item) => item.userId === value),
    [candidates, value]
  );
  const selectedLabel = formatOwnerLabel(
    selected?.name,
    selected?.username
  );

  useEffect(() => {
    if (!open) {
      return;
    }
    const onPointerDown = (event: MouseEvent) => {
      if (!rootRef.current?.contains(event.target as Node)) {
        setOpen(false);
      }
    };
    document.addEventListener("mousedown", onPointerDown);
    return () => document.removeEventListener("mousedown", onPointerDown);
  }, [open]);

  return (
    <div className="relative" ref={rootRef}>
      <Button
        aria-expanded={open}
        aria-label="归属人"
        className="w-full justify-between font-normal"
        onClick={() => setOpen((current) => !current)}
        type="button"
        variant="outline"
      >
        <span className="truncate">
          {selectedLabel || "选择归属人"}
        </span>
        <ChevronsUpDown className="size-3.5 opacity-50" />
      </Button>
      {open ? (
        <div className="absolute z-50 mt-1 w-full rounded-md border bg-popover shadow-md">
          <Command>
            <CommandInput placeholder="搜索姓名或工号" />
            <CommandList>
              <CommandEmpty>没有匹配的人</CommandEmpty>
              <CommandGroup>
                {candidates.map((candidate) => {
                  const label = formatOwnerLabel(
                    candidate.name,
                    candidate.username
                  );
                  return (
                    <CommandItem
                      data-checked={candidate.userId === value || undefined}
                      key={candidate.userId}
                      onSelect={() => {
                        onChange(candidate.userId);
                        setOpen(false);
                      }}
                      value={`${candidate.name} ${candidate.username ?? ""} ${candidate.userId}`}
                    >
                      <span className="truncate">{label || candidate.userId}</span>
                    </CommandItem>
                  );
                })}
              </CommandGroup>
            </CommandList>
          </Command>
        </div>
      ) : null}
    </div>
  );
}
