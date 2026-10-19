"use server";
import { AuthError } from "next-auth";
import { redirect } from "next/navigation";
import { signIn } from "@/auth";
import { homePath } from "@/lib/load";
import { safeNext } from "@/lib/routes";

/**
 * A relative path to land on after sign-in. "/" would only redirect again to
 * the first sector's feed, and a second hop leaves the action's redirect
 * hanging, so resolve it here.
 */
async function destination(next: string): Promise<string> {
  return next === "/" ? (await homePath()) ?? "/" : next;
}

export async function signInWithEntra(form: FormData) {
  // Redirects to Microsoft; Auth.js's callback then sends the browser to redirectTo.
  await signIn("microsoft-entra-id", { redirectTo: await destination(safeNext(form.get("next"))) });
}

export async function signInWithDev(form: FormData) {
  const next = safeNext(form.get("next"));
  try {
    await signIn("dev-password", { password: form.get("password"), redirect: false });
  } catch (e) {
    // A wrong password is an AuthError (CredentialsSignin); anything else,
    // including Next's own redirect signal, must propagate.
    if (e instanceof AuthError) redirect(`/login?${new URLSearchParams({ error: "CredentialsSignin", next })}`);
    throw e;
  }
  redirect(await destination(next));
}
