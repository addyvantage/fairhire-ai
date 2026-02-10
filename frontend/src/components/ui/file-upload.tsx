"use client"

import { useCallback, useRef, useState } from "react"
import { UploadCloud } from "lucide-react"
import { cn } from "@/lib/utils"

interface FileUploadProps {
  onFileSelect: (file: File) => void
  accept?: string
  disabled?: boolean
}

export function FileUpload({ onFileSelect, accept, disabled }: FileUploadProps) {
  const inputRef = useRef<HTMLInputElement>(null)
  const [isDragOver, setIsDragOver] = useState(false)

  const handleDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault()
    e.stopPropagation()
    if (!disabled) setIsDragOver(true)
  }, [disabled])

  const handleDragLeave = useCallback((e: React.DragEvent) => {
    e.preventDefault()
    e.stopPropagation()
    setIsDragOver(false)
  }, [])

  const handleDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault()
      e.stopPropagation()
      setIsDragOver(false)
      if (disabled) return
      const file = e.dataTransfer.files?.[0]
      if (file) onFileSelect(file)
    },
    [onFileSelect, disabled]
  )

  return (
    <div
      role="button"
      tabIndex={0}
      onClick={() => !disabled && inputRef.current?.click()}
      onKeyDown={(e) => {
        if (e.key === "Enter" || e.key === " ") {
          e.preventDefault()
          inputRef.current?.click()
        }
      }}
      onDragOver={handleDragOver}
      onDragLeave={handleDragLeave}
      onDrop={handleDrop}
      className={cn(
        "group surface-card cursor-pointer border-2 border-dashed px-6 py-10 text-center transition-all duration-200",
        "border-border/80 hover:border-primary/30 hover:bg-primary-soft/40",
        isDragOver && "border-primary/40 bg-primary-soft/50",
        disabled && "pointer-events-none opacity-50"
      )}
    >
      <div
        className={cn(
          "mx-auto mb-4 flex h-12 w-12 items-center justify-center rounded-xl transition-colors duration-200",
          "bg-muted group-hover:bg-background",
          isDragOver && "bg-background"
        )}
      >
        <UploadCloud
          className={cn(
            "h-5 w-5 transition-all duration-200",
            "text-muted-foreground group-hover:text-primary",
            isDragOver && "text-primary scale-105"
          )}
        />
      </div>
      <p className="text-sm font-medium text-foreground">
        {isDragOver ? "Drop your file here" : "Drop your resume here, or click to browse"}
      </p>
      <p className="mt-1.5 text-xs text-muted-foreground">
        PDF or DOCX, up to 10 MB
      </p>
      <input
        ref={inputRef}
        type="file"
        accept={accept}
        className="hidden"
        onChange={(e) => {
          if (e.target.files?.[0]) {
            onFileSelect(e.target.files[0])
            e.target.value = ""
          }
        }}
      />
    </div>
  )
}
