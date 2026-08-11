import { cn } from "@/utils/tailwind";
import { Separator } from "@/components/ui/separator";
import { SidebarTrigger } from "@/components/ui/sidebar";

type AppHeaderProps = React.HTMLAttributes<HTMLElement> & {
  title?: string;
  children?: React.ReactNode;
};

export function AppHeader({ className, title, children, ...props }: AppHeaderProps) {
  return (
    <header
      className={cn(
        "sticky top-0 z-50 flex h-14 shrink-0 items-center gap-2 border-b bg-background px-4",
        className
      )}
      {...props}
    >
      <SidebarTrigger className="-ms-1" />
      <Separator orientation="vertical" className="h-4" />
      {title && (
        <h1 className="text-sm font-medium text-muted-foreground">{title}</h1>
      )}
      <div className="flex flex-1 items-center justify-end gap-2">{children}</div>
    </header>
  );
}
