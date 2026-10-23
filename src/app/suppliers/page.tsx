"use client";
import { Card, EmptyState, LoadingSpinner, SectionHeader } from "@/components/shared/ui";
import { useSuppliers } from "@/hooks/useWarehouse";

export default function SuppliersPage(){
 const q=useSuppliers();
 return <div><SectionHeader title="Piegādātāji" subtitle="Piegādātāju kontaktinformācija"/>
  <Card>{q.isLoading?<LoadingSpinner/>:q.isError?<p className="p-6 text-red-700">Datus neizdevās ielādēt: {q.error.message}</p>:!q.data?.length?<EmptyState message="Piegādātāju vēl nav"/>:<table className="w-full text-sm"><thead><tr className="bg-secondary/60 text-xs text-muted-foreground"><th className="text-left p-3">Uzņēmums</th><th className="text-left p-3">Kontaktpersona</th><th className="text-left p-3">E-pasts</th><th className="text-left p-3">Tālrunis</th></tr></thead><tbody className="divide-y">{q.data.map(s=><tr key={s.id}><td className="p-3 font-medium">{s.name}</td><td className="p-3">{s.contactPerson}</td><td className="p-3">{s.email}</td><td className="p-3">{s.phone}</td></tr>)}</tbody></table>}</Card>
 </div>;
}