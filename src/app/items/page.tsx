"use client";

import { useEffect, useState } from "react";
import { Edit2, Plus, Search, Trash2 } from "lucide-react";
import { useCategories, useDeleteItem, useItems } from "@/hooks/useWarehouse";
import { useAppStore } from "@/store/useAppStore";
import { Button, Card, EmptyState, ItemStatusBadge, LoadingSpinner, SectionHeader, StockBar } from "@/components/shared/ui";
import AddItemModal from "@/components/items/AddItemModal";
import DeleteConfirmModal from "@/components/shared/DeleteConfirmModal";
import { formatCurrency, formatDate } from "@/lib/utils";
import type { Item } from "@/types";

export default function ItemsPage() {
  const user = useAppStore((state) => state.user);
  const toast = useAppStore((state) => state.showToast);
  const canOperate = user?.role === "VADITAJS" || user?.role === "ADMIN";
  const [search, setSearch] = useState("");
  const [category, setCategory] = useState(0);
  const [status, setStatus] = useState("");
  const [page, setPage] = useState(1);
  const [editing, setEditing] = useState<Item | null | undefined>(undefined);
  const [deleting, setDeleting] = useState<Item | null>(null);
  const result = useItems({ search, category: category || undefined, status, page, pageSize: 10 });
  const categories = useCategories();
  const remove = useDeleteItem();
  const pages = Math.max(1, Math.ceil((result.data?.total ?? 0) / 10));

  useEffect(() => setPage(1), [search, category, status]);

  return <div>
    <SectionHeader title="Preces" subtitle={`${result.data?.total ?? 0} atrastas preces`}>
      {canOperate && <Button variant="primary" onClick={() => setEditing(null)}><Plus size={13} />Pievienot preci</Button>}
    </SectionHeader>
    <div className="grid grid-cols-1 sm:grid-cols-3 gap-2 mb-4">
      <label className="relative">
        <Search className="absolute left-3 top-2.5 text-muted-foreground" size={14} />
        <input value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Meklēt pēc nosaukuma vai SKU" className="w-full border rounded-md pl-9 pr-3 py-2 text-sm" />
      </label>
      <select value={category} onChange={(event) => setCategory(Number(event.target.value))} className="border rounded-md px-3 py-2 text-sm">
        <option value={0}>Visas kategorijas</option>
        {categories.data?.map((entry) => <option value={entry.id} key={entry.id}>{entry.name}</option>)}
      </select>
      <select value={status} onChange={(event) => setStatus(event.target.value)} className="border rounded-md px-3 py-2 text-sm">
        <option value="">Visi krājuma statusi</option><option value="ok">Pietiekams</option><option value="low">Zems</option><option value="critical">Kritisks</option>
      </select>
    </div>
    <Card>
      {result.isLoading ? <LoadingSpinner /> : result.isError ? <p className="p-6 text-red-700">Datus neizdevās ielādēt: {result.error.message}</p> : !result.data?.items.length ? <EmptyState message="Neviena prece neatbilst izvēlētajiem filtriem" /> : <>
        <div className="overflow-x-auto">
          <table className="w-full text-[13px] min-w-[850px]">
            <thead><tr className="bg-secondary/60 text-[11px] uppercase text-muted-foreground">
              <th className="text-left p-3">Prece / SKU</th><th className="text-left p-3">Kategorija</th><th className="text-left p-3">Krājums</th><th className="text-left p-3">Vieta</th><th className="text-left p-3">Cena</th><th className="text-left p-3">Atjaunināts</th>{canOperate && <th className="p-3" />}
            </tr></thead>
            <tbody className="divide-y">{result.data.items.map((item) => <tr key={item.id} className="hover:bg-secondary/40">
              <td className="p-3"><b>{item.name}</b><p className="font-mono text-[11px] text-muted-foreground">{item.sku}</p></td>
              <td className="p-3">{item.categoryName}</td>
              <td className="p-3"><div className="flex items-center gap-2"><b>{item.stock}</b><ItemStatusBadge status={item.status} /></div><StockBar stock={item.stock} minStock={item.minStock} /></td>
              <td className="p-3">{item.locationName}</td><td className="p-3">{formatCurrency(item.price)}</td><td className="p-3">{formatDate(item.updatedAt)}</td>
              {canOperate && <td className="p-3"><div className="flex gap-1 justify-end"><Button size="sm" onClick={() => setEditing(item)}><Edit2 size={11} />Labot</Button><Button size="sm" variant="danger" aria-label={`Dzēst ${item.name}`} onClick={() => setDeleting(item)}><Trash2 size={11} /></Button></div></td>}
            </tr>)}</tbody>
          </table>
        </div>
        <div className="p-3 border-t flex gap-2 items-center">
          <Button size="sm" disabled={page <= 1} onClick={() => setPage((value) => value - 1)}>Iepriekšējā</Button>
          <span className="text-xs text-muted-foreground">Lapa {page} no {pages}</span>
          <Button size="sm" disabled={page >= pages} onClick={() => setPage((value) => value + 1)}>Nākamā</Button>
        </div>
      </>}
    </Card>
    {canOperate && <>
      <AddItemModal open={editing !== undefined} item={editing} onClose={() => setEditing(undefined)} />
      <DeleteConfirmModal open={!!deleting} itemName={deleting?.name ?? ""} isLoading={remove.isPending} onClose={() => setDeleting(null)} onConfirm={() => deleting && remove.mutate(deleting.id, {
        onSuccess: () => { toast("Prece izdzēsta", "warning"); setDeleting(null); },
        onError: (error) => toast(error.message, "error"),
      })} />
    </>}
  </div>;
}
