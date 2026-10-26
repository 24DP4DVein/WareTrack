"use client";

import { useEffect, useState } from "react";
import { Tag } from "lucide-react";
import Modal, { FormField, inputClass, selectClass, textareaClass } from "@/components/shared/Modal";
import { Button } from "@/components/shared/ui";
import { useAppStore } from "@/store/useAppStore";
import { useSaveCategory } from "@/hooks/useWarehouse";
import type { Category, CategoryInput } from "@/types";

const emptyCategory: CategoryInput = { name: "", description: "", icon: "Package", color: "blue" };

export default function CategoryModal({
  open,
  category,
  onClose,
}: {
  open: boolean;
  category?: Category | null;
  onClose: () => void;
}) {
  const save = useSaveCategory();
  const toast = useAppStore((state) => state.showToast);
  const [form, setForm] = useState<CategoryInput>(emptyCategory);

  useEffect(() => {
    if (open) {
      setForm(category ? {
        name: category.name,
        description: category.description,
        icon: category.icon,
        color: category.color,
      } : emptyCategory);
    }
  }, [open, category]);

  const update = <K extends keyof CategoryInput>(key: K, value: CategoryInput[K]) => {
    setForm((current) => ({ ...current, [key]: value }));
  };

  const submit = () => {
    if (form.name.trim().length < 2) {
      toast("Kategorijas nosaukumam vajadzīgas vismaz 2 rakstzīmes", "error");
      return;
    }
    save.mutate({ id: category?.id, data: { ...form, name: form.name.trim() } }, {
      onSuccess: () => {
        toast(category ? "Kategorija atjaunināta" : "Kategorija izveidota");
        onClose();
      },
      onError: (error) => toast(error.message, "error"),
    });
  };

  return (
    <Modal
      open={open}
      onClose={onClose}
      title={category ? "Rediģēt kategoriju" : "Pievienot kategoriju"}
      description="Norādiet kategorijas pamatinformāciju"
      footer={<><Button onClick={onClose}>Atcelt</Button><Button variant="primary" onClick={submit} isLoading={save.isPending}><Tag size={13} />Saglabāt</Button></>}
    >
      <div className="space-y-4">
        <FormField label="Nosaukums" required>
          <input value={form.name} onChange={(event) => update("name", event.target.value)} className={inputClass} maxLength={100} autoFocus />
        </FormField>
        <FormField label="Apraksts">
          <textarea value={form.description} onChange={(event) => update("description", event.target.value)} className={textareaClass} maxLength={300} />
        </FormField>
        <div className="grid grid-cols-2 gap-3">
          <FormField label="Ikona">
            <input value={form.icon} onChange={(event) => update("icon", event.target.value)} className={inputClass} maxLength={30} />
          </FormField>
          <FormField label="Krāsa">
            <select value={form.color} onChange={(event) => update("color", event.target.value as CategoryInput["color"])} className={selectClass}>
              <option value="blue">Zila</option>
              <option value="green">Zaļa</option>
              <option value="amber">Dzintara</option>
              <option value="red">Sarkana</option>
              <option value="purple">Violeta</option>
            </select>
          </FormField>
        </div>
      </div>
    </Modal>
  );
}
