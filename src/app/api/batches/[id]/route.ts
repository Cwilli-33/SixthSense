import { NextRequest, NextResponse } from "next/server";
import { getServerSession } from "next-auth";
import { authOptions } from "@/lib/auth";
import prisma from "@/lib/prisma";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

// GET /api/batches/[id] - Get batch details and status
export async function GET(
  request: NextRequest,
  { params }: { params: Promise<{ id: string }> }
) {
  const session = await getServerSession(authOptions);

  if (!session?.user) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }

  try {
    const { id } = await params;

    // Get batch from our database
    const batch = await prisma.batch.findUnique({
      where: { id },
      include: {
        user: {
          select: { name: true, email: true },
        },
        team: {
          select: { name: true },
        },
      },
    });

    if (!batch || !batch.teamId) {
      return NextResponse.json({ error: "Batch not found" }, { status: 404 });
    }

    // Verify user has access (is part of the team)
    const teamMember = await prisma.teamMember.findFirst({
      where: {
        userId: (session.user as any).id,
        teamId: batch.teamId,
      },
    });

    if (!teamMember) {
      return NextResponse.json({ error: "Access denied" }, { status: 403 });
    }

    // Get status from backend if batch is still processing
    if (batch.status !== "COMPLETED" && batch.status !== "FAILED") {
      try {
        const statusResponse = await fetch(
          `${API_URL}/api/v1/enrichment/batch/${id}/status`
        );

        if (statusResponse.ok) {
          const backendStatus = await statusResponse.json();

          // Update our database with backend status
          const updatedBatch = await prisma.batch.update({
            where: { id },
            data: {
              status: backendStatus.status.toUpperCase(),
              totalLeads: backendStatus.total_leads,
              processedLeads: backendStatus.processed_leads,
              approvedLeads: backendStatus.approved_leads,
              rejectedLeads: backendStatus.rejected_leads,
              errorMessage: backendStatus.error_message,
              completedAt: backendStatus.completed_at
                ? new Date(backendStatus.completed_at)
                : null,
            },
            include: {
              user: {
                select: { name: true, email: true },
              },
              team: {
                select: { name: true },
              },
            },
          });

          // Transform to expected format
          return NextResponse.json({
            id: updatedBatch.id,
            status: updatedBatch.status,
            createdAt: updatedBatch.createdAt,
            completedAt: updatedBatch.completedAt,
            totalLeads: updatedBatch.totalLeads,
            processedLeads: updatedBatch.processedLeads,
            approvedLeads: updatedBatch.approvedLeads,
            rejectedLeads: updatedBatch.rejectedLeads,
            errorMessage: updatedBatch.errorMessage,
            fileName: updatedBatch.inputFileName || updatedBatch.name || "Unknown",
            tier: updatedBatch.tier,
            createdBy: updatedBatch.user,
            team: updatedBatch.team,
          });
        }
      } catch (e) {
        // Backend might not be running, return cached data
        console.warn("Could not fetch backend status:", e);
      }
    }

    // Transform to expected format
    return NextResponse.json({
      id: batch.id,
      status: batch.status,
      createdAt: batch.createdAt,
      completedAt: batch.completedAt,
      totalLeads: batch.totalLeads,
      processedLeads: batch.processedLeads,
      approvedLeads: batch.approvedLeads,
      rejectedLeads: batch.rejectedLeads,
      errorMessage: batch.errorMessage,
      fileName: batch.inputFileName || batch.name || "Unknown",
      tier: batch.tier,
      createdBy: batch.user,
      team: batch.team,
    });
  } catch (error) {
    console.error("Error fetching batch:", error);
    return NextResponse.json(
      { error: "Failed to fetch batch" },
      { status: 500 }
    );
  }
}
