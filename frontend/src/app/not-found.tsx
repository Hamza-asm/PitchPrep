import Link from "next/link";
import { Logo } from "@/components/ui";
export default function NotFound() { return <main id="main" className="wrap section"><Link href="/"><Logo /></Link><div className="page-heading mt-16"><h1>This page isn’t here.</h1><p>Return to your workspace to open a saved brief or start a new one.</p></div><Link className="button button-primary" href="/app">Open workspace</Link></main>; }
