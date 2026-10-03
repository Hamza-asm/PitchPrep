"use client";

import { useRef, useState, type FormEvent } from "react";
import { useRouter } from "next/navigation";
import { api, ApiError, messageOf, type AcceptedRun, type ResearchInput, type SellerProfile } from "@/lib/api";
import { Icon, Notice } from "../ui";

export function SellerForm({ profile, onSaved, onCancel }: { profile: SellerProfile | null; onSaved: (value: SellerProfile) => void; onCancel?: () => void }) {
  const [offering, setOffering] = useState(profile?.offering ?? "");
  const [ideal, setIdeal] = useState(profile?.ideal_customer ?? "");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  async function submit(event: FormEvent) {
    event.preventDefault(); if (busy) return; setBusy(true); setError("");
    try { const saved = await api<SellerProfile>("/seller-profile", { method: "PUT", body: JSON.stringify({ offering: offering.trim(), ideal_customer: ideal.trim() }) }); onSaved(saved); }
    catch (error) { setError(messageOf(error)); } finally { setBusy(false); }
  }
  return <><div className="page-heading"><span className="eyebrow">Your starting point</span><h1>{profile ? "What you bring to the table." : "First, a little about you."}</h1><p>Give PitchPrep the context to connect a company’s needs to what you sell.</p></div><form className="panel form-panel form-stack" onSubmit={submit} aria-busy={busy}>
    {error && <Notice>{error}</Notice>}
    <div className="field"><label className="field-label" htmlFor="offering">What do you sell?<small>Required</small></label><textarea id="offering" required maxLength={4000} value={offering} onChange={(e) => setOffering(e.target.value)} placeholder="Describe your product or service and the problem it solves." aria-describedby="offering-help" /><p id="offering-help" className="field-help">Be specific about what you can help a customer do.</p></div>
    <div className="field"><label className="field-label" htmlFor="ideal">Who is your ideal customer?<small>Required</small></label><textarea id="ideal" required maxLength={4000} value={ideal} onChange={(e) => setIdeal(e.target.value)} placeholder="Describe the businesses, teams, or needs you work with." /></div>
    <div className="form-footer"><p>Saved for your next brief. Editable anytime.</p><div className="flex gap-2">{onCancel && <button type="button" className="button button-quiet" onClick={onCancel}>Cancel</button>}<button className="button button-primary" disabled={busy || !offering.trim() || !ideal.trim()}>{busy ? "Saving…" : "Save seller profile"}<Icon name="arrow" /></button></div></div>
  </form></>;
}

export function TargetForm({ initial }: { initial?: ResearchInput }) {
  const router = useRouter();
  const [value, setValue] = useState<ResearchInput>(initial ?? { company_name: "", target_url: "", pasted_text: "", link_confirmed: false });
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [fields, setFields] = useState<Record<string, string>>({});
  const submission = useRef<{ body: string; key: string } | null>(null);
  function change(field: keyof ResearchInput, text: string) { setValue({ ...value, [field]: text, link_confirmed: false }); setFields({ ...fields, [field]: "" }); }
  async function submit(event: FormEvent) {
    event.preventDefault(); if (busy) return;
    setBusy(true); setError(""); setFields({});
    const body = JSON.stringify({ ...value, company_name: value.company_name.trim(), target_url: value.target_url.trim(), link_confirmed: false });
    if (submission.current?.body !== body) submission.current = { body, key: crypto.randomUUID() };
    try { const run = await api<AcceptedRun>("/briefs", { method: "POST", body, headers: { "Idempotency-Key": submission.current.key } }); router.push(`/app/${run.id}`); }
    catch (error) { setError(messageOf(error)); if (error instanceof ApiError) setFields(error.fields); setBusy(false); }
  }
  return <><div className="page-heading"><span className="eyebrow">A better first conversation</span><h1>Who’s your next prospect?</h1><p>Add the company and a link. We’ll put the research in context, check the evidence, and prepare your first email.</p></div><form className="panel form-panel form-stack" onSubmit={submit} aria-busy={busy}>
    <div className="setup-intro"><Icon name="document" /><p>One company. A sourced brief. An email you make your own.</p></div>
    {error && <Notice>{error}</Notice>}
    <div className="field"><label className="field-label" htmlFor="company-name">Company name<small>Required</small></label><input id="company-name" autoComplete="organization" required maxLength={200} value={value.company_name} onChange={(e) => change("company_name", e.target.value)} placeholder="The company you’d like to work with" aria-invalid={!!fields.company_name} aria-describedby={fields.company_name ? "name-error" : undefined} />{fields.company_name && <p id="name-error" className="field-help text-[var(--error)]">{fields.company_name}</p>}</div>
    <div className="field"><label className="field-label" htmlFor="target-url">Website or social link<small>Required</small></label><input id="target-url" type="url" required value={value.target_url} onChange={(e) => change("target_url", e.target.value)} placeholder="Paste the company’s full link" aria-invalid={!!fields.target_url} aria-describedby="url-help url-error" /><p id="url-help" className="field-help">Use the company’s website. If it has none, use its Instagram, Facebook, or LinkedIn page.</p><p id="url-error" className="field-help text-[var(--error)]">{fields.target_url}</p></div>
    <div className="field"><label className="field-label" htmlFor="pasted-text">A little more context<small>Optional</small></label><textarea id="pasted-text" maxLength={20000} value={value.pasted_text} onChange={(e) => change("pasted_text", e.target.value)} placeholder="Paste listing details, opening hours, reviews, or other company information." aria-describedby="paste-help" /><p id="paste-help" className="field-help">Have a Google Maps listing? Paste its text here. We don’t scrape Maps.</p></div>
    <div className="form-footer"><p><Icon name="check" /> Every retained claim gets checked.</p><button className="button button-primary" disabled={busy || !value.company_name.trim()}>{busy ? "Starting your brief…" : "Prepare my brief"}<Icon name="arrow-circle" /></button></div>
  </form></>;
}
