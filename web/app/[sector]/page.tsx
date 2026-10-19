import { redirect } from "next/navigation";

export default async function SectorIndex({ params }: { params: Promise<{ sector: string }> }) {
  const { sector } = await params;
  redirect(`/${sector}/feed`);
}
