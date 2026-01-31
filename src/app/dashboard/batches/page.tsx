"use client";

import { useState, useEffect, useCallback } from "react";
import Link from "next/link";
import {
  FileSpreadsheet,
  Clock,
  CheckCircle,
  XCircle,
  Loader2,
  Download,
  Eye,
  RefreshCw,
} from "lucide-react";
import { formatDistanceToNow } from "date-fns";

interface Batch {
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
}

const statusConfig = {
  PENDING: { icon: Clock, color: "text-yellow-400", bg: "bg-yellow-400/20", label: "Pending" },
  PROCESSING: { icon: Loader2, color: "text-blue-400", bg: "bg-blue-400/20", label: "Processing" },
  COMPLETED: { icon: CheckCircle, color: "text-green-400", bg: "bg-green-400/20", label: "Completed" },
  FAILED: { icon: XCircle, color: "text-red-400", bg: "bg-red-400/20", label: "Failed" },
};

export default function BatchesPage() {
  const [batches, setBatches] = useState<Batch[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchBatches = useCallback(async () => {
    try {
      const response = await fetch("/api/batches");
      if (!response.ok) throw new Error("Failed to fetch batches");
      const data = await response.json();
      setBatches(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load batches");
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchBatches();
  }, [fetchBatches]);

  // Poll for updates if there are processing batches
  useEffect(() => {
    const hasProcessing = batches.some(
      (b) => b.status === "PROCESSING" || b.status === "PENDING"
    );
    if (!hasProcessing) return;

    const interval = setInterval(fetchBatches, 5000);
    return () => clearInterval(interval);
  }, [batches, fetchBatches]);

  const handleDownload = async (batchId: string) => {
    window.open(`/api/batches/${batchId}/download`, "_blank");
  };

  if (isLoading) {
    return (
      <div className="p-8 flex items-center justify-center min-h-[400px]">
        <Loader2 className="w-8 h-8 text-blue-500 animate-spin" />
      </div>
    );
  }

  return (
    <div className="p-8">
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="text-3xl font-bold text-white mb-2">Batch History</h1>
          <p className="text-slate-400">View and manage your lead enrichment batches</p>
        </div>
        <button
          onClick={fetchBatches}
          className="flex items-center gap-2 px-4 py-2 text-slate-300 hover:text-white transition-colors"
        >
          <RefreshCw className="w-4 h-4" />
          Refresh
        </button>
      </div>

      {error && (
        <div className="mb-6 p-4 bg-red-500/10 border border-red-500/50 rounded-lg text-red-400">
          {error}
        </div>
      )}

      {batches.length === 0 ? (
        <div className="text-center py-16 bg-slate-800/50 border border-slate-700 rounded-xl">
          <div className="w-16 h-16 rounded-full bg-slate-700/50 flex items-center justify-center mx-auto mb-4">
            <FileSpreadsheet className="w-8 h-8 text-slate-500" />
          </div>
          <h3 className="text-xl font-semibold text-white mb-2">No batches yet</h3>
          <p className="text-slate-400 mb-6">Upload your first lead file to get started</p>
          <Link
            href="/dashboard/upload"
            className="inline-flex items-center gap-2 px-6 py-3 bg-blue-600 hover:bg-blue-700 text-white font-medium rounded-lg transition-colors"
          >
            Upload Leads
          </Link>
        </div>
      ) : (
        <div className="bg-slate-800/50 border border-slate-700 rounded-xl overflow-hidden">
          <table className="w-full">
            <thead>
              <tr className="border-b border-slate-700">
                <th className="text-left px-6 py-4 text-sm font-medium text-slate-400">
                  File Name
                </th>
                <th className="text-left px-6 py-4 text-sm font-medium text-slate-400">Status</th>
                <th className="text-left px-6 py-4 text-sm font-medium text-slate-400">Tier</th>
                <th className="text-left px-6 py-4 text-sm font-medium text-slate-400">Leads</th>
                <th className="text-left px-6 py-4 text-sm font-medium text-slate-400">Created</th>
                <th className="text-right px-6 py-4 text-sm font-medium text-slate-400">
                  Actions
                </th>
              </tr>
            </thead>
            <tbody>
              {batches.map((batch) => {
                const status = statusConfig[batch.status];
                const StatusIcon = status.icon;
                return (
                  <tr
                    key={batch.id}
                    className="border-b border-slate-700/50 hover:bg-slate-700/20 transition-colors"
                  >
                    <td className="px-6 py-4">
                      <span className="text-white">{batch.fileName}</span>
                      {batch.createdBy && (
                        <div className="text-xs text-slate-400">
                          by {batch.createdBy.name || batch.createdBy.email}
                        </div>
                      )}
                    </td>
                    <td className="px-6 py-4">
                      <span
                        className={`inline-flex items-center gap-2 px-3 py-1 rounded-full text-sm ${status.bg} ${status.color}`}
                      >
                        <StatusIcon
                          className={`w-4 h-4 ${batch.status === "PROCESSING" ? "animate-spin" : ""}`}
                        />
                        {status.label}
                      </span>
                    </td>
                    <td className="px-6 py-4">
                      <span className="text-slate-300 text-sm">{batch.tier}</span>
                    </td>
                    <td className="px-6 py-4">
                      <div className="text-white">
                        {batch.processedLeads} / {batch.totalLeads}
                      </div>
                      {(batch.approvedLeads > 0 || batch.rejectedLeads > 0) && (
                        <div className="text-xs text-slate-400">
                          {batch.approvedLeads} approved, {batch.rejectedLeads} rejected
                        </div>
                      )}
                    </td>
                    <td className="px-6 py-4 text-slate-400">
                      {formatDistanceToNow(new Date(batch.createdAt), { addSuffix: true })}
                    </td>
                    <td className="px-6 py-4">
                      <div className="flex items-center justify-end gap-2">
                        <Link
                          href={`/dashboard/batches/${batch.id}`}
                          className="p-2 text-slate-400 hover:text-white transition-colors"
                          title="View details"
                        >
                          <Eye className="w-5 h-5" />
                        </Link>
                        {batch.status === "COMPLETED" && (
                          <button
                            onClick={() => handleDownload(batch.id)}
                            className="p-2 text-slate-400 hover:text-green-400 transition-colors"
                            title="Download results"
                          >
                            <Download className="w-5 h-5" />
                          </button>
                        )}
                      </div>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
