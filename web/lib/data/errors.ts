export type DataErrorKind = "not_found" | "invalid" | "unreachable";

export class DataError extends Error {
  constructor(public kind: DataErrorKind, message: string) {
    super(message);
    this.name = "DataError";
  }
}

const SLUG = /^[a-z0-9-]+$/;
export const isSlug = (v: unknown): v is string => typeof v === "string" && SLUG.test(v);
