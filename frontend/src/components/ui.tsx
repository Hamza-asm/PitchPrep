import type { ReactNode } from "react";
import Image from "next/image";

export type IconName = "arrow" | "arrow-circle" | "text" | "globe" | "chart" | "link" | "mail" | "check" | "document" | "alert" | "refresh" | "plus" | "history" | "settings" | "copy" | "external" | "up" | "down" | "close" | "menu";

// Original glyphs with the consistent stroke specified in DESIGN.md.
export function Icon({ name, className = "" }: { name: IconName; className?: string }) {
  const paths: Record<IconName, ReactNode> = {
    arrow: <path d="M5 12h14m-6-6 6 6-6 6" />,
    "arrow-circle": <><circle cx="12" cy="12" r="9" /><path d="M8 12h8m-4-4 4 4-4 4" /></>,
    text: <><rect x="5" y="3" width="14" height="18" rx="2" /><path d="M8 8h8M8 12h8M8 16h4" /></>,
    globe: <><circle cx="10" cy="10" r="7" /><path d="M3 10h14M10 3c4 4 4 10 0 14-4-4-4-10 0-14m5 12 6 6" /></>,
    chart: <path d="M4 4v16h16M8 15v-4m5 4V7m5 8v-5m-4-6 4-2 3 3" />,
    link: <path d="m10 8 3-3a4 4 0 0 1 6 6l-3 3m-2 2-3 3a4 4 0 0 1-6-6l3-3m1 5 6-6" />,
    mail: <><rect x="3" y="5" width="18" height="14" rx="3" /><path d="m4 7 8 6 8-6m-5 10 2 2 4-4" /></>,
    check: <path d="m5 12 4 4L19 6" />,
    document: <path d="M14 3H6a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V9l-6-6Zm0 0v6h6M8 13h8m-8 4h5" />,
    alert: <path d="m10.3 4.5-8 14A1.7 1.7 0 0 0 3.8 21h16.4a1.7 1.7 0 0 0 1.5-2.5l-8-14a2 2 0 0 0-3.4 0ZM12 9v5m0 3v.1" />,
    refresh: <path d="M20 10a8 8 0 0 0-14-5L3 8m0-5v5h5m-4 6a8 8 0 0 0 14 5l3-3m0 5v-5h-5" />,
    plus: <path d="M12 5v14M5 12h14" />,
    history: <path d="M3 11a9 9 0 1 1 2 7M3 4v7h7m2-4v6l4 2" />,
    settings: <><path d="M5 3v5m0 4v9m7-18v11m0 4v3m7-18v3m0 4v11" /><path d="M2 8h6v4H2zm7 6h6v4H9zm7-8h6v4h-6z" /></>,
    copy: <><rect x="8" y="8" width="12" height="13" rx="2" /><path d="M16 8V5a2 2 0 0 0-2-2H5a2 2 0 0 0-2 2v9a2 2 0 0 0 2 2h3" /></>,
    external: <path d="M14 3h7v7m0-7L10 14m-1-9H5a2 2 0 0 0-2 2v12a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-4" />,
    up: <path d="M7 10H3v11h4m0-11 5-8 2 1v6h5a2 2 0 0 1 2 2l-2 8a2 2 0 0 1-2 2H7V10Z" />,
    down: <g transform="rotate(180 12 12)"><path d="M7 10H3v11h4m0-11 5-8 2 1v6h5a2 2 0 0 1 2 2l-2 8a2 2 0 0 1-2 2H7V10Z" /></g>,
    close: <path d="m6 6 12 12M6 18 18 6" />,
    menu: <path d="M4 7h16M4 12h16M4 17h16" />,
  };
  return <svg className={`icon ${className}`} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">{paths[name]}</svg>;
}

export function Logo({ markOnly = false }: { markOnly?: boolean }) {
  if (markOnly) {
    return <span className="brand"><svg className="brand-mark" viewBox="0 0 32 32" fill="none" aria-hidden="true"><path d="M7 3h13l6 6v20H7V3Z" fill="currentColor" /><path d="M20 3v7h6M11 17l4 4 8-9" stroke="var(--surface)" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" /></svg></span>;
  }
  return <span className="brand"><Image className="brand-logo" src="/PitchPrepLogo.png" alt="PitchPrep" width={2172} height={724} /></span>;
}

export function Notice({ children, kind = "error" }: { children: ReactNode; kind?: "error" | "caution" | "info" }) {
  return <div className={`notice notice-${kind}`} role={kind === "error" ? "alert" : "status"}><Icon name="alert" /><div>{children}</div></div>;
}

export function SharedDemoNotice() {
  return <aside className="demo-notice wrap" aria-label="Shared demo workspace notice"><Icon name="alert" /><div><strong>PitchPrep demo workspace</strong><p>Sign-up and login are not available yet. This deployment is shared, so the seller profile, research briefs, pasted details, and email edits can be seen by everyone using it. Please do not enter confidential information.</p></div></aside>;
}

export function Skeleton({ label = "Loading your workspace" }: { label?: string }) {
  return <div className="loading-panel" role="status" aria-label={label}><div className="skeleton skeleton-title" /><div className="skeleton" /><div className="skeleton" /><div className="skeleton skeleton-block" /><span className="sr-only">{label}</span></div>;
}
