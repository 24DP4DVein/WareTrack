"use client";

import { useState } from "react";
import { Edit2, Plus, Trash2 } from "lucide-react";
import { useDeleteItem, useItems } from "@/hooks/useWarehouse";
import { useAppStore } from "@/store/useAppStore";
import {
  Button,
  Card,
  EmptyState,
  ItemStatusBadge,
  LoadingSpinner,
  SectionHeader,
  StockBar,
} from "@/components/shared/ui";
import AddItemModal from "@/components/items/AddItemModal";
import DeleteConfirmModal from "@/components/shared/DeleteConfirmModal";
import { formatCurrency, formatDate } from "@/lib/utils";
import type { Item } from "@/types";

export default function ItemsPage() {
  const [page, setPage] = useState(1);
  const [edit, setEdit] = useState<Item | null | undefined>(undefined);
  const [del, setDel] = useState<Item | null>(null);

  const result = useItems({
    page,
    pageSize: 10,
  });

  const remove = useDeleteItem();
  const toast = useAppStore((s) => s.showToast);

  const pages = Math.max(
    1,
    Math.ceil((result.data?.total ?? 0) / 10)
  );

  return (
    <div>
      <SectionHeader
        title="Preces"
        subtitle={(result.data?.total ?? 0) + " preces"}
      >
        <Button
          variant="primary"
          onClick={() => setEdit(null)}
        >
          <Plus size={13} />
          Pievienot preci
        </Button>
      </SectionHeader>

      <Card>
        {result.isLoading ? (
          <LoadingSpinner />
        ) : result.isError ? (
          <p className="p-6 text-red-700">
            Datus neizdevās ielādēt: {result.error.message}
          </p>
        ) : !result.data?.items.length ? (
          <EmptyState message="Nav pievienota neviena prece" />
        ) : (
          <>
            <div className="overflow-x-auto">
              <table className="w-full text-[13px] min-w-[850px]">
                <thead>
                  <tr className="bg-secondary/60 text-[11px] uppercase text-muted-foreground">
                    <th className="text-left p-3">Prece / SKU</th>
                    <th className="text-left p-3">Kategorija</th>
                    <th className="text-left p-3">Krājums</th>
                    <th className="text-left p-3">Vieta</th>
                    <th className="text-left p-3">Cena</th>
                    <th className="text-left p-3">Atjaunināts</th>
                    <th className="p-3" />
                  </tr>
                </thead>

                <tbody className="divide-y">
                  {result.data.items.map((item) => (
                    <tr
                      key={item.id}
                      className="hover:bg-secondary/40"
                    >
                      <td className="p-3">
                        <b>{item.name}</b>
                        <p className="font-mono text-[11px] text-muted-foreground">
                          {item.sku}
                        </p>
                      </td>

                      <td className="p-3">
                        {item.categoryName}
                      </td>

                      <td className="p-3">
                        <div className="flex items-center gap-2">
                          <b>{item.stock}</b>
                          <ItemStatusBadge status={item.status} />
                        </div>

                        <StockBar
                          stock={item.stock}
                          minStock={item.minStock}
                        />
                      </td>

                      <td className="p-3">
                        {item.locationName}
                      </td>

                      <td className="p-3">
                        {formatCurrency(item.price)}
                      </td>

                      <td className="p-3">
                        {formatDate(item.updatedAt)}
                      </td>

                      <td className="p-3">
                        <div className="flex gap-1 justify-end">
                          <Button
                            size="sm"
                            onClick={() => setEdit(item)}
                          >
                            <Edit2 size={11} />
                            Labot
                          </Button>

                          <Button
                            size="sm"
                            variant="danger"
                            onClick={() => setDel(item)}
                          >
                            <Trash2 size={11} />
                          </Button>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            <div className="p-3 border-t flex gap-2 items-center">
              <Button
                size="sm"
                disabled={page <= 1}
                onClick={() => setPage((p) => p - 1)}
              >
                Iepriekšējā
              </Button>

              <span className="text-xs text-muted-foreground">
                Lapa {page} no {pages}
              </span>

              <Button
                size="sm"
                disabled={page >= pages}
                onClick={() => setPage((p) => p + 1)}
              >
                Nākamā
              </Button>
            </div>
          </>
        )}
      </Card>

      <AddItemModal
        open={edit !== undefined}
        item={edit}
        onClose={() => setEdit(undefined)}
      />

      <DeleteConfirmModal
        open={!!del}
        itemName={del?.name ?? ""}
        isLoading={remove.isPending}
        onClose={() => setDel(null)}
        onConfirm={() =>
          del &&
          remove.mutate(del.id, {
            onSuccess: () => {
              toast("Prece izdzēsta", "warning");
              setDel(null);
            },
            onError: (error) =>
              toast(error.message, "error"),
          })
        }
      />
    </div>
  );
}
