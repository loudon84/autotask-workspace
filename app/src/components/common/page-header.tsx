type PageHeaderProps = {
  title: string;
  description?: string;
  /** 右侧操作区；与 children 等价，优先取 actions */
  actions?: React.ReactNode;
  children?: React.ReactNode;
};

export function PageHeader({
  title,
  description,
  actions,
  children,
}: PageHeaderProps) {
  return (
    <div className="flex flex-wrap items-end justify-between gap-2">
      <div>
        <h2 className="text-2xl font-bold tracking-tight">{title}</h2>
        {description && (
          <p className="text-muted-foreground">{description}</p>
        )}
      </div>
      {actions ?? children}
    </div>
  );
}
