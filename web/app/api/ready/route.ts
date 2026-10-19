import { getDataSource } from "@/lib/data/source";
export const dynamic = "force-dynamic";
export async function GET() {
  try {
    await getDataSource().listSectors();
    return Response.json({ ready: true });
  } catch {
    return Response.json({ ready: false }, { status: 503 });
  }
}
