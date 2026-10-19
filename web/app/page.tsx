import { redirect } from "next/navigation";
import { EmptyState } from "@/components/EmptyState";
import { Masthead } from "@/components/Masthead";
import styles from "@/components/shell.module.css";
import { getDataSource } from "@/lib/data/source";
import { orderSectors } from "@/lib/load";

export const dynamic = "force-dynamic";

export default async function Home() {
  let target: string | undefined;
  try {
    const sectors = orderSectors(await getDataSource().listSectors());
    target = (sectors.find((s) => s.status === "ready") ?? sectors[0])?.slug;
  } catch {
    target = undefined;
  }
  if (target) redirect(`/${target}/feed`);
  return (
    <div className={styles.page}>
      <Masthead />
      <EmptyState kind="unavailable" />
    </div>
  );
}
