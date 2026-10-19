import { redirect } from "next/navigation";
import { EmptyState } from "@/components/EmptyState";
import { Masthead } from "@/components/Masthead";
import styles from "@/components/shell.module.css";
import { homePath } from "@/lib/load";

export const dynamic = "force-dynamic";

export default async function Home() {
  const target = await homePath();
  if (target) redirect(target);
  return (
    <div className={styles.page}>
      <Masthead />
      <EmptyState kind="unavailable" />
    </div>
  );
}
