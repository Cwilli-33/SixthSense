import { NextResponse } from "next/server";
import { getServerSession } from "next-auth";
import { authOptions } from "@/lib/auth";
import prisma from "@/lib/prisma";

// GET /api/team - Get current user's team and members
export async function GET() {
  const session = await getServerSession(authOptions);

  if (!session?.user) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }

  try {
    // Get user's team
    const teamMember = await prisma.teamMember.findFirst({
      where: { userId: (session.user as any).id },
      include: {
        team: {
          include: {
            members: {
              include: {
                user: {
                  select: {
                    id: true,
                    name: true,
                    email: true,
                    image: true,
                  },
                },
              },
            },
          },
        },
      },
    });

    if (!teamMember) {
      return NextResponse.json({ error: "No team found" }, { status: 404 });
    }

    // Get batch stats for the team
    const batchStats = await prisma.batch.aggregate({
      where: { teamId: teamMember.teamId },
      _count: true,
      _sum: {
        totalLeads: true,
        approvedLeads: true,
      },
    });

    return NextResponse.json({
      ...teamMember.team,
      currentUserRole: teamMember.role,
      stats: {
        totalBatches: batchStats._count,
        totalLeads: batchStats._sum.totalLeads || 0,
        approvedLeads: batchStats._sum.approvedLeads || 0,
      },
    });
  } catch (error) {
    console.error("Error fetching team:", error);
    return NextResponse.json(
      { error: "Failed to fetch team" },
      { status: 500 }
    );
  }
}
