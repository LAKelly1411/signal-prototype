export const dynamic = "force-dynamic";

export async function GET() {
  return Response.json({ ok: true, tag: process.env.BUILD_TAG || "dev" });
}
