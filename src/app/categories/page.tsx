"use client";
import { useState } from "react";
import { Edit2, Plus, Trash2 } from "lucide-react";
import { Card, EmptyState, LoadingSpinner, SectionHeader, Button } from "@/components/shared/ui";
import DeleteConfirmModal from "@/components/shared/DeleteConfirmModal";
import { useCategories, useDeleteCategory } from "@/hooks/useWarehouse";
import { useAppStore } from "@/store/useAppStore";
import CategoryModal from "@/components/categories/CategoryModal";
import type { Category } from "@/types";

export default function CategoriesPage(){
 const q=useCategories();
 const user=useAppStore((state)=>state.user);
 const canOperate=user?.role==="VADITAJS"||user?.role==="ADMIN";
 const [editing,setEditing]=useState<Category|null|undefined>(undefined);
 const [deleting,setDeleting]=useState<Category|null>(null);
 const remove=useDeleteCategory();
 return <div><SectionHeader title="Kategorijas" subtitle="Preču kategoriju saraksts">{canOperate&&<Button variant="primary" onClick={()=>setEditing(null)}><Plus size={13}/>Pievienot kategoriju</Button>}</SectionHeader>
   <Card>{q.isLoading?<LoadingSpinner/>:q.isError?<p className="p-6 text-red-700">Datus neizdevās ielādēt: {q.error.message}</p>:!q.data?.length?<EmptyState message="Kategoriju vēl nav"/>:<table className="w-full text-sm"><thead><tr className="bg-secondary/60 text-xs text-muted-foreground"><th className="text-left p-3">Nosaukums</th><th className="text-left p-3">Apraksts</th><th className="text-left p-3">Preces</th>{canOperate&&<th className="p-3"/>}</tr></thead><tbody className="divide-y">{q.data.map(c=><tr key={c.id}><td className="p-3 font-medium">{c.icon} {c.name}</td><td className="p-3 text-muted-foreground">{c.description||"—"}</td><td className="p-3">{c.itemCount}</td>{canOperate&&<td className="p-3 text-right"><div className="flex justify-end gap-1"><Button size="sm" onClick={()=>setEditing(c)}><Edit2 size={11}/>Labot</Button><Button size="sm" variant="danger" aria-label={`Dzēst ${c.name}`} onClick={()=>setDeleting(c)}><Trash2 size={11}/></Button></div></td>}</tr>)}</tbody></table>}</Card>
    {canOperate&&<CategoryModal open={editing!==undefined} category={editing} onClose={()=>setEditing(undefined)}/>}
   {canOperate&&<DeleteConfirmModal open={!!deleting} itemName={deleting?.name??""} isLoading={remove.isPending} onClose={()=>setDeleting(null)} onConfirm={()=>deleting&&remove.mutate(deleting.id,{onSuccess:()=>{useAppStore.getState().showToast("Kategorija izdzēsta","warning");setDeleting(null)},onError:error=>useAppStore.getState().showToast(error.message,"error")})}/>}
 </div>;
}
