import { NextResponse } from "next/server";
import { getServerSession } from "next-auth";
import { authOptions } from "@/lib/auth";
import prisma from "@/lib/prisma";

// GET /api/stats - Get dashboard statistics
export async function GET() {
  const session = await getServerSession(authOptions);

  if (!session?.user) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }

  try {
    // Get user's team
    const teamMember = await prisma.teamMember.findFirst({
      where: { userId: (session.user as any).id },
    });

    if (!teamMember) {
      return NextResponse.json({ error: "No team found" }, { status: 404 });
    }

    // Get batch statistics
    const batches = await prisma.batch.findMany({
      where: { teamId: teamMember.teamId },
      orderBy: { createdAt: "desc" },
      take: 10, // Recent batches for dashboard
    });

    const totals = await prisma.batch.aggregate({
      where: { teamId: teamMember.teamId },
      _count: true,
      _sum: {
        totalLeads: true,
        processedLeads: true,
        approvedLeads: true,
        rejectedLeads: true,
      },
    });

    // Get counts by status
    const statusCounts = await prisma.batch.groupBy({
      by: ["status"],
      where: { teamId: teamMember.teamId },
      _count: true,
    });

    const statusMap = statusCounts.reduce(
      (acc, item) => {
        acc[item.status] = item._count;
        return acc;
      },
      {} as Record<string, number>
    );

    return NextResponse.json({
      totalBatches: totals._count,
      totalLeads: totals._sum.totalLeads || 0,
      processedLeads: totals._sum.processedLeads || 0,
      approvedLeads: totals._sum.approvedLeads || 0,
      rejectedLeads: totals._sum.rejectedLeads || 0,
      batchesByStatus: {
        pending: statusMap["PENDING"] || 0,
        processing: statusMap["PROCESSING"] || 0,
        completed: statusMap["COMPLETED"] || 0,
        failed: statusMap["FAILED"] || 0,
      },
      recentBatches: batches,
    });
  } catch (error) {
    console.error("Error fetching stats:", error);
    return NextResponse.json(
      { error: "Failed to fetch stats" },
      { status: 500 }
    );
  }
}
