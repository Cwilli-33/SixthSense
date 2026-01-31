"use client";

import { useSession } from "next-auth/react";
import Link from "next/link";
import { Upload, FileSpreadsheet, TrendingUp, Clock, ArrowRight } from "lucide-react";

export default function Dashboard() {
  const { data: session } = useSession();

  const stats = [
    { name: "Total Batches", value: "0", icon: FileSpreadsheet, color: "blue" },
    { name: "Leads Processed", value: "0", icon: TrendingUp, color: "green" },
    { name: "This Month", value: "0", icon: Clock, color: "purple" },
  ];

  return (
    <div className="p-8">
      {/* Header */}
      <div className="mb-8">
        <h1 className="text-3xl font-bold text-white mb-2">
          Welcome back, {session?.user?.name?.split(" ")[0] || "there"}!
        </h1>
        <p className="text-slate-400">
          Upload your leads to get started with intelligent enrichment
        </p>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-8">
        {stats.map((stat) => (
          <div
            key={stat.name}
            className="bg-slate-800/50 border border-slate-700 rounded-xl p-6"
          >
            <div className="flex items-center gap-4">
              <div
                className={`w-12 h-12 rounded-lg flex items-center justify-center ${
                  stat.color === "blue"
                    ? "bg-blue-500/20 text-blue-400"
                    : stat.color === "green"
                    ? "bg-green-500/20 text-green-400"
                    : "bg-purple-500/20 text-purple-400"
                }`}
              >
                <stat.icon className="w-6 h-6" />
              </div>
              <div>
                <p className="text-sm text-slate-400">{stat.name}</p>
                <p className="text-2xl font-bold text-white">{stat.value}</p>
              </div>
            </div>
          </div>
        ))}
      </div>

      {/* Quick Actions */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Upload Card */}
        <Link
          href="/dashboard/upload"
          className="group bg-gradient-to-br from-blue-600/20 to-blue-600/5 border border-blue-500/30 hover:border-blue-500/50 rounded-xl p-8 transition-all"
        >
          <div className="flex items-start justify-between">
            <div>
              <div className="w-14 h-14 rounded-xl bg-blue-500/20 flex items-center justify-center mb-4">
                <Upload className="w-7 h-7 text-blue-400" />
              </div>
              <h3 className="text-xl font-semibold text-white mb-2">Upload New Leads</h3>
              <p className="text-slate-400 mb-4">
                Upload a CSV or Excel file to enrich your leads with business intelligence
              </p>
              <div className="flex items-center text-blue-400 font-medium group-hover:gap-3 gap-2 transition-all">
                Get started <ArrowRight className="w-4 h-4" />
              </div>
            </div>
          </div>
        </Link>

        {/* Recent Activity Card */}
        <div className="bg-slate-800/50 border border-slate-700 rounded-xl p-8">
          <h3 className="text-xl font-semibold text-white mb-4">Recent Activity</h3>
          <div className="text-center py-8">
            <div className="w-16 h-16 rounded-full bg-slate-700/50 flex items-center justify-center mx-auto mb-4">
              <FileSpreadsheet className="w-8 h-8 text-slate-500" />
            </div>
            <p className="text-slate-400 mb-2">No batches yet</p>
            <p className="text-slate-500 text-sm">
              Upload your first lead file to get started
            </p>
          </div>
        </div>
      </div>

      {/* How It Works */}
      <div className="mt-12">
        <h2 className="text-xl font-semibold text-white mb-6">How It Works</h2>
        <div className="grid grid-cols-1 md:grid-cols-4 gap-6">
          {[
            {
              step: "1",
              title: "Upload",
              description: "Upload your CSV or Excel file with raw leads",
            },
            {
              step: "2",
              title: "Process",
              description: "We validate and enrich each lead with business data",
            },
            {
              step: "3",
              title: "Score",
              description: "AI scores leads based on fit, intent, and timing",
            },
            {
              step: "4",
              title: "Download",
              description: "Get an enriched file with sales intelligence",
            },
          ].map((item) => (
            <div key={item.step} className="relative">
              <div className="bg-slate-800/50 border border-slate-700 rounded-xl p-6">
                <div className="w-10 h-10 rounded-full bg-blue-600 flex items-center justify-center text-white font-bold mb-4">
                  {item.step}
                </div>
                <h3 className="text-lg font-semibold text-white mb-2">{item.title}</h3>
                <p className="text-slate-400 text-sm">{item.description}</p>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
