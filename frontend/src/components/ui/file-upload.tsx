"use client"

import { useRef } from "react"
import { UploadCloud } from "lucide-react"
import { Card } from "@/components/ui/card"
import { Button } from "@/components/ui/button"

interface FileUploadProps {
  onFileSelect: (file: File) => void
  accept?: string
}

export function FileUpload({ onFileSelect, accept }: FileUploadProps) {
  const inputRef = useRef<HTMLInputElement>(null)

  return (
    <Card className="border-dashed border-2 p-8 text-center bg-background">
      <UploadCloud className="mx-auto h-10 w-10 text-muted-foreground" />
      <p className="mt-4 text-sm text-muted-foreground">
        Drag & drop your resume here, or click to upload
      </p>
      <Button
        variant="outline"
        className="mt-4"
        onClick={() => inputRef.current?.click()}
      >
        Select File
      </Button>
      <input
        ref={inputRef}
        type="file"
        accept={accept}
        className="hidden"
        onChange={(e) => {
          if (e.target.files?.[0]) {
            onFileSelect(e.target.files[0])
          }
        }}
      />
    </Card>
  )
}
