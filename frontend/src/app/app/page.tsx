import type { Metadata } from "next";
import { Workspace } from "@/components/workspace/workspace";
export const metadata: Metadata = { title: "Your workspace", robots: { index: false, follow: false } };
export default function AppPage() { return <Workspace />; }
