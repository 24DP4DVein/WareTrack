"use client";

import { FormEvent, useEffect, useState } from "react";
import { Package } from "lucide-react";
import {
  useCategories,
  useLocations,
  useSaveItem,
  useSuppliers,
} from "@/hooks/useWarehouse";
import { useAppStore } from "@/store/useAppStore";
import Modal, {
  FormField,
  inputClass,
  selectClass,
  textareaClass,
} from "@/components/shared/Modal";
import { Button } from "@/components/shared/ui";
import { generateSKU } from "@/lib/utils";
import type { Item, ItemInput } from "@/types";

const emptyItem: ItemInput = {
  name: "",
  sku: "",
  categoryId: 0,
  supplierId: null,
  locationId: 0,
  stock: 0,
  minStock: 0,
  price: 0,
  description: "",
};

export default function AddItemModal({
  open,
  onClose,
  item,
}: {
  open: boolean;
  onClose: () => void;
  item?: Item | null;
}) {
  const save = useSaveItem();
  const categories = useCategories();
  const locations = useLocations();
  const suppliers = useSuppliers();
  const toast = useAppStore((s) => s.showToast);

  const [form, setForm] = useState<ItemInput>(emptyItem);

  useEffect(() => {
    if (!open) return;

    if (item) {
      setForm({
        name: item.name,
        sku: item.sku,
        categoryId: item.categoryId,
        supplierId: item.supplierId,
        locationId: item.locationId,
        stock: item.stock,
        minStock: item.minStock,
        price: item.price,
        description: item.description,
      });
    } else {
      setForm(emptyItem);
    }
  }, [open, item]);

  const close = () => {
    setForm(emptyItem);
    onClose();
  };

  const submit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();

    save.mutate(
      {
        id: item?.id,
        data: form,
      },
      {
        onSuccess: () => {
          toast(
            item
              ? "Prece veiksmīgi atjaunināta"
              : "Prece veiksmīgi pievienota"
          );
          close();
        },
        onError: (error) => toast(error.message, "error"),
      }
    );
  };

  return (
    <Modal
      open={open}
      onClose={close}
      title={item ? "Rediģēt preci" : "Pievienot preci"}
      description="Aizpildiet preces datus"
      size="lg"
      footer={
        <>
          <Button onClick={close}>Atcelt</Button>

          <Button
            type="submit"
            form="item-form"
            variant="primary"
            isLoading={save.isPending}
          >
            <Package size={13} />
            Saglabāt
          </Button>
        </>
      }
    >
      <form
        id="item-form"
        className="grid grid-cols-1 sm:grid-cols-2 gap-4"
        onSubmit={submit}
      >
        <FormField
          label="Nosaukums"
          required
          className="sm:col-span-2"
        >
          <input
            required
            value={form.name}
            onChange={(e) =>
              setForm({ ...form, name: e.target.value })
            }
            className={inputClass}
          />
        </FormField>

        <FormField label="SKU" required>
          <div className="flex gap-2">
            <input
              required
              value={form.sku}
              onChange={(e) =>
                setForm({ ...form, sku: e.target.value })
              }
              className={inputClass}
            />

            <Button
              type="button"
              size="sm"
              onClick={() =>
                form.name &&
                setForm({
                  ...form,
                  sku: generateSKU(form.name),
                })
              }
            >
              Ģenerēt
            </Button>
          </div>
        </FormField>

        <FormField label="Kategorija" required>
          <select
            required
            value={form.categoryId}
            onChange={(e) =>
              setForm({
                ...form,
                categoryId: Number(e.target.value),
              })
            }
            className={selectClass}
          >
            <option value={0}>Izvēlieties</option>

            {categories.data?.map((category) => (
              <option
                key={category.id}
                value={category.id}
              >
                {category.name}
              </option>
            ))}
          </select>
        </FormField>

        <FormField label="Krājums" required>
          <input
            type="number"
            min={0}
            required
            value={form.stock}
            onChange={(e) =>
              setForm({
                ...form,
                stock: Number(e.target.value),
              })
            }
            className={inputClass}
          />
        </FormField>

        <FormField label="Minimālais krājums" required>
          <input
            type="number"
            min={0}
            required
            value={form.minStock}
            onChange={(e) =>
              setForm({
                ...form,
                minStock: Number(e.target.value),
              })
            }
            className={inputClass}
          />
        </FormField>

        <FormField label="Noliktavas vieta" required>
          <select
            required
            value={form.locationId}
            onChange={(e) =>
              setForm({
                ...form,
                locationId: Number(e.target.value),
              })
            }
            className={selectClass}
          >
            <option value={0}>Izvēlieties</option>

            {locations.data?.map((location) => (
              <option
                key={location.id}
                value={location.id}
              >
                {location.code} — {location.name}
              </option>
            ))}
          </select>
        </FormField>

        <FormField label="Piegādātājs">
          <select
            value={form.supplierId ?? ""}
            onChange={(e) =>
              setForm({
                ...form,
                supplierId: e.target.value
                  ? Number(e.target.value)
                  : null,
              })
            }
            className={selectClass}
          >
            <option value="">Nav norādīts</option>

            {suppliers.data?.map((supplier) => (
              <option
                key={supplier.id}
                value={supplier.id}
              >
                {supplier.name}
              </option>
            ))}
          </select>
        </FormField>

        <FormField label="Cena (€)" required>
          <input
            type="number"
            min={0}
            step="0.01"
            required
            value={form.price}
            onChange={(e) =>
              setForm({
                ...form,
                price: Number(e.target.value),
              })
            }
            className={inputClass}
          />
        </FormField>

        <FormField
          label="Apraksts"
          className="sm:col-span-2"
        >
          <textarea
            value={form.description ?? ""}
            onChange={(e) =>
              setForm({
                ...form,
                description: e.target.value,
              })
            }
            className={textareaClass}
          />
        </FormField>
      </form>
    </Modal>
  );
}
