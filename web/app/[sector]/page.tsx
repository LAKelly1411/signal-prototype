import { notFound, redirect } from "next/navigation";
import { isSlug } from "@/lib/data/errors";

export default async function SectorIndex({ params }: { params: Promise<{ sector: string }> }) {
  const { sector } = await params;
  if (!isSlug(sector)) notFound();
  redirect(`/${sector}/feed`);
}
