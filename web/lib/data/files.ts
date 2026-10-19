import { readFile, stat } from "node:fs/promises";
import path from "node:path";
import yaml from "js-yaml";
import { z } from "zod";
import { DataError, isSlug } from "./errors";
import { RunStatusSchema, SectorEntrySchema, SignalSchema, type RunStatus, type SectorEntry, type SectorRules, type Signal } from "./types";
import type { DataSource } from "./source";

type Opts = { dataDir?: string; configDir?: string; dataBaseUrl?: string; configBaseUrl?: string; fetchFn?: typeof fetch; clock?: () => number };
type Company = SectorRules["companies"][number];

const REVALIDATE = 300;

export class FileDataSource implements DataSource {
  private dataDir: string;
  private configDir: string;
  private dataBaseUrl?: string;
  private configBaseUrl?: string;
  private fetchFn: typeof fetch;
  private clock: () => number;
  /** Disk mode: file text by path, kept for REVALIDATE seconds unless the file's mtime changes. */
  private memo = new Map<string, { at: number; mtimeMs: number; text: string }>();

  constructor(opts: Opts = {}) {
    this.dataDir = opts.dataDir || path.resolve(process.cwd(), "../data");
    this.configDir = opts.configDir || path.resolve(process.cwd(), "../config");
    this.dataBaseUrl = opts.dataBaseUrl?.replace(/\/?$/, "/");
    this.configBaseUrl = opts.configBaseUrl?.replace(/\/?$/, "/");
    this.fetchFn = opts.fetchFn ?? fetch;
    this.clock = opts.clock ?? Date.now;
  }

  /** Raw text of a file under data/ or config/, or null when it doesn't exist. */
  private async read(root: "data" | "config", rel: string): Promise<string | null> {
    const base = root === "data" ? this.dataBaseUrl : this.configBaseUrl;
    if (base) {
      let res: Response;
      try {
        res = await this.fetchFn(base + rel, { next: { revalidate: REVALIDATE } } as RequestInit);
      } catch (e) {
        throw new DataError("unreachable", `Couldn't reach ${base + rel}: ${(e as Error).message}`);
      }
      if (res.status === 404) return null;
      if (!res.ok) throw new DataError("unreachable", `${base + rel} answered ${res.status}`);
      return res.text();
    }
    const file = path.join(root === "data" ? this.dataDir : this.configDir, rel);
    try {
      const { mtimeMs } = await stat(file);
      const now = this.clock();
      const hit = this.memo.get(file);
      if (hit && hit.mtimeMs === mtimeMs && now - hit.at < REVALIDATE * 1000) return hit.text;
      const text = await readFile(file, "utf8");
      this.memo.set(file, { at: now, mtimeMs, text });
      return text;
    } catch (e) {
      this.memo.delete(file);
      if ((e as NodeJS.ErrnoException).code === "ENOENT") return null;
      throw new DataError("unreachable", `Couldn't read ${rel}: ${(e as Error).message}`);
    }
  }

  private parse<T>(schema: z.ZodType<T, z.ZodTypeDef, unknown>, text: string, what: string): T {
    let raw: unknown;
    try {
      raw = JSON.parse(text);
    } catch {
      throw new DataError("invalid", `${what} isn't valid JSON`);
    }
    const result = schema.safeParse(raw);
    if (!result.success) throw new DataError("invalid", `${what} doesn't match the expected shape: ${result.error.message}`);
    return result.data;
  }

  private slug(slug: string): string {
    if (!isSlug(slug)) throw new DataError("not_found", `Not a sector: ${JSON.stringify(slug)}`);
    return slug;
  }

  private yamlMap(text: string | null, what: string): Record<string, unknown> {
    if (!text) return {};
    try {
      const v = yaml.load(text);
      return v && typeof v === "object" && !Array.isArray(v) ? (v as Record<string, unknown>) : {};
    } catch (e) {
      throw new DataError("invalid", `${what} isn't valid YAML: ${(e as Error).message}`);
    }
  }

  async listSectors(): Promise<SectorEntry[]> {
    const text = await this.read("data", "sectors.json");
    if (text === null) throw new DataError("not_found", "data/sectors.json is missing");
    return this.parse(z.array(SectorEntrySchema), text, "sectors.json");
  }

  async getSignals(slug: string): Promise<Signal[]> {
    const s = this.slug(slug);
    const text = await this.read("data", `${s}/signals.json`);
    if (text === null) throw new DataError("not_found", `No signals for ${s} yet`);
    return this.parse(z.array(SignalSchema), text, `${s}/signals.json`);
  }

  async getRunStatus(slug: string): Promise<RunStatus | null> {
    const s = this.slug(slug);
    const text = await this.read("data", `${s}/run_status.json`);
    return text === null ? null : this.parse(RunStatusSchema, text, `${s}/run_status.json`);
  }

  /**
   * Mirrors src/sectors.py `_build`: categories are objects with a `name`
   * (strings tolerated), `excluded_bodies` is a flat list (a mapping of lists
   * is flattened), and the user file's `companies` and `operators` are both
   * appended to the main file's `companies`.
   */
  async getSectorRules(slug: string): Promise<SectorRules> {
    const s = this.slug(slug);
    const main = await this.read("config", `sectors/${s}.yaml`);
    if (main === null) throw new DataError("not_found", `No config for ${s}`);
    const cfg = this.yamlMap(main, `${s}.yaml`);
    const extra = this.yamlMap(await this.read("config", `sectors/${s}.user.yaml`), `${s}.user.yaml`);

    const list = (v: unknown): Company[] => (Array.isArray(v) ? (v as Company[]) : []);
    const companies = [...list(cfg.companies), ...list(extra.companies), ...list(extra.operators)]
      .filter((c) => c && typeof c.name === "string")
      .map((c) => ({ name: c.name, company_number: c.company_number ?? null, aliases: c.aliases ?? [] }));

    const categories = (Array.isArray(cfg.categories) ? (cfg.categories as (string | { name?: string })[]) : [])
      .map((c) => (typeof c === "string" ? c : c?.name))
      .filter((n): n is string => typeof n === "string" && n !== "");

    const excluded = cfg.excluded_bodies;
    const excludedBodies = (Array.isArray(excluded) ? excluded : excluded && typeof excluded === "object" ? Object.values(excluded).flat() : [])
      .filter((b): b is string => typeof b === "string");

    return { slug: s, name: String(cfg.name ?? s), categories, companies, excludedBodies };
  }
}
