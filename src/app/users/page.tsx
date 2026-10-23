"use client";
import { Card, EmptyState, LoadingSpinner, SectionHeader, Badge } from "@/components/shared/ui";
import { useUsers } from "@/hooks/useWarehouse";

export default function UsersPage(){
 const q=useUsers();
 return <div><SectionHeader title="Lietotāji" subtitle="Sistēmas lietotāju pārvaldība"/>
  <Card>{q.isLoading?<LoadingSpinner/>:q.isError?<p className="p-6 text-red-700">Datus neizdevās ielādēt: {q.error.message}</p>:!q.data?.length?<EmptyState message="Lietotāju vēl nav"/>:<table className="w-full text-sm"><thead><tr className="bg-secondary/60 text-xs text-muted-foreground"><th className="text-left p-3">Vārds</th><th className="text-left p-3">E-pasts</th><th className="text-left p-3">Loma</th><th className="text-left p-3">Statuss</th></tr></thead><tbody className="divide-y">{q.data.map(u=><tr key={u.id}><td className="p-3 font-medium">{u.name}</td><td className="p-3">{u.email}</td><td className="p-3"><Badge variant={u.role==="ADMIN"?"purple":"blue"}>{u.role==="ADMIN"?"Administrators":"Lietotājs"}</Badge></td><td className="p-3"><Badge variant={u.isActive?"green":"gray"}>{u.isActive?"Aktīvs":"Neaktīvs"}</Badge></td></tr>)}</tbody></table>}</Card>
 </div>;
}