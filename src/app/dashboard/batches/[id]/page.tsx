"use client";

import { useState, useEffect, useCallback } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import {
  ArrowLeft,
  Clock,
  CheckCircle,
  XCircle,
  Loader2,
  Download,
  FileSpreadsheet,
  TrendingUp,
  AlertTriangle,
} from "lucide-react";
import { format } from "date-fns";

interface BatchStatus {
  id: string;
  status: "PENDING" | "PROCESSING" | "COMPLETED" | "FAILED";
  createdAt: string;
  completedAt: string | null;
  totalLeads: number;
  processedLeads: number;
  approvedLeads: number;
  rejectedLeads: number;
  errorMessage: string | null;
  fileName: string;
  tier: string;
  createdBy?: {
    name: string | null;
    email: string | null;
  };
  team?: {
    name: string;
  };
}

const statusConfig = {
  PENDING: { icon: Clock, color: "text-yellow-400", bg: "bg-yellow-400/20", label: "Pending" },
  PROCESSING: { icon: Loader2, color: "text-blue-400", bg: "bg-blue-400/20", label: "Processing" },
  COMPLETED: { icon: CheckCircle, color: "text-green-400", bg: "bg-green-400/20", label: "Completed" },
  FAILED: { icon: XCircle, color: "text-red-400", bg: "bg-red-400/20", label: "Failed" },
};

export default function BatchDetailPage() {
  const params = useParams();
  const batchId = params.id as string;

  const [batch, setBatch] = useState<BatchStatus | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchBatchStatus = useCallback(async () => {
    try {
      const response = await fetch(`/api/batches/${batchId}`);
      if (!response.ok) {
        if (response.status === 404) {
          throw new Error("Batch not found");
        }
        throw new Error("Failed to fetch batch status");
      }
      const data = await response.json();
      setBatch(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load batch");
    } finally {
      setIsLoading(false);
    }
  }, [batchId]);

  useEffect(() => {
    fetchBatchStatus();
  }, [fetchBatchStatus]);

  // Poll for updates if batch is processing
  useEffect(() => {
    if (!batch || (batch.status !== "PROCESSING" && batch.status !== "PENDING")) {
      return;
    }

    const interval = setInterval(fetchBatchStatus, 2000);
    return () => clearInterval(interval);
  }, [batch, fetchBatchStatus]);

  const handleDownload = () => {
    window.open(`/api/batches/${batchId}/download`, "_blank");
  };

  if (isLoading) {
    return (
      <div className="p-8 flex items-center justify-center min-h-[400px]">
        <Loader2 className="w-8 h-8 text-blue-500 animate-spin" />
      </div>
    );
  }

  if (error || !batch) {
    return (
      <div className="p-8">
        <div className="text-center py-16 bg-slate-800/50 border border-slate-700 rounded-xl">
          <div className="w-16 h-16 rounded-full bg-red-500/20 flex items-center justify-center mx-auto mb-4">
            <AlertTriangle className="w-8 h-8 text-red-400" />
          </div>
          <h3 className="text-xl font-semibold text-white mb-2">
            {error || "Batch not found"}
          </h3>
          <Link
            href="/dashboard/batches"
            className="inline-flex items-center gap-2 px-6 py-3 bg-slate-700 hover:bg-slate-600 text-white font-medium rounded-lg transition-colors mt-4"
          >
            <ArrowLeft className="w-4 h-4" />
            Back to Batches
          </Link>
        </div>
      </div>
    );
  }

  const status = statusConfig[batch.status];
  const StatusIcon = status.icon;
  const progress = batch.totalLeads > 0
    ? Math.round((batch.processedLeads / batch.totalLeads) * 100)
    : 0;

  return (
    <div className="p-8">
      {/* Header */}
      <div className="mb-8">
        <Link
          href="/dashboard/batches"
          className="inline-flex items-center gap-2 text-slate-400 hover:text-white transition-colors mb-4"
        >
          <ArrowLeft className="w-4 h-4" />
          Back to Batches
        </Link>
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-3xl font-bold text-white mb-2">{batch.fileName}</h1>
            <p className="text-slate-400">
              {batch.tier} tier
              {batch.createdBy && (
                <span> &bull; Created by {batch.createdBy.name || batch.createdBy.email}</span>
              )}
            </p>
          </div>
          {batch.status === "COMPLETED" && (
            <button
              onClick={handleDownload}
              className="flex items-center gap-2 px-6 py-3 bg-green-600 hover:bg-green-700 text-white font-medium rounded-lg transition-colors"
            >
              <Download className="w-5 h-5" />
              Download Results
            </button>
          )}
        </div>
      </div>

      {/* Status Card */}
      <div className="bg-slate-800/50 border border-slate-700 rounded-xl p-8 mb-8">
        <div className="flex items-center gap-6 mb-8">
          <div className={`w-16 h-16 rounded-xl ${status.bg} flex items-center justify-center`}>
            <StatusIcon
              className={`w-8 h-8 ${status.color} ${batch.status === "PROCESSING" ? "animate-spin" : ""}`}
            />
          </div>
          <div>
            <p className="text-sm text-slate-400 mb-1">Status</p>
            <p className={`text-2xl font-semibold ${status.color}`}>{status.label}</p>
          </div>
        </div>

        {/* Progress Bar */}
        {(batch.status === "PROCESSING" || batch.status === "PENDING") && (
          <div className="mb-8">
            <div className="flex items-center justify-between text-sm mb-2">
              <span className="text-slate-400">Processing leads...</span>
              <span className="text-white">{progress}%</span>
            </div>
            <div className="h-3 bg-slate-700 rounded-full overflow-hidden">
              <div
                className="h-full bg-blue-500 transition-all duration-500"
                style={{ width: `${progress}%` }}
              />
            </div>
          </div>
        )}

        {/* Error Message */}
        {batch.status === "FAILED" && batch.errorMessage && (
          <div className="mb-8 p-4 bg-red-500/10 border border-red-500/30 rounded-lg">
            <p className="text-red-400">{batch.errorMessage}</p>
          </div>
        )}

        {/* Stats Grid */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-6">
          <div className="bg-slate-700/30 rounded-lg p-4">
            <div className="flex items-center gap-3 mb-2">
              <FileSpreadsheet className="w-5 h-5 text-slate-400" />
              <span className="text-sm text-slate-400">Total Leads</span>
            </div>
            <p className="text-2xl font-bold text-white">{batch.totalLeads}</p>
          </div>

          <div className="bg-slate-700/30 rounded-lg p-4">
            <div className="flex items-center gap-3 mb-2">
              <TrendingUp className="w-5 h-5 text-slate-400" />
              <span className="text-sm text-slate-400">Processed</span>
            </div>
            <p className="text-2xl font-bold text-white">{batch.processedLeads}</p>
          </div>

          <div className="bg-slate-700/30 rounded-lg p-4">
            <div className="flex items-center gap-3 mb-2">
              <CheckCircle className="w-5 h-5 text-green-400" />
              <span className="text-sm text-slate-400">Approved</span>
            </div>
            <p className="text-2xl font-bold text-green-400">{batch.approvedLeads}</p>
          </div>

          <div className="bg-slate-700/30 rounded-lg p-4">
            <div className="flex items-center gap-3 mb-2">
              <XCircle className="w-5 h-5 text-red-400" />
              <span className="text-sm text-slate-400">Rejected</span>
            </div>
            <p className="text-2xl font-bold text-red-400">{batch.rejectedLeads}</p>
          </div>
        </div>
      </div>

      {/* Timeline */}
      <div className="bg-slate-800/50 border border-slate-700 rounded-xl p-6">
        <h2 className="text-lg font-semibold text-white mb-4">Timeline</h2>
        <div className="space-y-4">
          <div className="flex items-center gap-4">
            <div className="w-10 h-10 rounded-full bg-blue-500/20 flex items-center justify-center">
              <Clock className="w-5 h-5 text-blue-400" />
            </div>
            <div>
              <p className="text-white">Batch Created</p>
              <p className="text-sm text-slate-400">
                {format(new Date(batch.createdAt), "PPpp")}
              </p>
            </div>
          </div>

          {batch.completedAt && (
            <div className="flex items-center gap-4">
              <div className="w-10 h-10 rounded-full bg-green-500/20 flex items-center justify-center">
                <CheckCircle className="w-5 h-5 text-green-400" />
              </div>
              <div>
                <p className="text-white">Processing Completed</p>
                <p className="text-sm text-slate-400">
                  {format(new Date(batch.completedAt), "PPpp")}
                </p>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
