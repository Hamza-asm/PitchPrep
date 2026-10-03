import { notFound } from "next/navigation";
import type { Metadata } from "next";
import { Workspace } from "@/components/workspace/workspace";
export const metadata: Metadata = { title: "Prospect brief", robots: { index: false, follow: false } };
export default async function BriefPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  if (!/^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(id)) notFound();
  return <Workspace briefId={id} />;
}
