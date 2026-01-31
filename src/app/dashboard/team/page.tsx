"use client";

import { useState } from "react";
import { useSession } from "next-auth/react";
import {
  Users,
  UserPlus,
  Mail,
  Shield,
  Trash2,
  Loader2,
  CheckCircle,
  X,
} from "lucide-react";

interface TeamMember {
  id: string;
  name: string;
  email: string;
  role: "OWNER" | "ADMIN" | "MEMBER";
  joinedAt: string;
}

// Mock data for now - will be replaced with real API calls
const mockMembers: TeamMember[] = [];

export default function TeamPage() {
  const { data: session } = useSession();
  const [members, setMembers] = useState<TeamMember[]>(mockMembers);
  const [showInviteModal, setShowInviteModal] = useState(false);
  const [inviteEmail, setInviteEmail] = useState("");
  const [inviteRole, setInviteRole] = useState<"ADMIN" | "MEMBER">("MEMBER");
  const [isInviting, setIsInviting] = useState(false);
  const [inviteSuccess, setInviteSuccess] = useState(false);

  const handleInvite = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsInviting(true);

    // Simulate API call
    await new Promise((resolve) => setTimeout(resolve, 1000));

    // Add to local state (in real app, this would be handled by the backend)
    const newMember: TeamMember = {
      id: Math.random().toString(),
      name: inviteEmail.split("@")[0],
      email: inviteEmail,
      role: inviteRole,
      joinedAt: new Date().toISOString(),
    };
    setMembers([...members, newMember]);

    setIsInviting(false);
    setInviteSuccess(true);
    setTimeout(() => {
      setShowInviteModal(false);
      setInviteEmail("");
      setInviteSuccess(false);
    }, 1500);
  };

  const handleRemoveMember = async (memberId: string) => {
    if (confirm("Are you sure you want to remove this team member?")) {
      setMembers(members.filter((m) => m.id !== memberId));
    }
  };

  const getRoleColor = (role: string) => {
    switch (role) {
      case "OWNER":
        return "text-purple-400 bg-purple-400/20";
      case "ADMIN":
        return "text-blue-400 bg-blue-400/20";
      default:
        return "text-slate-400 bg-slate-400/20";
    }
  };

  // Current user as owner
  const currentUserMember: TeamMember = {
    id: "current",
    name: session?.user?.name || "You",
    email: session?.user?.email || "",
    role: "OWNER",
    joinedAt: new Date().toISOString(),
  };

  const allMembers = [currentUserMember, ...members];

  return (
    <div className="p-8">
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="text-3xl font-bold text-white mb-2">Team</h1>
          <p className="text-slate-400">Manage your team members and their access</p>
        </div>
        <button
          onClick={() => setShowInviteModal(true)}
          className="flex items-center gap-2 px-6 py-3 bg-blue-600 hover:bg-blue-700 text-white font-medium rounded-lg transition-colors"
        >
          <UserPlus className="w-5 h-5" />
          Invite Member
        </button>
      </div>

      {/* Team Stats */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-8">
        <div className="bg-slate-800/50 border border-slate-700 rounded-xl p-6">
          <div className="flex items-center gap-4">
            <div className="w-12 h-12 rounded-lg bg-blue-500/20 flex items-center justify-center">
              <Users className="w-6 h-6 text-blue-400" />
            </div>
            <div>
              <p className="text-sm text-slate-400">Team Members</p>
              <p className="text-2xl font-bold text-white">{allMembers.length}</p>
            </div>
          </div>
        </div>

        <div className="bg-slate-800/50 border border-slate-700 rounded-xl p-6">
          <div className="flex items-center gap-4">
            <div className="w-12 h-12 rounded-lg bg-purple-500/20 flex items-center justify-center">
              <Shield className="w-6 h-6 text-purple-400" />
            </div>
            <div>
              <p className="text-sm text-slate-400">Admins</p>
              <p className="text-2xl font-bold text-white">
                {allMembers.filter((m) => m.role === "ADMIN" || m.role === "OWNER").length}
              </p>
            </div>
          </div>
        </div>

        <div className="bg-slate-800/50 border border-slate-700 rounded-xl p-6">
          <div className="flex items-center gap-4">
            <div className="w-12 h-12 rounded-lg bg-green-500/20 flex items-center justify-center">
              <Mail className="w-6 h-6 text-green-400" />
            </div>
            <div>
              <p className="text-sm text-slate-400">Pending Invites</p>
              <p className="text-2xl font-bold text-white">0</p>
            </div>
          </div>
        </div>
      </div>

      {/* Members Table */}
      <div className="bg-slate-800/50 border border-slate-700 rounded-xl overflow-hidden">
        <table className="w-full">
          <thead>
            <tr className="border-b border-slate-700">
              <th className="text-left px-6 py-4 text-sm font-medium text-slate-400">Member</th>
              <th className="text-left px-6 py-4 text-sm font-medium text-slate-400">Role</th>
              <th className="text-right px-6 py-4 text-sm font-medium text-slate-400">Actions</th>
            </tr>
          </thead>
          <tbody>
            {allMembers.map((member) => (
              <tr
                key={member.id}
                className="border-b border-slate-700/50 hover:bg-slate-700/20 transition-colors"
              >
                <td className="px-6 py-4">
                  <div className="flex items-center gap-4">
                    <div className="w-10 h-10 rounded-full bg-blue-600 flex items-center justify-center text-white font-semibold">
                      {member.name[0].toUpperCase()}
                    </div>
                    <div>
                      <p className="text-white font-medium">
                        {member.name}
                        {member.id === "current" && (
                          <span className="ml-2 text-xs text-slate-400">(You)</span>
                        )}
                      </p>
                      <p className="text-sm text-slate-400">{member.email}</p>
                    </div>
                  </div>
                </td>
                <td className="px-6 py-4">
                  <span
                    className={`inline-flex items-center gap-1 px-3 py-1 rounded-full text-sm ${getRoleColor(
                      member.role
                    )}`}
                  >
                    {member.role === "OWNER" && <Shield className="w-3 h-3" />}
                    {member.role}
                  </span>
                </td>
                <td className="px-6 py-4">
                  <div className="flex items-center justify-end">
                    {member.id !== "current" && (
                      <button
                        onClick={() => handleRemoveMember(member.id)}
                        className="p-2 text-slate-400 hover:text-red-400 transition-colors"
                        title="Remove member"
                      >
                        <Trash2 className="w-5 h-5" />
                      </button>
                    )}
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Invite Modal */}
      {showInviteModal && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
          <div className="bg-slate-800 border border-slate-700 rounded-xl w-full max-w-md p-6">
            <div className="flex items-center justify-between mb-6">
              <h2 className="text-xl font-semibold text-white">Invite Team Member</h2>
              <button
                onClick={() => setShowInviteModal(false)}
                className="text-slate-400 hover:text-white transition-colors"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            {inviteSuccess ? (
              <div className="text-center py-8">
                <div className="w-16 h-16 rounded-full bg-green-500/20 flex items-center justify-center mx-auto mb-4">
                  <CheckCircle className="w-8 h-8 text-green-400" />
                </div>
                <p className="text-white font-medium">Invitation sent!</p>
              </div>
            ) : (
              <form onSubmit={handleInvite} className="space-y-4">
                <div>
                  <label className="block text-sm font-medium text-slate-300 mb-2">
                    Email Address
                  </label>
                  <input
                    type="email"
                    value={inviteEmail}
                    onChange={(e) => setInviteEmail(e.target.value)}
                    className="w-full px-4 py-3 bg-slate-700/50 border border-slate-600 rounded-lg text-white placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-blue-500"
                    placeholder="colleague@company.com"
                    required
                  />
                </div>

                <div>
                  <label className="block text-sm font-medium text-slate-300 mb-2">Role</label>
                  <div className="grid grid-cols-2 gap-3">
                    <button
                      type="button"
                      onClick={() => setInviteRole("MEMBER")}
                      className={`p-3 rounded-lg border text-left transition-all ${
                        inviteRole === "MEMBER"
                          ? "border-blue-500 bg-blue-500/10"
                          : "border-slate-600 hover:border-slate-500"
                      }`}
                    >
                      <p className="text-white font-medium">Member</p>
                      <p className="text-xs text-slate-400">Can upload and view batches</p>
                    </button>
                    <button
                      type="button"
                      onClick={() => setInviteRole("ADMIN")}
                      className={`p-3 rounded-lg border text-left transition-all ${
                        inviteRole === "ADMIN"
                          ? "border-blue-500 bg-blue-500/10"
                          : "border-slate-600 hover:border-slate-500"
                      }`}
                    >
                      <p className="text-white font-medium">Admin</p>
                      <p className="text-xs text-slate-400">Can manage team members</p>
                    </button>
                  </div>
                </div>

                <button
                  type="submit"
                  disabled={isInviting}
                  className="w-full bg-blue-600 hover:bg-blue-700 disabled:bg-blue-600/50 text-white font-medium py-3 rounded-lg transition-colors flex items-center justify-center gap-2"
                >
                  {isInviting ? (
                    <>
                      <Loader2 className="w-5 h-5 animate-spin" />
                      Sending invite...
                    </>
                  ) : (
                    <>
                      <Mail className="w-5 h-5" />
                      Send Invitation
                    </>
                  )}
                </button>
              </form>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
