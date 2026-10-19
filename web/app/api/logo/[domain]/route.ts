import { COMPANY_DOMAINS, SOURCE_DOMAINS } from "@/lib/brand";

const ALLOWED = new Set([...Object.values(SOURCE_DOMAINS), ...Object.values(COMPANY_DOMAINS)]);

const notFound = () => new Response(null, { status: 404 });

/** Proxy a logo.dev image so the token stays on the server. */
export async function GET(_req: Request, { params }: { params: Promise<{ domain: string }> }) {
  const { domain } = await params;
  const token = process.env.LOGO_DEV_TOKEN;
  if (!token || !ALLOWED.has(domain)) return notFound();
  let upstream: Response;
  try {
    upstream = await fetch(`https://img.logo.dev/${encodeURIComponent(domain)}?token=${encodeURIComponent(token)}&size=64&format=png`);
  } catch {
    return notFound();
  }
  if (!upstream.ok) return notFound();
  return new Response(await upstream.arrayBuffer(), {
    headers: {
      "content-type": upstream.headers.get("content-type") ?? "image/png",
      "cache-control": "public, max-age=86400",
    },
  });
}
