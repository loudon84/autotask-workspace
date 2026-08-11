import { Globe } from "lucide-react";
import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

type WebAddressInputProps = {
  value: string;
  onChange: (value: string) => void;
  onNavigate: (url: string) => void;
  disabled?: boolean;
};

function normalizeUrl(input: string): string {
  const trimmed = input.trim();
  if (!trimmed) {
    return "";
  }
  if (/^https?:\/\//i.test(trimmed)) {
    return trimmed;
  }
  return `https://${trimmed}`;
}

export function WebAddressInput({
  value,
  onChange,
  onNavigate,
  disabled,
}: WebAddressInputProps) {
  const [editing, setEditing] = useState(false);

  const handleSubmit = () => {
    const url = normalizeUrl(value);
    if (!url) {
      return;
    }
    onNavigate(url);
    setEditing(false);
  };

  return (
    <div className="flex flex-1 items-center gap-2">
      <Globe className="h-4 w-4 shrink-0 text-muted-foreground" />
      {editing ? (
        <Input
          autoFocus
          className="h-8 font-mono text-xs"
          disabled={disabled}
          onBlur={() => setEditing(false)}
          onChange={(e) => onChange(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter") {
              handleSubmit();
            }
            if (e.key === "Escape") {
              setEditing(false);
            }
          }}
          value={value}
        />
      ) : (
        <button
          className="flex-1 truncate text-left font-mono text-muted-foreground text-xs hover:text-foreground"
          onClick={() => setEditing(true)}
          type="button"
        >
          {value || "输入网址..."}
        </button>
      )}
      {editing && (
        <Button
          className="h-8"
          onClick={handleSubmit}
          size="sm"
          variant="outline"
        >
          前往
        </Button>
      )}
    </div>
  );
}
