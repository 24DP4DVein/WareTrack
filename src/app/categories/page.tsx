"use client";
import { Card, EmptyState, LoadingSpinner, SectionHeader } from "@/components/shared/ui";
import { useCategories } from "@/hooks/useWarehouse";

export default function CategoriesPage(){
 const q=useCategories();
 return <div><SectionHeader title="Kategorijas" subtitle="Preču kategoriju saraksts"/>
  <Card>{q.isLoading?<LoadingSpinner/>:q.isError?<p className="p-6 text-red-700">Datus neizdevās ielādēt: {q.error.message}</p>:!q.data?.length?<EmptyState message="Kategoriju vēl nav"/>:<table className="w-full text-sm"><thead><tr className="bg-secondary/60 text-xs text-muted-foreground"><th className="text-left p-3">Nosaukums</th><th className="text-left p-3">Apraksts</th><th className="text-left p-3">Preces</th></tr></thead><tbody className="divide-y">{q.data.map(c=><tr key={c.id}><td className="p-3 font-medium">{c.icon} {c.name}</td><td className="p-3 text-muted-foreground">{c.description||"—"}</td><td className="p-3">{c.itemCount}</td></tr>)}</tbody></table>}</Card>
 </div>;
}