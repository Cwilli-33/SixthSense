import { NextRequest, NextResponse } from "next/server";
import { getServerSession } from "next-auth";
import { authOptions } from "@/lib/auth";
import prisma from "@/lib/prisma";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

// GET /api/batches - List all batches for the user's team
export async function GET() {
  const session = await getServerSession(authOptions);

  if (!session?.user) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }

  try {
    // Get user's team
    const teamMember = await prisma.teamMember.findFirst({
      where: { userId: (session.user as any).id },
      include: { team: true },
    });

    if (!teamMember) {
      return NextResponse.json({ error: "No team found" }, { status: 404 });
    }

    // Get batches for the team
    const batches = await prisma.batch.findMany({
      where: { teamId: teamMember.teamId },
      orderBy: { createdAt: "desc" },
      include: {
        user: {
          select: { name: true, email: true },
        },
      },
    });

    // Transform to expected format
    const transformedBatches = batches.map((batch) => ({
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
    }));

    return NextResponse.json(transformedBatches);
  } catch (error) {
    console.error("Error fetching batches:", error);
    return NextResponse.json(
      { error: "Failed to fetch batches" },
      { status: 500 }
    );
  }
}

// POST /api/batches - Create a new batch (upload file)
export async function POST(request: NextRequest) {
  const session = await getServerSession(authOptions);

  if (!session?.user) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }

  try {
    const formData = await request.formData();
    const file = formData.get("file") as File;
    const tier = (formData.get("tier") as string) || "STANDARD";

    if (!file) {
      return NextResponse.json({ error: "No file provided" }, { status: 400 });
    }

    // Get user's team
    const teamMember = await prisma.teamMember.findFirst({
      where: { userId: (session.user as any).id },
      include: { team: true },
    });

    if (!teamMember) {
      return NextResponse.json({ error: "No team found" }, { status: 404 });
    }

    // Forward to FastAPI backend
    const backendFormData = new FormData();
    backendFormData.append("file", file);
    backendFormData.append("tier", tier);
    backendFormData.append("mock_data", "true"); // Use mock data for now

    const response = await fetch(`${API_URL}/api/v1/enrichment/batch`, {
      method: "POST",
      body: backendFormData,
    });

    if (!response.ok) {
      const error = await response.text();
      return NextResponse.json(
        { error: `Backend error: ${error}` },
        { status: response.status }
      );
    }

    const result = await response.json();

    // Create batch record in our database
    const batch = await prisma.batch.create({
      data: {
        id: result.batch_id,
        teamId: teamMember.teamId,
        userId: (session.user as any).id,
        inputFileName: file.name,
        inputFileSize: file.size,
        tier: tier,
        status: "PENDING",
      },
    });

    return NextResponse.json({
      id: batch.id,
      status: batch.status,
      createdAt: batch.createdAt,
      fileName: batch.inputFileName,
      tier: batch.tier,
      backend_response: result,
    });
  } catch (error) {
    console.error("Error creating batch:", error);
    return NextResponse.json(
      { error: "Failed to create batch" },
      { status: 500 }
    );
  }
}
