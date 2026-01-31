import { NextRequest, NextResponse } from "next/server";
import { getServerSession } from "next-auth";
import { authOptions } from "@/lib/auth";
import prisma from "@/lib/prisma";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

// GET /api/batches/[id]/download - Download batch results
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

    if (batch.status !== "COMPLETED") {
      return NextResponse.json(
        { error: "Batch is not complete yet" },
        { status: 400 }
      );
    }

    // Proxy the download from backend
    const downloadResponse = await fetch(
      `${API_URL}/api/v1/enrichment/batch/${id}/download`
    );

    if (!downloadResponse.ok) {
      return NextResponse.json(
        { error: "Download failed" },
        { status: downloadResponse.status }
      );
    }

    // Forward the file
    const blob = await downloadResponse.blob();
    const headers = new Headers();
    headers.set(
      "Content-Type",
      "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    );
    headers.set(
      "Content-Disposition",
      `attachment; filename="enriched_leads_${id}.xlsx"`
    );

    return new NextResponse(blob, { headers });
  } catch (error) {
    console.error("Error downloading batch:", error);
    return NextResponse.json(
      { error: "Failed to download batch" },
      { status: 500 }
    );
  }
}
