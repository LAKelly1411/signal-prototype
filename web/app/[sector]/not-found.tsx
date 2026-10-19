import Link from "next/link";
import styles from "@/components/shell.module.css";

export default function NotFound() {
  return (
    <div className={`${styles.page} ${styles.notFound}`}>
      <h1 className="pa-title">We couldn&apos;t find that sector.</h1>
      <p><Link href="/">Back to Sector Signal</Link></p>
    </div>
  );
}
