"use client";

import { useState } from "react";
import { Edit2, MapPin, Plus, Trash2 } from "lucide-react";
import { Button, Card, EmptyState, LoadingSpinner, SectionHeader, StockBar } from "@/components/shared/ui";
import DeleteConfirmModal from "@/components/shared/DeleteConfirmModal";
import LocationModal from "@/components/locations/LocationModal";
import { useDeleteLocation, useLocations } from "@/hooks/useWarehouse";
import { useAppStore } from "@/store/useAppStore";
import type { Location } from "@/types";

export default function LocationsPage() {
  const user = useAppStore((state) => state.user);
  const toast = useAppStore((state) => state.showToast);
  const canOperate = user?.role === "VADITAJS" || user?.role === "ADMIN";
  const query = useLocations();
  const remove = useDeleteLocation();
  const [editing, setEditing] = useState<Location | null | undefined>(undefined);
  const [deleting, setDeleting] = useState<Location | null>(null);

  return <div>
    <SectionHeader title="Noliktavas vietas" subtitle="Noliktavas zonu un ietilpības pārskats">
      {canOperate && <Button variant="primary" onClick={() => setEditing(null)}><Plus size={13} />Pievienot vietu</Button>}
    </SectionHeader>
    <Card>
      {query.isLoading ? <LoadingSpinner /> : query.isError ? <p className="p-6 text-red-700">Datus neizdevās ielādēt: {query.error.message}</p> : !query.data?.length ? <EmptyState message="Noliktavas vietu vēl nav" /> : <div className="overflow-x-auto">
        <table className="w-full text-sm min-w-[680px]"><thead><tr className="bg-secondary/60 text-xs text-muted-foreground">
          <th className="text-left p-3">Kods</th><th className="text-left p-3">Nosaukums</th><th className="text-left p-3">Aizpildījums</th><th className="text-left p-3">Ietilpība</th>{canOperate && <th className="p-3" />}
        </tr></thead><tbody className="divide-y">{query.data.map((location) => <tr key={location.id}>
          <td className="p-3 font-mono">{location.code}</td><td className="p-3 font-medium">{location.name}</td>
          <td className="p-3"><div className="flex items-center gap-2">{location.usedCapacity}<StockBar stock={location.usedCapacity} minStock={Math.max(1, Math.floor(location.capacity / 3))} /></div></td>
          <td className="p-3">{location.capacity}</td>
          {canOperate && <td className="p-3"><div className="flex justify-end gap-1"><Button size="sm" onClick={() => setEditing(location)}><Edit2 size={11} />Labot</Button><Button size="sm" variant="danger" aria-label={`Dzēst ${location.name}`} onClick={() => setDeleting(location)}><Trash2 size={11} /></Button></div></td>}
        </tr>)}</tbody></table>
      </div>}
    </Card>
    {canOperate && <>
      <LocationModal open={editing !== undefined} location={editing} onClose={() => setEditing(undefined)} />
      <DeleteConfirmModal open={!!deleting} itemName={deleting?.name ?? ""} isLoading={remove.isPending} onClose={() => setDeleting(null)} onConfirm={() => deleting && remove.mutate(deleting.id, {
        onSuccess: () => { toast("Noliktavas vieta izdzēsta", "warning"); setDeleting(null); },
        onError: (error) => toast(error.message, "error"),
      })} />
    </>}
  </div>;
}
