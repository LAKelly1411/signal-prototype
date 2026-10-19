import { Masthead } from "@/components/Masthead";
import { SectorMenu } from "@/components/SectorMenu";
import { StatusStrip } from "@/components/StatusStrip";
import { Tabs } from "@/components/Tabs";
import { EmptyState, UpdateNotice } from "@/components/EmptyState";
import { LogosProvider } from "@/components/SourceLogo";
import styles from "@/components/shell.module.css";
import { loadSector, sectorNote } from "@/lib/load";

export const dynamic = "force-dynamic";

export default async function SectorLayout({ children, params }: { children: React.ReactNode; params: Promise<{ sector: string }> }) {
  const { sector: slug } = await params;
  const view = await loadSector(slug);
  if (view.state === "unavailable") {
    return (
      <div className={styles.page}>
        <Masthead />
        <EmptyState kind="unavailable" />
      </div>
    );
  }
  const now = view.state === "ready" ? view.now : new Date();
  return (
    <div className={styles.frame}>
      <div className={styles.page}>
        <Masthead />
        <div className={styles.head}>
          <div className={styles.intro}>
            <span className="pa-kicker">Sector</span>
            <SectorMenu
              items={view.sectors.map((s) => ({ slug: s.slug, name: s.name, note: sectorNote(s) }))}
              current={{ slug: view.sector.slug, name: view.sector.name, note: "" }}
            />
            <p className={styles.standfirst}>Sector signals, scored for newsworthiness.</p>
          </div>
          <StatusStrip status={view.status} now={now} />
        </div>
        {view.state === "ready" ? (
          <>
            {view.notice === "update_failed" && <UpdateNotice />}
            <Tabs slug={view.sector.slug} />
            <LogosProvider enabled={Boolean(process.env.LOGO_DEV_TOKEN)}>{children}</LogosProvider>
          </>
        ) : (
          <EmptyState kind={view.state} name={view.sector.name} />
        )}
      </div>
    </div>
  );
}
