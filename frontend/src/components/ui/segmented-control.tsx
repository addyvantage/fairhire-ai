import { cn } from "@/lib/utils"

type Segment<T extends string> = {
  label: string
  value: T
}

export function SegmentedControl<T extends string>({
  options,
  value,
  onChange,
}: {
  options: Segment<T>[]
  value: T
  onChange: (value: T) => void
}) {
  return (
    <div className="inline-flex rounded-xl border border-border bg-card p-1 shadow-[var(--shadow-xs)]">
      {options.map((option) => {
        const active = option.value === value
        return (
          <button
            key={option.value}
            type="button"
            onClick={() => onChange(option.value)}
            className={cn(
              "rounded-lg px-3 py-1.5 text-sm font-medium transition-colors",
              active ? "bg-primary-soft text-primary" : "text-muted-foreground hover:text-foreground"
            )}
          >
            {option.label}
          </button>
        )
      })}
    </div>
  )
}
