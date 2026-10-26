"use client";

import { useState } from "react";
import { Edit2, Plus, Trash2 } from "lucide-react";
import { Button, Card, EmptyState, LoadingSpinner, SectionHeader } from "@/components/shared/ui";
import DeleteConfirmModal from "@/components/shared/DeleteConfirmModal";
import SupplierModal from "@/components/suppliers/SupplierModal";
import { useDeleteSupplier, useSuppliers } from "@/hooks/useWarehouse";
import { useAppStore } from "@/store/useAppStore";
import type { Supplier } from "@/types";

export default function SuppliersPage() {
  const user = useAppStore((state) => state.user);
  const toast = useAppStore((state) => state.showToast);
  const canOperate = user?.role === "VADITAJS" || user?.role === "ADMIN";
  const query = useSuppliers();
  const remove = useDeleteSupplier();
  const [editing, setEditing] = useState<Supplier | null | undefined>(undefined);
  const [deleting, setDeleting] = useState<Supplier | null>(null);

  return <div>
    <SectionHeader title="Piegādātāji" subtitle="Piegādātāju kontaktinformācija">
      {canOperate && <Button variant="primary" onClick={() => setEditing(null)}><Plus size={13} />Pievienot piegādātāju</Button>}
    </SectionHeader>
    <Card>
      {query.isLoading ? <LoadingSpinner /> : query.isError ? <p className="p-6 text-red-700">Datus neizdevās ielādēt: {query.error.message}</p> : !query.data?.length ? <EmptyState message="Piegādātāju vēl nav" /> : <div className="overflow-x-auto">
        <table className="w-full text-sm min-w-[760px]"><thead><tr className="bg-secondary/60 text-xs text-muted-foreground">
          <th className="text-left p-3">Uzņēmums</th><th className="text-left p-3">Kontaktpersona</th><th className="text-left p-3">E-pasts</th><th className="text-left p-3">Tālrunis</th>{canOperate && <th className="p-3" />}
        </tr></thead><tbody className="divide-y">{query.data.map((supplier) => <tr key={supplier.id}>
          <td className="p-3 font-medium">{supplier.name}</td><td className="p-3">{supplier.contactPerson}</td><td className="p-3">{supplier.email}</td><td className="p-3">{supplier.phone}</td>
          {canOperate && <td className="p-3"><div className="flex justify-end gap-1"><Button size="sm" onClick={() => setEditing(supplier)}><Edit2 size={11} />Labot</Button><Button size="sm" variant="danger" aria-label={`Dzēst ${supplier.name}`} onClick={() => setDeleting(supplier)}><Trash2 size={11} /></Button></div></td>}
        </tr>)}</tbody></table>
      </div>}
    </Card>
    {canOperate && <>
      <SupplierModal open={editing !== undefined} supplier={editing} onClose={() => setEditing(undefined)} />
      <DeleteConfirmModal open={!!deleting} itemName={deleting?.name ?? ""} isLoading={remove.isPending} onClose={() => setDeleting(null)} onConfirm={() => deleting && remove.mutate(deleting.id, {
        onSuccess: () => { toast("Piegādātājs izdzēsts", "warning"); setDeleting(null); },
        onError: (error) => toast(error.message, "error"),
      })} />
    </>}
  </div>;
}
