import Link from "next/link";
import {
  Upload,
  Zap,
  Target,
  TrendingUp,
  Shield,
  Users,
  ArrowRight,
} from "lucide-react";

export default function Home() {
  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-900 via-slate-800 to-slate-900">
      {/* Navigation */}
      <nav className="border-b border-slate-700/50">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex items-center justify-between h-16">
            <div className="text-2xl font-bold text-white">
              Sixth<span className="text-blue-500">Sense</span>
            </div>
            <div className="flex items-center gap-4">
              <Link
                href="/auth/signin"
                className="text-slate-300 hover:text-white transition-colors"
              >
                Sign in
              </Link>
              <Link
                href="/auth/signup"
                className="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white font-medium rounded-lg transition-colors"
              >
                Get Started
              </Link>
            </div>
          </div>
        </div>
      </nav>

      {/* Hero Section */}
      <section className="pt-20 pb-32 px-4">
        <div className="max-w-4xl mx-auto text-center">
          <div className="inline-flex items-center gap-2 px-4 py-2 bg-blue-500/10 border border-blue-500/30 rounded-full text-blue-400 text-sm mb-8">
            <Zap className="w-4 h-4" />
            Lead Intelligence Platform
          </div>
          <h1 className="text-5xl md:text-6xl font-bold text-white mb-6 leading-tight">
            Transform Raw Leads Into{" "}
            <span className="text-transparent bg-clip-text bg-gradient-to-r from-blue-400 to-cyan-400">
              Sales Intelligence
            </span>
          </h1>
          <p className="text-xl text-slate-400 mb-10 max-w-2xl mx-auto">
            Upload your lead lists and get enriched data with business verification,
            scoring, and AI-powered sales intelligence in minutes.
          </p>
          <div className="flex flex-col sm:flex-row items-center justify-center gap-4">
            <Link
              href="/auth/signup"
              className="flex items-center gap-2 px-8 py-4 bg-blue-600 hover:bg-blue-700 text-white font-medium rounded-lg transition-colors text-lg"
            >
              Start Free <ArrowRight className="w-5 h-5" />
            </Link>
            <Link
              href="/auth/signin"
              className="flex items-center gap-2 px-8 py-4 bg-slate-700 hover:bg-slate-600 text-white font-medium rounded-lg transition-colors text-lg"
            >
              Sign In
            </Link>
          </div>
        </div>
      </section>

      {/* Features Grid */}
      <section className="py-20 px-4 bg-slate-800/30">
        <div className="max-w-6xl mx-auto">
          <div className="text-center mb-16">
            <h2 className="text-3xl font-bold text-white mb-4">
              Everything You Need to Close More Deals
            </h2>
            <p className="text-slate-400 max-w-2xl mx-auto">
              From raw CSV to actionable intelligence, we handle the entire enrichment pipeline
            </p>
          </div>

          <div className="grid md:grid-cols-3 gap-8">
            {[
              {
                icon: Upload,
                title: "Easy Upload",
                description:
                  "Drag and drop your CSV or Excel files. We handle the rest.",
              },
              {
                icon: Shield,
                title: "Data Verification",
                description:
                  "Validate businesses against Google Places and Secretary of State records.",
              },
              {
                icon: Target,
                title: "Smart Scoring",
                description:
                  "AI-powered FIT, INTENT, and TIMING scores to prioritize your outreach.",
              },
              {
                icon: TrendingUp,
                title: "UCC Analysis",
                description:
                  "Identify existing MCA positions and optimal refinance windows.",
              },
              {
                icon: Zap,
                title: "Sales Intelligence",
                description:
                  "AI-generated narratives, openers, and objection handling scripts.",
              },
              {
                icon: Users,
                title: "Team Collaboration",
                description:
                  "Share enriched leads with your team and track processing history.",
              },
            ].map((feature, i) => (
              <div
                key={i}
                className="bg-slate-800/50 border border-slate-700 rounded-xl p-6 hover:border-slate-600 transition-colors"
              >
                <div className="w-12 h-12 rounded-lg bg-blue-500/20 flex items-center justify-center mb-4">
                  <feature.icon className="w-6 h-6 text-blue-400" />
                </div>
                <h3 className="text-xl font-semibold text-white mb-2">{feature.title}</h3>
                <p className="text-slate-400">{feature.description}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* How It Works */}
      <section className="py-20 px-4">
        <div className="max-w-6xl mx-auto">
          <div className="text-center mb-16">
            <h2 className="text-3xl font-bold text-white mb-4">How It Works</h2>
            <p className="text-slate-400">Three simple steps to supercharge your leads</p>
          </div>

          <div className="grid md:grid-cols-3 gap-8">
            {[
              {
                step: "1",
                title: "Upload Your Leads",
                description:
                  "Upload a CSV or Excel file with your raw leads. Just need business name and state to get started.",
              },
              {
                step: "2",
                title: "We Enrich & Score",
                description:
                  "Our system validates, enriches with external data, and scores each lead using AI.",
              },
              {
                step: "3",
                title: "Download & Close",
                description:
                  "Get a complete Excel file with verified data, scores, and sales intelligence.",
              },
            ].map((step, i) => (
              <div key={i} className="text-center">
                <div className="w-16 h-16 rounded-full bg-blue-600 flex items-center justify-center text-2xl font-bold text-white mx-auto mb-6">
                  {step.step}
                </div>
                <h3 className="text-xl font-semibold text-white mb-3">{step.title}</h3>
                <p className="text-slate-400">{step.description}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* CTA Section */}
      <section className="py-20 px-4">
        <div className="max-w-4xl mx-auto">
          <div className="bg-gradient-to-br from-blue-600/20 to-cyan-600/20 border border-blue-500/30 rounded-2xl p-12 text-center">
            <h2 className="text-3xl font-bold text-white mb-4">Ready to Get Started?</h2>
            <p className="text-slate-300 mb-8 max-w-xl mx-auto">
              Join teams who are using SixthSense to close more deals with intelligent lead data.
            </p>
            <Link
              href="/auth/signup"
              className="inline-flex items-center gap-2 px-8 py-4 bg-blue-600 hover:bg-blue-700 text-white font-medium rounded-lg transition-colors text-lg"
            >
              Create Free Account <ArrowRight className="w-5 h-5" />
            </Link>
          </div>
        </div>
      </section>

      {/* Footer */}
      <footer className="border-t border-slate-700/50 py-8 px-4">
        <div className="max-w-6xl mx-auto flex flex-col md:flex-row items-center justify-between gap-4">
          <div className="text-2xl font-bold text-white">
            Sixth<span className="text-blue-500">Sense</span>
          </div>
          <p className="text-slate-400 text-sm">
            © 2025 SixthSense. All rights reserved.
          </p>
        </div>
      </footer>
    </div>
  );
}
