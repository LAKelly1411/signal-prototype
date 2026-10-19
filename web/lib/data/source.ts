import type { RunStatus, SectorEntry, SectorRules, Signal } from "./types";
import { FileDataSource } from "./files";

export interface DataSource {
  listSectors(): Promise<SectorEntry[]>;
  getSignals(slug: string): Promise<Signal[]>;
  getRunStatus(slug: string): Promise<RunStatus | null>;
  getSectorRules(slug: string): Promise<SectorRules>;
}

let memo: DataSource | null = null;

/** The app's one data source. v1: the pipeline's JSON files, from disk or a base URL. */
export function getDataSource(): DataSource {
  if (!memo) {
    memo = new FileDataSource({
      dataDir: process.env.DATA_DIR,
      configDir: process.env.CONFIG_DIR,
      dataBaseUrl: process.env.DATA_BASE_URL,
      configBaseUrl: process.env.CONFIG_BASE_URL,
    });
  }
  return memo;
}
