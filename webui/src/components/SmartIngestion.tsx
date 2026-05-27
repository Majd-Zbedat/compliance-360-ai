"use client";

import { useCallback, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { CheckCircle2, FileText, Sparkles, Upload } from "lucide-react";

type DetectionStatus = "idle" | "analyzing-pdf" | "ocr-vision" | "transcribing-media";

const statusMessages: Record<DetectionStatus, string> = {
  idle: "AI-Powered Detection Ready",
  "analyzing-pdf": "Analyzing PDF...",
  "ocr-vision": "Running Smart Vision OCR...",
  "transcribing-media": "Transcribing Media...",
};

export function SmartIngestion() {
  const router = useRouter();
  const [isDragging, setIsDragging] = useState(false);
  const [files, setFiles] = useState<string[]>([]);
  const [currentStatus, setCurrentStatus] = useState<DetectionStatus>("idle");
  const inputRef = useRef<HTMLInputElement>(null);

  const simulateProcessing = (fileName: string) => {
    const ext = fileName.split(".").pop()?.toLowerCase();
    let status: DetectionStatus = "analyzing-pdf";
    if (ext === "png" || ext === "jpg" || ext === "jpeg" || ext === "tiff") {
      status = "ocr-vision";
    } else if (ext === "mp4" || ext === "mp3" || ext === "wav") {
      status = "transcribing-media";
    }
    setCurrentStatus(status);
    setTimeout(() => setCurrentStatus("idle"), 2000);
  };

  const addFiles = (names: string[]) => {
    setFiles((prev) => [...prev, ...names]);
    if (names[0]) simulateProcessing(names[0]);
  };

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
    addFiles(Array.from(e.dataTransfer.files).map((f) => f.name));
  }, []);

  const isProcessing = currentStatus !== "idle";

  return (
    <div>
      <div className="mb-4 flex items-center gap-2.5">
        <div className="h-5 w-0.5 rounded-full bg-accent" />
        <p className="text-xs font-semibold uppercase tracking-widest text-primary">
          Content Ingestion
        </p>
      </div>

      <div
        onDragOver={(e) => {
          e.preventDefault();
          setIsDragging(true);
        }}
        onDragLeave={() => setIsDragging(false)}
        onDrop={handleDrop}
        onClick={() => inputRef.current?.click()}
        className="cursor-pointer select-none rounded-lg border-2 border-dashed transition-all"
        style={{
          borderColor: isDragging ? "#86BC25" : "#D1D5DB",
          backgroundColor: isDragging ? "#F4FAE8" : "#FAFAFA",
        }}
      >
        <input
          ref={inputRef}
          type="file"
          accept=".pdf,.docx,.txt,.png,.jpg,.jpeg,.tiff,.mp4,.mp3,.wav"
          className="hidden"
          multiple
          onChange={(e) => {
            addFiles(Array.from(e.target.files || []).map((f) => f.name));
            router.push("/audits/new");
          }}
        />

        <div className="flex min-h-[220px] flex-col items-center justify-center p-10 text-center">
          <div
            className="mb-4 flex h-14 w-14 items-center justify-center rounded-lg transition-all"
            style={{
              backgroundColor: isDragging ? "#D4F0A0" : "#EEF1F4",
              color: isDragging ? "#2D6A0A" : "#003B5C",
            }}
          >
            <FileText size={24} />
          </div>

          <p className="mb-1.5 text-base font-semibold text-primary">Upload Documents or Media</p>
          <p className="mb-5 max-w-md text-sm text-[#9CA3AF]">
            Drag & drop contracts, PDFs, scanned images, or media files here
          </p>

          <button
            type="button"
            className="mb-6 inline-flex items-center gap-2.5 rounded-md bg-accent px-5 py-2.5 text-sm font-medium text-white"
            onClick={(e) => {
              e.stopPropagation();
              router.push("/audits/new");
            }}
          >
            <Upload size={14} />
            Analyze
          </button>

          <div
            className="inline-flex items-center gap-2 rounded-md px-4 py-2 text-xs font-medium transition-all"
            style={{
              backgroundColor: isProcessing ? "#EFF6FF" : "#F0F9E8",
              color: isProcessing ? "#1D4ED8" : "#2D6A0A",
              border: `1px solid ${isProcessing ? "#3B82F640" : "#86BC2540"}`,
            }}
          >
            <Sparkles size={13} className={isProcessing ? "animate-pulse" : ""} />
            <span>{statusMessages[currentStatus]}</span>
          </div>

          {files.length > 0 && (
            <div className="mt-6 w-full max-w-lg space-y-2">
              {files.slice(-3).map((name, i) => (
                <div
                  key={i}
                  className="flex items-center gap-2.5 rounded border border-border bg-white px-3 py-2 text-sm text-brand-ink"
                >
                  <CheckCircle2 size={14} className="text-accent" />
                  <span className="flex-1 truncate text-left">{name}</span>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
