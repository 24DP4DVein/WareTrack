"use client";

import { useEffect, useState } from "react";
import { Truck } from "lucide-react";
import Modal, { FormField, inputClass, selectClass } from "@/components/shared/Modal";
import { Button } from "@/components/shared/ui";
import { useAppStore } from "@/store/useAppStore";
import { useSaveSupplier } from "@/hooks/useWarehouse";
import type { Supplier, SupplierInput } from "@/types";

const blank: SupplierInput = { name: "", contactPerson: "", email: "", phone: "", address: "", category: "Dažādi", paymentTerms: "net30" };

export default function SupplierModal({ open, supplier, onClose }: { open: boolean; supplier?: Supplier | null; onClose: () => void }) {
  const save = useSaveSupplier();
  const toast = useAppStore((state) => state.showToast);
  const [form, setForm] = useState<SupplierInput>(blank);

  useEffect(() => {
    if (open) setForm(supplier ? {
      name: supplier.name,
      contactPerson: supplier.contactPerson,
      email: supplier.email,
      phone: supplier.phone,
      address: supplier.address,
      category: supplier.category,
      paymentTerms: supplier.paymentTerms,
    } : blank);
  }, [open, supplier]);

  const update = <K extends keyof SupplierInput>(key: K, value: SupplierInput[K]) => setForm((current) => ({ ...current, [key]: value }));
  const submit = () => {
    if (form.name.trim().length < 3 || form.contactPerson.trim().length < 2 || !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(form.email)
      || !/^[+\d\s()-]{7,30}$/.test(form.phone) || form.address.trim().length < 5) {
      toast("Pārbaudiet piegādātāja nosaukumu, kontaktpersonu un kontaktinformāciju", "error");
      return;
    }
    save.mutate({ id: supplier?.id, data: { ...form, name: form.name.trim(), contactPerson: form.contactPerson.trim(), address: form.address.trim() } }, {
      onSuccess: () => { toast(supplier ? "Piegādātājs atjaunināts" : "Piegādātājs izveidots"); onClose(); },
      onError: (error) => toast(error.message, "error"),
    });
  };

  return <Modal open={open} onClose={onClose} title={supplier ? "Rediģēt piegādātāju" : "Pievienot piegādātāju"} size="lg" footer={<><Button onClick={onClose}>Atcelt</Button><Button variant="primary" onClick={submit} isLoading={save.isPending}><Truck size={13} />Saglabāt</Button></>}>
    <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
      <FormField label="Uzņēmums" required><input required minLength={3} value={form.name} onChange={(event) => update("name", event.target.value)} className={inputClass} /></FormField>
      <FormField label="Kontaktpersona" required><input required value={form.contactPerson} onChange={(event) => update("contactPerson", event.target.value)} className={inputClass} /></FormField>
      <FormField label="E-pasts" required><input required type="email" value={form.email} onChange={(event) => update("email", event.target.value)} className={inputClass} /></FormField>
      <FormField label="Tālrunis" required><input required pattern="[+\d\s()-]{7,30}" value={form.phone} onChange={(event) => update("phone", event.target.value)} className={inputClass} /></FormField>
      <FormField label="Adrese" required className="sm:col-span-2"><input required minLength={5} value={form.address} onChange={(event) => update("address", event.target.value)} className={inputClass} /></FormField>
      <FormField label="Preču grupa"><input value={form.category} onChange={(event) => update("category", event.target.value)} className={inputClass} /></FormField>
      <FormField label="Apmaksas termiņš"><select value={form.paymentTerms} onChange={(event) => update("paymentTerms", event.target.value as SupplierInput["paymentTerms"])} className={selectClass}><option value="net30">30 dienas</option><option value="net60">60 dienas</option><option value="cod">Saņemot</option></select></FormField>
    </div>
  </Modal>;
}
