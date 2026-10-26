"use client";

import { useEffect, useState } from "react";
import { MapPin } from "lucide-react";
import Modal, { FormField, inputClass } from "@/components/shared/Modal";
import { Button } from "@/components/shared/ui";
import { useAppStore } from "@/store/useAppStore";
import { useSaveLocation } from "@/hooks/useWarehouse";
import type { Location, LocationInput } from "@/types";

const blank: LocationInput = { code: "", name: "", capacity: 100 };

export default function LocationModal({ open, location, onClose }: { open: boolean; location?: Location | null; onClose: () => void }) {
  const save = useSaveLocation();
  const toast = useAppStore((state) => state.showToast);
  const [form, setForm] = useState<LocationInput>(blank);

  useEffect(() => {
    if (open) setForm(location ? { code: location.code, name: location.name, capacity: location.capacity } : blank);
  }, [open, location]);

  const submit = () => {
    if (!/^[A-Z0-9-]{2,30}$/.test(form.code) || form.name.trim().length < 2 || form.capacity < 1) {
      toast("Pārbaudiet vietas kodu, nosaukumu un ietilpību", "error");
      return;
    }
    save.mutate({ id: location?.id, data: { ...form, name: form.name.trim() } }, {
      onSuccess: () => { toast(location ? "Noliktavas vieta atjaunināta" : "Noliktavas vieta izveidota"); onClose(); },
      onError: (error) => toast(error.message, "error"),
    });
  };

  return <Modal open={open} onClose={onClose} title={location ? "Rediģēt noliktavas vietu" : "Pievienot noliktavas vietu"} footer={<><Button onClick={onClose}>Atcelt</Button><Button variant="primary" onClick={submit} isLoading={save.isPending}><MapPin size={13} />Saglabāt</Button></>}>
    <div className="space-y-4">
      <FormField label="Kods" required><input required pattern="[A-Z0-9-]+" minLength={2} maxLength={30} value={form.code} onChange={(event) => setForm((current) => ({ ...current, code: event.target.value.toUpperCase() }))} className={inputClass} /></FormField>
      <FormField label="Nosaukums" required><input required minLength={2} value={form.name} onChange={(event) => setForm((current) => ({ ...current, name: event.target.value }))} className={inputClass} /></FormField>
      <FormField label="Ietilpība" required><input required type="number" min={1} value={form.capacity} onChange={(event) => setForm((current) => ({ ...current, capacity: Number(event.target.value) }))} className={inputClass} /></FormField>
    </div>
  </Modal>;
}
