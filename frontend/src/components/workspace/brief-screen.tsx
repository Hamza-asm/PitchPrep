"use client";

import { useEffect, useState, type FormEvent } from "react";
import { api, apiUrl, isActive, messageOf, safeSourceUrl, sourceDomain, statusLabels, type BriefDetail, type EmailEdit, type ResearchInput, type Source, type Stage, type WorkflowNode } from "@/lib/api";
import { Icon, Notice, Skeleton } from "../ui";

const stages: [Stage, string][] = [["parsing", "Parsing"], ["collecting", "Collecting"], ["analyzing", "Analyzing"], ["matching", "Matching"], ["writing", "Writing"], ["verifying", "Verifying"]];
const retryLabels: Record<WorkflowNode, string> = { parser: "Input Parser", source_fetch: "source collection", source_collector: "Source Collector", link_check: "link check", analyst: "Analyst", matcher: "Matcher", writer: "Writer", verifier: "Verifier" };

function useBrief(id: string, onComplete: () => void) {
  const [detail, setDetail] = useState<BriefDetail | null>(null);
  const [error, setError] = useState("");
  const [connection, setConnection] = useState("");
  const [revision, setRevision] = useState(0);
  useEffect(() => {
    const abort = new AbortController();
    let stream: EventSource | undefined;
    let timer: ReturnType<typeof setTimeout> | undefined;
    let terminal = false;
    let inFlight = false;
    let newestVersion = -1;
    function accept(row: BriefDetail) {
      if (abort.signal.aborted || row.id !== id || row.version < newestVersion) return;
      newestVersion = row.version;
      setDetail((previous) => !previous || row.version >= previous.version ? row : previous);
      setError("");
      if (!isActive(row.status) && !terminal) {
        terminal = true; stream?.close(); clearTimeout(timer); setConnection(""); onComplete();
      }
    }
    async function fetchSnapshot() {
      if (inFlight || abort.signal.aborted || terminal) return;
      inFlight = true;
      try { accept(await api<BriefDetail>(`/briefs/${id}`, { signal: abort.signal })); setConnection(""); }
      catch (error) { if (!abort.signal.aborted) setError(messageOf(error)); }
      finally { inFlight = false; }
    }
    async function poll() {
      await fetchSnapshot();
      if (!abort.signal.aborted && !terminal) timer = setTimeout(poll, 8000);
    }
    void poll();
    try {
      stream = new EventSource(apiUrl(`/briefs/${id}/stream`));
      const event = (event: MessageEvent) => {
        try { const row = JSON.parse(event.data) as BriefDetail; if (typeof row.version !== "number" || !Array.isArray(row.progress)) throw new Error(); accept(row); setConnection(""); }
        catch { setConnection("Live updates were interrupted. We’re checking saved progress."); }
      };
      stream.addEventListener("progress", event);
      stream.addEventListener("result", event);
      stream.addEventListener("unavailable", () => setConnection("Live updates were interrupted. We’re checking saved progress."));
      stream.onerror = () => { if (!terminal) setConnection("Reconnecting to live updates. Your research continues in the background."); };
    } catch { /* Polling remains available when EventSource is unavailable. */ }
    return () => { abort.abort(); stream?.close(); clearTimeout(timer); };
  }, [id, revision, onComplete]);
  return { detail, setDetail, error, connection, reload: () => setRevision((n) => n + 1) };
}

export function BriefScreen({ id, onEdit, onComplete }: { id: string; onEdit: (input: ResearchInput) => void; onComplete: () => void }) {
  const { detail, setDetail, error, connection, reload } = useBrief(id, onComplete);
  const [actionError, setActionError] = useState("");
  const [confirming, setConfirming] = useState(false);
  const [retrying, setRetrying] = useState(false);
  async function confirm() {
    if (!detail || confirming) return; setConfirming(true); setActionError("");
    try { await api(`/briefs/${id}/confirm-link`, { method: "POST", body: JSON.stringify({ confirmed: true, expected_version: detail.version }) }); reload(); }
    catch (error) { setActionError(messageOf(error)); } finally { setConfirming(false); }
  }
  async function retryStage() {
    if (!detail || !detail.retry_node || retrying) return;
    setRetrying(true); setActionError("");
    try { await api(`/briefs/${id}/retry`, { method: "POST", body: JSON.stringify({ expected_version: detail.version }) }); reload(); }
    catch (error) { setActionError(messageOf(error)); }
    finally { setRetrying(false); }
  }
  if (!detail) return error ? <><div className="page-heading"><h1>We couldn’t open this brief.</h1></div><Notice>{error}<button className="button button-secondary button-small" onClick={reload}>Try again</button></Notice></> : <Skeleton label="Opening your brief" />;
  const result = detail.result;
  const active = isActive(detail.status);
  return <>
    <div className="page-heading"><span className="eyebrow">Your prospect brief · {statusLabels[detail.status]}</span><h1>{detail.request.company_name}</h1><p>{active ? "We’re following the evidence. You can leave this page and return from history." : "Review the research, follow the sources, and make the email your own."}</p></div>
    {error && <Notice>{error}<button className="button button-small button-secondary" onClick={reload}>Refresh brief</button></Notice>}
    {connection && active && <Notice kind="info">{connection}</Notice>}
    {actionError && <Notice>{actionError}<button className="button button-small button-secondary" onClick={reload}>Refresh brief</button></Notice>}
    {(active || !result) && <ProgressPanel detail={detail} />}
    {detail.status === "needs_confirmation" && <Notice kind="caution"><strong>Is this the right company link?</strong><p>{detail.message}</p><p className="break-all">{detail.request.target_url}</p><div className="brief-actions"><button className="button button-primary" disabled={confirming} onClick={confirm}>{confirming ? "Continuing…" : "Yes, continue with this link"}</button><button className="button button-secondary" onClick={() => onEdit(detail.request)}>Change the input</button></div></Notice>}
    {detail.status === "failed" && <Notice kind="error"><strong>This run couldn’t finish.</strong><p>{detail.message}</p><div className="brief-actions">{detail.retry_node && <button className="button button-primary" onClick={retryStage} disabled={retrying}>Retry failed step{retrying ? "…" : ""}<span className="sr-only">: {retryLabels[detail.retry_node]}</span></button>}<button className="button button-secondary" onClick={() => onEdit(detail.request)}>Edit company details</button></div>{detail.retry_node && <p className="field-help">Only {retryLabels[detail.retry_node]} will run again. Completed stages and collected sources are reused.</p>}</Notice>}
    {detail.status === "needs_input" && <Notice kind="caution"><strong>A little more context is needed.</strong><p>{detail.message}</p><div className="brief-actions">{detail.retry_node === "source_fetch" && <button className="button button-primary" onClick={retryStage} disabled={retrying}>{retrying ? "Retrying source collection…" : "Retry source collection"}</button>}<button className="button button-secondary" onClick={() => onEdit(detail.request)}>Edit company details</button></div>{detail.retry_node === "source_fetch" && <p className="field-help">This retries source collection only. Editing fields does not start a run; submit the form only when you want a new research run.</p>}</Notice>}
    {result && <>
      {active && <Notice kind="info">Your previous result stays available while the new email is prepared.</Notice>}
      {result.limited_data && <Notice kind="caution"><strong>Limited data</strong><p>The available evidence doesn’t tell the whole story. Review the sources before reaching out.</p></Notice>}
      <div className="brief-columns"><div>
        {([ ["snapshot", "Company snapshot"], ["trigger", "Recent signals"], ["need", "Likely needs"], ["role", "Target roles"] ] as const).map(([section, title]) => {
          const claims = result.claims.filter((claim) => claim.section === section);
          return <section key={section} className="brief-section"><h2>{title}</h2>{claims.length ? claims.map((claim) => <article className="claim" key={claim.id}><p>{claim.text}</p><div className="claim-footer"><span className="badge verified"><Icon name="check" /> Verified</span>{claim.source_ids.map((sourceId) => { const source = result.sources.find((s) => s.id === sourceId); return source ? <SourceChip source={source} key={sourceId} /> : null; })}</div></article>) : <p className="empty-copy">Not enough evidence to include this section.</p>}</section>;
        })}
        {result.evidence_limitations.length > 0 && <section className="brief-section"><h2>Evidence limits</h2><Notice kind="caution"><span className="badge caution mb-2"><Icon name="alert" /> Flagged for review</span>{result.evidence_limitations.map((note) => <p key={note}>{note}</p>)}</Notice></section>}
      </div><div><EmailPanel key={JSON.stringify([detail.email_edit, result.email])} detail={detail} onSaved={setDetail} onRegenerate={reload} /><FeedbackPanel id={id} disabled={active} /></div></div>
      <section className="source-list"><h2>Follow the sources <span className="text-[var(--ink-subtle)]">({result.sources.length})</span></h2>{result.sources.map((source) => <details key={source.id} id={`source-${source.id}`} className="source-details"><summary>{source.title} {source.type === "user_provided" && <span className="badge neutral"><Icon name="text" /> User-provided</span>}</summary><SourceChip source={source} /><blockquote>{source.excerpt}</blockquote></details>)}</section>
    </>}
  </>;
}

function SourceChip({ source }: { source: Source }) {
  const url = safeSourceUrl(source.url);
  return url ? <a className="source-chip" href={url} target="_blank" rel="noopener noreferrer"><Icon name="external" />{sourceDomain(url)}<span className="sr-only">, opens in a new tab</span></a> : <a className="source-chip" href={`#source-${source.id}`} onClick={() => { const element = document.getElementById(`source-${source.id}`); if (element instanceof HTMLDetailsElement) element.open = true; }}><Icon name="text" /> User-provided</a>;
}

function ProgressPanel({ detail }: { detail: BriefDetail }) {
  const latest = detail.progress.at(-1);
  const lastIndex = latest ? stages.findIndex(([stage]) => stage === latest.stage) : -1;
  const announcement = latest ? `${stages[lastIndex]?.[1]} ${latest.status === "active" ? "in progress" : latest.status}.` : "Your brief is waiting to begin.";
  return <section className="panel progress-panel" aria-label="Research progress"><div className="progress-heading"><div><h2>{detail.status === "queued" ? "Your brief is in the queue." : "A closer look, step by step."}</h2><p role="status" aria-live="polite">{announcement}{latest?.revision_attempt ? ` Revision ${latest.revision_attempt} of 2.` : ""}</p></div><Icon name="document" /></div><ol className="steps">{stages.map(([stage, label], index) => { const event = detail.progress.findLast((e) => e.stage === stage); const state = event?.status ?? (index < lastIndex ? "complete" : "pending"); return <li key={stage} className="step" data-state={state} aria-current={state === "active" ? "step" : undefined}><span className="step-marker">{state === "complete" ? <Icon name="check" /> : state === "failed" ? <Icon name="alert" /> : null}</span><span>{label}<span className="sr-only">: {state}</span></span></li>; })}</ol></section>;
}

function EmailPanel({ detail, onSaved, onRegenerate }: { detail: BriefDetail; onSaved: (row: BriefDetail) => void; onRegenerate: () => void }) {
  const original = detail.email_edit ?? { subject: detail.result!.email.subject.text, body: detail.result!.email.paragraphs.map((p) => p.text).join("\n\n") };
  const [value, setValue] = useState<EmailEdit>(original);
  const [tone, setTone] = useState("professional");
  const [busy, setBusy] = useState("");
  const [error, setError] = useState("");
  const [status, setStatus] = useState("");
  const dirty = value.subject !== original.subject || value.body !== original.body;
  const disabled = isActive(detail.status) || !!busy;
  async function save(event: FormEvent) {
    event.preventDefault(); if (disabled) return; setBusy("save"); setError("");
    try { const row = await api<BriefDetail>(`/briefs/${detail.id}/email`, { method: "PUT", body: JSON.stringify({ ...value, expected_version: detail.version }) }); onSaved(row); setStatus("Your edit is saved."); }
    catch (error) { setError(messageOf(error)); } finally { setBusy(""); }
  }
  async function regenerate() {
    if (disabled || dirty) return; setBusy("regenerate"); setError("");
    try { await api(`/briefs/${detail.id}/email/regenerate`, { method: "POST", body: JSON.stringify({ tone, expected_version: detail.version }) }); onRegenerate(); }
    catch (error) { setError(messageOf(error)); } finally { setBusy(""); }
  }
  async function copy() {
    try { await navigator.clipboard.writeText(`Subject: ${value.subject}\n\n${value.body}`); setStatus("Email copied. Ready for your review."); }
    catch { setError("Copy isn’t available in this browser. Select the email text and copy it manually."); }
  }
  const sources = detail.result!.sources;
  const cited = Array.from(new Set([detail.result!.email.subject, ...detail.result!.email.paragraphs].flatMap((p) => p.source_ids)));
  return <section className="panel email-panel"><div className="panel-title"><Icon name="mail" /><h2>Your first email</h2></div><p>{dirty ? "Unsaved edits. Save your changes before regenerating." : detail.email_edit ? "Your saved edit. Changes you make are not automatically verified." : "A checked starting point. Review and edit before sending."}</p>
    {error && <Notice>{error}</Notice>}
    <form className="form-stack" onSubmit={save}>
      <div className="field"><label className="field-label" htmlFor="email-subject">Subject</label><input id="email-subject" maxLength={500} required value={value.subject} onChange={(e) => setValue({ ...value, subject: e.target.value })} disabled={disabled} /></div>
      <div className="field"><label className="field-label" htmlFor="email-body">Message</label><textarea id="email-body" maxLength={12000} required value={value.body} onChange={(e) => setValue({ ...value, body: e.target.value })} disabled={disabled} /></div>
      <div className="email-actions"><button className="button button-primary button-small" disabled={disabled || !dirty || !value.body.trim()}>{busy === "save" ? "Saving…" : "Save edits"}</button><button type="button" className="button button-secondary button-small" onClick={copy} disabled={!value.body.trim()}><Icon name="copy" />Copy email</button></div>
    </form>
    <p className="inline-status mt-3" role="status">{status}</p>
    {!detail.email_edit && !dirty && cited.length > 0 && <div className="claim-footer mb-4">{cited.map((id) => { const source = sources.find((s) => s.id === id); return source ? <SourceChip key={id} source={source} /> : null; })}</div>}
    <div className="regenerate-row"><div className="field"><label className="field-label" htmlFor="email-tone">Email tone</label><select id="email-tone" value={tone} onChange={(e) => setTone(e.target.value)} disabled={disabled || dirty}><option value="professional">Professional</option><option value="friendly">Friendly</option><option value="concise">Concise</option></select></div><button className="button button-secondary button-small" disabled={disabled || dirty} onClick={regenerate}><Icon name="refresh" />{busy === "regenerate" ? "Starting…" : "Regenerate"}</button></div><p className="field-help mt-3">Regeneration replaces the email when it’s ready. Your company research stays intact.</p>
  </section>;
}

function FeedbackPanel({ id, disabled }: { id: string; disabled: boolean }) {
  const [rating, setRating] = useState<number | null>(null);
  const [comment, setComment] = useState("");
  const [busy, setBusy] = useState(false);
  const [status, setStatus] = useState("");
  const [error, setError] = useState("");
  async function submit(event: FormEvent) {
    event.preventDefault(); if (!rating || busy) return; setBusy(true); setError("");
    try { await api(`/briefs/${id}/feedback`, { method: "POST", body: JSON.stringify({ rating, comment }) }); setStatus("Thanks. Your feedback is saved."); }
    catch (error) { setError(messageOf(error)); } finally { setBusy(false); }
  }
  return <form className="panel feedback-panel" onSubmit={submit}><h3>Was this brief useful?</h3><div className="feedback-buttons"><button type="button" className="button button-secondary button-small" aria-pressed={rating === 1} onClick={() => { setRating(1); setStatus(""); }} disabled={disabled}><Icon name="up" />Useful</button><button type="button" className="button button-secondary button-small" aria-pressed={rating === -1} onClick={() => { setRating(-1); setStatus(""); }} disabled={disabled}><Icon name="down" />Needs work</button></div>{rating !== null && <><div className="field"><label className="field-label" htmlFor="feedback-comment">Anything to add?<small>Optional</small></label><textarea id="feedback-comment" value={comment} maxLength={2000} onChange={(e) => setComment(e.target.value)} disabled={disabled || busy} /></div><button className="button button-secondary button-small" disabled={disabled || busy}>{busy ? "Saving…" : "Save feedback"}</button></>}{error && <Notice>{error}</Notice>}<p className="inline-status mt-3" role="status">{status}</p></form>;
}
