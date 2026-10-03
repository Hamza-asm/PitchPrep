"use client";
import { Notice } from "@/components/ui";
export default function WorkspaceError({ reset }: { reset: () => void }) { return <main id="main" className="wrap section"><div className="page-heading"><h1>The workspace couldn’t open.</h1></div><Notice>Your saved briefs are still available. Try opening the workspace again.</Notice><button className="button button-primary" onClick={reset}>Try again</button></main>; }
