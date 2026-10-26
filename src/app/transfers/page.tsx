"use client";

import { useMemo, useState } from "react";
import { ArrowRight, Check, Plus, X } from "lucide-react";
import { Button, Card, EmptyState, LoadingSpinner, PriorityBadge, SectionHeader, TransferStatusBadge } from "@/components/shared/ui";
import { useAddTransfer, useItems, useLocations, useTransfers, useUpdateTransferStatus } from "@/hooks/useWarehouse";
import { useAppStore } from "@/store/useAppStore";

export default function TransfersPage() {
  const user = useAppStore((state) => state.user);
  const toast = useAppStore((state) => state.showToast);
  const canOperate = user?.role === "VADITAJS" || user?.role === "ADMIN";
  const transfers = useTransfers();
  const items = useItems({ pageSize: 100 });
  const locations = useLocations();
  const add = useAddTransfer();
  const update = useUpdateTransferStatus();
  const [itemId, setItemId] = useState(0);
  const [source, setSource] = useState(0);
  const [destination, setDestination] = useState(0);
  const [quantity, setQuantity] = useState(1);
  const [priority, setPriority] = useState("normal");
  const [notes, setNotes] = useState("");
  const selectedItem = items.data?.items.find((item) => item.id === itemId);
  const sourceOptions = useMemo(() => selectedItem?.locations.filter((location) => location.quantity > 0).map((location) => ({
    ...location,
    available: location.quantity - (transfers.data?.filter((transfer) => transfer.itemId === itemId && transfer.sourceLocationId === location.locationId && ["pending", "in-transit"].includes(transfer.status)).reduce((sum, transfer) => sum + transfer.quantity, 0) ?? 0),
  })) ?? [], [itemId, selectedItem, transfers.data]);

  const selectItem = (id: number) => {
    setItemId(id);
    setSource(items.data?.items.find((item) => item.id === id)?.locations.find((location) => location.quantity > 0)?.locationId ?? 0);
    setDestination(0);
  };
  const submit = () => {
    if (!itemId || !source || !destination || source === destination || quantity < 1) {
      toast("Norādiet derīgu preci, vietas un daudzumu", "error");
      return;
    }
    add.mutate({ itemId, sourceLocationId: source, destinationLocationId: destination, quantity, priority: priority as "normal" | "high" | "urgent", notes }, {
      onSuccess: () => { toast("Pārvietojums izveidots"); setQuantity(1); setNotes(""); },
      onError: (error) => toast(error.message, "error"),
    });
  };
  const changeStatus = (id: number, status: "in-transit" | "done" | "cancelled") => update.mutate({ id, status }, { onError: (error) => toast(error.message, "error") });

  return <div>
    <SectionHeader title="Pārvietošana" subtitle="Preču pārvietošanas uzdevumi">
      {canOperate && <Button variant="primary" onClick={submit} isLoading={add.isPending}><Plus size={13} />Izveidot</Button>}
    </SectionHeader>
    {canOperate && <Card className="p-4 mb-4">
      <div className="grid grid-cols-1 md:grid-cols-6 gap-3">
        <label className="text-xs md:col-span-2">Prece<select value={itemId} onChange={(event) => selectItem(Number(event.target.value))} className="mt-1 w-full border rounded-md px-2 py-2 text-sm"><option value={0}>Izvēlieties preci</option>{items.data?.items.map((item) => <option key={item.id} value={item.id}>{item.name} ({item.stock} kopā)</option>)}</select></label>
        <label className="text-xs">No<select value={source} onChange={(event) => setSource(Number(event.target.value))} className="mt-1 w-full border rounded-md px-2 py-2 text-sm"><option value={0}>Avots</option>{sourceOptions.map((location) => <option key={location.locationId} value={location.locationId}>{location.locationName} ({Math.max(0, location.available)} pieejami)</option>)}</select></label>
        <label className="text-xs">Uz<select value={destination} onChange={(event) => setDestination(Number(event.target.value))} className="mt-1 w-full border rounded-md px-2 py-2 text-sm"><option value={0}>Galamērķis</option>{locations.data?.filter((location) => location.id !== source).map((location) => <option key={location.id} value={location.id}>{location.code}</option>)}</select></label>
        <label className="text-xs">Daudzums<input type="number" min={1} max={Math.max(1, sourceOptions.find((location) => location.locationId === source)?.available ?? 1)} value={quantity} onChange={(event) => setQuantity(Number(event.target.value))} className="mt-1 w-full border rounded-md px-2 py-2 text-sm" /></label>
        <label className="text-xs">Prioritāte<select value={priority} onChange={(event) => setPriority(event.target.value)} className="mt-1 w-full border rounded-md px-2 py-2 text-sm"><option value="normal">Parasta</option><option value="high">Augsta</option><option value="urgent">Steidzama</option></select></label>
        <label className="text-xs md:col-span-6">Piezīmes<input value={notes} onChange={(event) => setNotes(event.target.value)} maxLength={300} className="mt-1 w-full border rounded-md px-2 py-2 text-sm" /></label>
      </div>
    </Card>}
    <Card>
      {transfers.isLoading ? <LoadingSpinner /> : transfers.isError ? <p className="p-6 text-red-700">Datus neizdevās ielādēt: {transfers.error.message}</p> : !transfers.data?.length ? <EmptyState message="Pārvietojumu vēl nav" /> : <div className="overflow-x-auto">
        <table className="w-full text-sm"><thead><tr className="bg-secondary/60 text-xs text-muted-foreground">
          <th className="text-left p-3">Kods</th><th className="text-left p-3">Prece</th><th className="text-left p-3">No</th><th className="text-left p-3">Uz</th><th className="text-left p-3">Daudzums</th><th className="text-left p-3">Statuss</th>{canOperate && <th className="text-left p-3">Darbības</th>}
        </tr></thead><tbody className="divide-y">{transfers.data.map((transfer) => <tr key={transfer.id}>
          <td className="p-3 font-mono">{transfer.code}</td><td className="p-3 font-medium">{transfer.itemName}</td><td className="p-3">{transfer.sourceLocationName}</td><td className="p-3"><ArrowRight size={13} className="inline mr-1" />{transfer.destinationLocationName}</td><td className="p-3">{transfer.quantity}</td><td className="p-3"><TransferStatusBadge status={transfer.status} /></td>
          {canOperate && <td className="p-3"><div className="flex gap-1">{transfer.status === "pending" && <><Button size="sm" onClick={() => changeStatus(transfer.id, "in-transit")}><ArrowRight size={11} />Nosūtīt</Button><Button size="sm" variant="danger" onClick={() => changeStatus(transfer.id, "cancelled")}><X size={11} />Atcelt</Button></>}{transfer.status === "in-transit" && <><Button size="sm" variant="primary" onClick={() => changeStatus(transfer.id, "done")}><Check size={11} />Pabeigt</Button><Button size="sm" variant="danger" onClick={() => changeStatus(transfer.id, "cancelled")}><X size={11} />Atcelt</Button></>}</div></td>}
        </tr>)}</tbody></table>
      </div>}
    </Card>
  </div>;
}
