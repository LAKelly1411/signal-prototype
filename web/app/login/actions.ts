"use server";
import { signIn } from "@/auth";

const safeNext = (next: FormDataEntryValue | null) =>
  typeof next === "string" && next.startsWith("/") && !next.startsWith("//") ? next : "/";

export async function signInWithEntra(form: FormData) {
  await signIn("microsoft-entra-id", { redirectTo: safeNext(form.get("next")) });
}

export async function signInWithDev(form: FormData) {
  await signIn("dev-password", { password: form.get("password"), redirectTo: safeNext(form.get("next")) });
}
