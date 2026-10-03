"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { api, messageOf, statusLabels, type BriefPage, type ResearchInput, type SellerProfile } from "@/lib/api";
import { Icon, Logo, Notice, SharedDemoNotice, Skeleton } from "../ui";
import { SellerForm, TargetForm } from "./forms";
import { BriefScreen } from "./brief-screen";

export function Workspace({ briefId }: { briefId?: string }) {
  const [profile, setProfile] = useState<SellerProfile | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [history, setHistory] = useState<BriefPage | null>(null);
  const [historyError, setHistoryError] = useState("");
  const [historyBusy, setHistoryBusy] = useState(true);
  const [editSeller, setEditSeller] = useState(false);
  const [editInput, setEditInput] = useState<ResearchInput | undefined>();
  const loadHistory = useCallback(async (offset = 0) => {
    setHistoryBusy(true); setHistoryError("");
    try { const page = await api<BriefPage>(`/briefs?limit=10&offset=${offset}`); setHistory((previous) => offset && previous ? { ...page, items: [...previous.items, ...page.items] } : page); }
    catch (error) { setHistoryError(messageOf(error)); } finally { setHistoryBusy(false); }
  }, []);
  const loadProfile = useCallback(async () => {
    setError(""); setLoading(true);
    try { setProfile(await api<SellerProfile | null>("/seller-profile")); } catch (error) { setError(messageOf(error)); } finally { setLoading(false); }
  }, []);
  useEffect(() => {
    const abort = new AbortController();
    api<SellerProfile | null>("/seller-profile", { signal: abort.signal })
      .then(setProfile).catch((error) => { if (!abort.signal.aborted) setError(messageOf(error)); })
      .finally(() => { if (!abort.signal.aborted) setLoading(false); });
    api<BriefPage>("/briefs?limit=10&offset=0", { signal: abort.signal })
      .then(setHistory).catch((error) => { if (!abort.signal.aborted) setHistoryError(messageOf(error)); })
      .finally(() => { if (!abort.signal.aborted) setHistoryBusy(false); });
    return () => abort.abort();
  }, []);
  const saved = (value: SellerProfile) => { setProfile(value); setEditSeller(false); };
  return <>
    <header className="app-header"><div className="app-header-inner wrap"><div className="flex items-center"><Link href="/" aria-label="PitchPrep home"><Logo /></Link><span className="workspace-tag">Your research workspace</span></div><Link href="/" className="button button-quiet button-small">Back to home<Icon name="external" /></Link></div></header>
    <SharedDemoNotice />
    <div className="workspace-shell wrap"><aside className="workspace-sidebar" aria-label="Workspace navigation"><div className="sidebar-actions"><Link className="button button-primary" href="/app" onClick={() => { setEditSeller(false); setEditInput(undefined); }}><Icon name="plus" /> New brief</Link><button className="button button-secondary" onClick={() => { setEditSeller(true); setEditInput(undefined); }}><Icon name="settings" /> Seller profile</button></div><div className="sidebar-history"><div className="sidebar-heading"><span className="flex items-center gap-2"><Icon name="history" /> Recent briefs</span><button type="button" className="icon-button" aria-label="Refresh history" onClick={() => void loadHistory()} disabled={historyBusy}><Icon name="refresh" /></button></div>
      {historyError && <Notice>{historyError}<button className="button button-small button-secondary" onClick={() => void loadHistory()}>Retry history</button></Notice>}
      {!history && historyBusy && <Skeleton label="Loading history" />}
      {history?.items.length === 0 && <div className="history-empty">Your next conversation starts here. Saved briefs will appear in this list.</div>}
      <nav className="history-list" aria-label="Saved briefs">{history?.items.map((item) => <Link key={item.id} href={`/app/${item.id}`} className="history-item" aria-current={item.id === briefId ? "page" : undefined} onClick={() => { setEditSeller(false); setEditInput(undefined); }}><strong>{item.company_name}</strong><span className="history-meta"><span>{new Date(item.created_at).toLocaleDateString(undefined, { month: "short", day: "numeric" })}</span><span>{statusLabels[item.status]}</span></span></Link>)}</nav>
      {history?.next_offset != null && <button className="button button-quiet button-small mt-2" disabled={historyBusy} onClick={() => void loadHistory(history.next_offset!)}>{historyBusy ? "Loading…" : "Load older briefs"}</button>}
    </div></aside>
    <main id="main" className="workspace-main">
      {loading ? <Skeleton /> : error ? <><div className="page-heading"><h1>Let’s get you connected.</h1><p>Your research workspace will be here when the connection returns.</p></div><Notice>{error}<button className="button button-secondary button-small" onClick={() => void loadProfile()}>Try again</button></Notice></> : editSeller || !profile ? <SellerForm key={profile ? "edit" : "setup"} profile={profile} onSaved={saved} onCancel={profile ? () => setEditSeller(false) : undefined} /> : editInput ? <TargetForm key="edit-input" initial={editInput} onCancel={() => setEditInput(undefined)} /> : briefId ? <BriefScreen key={briefId} id={briefId} onEdit={setEditInput} onComplete={loadHistory} /> : <TargetForm />}
    </main></div>
  </>;
}
