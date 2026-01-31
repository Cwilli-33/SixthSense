"use client";

import { useState, useCallback } from "react";
import { useRouter } from "next/navigation";
import { useDropzone } from "react-dropzone";
import {
  Upload,
  FileSpreadsheet,
  X,
  Loader2,
  CheckCircle,
  AlertCircle,
  Sparkles,
} from "lucide-react";

type ProcessingTier = "BASIC" | "STANDARD" | "PREMIUM";

const tiers = [
  {
    id: "BASIC" as ProcessingTier,
    name: "Basic",
    description: "Validation + Google Places data",
    features: ["Lead validation", "Business verification", "Google ratings"],
  },
  {
    id: "STANDARD" as ProcessingTier,
    name: "Standard",
    description: "Basic + UCC filings + Scoring",
    features: ["Everything in Basic", "UCC lien search", "Fit/Intent/Timing scores", "Deal sizing"],
    recommended: true,
  },
  {
    id: "PREMIUM" as ProcessingTier,
    name: "Premium",
    description: "Full enrichment + Sales intelligence",
    features: [
      "Everything in Standard",
      "AI-generated narratives",
      "Sales openers",
      "Objection handling",
    ],
  },
];

export default function UploadPage() {
  const router = useRouter();
  const [file, setFile] = useState<File | null>(null);
  const [tier, setTier] = useState<ProcessingTier>("STANDARD");
  const [isUploading, setIsUploading] = useState(false);
  const [uploadProgress, setUploadProgress] = useState(0);
  const [error, setError] = useState<string | null>(null);

  const onDrop = useCallback((acceptedFiles: File[]) => {
    setError(null);
    const selectedFile = acceptedFiles[0];

    if (selectedFile) {
      const extension = selectedFile.name.split(".").pop()?.toLowerCase();
      if (!["csv", "xlsx", "xls"].includes(extension || "")) {
        setError("Please upload a CSV or Excel file");
        return;
      }

      if (selectedFile.size > 10 * 1024 * 1024) {
        setError("File size must be less than 10MB");
        return;
      }

      setFile(selectedFile);
    }
  }, []);

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: {
      "text/csv": [".csv"],
      "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": [".xlsx"],
      "application/vnd.ms-excel": [".xls"],
    },
    maxFiles: 1,
  });

  const handleUpload = async () => {
    if (!file) return;

    setIsUploading(true);
    setError(null);
    setUploadProgress(0);

    try {
      const formData = new FormData();
      formData.append("file", file);
      formData.append("tier", tier);

      // Simulate progress for better UX
      const progressInterval = setInterval(() => {
        setUploadProgress((prev) => Math.min(prev + 10, 90));
      }, 200);

      const response = await fetch("/api/batches", {
        method: "POST",
        body: formData,
      });

      clearInterval(progressInterval);

      if (!response.ok) {
        const data = await response.json();
        throw new Error(data.detail || "Failed to upload file");
      }

      const data = await response.json();
      setUploadProgress(100);

      // Redirect to batch status page
      setTimeout(() => {
        router.push(`/dashboard/batches/${data.id || data.batch_id}`);
      }, 500);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to upload file");
      setIsUploading(false);
    }
  };

  const removeFile = () => {
    setFile(null);
    setError(null);
  };

  const formatFileSize = (bytes: number) => {
    if (bytes < 1024) return bytes + " B";
    if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + " KB";
    return (bytes / (1024 * 1024)).toFixed(1) + " MB";
  };

  return (
    <div className="p-8 max-w-4xl mx-auto">
      <div className="mb-8">
        <h1 className="text-3xl font-bold text-white mb-2">Upload Leads</h1>
        <p className="text-slate-400">
          Upload a CSV or Excel file to enrich your leads with business intelligence
        </p>
      </div>

      {/* File Upload Zone */}
      <div className="mb-8">
        {!file ? (
          <div
            {...getRootProps()}
            className={`border-2 border-dashed rounded-xl p-12 text-center cursor-pointer transition-all ${
              isDragActive
                ? "border-blue-500 bg-blue-500/10"
                : "border-slate-600 hover:border-slate-500 bg-slate-800/50"
            }`}
          >
            <input {...getInputProps()} />
            <div className="w-16 h-16 rounded-full bg-slate-700 flex items-center justify-center mx-auto mb-4">
              <Upload className="w-8 h-8 text-slate-400" />
            </div>
            <p className="text-lg text-white mb-2">
              {isDragActive ? "Drop your file here" : "Drag & drop your lead file"}
            </p>
            <p className="text-slate-400 mb-4">or click to browse</p>
            <p className="text-sm text-slate-500">Supports CSV, XLS, XLSX (max 10MB)</p>
          </div>
        ) : (
          <div className="bg-slate-800/50 border border-slate-700 rounded-xl p-6">
            <div className="flex items-center gap-4">
              <div className="w-12 h-12 rounded-lg bg-green-500/20 flex items-center justify-center">
                <FileSpreadsheet className="w-6 h-6 text-green-400" />
              </div>
              <div className="flex-1 min-w-0">
                <p className="text-white font-medium truncate">{file.name}</p>
                <p className="text-sm text-slate-400">{formatFileSize(file.size)}</p>
              </div>
              {!isUploading && (
                <button
                  onClick={removeFile}
                  className="p-2 text-slate-400 hover:text-white transition-colors"
                >
                  <X className="w-5 h-5" />
                </button>
              )}
            </div>

            {isUploading && (
              <div className="mt-4">
                <div className="flex items-center justify-between text-sm mb-2">
                  <span className="text-slate-400">Uploading...</span>
                  <span className="text-white">{uploadProgress}%</span>
                </div>
                <div className="h-2 bg-slate-700 rounded-full overflow-hidden">
                  <div
                    className="h-full bg-blue-500 transition-all duration-300"
                    style={{ width: `${uploadProgress}%` }}
                  />
                </div>
              </div>
            )}
          </div>
        )}

        {error && (
          <div className="mt-4 p-4 bg-red-500/10 border border-red-500/50 rounded-lg flex items-center gap-3 text-red-400">
            <AlertCircle className="w-5 h-5 flex-shrink-0" />
            {error}
          </div>
        )}
      </div>

      {/* Processing Tier Selection */}
      <div className="mb-8">
        <h2 className="text-xl font-semibold text-white mb-4">Select Processing Tier</h2>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          {tiers.map((t) => (
            <button
              key={t.id}
              onClick={() => setTier(t.id)}
              disabled={isUploading}
              className={`relative p-6 rounded-xl border-2 text-left transition-all ${
                tier === t.id
                  ? "border-blue-500 bg-blue-500/10"
                  : "border-slate-700 bg-slate-800/50 hover:border-slate-600"
              } ${isUploading ? "opacity-50 cursor-not-allowed" : ""}`}
            >
              {t.recommended && (
                <div className="absolute -top-3 left-4 px-3 py-1 bg-blue-500 text-white text-xs font-medium rounded-full flex items-center gap-1">
                  <Sparkles className="w-3 h-3" />
                  Recommended
                </div>
              )}
              <h3 className="text-lg font-semibold text-white mb-1">{t.name}</h3>
              <p className="text-sm text-slate-400 mb-4">{t.description}</p>
              <ul className="space-y-2">
                {t.features.map((feature, i) => (
                  <li key={i} className="flex items-center gap-2 text-sm text-slate-300">
                    <CheckCircle className="w-4 h-4 text-green-400" />
                    {feature}
                  </li>
                ))}
              </ul>
            </button>
          ))}
        </div>
      </div>

      {/* Upload Button */}
      <div className="flex justify-end">
        <button
          onClick={handleUpload}
          disabled={!file || isUploading}
          className="px-8 py-3 bg-blue-600 hover:bg-blue-700 disabled:bg-blue-600/50 disabled:cursor-not-allowed text-white font-medium rounded-lg transition-colors flex items-center gap-2"
        >
          {isUploading ? (
            <>
              <Loader2 className="w-5 h-5 animate-spin" />
              Processing...
            </>
          ) : (
            <>
              <Upload className="w-5 h-5" />
              Start Enrichment
            </>
          )}
        </button>
      </div>

      {/* Expected Columns Info */}
      <div className="mt-12 bg-slate-800/30 border border-slate-700 rounded-xl p-6">
        <h3 className="text-lg font-semibold text-white mb-4">Expected File Format</h3>
        <p className="text-slate-400 mb-4">Your file should include these columns:</p>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          {[
            { name: "Business Name", required: true },
            { name: "State", required: true },
            { name: "Phone", required: false },
            { name: "City", required: false },
            { name: "Industry", required: false },
            { name: "Monthly Revenue", required: false },
            { name: "TIB Months", required: false },
            { name: "Owner Name", required: false },
          ].map((col) => (
            <div
              key={col.name}
              className="flex items-center gap-2 text-sm"
            >
              <span
                className={`w-2 h-2 rounded-full ${
                  col.required ? "bg-red-400" : "bg-slate-500"
                }`}
              />
              <span className={col.required ? "text-white" : "text-slate-400"}>
                {col.name}
              </span>
            </div>
          ))}
        </div>
        <p className="text-sm text-slate-500 mt-4">
          <span className="text-red-400">●</span> Required fields &nbsp;
          <span className="text-slate-500">●</span> Optional fields
        </p>
      </div>
    </div>
  );
}
