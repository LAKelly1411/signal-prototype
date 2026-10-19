import { z } from "zod";

export const SignalSchema = z
  .object({
    id: z.string(),
    source: z.string(),
    source_url: z.string().nullable().optional(),
    title: z.string(),
    raw_summary: z.string().nullable().optional(),
    published_at: z.string(),
    published_at_estimated: z.boolean().optional(),
    ingested_at: z.string().optional(),
    signal_type: z.string().nullable().optional(),
    entities: z.array(z.string()).optional().default([]),
    newsworthiness_score: z.number().nullable().optional(),
    why_it_matters: z.string().nullable().optional(),
    category: z.string().nullable().optional(),
    canonical_entities: z.array(z.string()).optional(),
    canonical_category: z.string().nullable().optional(),
    cluster_id: z.string().nullable().optional(),
    cluster_summary: z.string().nullable().optional(),
    cluster_pattern_type: z.string().nullable().optional(),
    cluster_coherent: z.boolean().nullable().optional(),
    cluster_significance: z.number().nullable().optional(),
    theme_id: z.string().nullable().optional(),
    theme_summary: z.string().nullable().optional(),
    theme_key_points: z.array(z.string()).nullable().optional(),
    theme_direction: z.string().nullable().optional(),
    sector: z.string().optional(),
  })
  .passthrough();
export type Signal = z.infer<typeof SignalSchema>;

export const SectorEntrySchema = z
  .object({
    slug: z.string(),
    name: z.string(),
    status: z.string().optional().default("ready"),
    brief: z.string().nullable().optional(),
    signal_count: z.number().nullable().optional(),
    last_run_at: z.string().nullable().optional(),
    error: z.string().nullable().optional(),
    created_at: z.string().nullable().optional(),
  })
  .passthrough();
export type SectorEntry = z.infer<typeof SectorEntrySchema>;

export const RunStatusSchema = z
  .object({
    sector: z.string().optional(),
    started_at: z.string().optional(),
    finished_at: z.string(),
    // A failed run (src/pipeline.py main) writes only sector, finished_at and error.
    sources: z.record(z.string(), z.object({ items: z.number(), ok: z.boolean(), error: z.boolean() }).passthrough()).optional(),
    healthy_sources: z.number().optional(),
    total_sources: z.number().optional(),
    error: z.string().nullable().optional(),
  })
  .passthrough();
export type RunStatus = z.infer<typeof RunStatusSchema>;

export type SectorRules = {
  slug: string;
  name: string;
  categories: string[];
  companies: { name: string; company_number?: string | null; aliases: string[] }[];
  excludedBodies: string[];
};
