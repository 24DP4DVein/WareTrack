"use client";
import { Card, EmptyState, LoadingSpinner, SectionHeader, StockBar } from "@/components/shared/ui";
import { useLocations } from "@/hooks/useWarehouse";

export default function LocationsPage(){
 const q=useLocations();
 return <div><SectionHeader title="Noliktavas vietas" subtitle="Noliktavas zonu un ietilpības pārskats"/>
  <Card>{q.isLoading?<LoadingSpinner/>:q.isError?<p className="p-6 text-red-700">Datus neizdevās ielādēt: {q.error.message}</p>:!q.data?.length?<EmptyState message="Noliktavas vietu vēl nav"/>:<table className="w-full text-sm"><thead><tr className="bg-secondary/60 text-xs text-muted-foreground"><th className="text-left p-3">Kods</th><th className="text-left p-3">Nosaukums</th><th className="text-left p-3">Aizpildījums</th><th className="text-left p-3">Ietilpība</th></tr></thead><tbody className="divide-y">{q.data.map(l=><tr key={l.id}><td className="p-3 font-mono">{l.code}</td><td className="p-3 font-medium">{l.name}</td><td className="p-3"><div className="flex items-center gap-2">{l.usedCapacity}<StockBar stock={l.usedCapacity} minStock={Math.max(1,Math.floor(l.capacity/3))}/></div></td><td className="p-3">{l.capacity}</td></tr>)}</tbody></table>}</Card>
 </div>;
}