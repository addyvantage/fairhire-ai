"use client"

import {
  ColumnDef,
  flexRender,
  getCoreRowModel,
  useReactTable,
} from "@tanstack/react-table"

interface DataTableProps<TData> {
  columns: ColumnDef<TData, any>[]
  data: TData[]
}

export function VirtualizedTable<TData>({
  columns,
  data,
}: DataTableProps<TData>) {
  const table = useReactTable({
    data,
    columns,
    getCoreRowModel: getCoreRowModel(),
  })

  return (
    <div className="overflow-hidden rounded-xl border bg-background shadow-[var(--shadow-xs)]">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b bg-muted/30">
            {table.getHeaderGroups().map((headerGroup) =>
              headerGroup.headers.map((header) => (
                <th
                  key={header.id}
                  className="px-4 py-2.5 text-left text-[11px] font-semibold uppercase tracking-wider text-muted-foreground"
                >
                  {flexRender(
                    header.column.columnDef.header,
                    header.getContext(),
                  )}
                </th>
              ))
            )}
          </tr>
        </thead>
        <tbody className="divide-y divide-border/60">
          {table.getRowModel().rows.map((row) => (
            <tr
              key={row.id}
              className="transition-colors duration-100 hover:bg-muted/30"
            >
              {row.getVisibleCells().map((cell) => (
                <td key={cell.id} className="px-4 py-3">
                  {flexRender(
                    cell.column.columnDef.cell,
                    cell.getContext(),
                  )}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
