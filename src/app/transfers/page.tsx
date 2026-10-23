"use client";
import { Card, EmptyState, LoadingSpinner, PriorityBadge, SectionHeader, TransferStatusBadge } from "@/components/shared/ui";
import { useTransfers } from "@/hooks/useWarehouse";

export default function TransfersPage(){
 const q=useTransfers();
 return <div><SectionHeader title="Pārvietošana" subtitle="Preču pārvietošanas uzdevumi"/>
  <Card>{q.isLoading?<LoadingSpinner/>:q.isError?<p className="p-6 text-red-700">Datus neizdevās ielādēt: {q.error.message}</p>:!q.data?.length?<EmptyState message="Pārvietojumu vēl nav"/>:<table className="w-full text-sm"><thead><tr className="bg-secondary/60 text-xs text-muted-foreground"><th className="text-left p-3">Kods</th><th className="text-left p-3">Prece</th><th className="text-left p-3">No</th><th className="text-left p-3">Uz</th><th className="text-left p-3">Daudzums</th><th className="text-left p-3">Statuss</th><th className="text-left p-3">Prioritāte</th></tr></thead><tbody className="divide-y">{q.data.map(t=><tr key={t.id}><td className="p-3 font-mono">{t.code}</td><td className="p-3 font-medium">{t.itemName}</td><td className="p-3">{t.sourceLocationName}</td><td className="p-3">{t.destinationLocationName}</td><td className="p-3">{t.quantity}</td><td className="p-3"><TransferStatusBadge status={t.status}/></td><td className="p-3"><PriorityBadge priority={t.priority}/></td></tr>)}</tbody></table>}</Card>
 </div>;
}