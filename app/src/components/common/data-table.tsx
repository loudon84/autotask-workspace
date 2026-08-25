import {
  type Column,
  type ColumnDef,
  flexRender,
  getCoreRowModel,
  getFilteredRowModel,
  getPaginationRowModel,
  getSortedRowModel,
  useReactTable,
} from "@tanstack/react-table";
import type { CSSProperties } from "react";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Button } from "@/components/ui/button";
import { cn } from "@/utils/tailwind";
import { EmptyState } from "./empty-state";

declare module "@tanstack/react-table" {
  // eslint-disable-next-line @typescript-eslint/no-unused-vars
  interface ColumnMeta<TData, TValue> {
    sticky?: "left" | "right";
  }
}

type DataTableProps<TData> = {
  columns: ColumnDef<TData>[];
  data: TData[];
  pageSize?: number;
};

function stickyProps<TData>(
  column: Column<TData, unknown>,
  head = false
): { className?: string; style?: CSSProperties } {
  const sticky = column.columnDef.meta?.sticky;
  if (!sticky) {
    return {};
  }
  // 表格默认 border-collapse 时 right sticky 常失效；配合 border-separate + 内联 right/left
  return {
    className: cn(
      "sticky bg-background group-hover:bg-muted/50",
      head ? "z-30" : "z-20",
      sticky === "left" &&
        "border-r shadow-[6px_0_8px_-6px_rgba(0,0,0,0.12)]",
      sticky === "right" &&
        "border-l shadow-[-6px_0_8px_-6px_rgba(0,0,0,0.12)]"
    ),
    style:
      sticky === "left"
        ? { left: 0 }
        : {
            right: 0,
            // 操作列按钮文案较长，避免被压扁后 sticky 盒宽为 0 看起来像没固定
            minWidth: "10.5rem",
          },
  };
}

export function DataTable<TData>({
  columns,
  data,
  pageSize = 10,
}: DataTableProps<TData>) {
  const table = useReactTable({
    data,
    columns,
    getCoreRowModel: getCoreRowModel(),
    getFilteredRowModel: getFilteredRowModel(),
    getPaginationRowModel: getPaginationRowModel(),
    getSortedRowModel: getSortedRowModel(),
    initialState: { pagination: { pageSize } },
  });

  const hasSticky = columns.some(
    (column) =>
      "meta" in column &&
      column.meta &&
      typeof column.meta === "object" &&
      "sticky" in column.meta &&
      Boolean((column.meta as { sticky?: string }).sticky)
  );

  if (data.length === 0) {
    return <EmptyState />;
  }

  return (
    <div className="space-y-4">
      <div className="rounded-md border">
        <Table
          className={cn(
            hasSticky &&
              "w-max min-w-full border-separate border-spacing-0"
          )}
        >
          <TableHeader>
            {table.getHeaderGroups().map((headerGroup) => (
              <TableRow
                className={hasSticky ? "group" : undefined}
                key={headerGroup.id}
              >
                {headerGroup.headers.map((header) => {
                  const sticky = stickyProps(header.column, true);
                  return (
                    <TableHead
                      className={sticky.className}
                      key={header.id}
                      style={sticky.style}
                    >
                      {header.isPlaceholder
                        ? null
                        : flexRender(
                            header.column.columnDef.header,
                            header.getContext()
                          )}
                    </TableHead>
                  );
                })}
              </TableRow>
            ))}
          </TableHeader>
          <TableBody>
            {table.getRowModel().rows.map((row) => (
              <TableRow className={hasSticky ? "group" : undefined} key={row.id}>
                {row.getVisibleCells().map((cell) => {
                  const sticky = stickyProps(cell.column);
                  return (
                    <TableCell
                      className={sticky.className}
                      key={cell.id}
                      style={sticky.style}
                    >
                      {flexRender(
                        cell.column.columnDef.cell,
                        cell.getContext()
                      )}
                    </TableCell>
                  );
                })}
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>
      {table.getPageCount() > 1 && (
        <div className="flex items-center justify-end gap-2">
          <Button
            disabled={!table.getCanPreviousPage()}
            onClick={() => table.previousPage()}
            size="sm"
            variant="outline"
          >
            上一页
          </Button>
          <span className="text-muted-foreground text-sm">
            {table.getState().pagination.pageIndex + 1} / {table.getPageCount()}
          </span>
          <Button
            disabled={!table.getCanNextPage()}
            onClick={() => table.nextPage()}
            size="sm"
            variant="outline"
          >
            下一页
          </Button>
        </div>
      )}
    </div>
  );
}
