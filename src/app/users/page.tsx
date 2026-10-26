"use client";

import { Card, EmptyState, LoadingSpinner, SectionHeader, Badge } from "@/components/shared/ui";
import Modal, { FormField, inputClass, selectClass } from "@/components/shared/Modal";
import { Button } from "@/components/shared/ui";
import { useCreateUser, useUpdateUser, useUsers } from "@/hooks/useWarehouse";
import { useAppStore } from "@/store/useAppStore";
import { roleLabels, type Role } from "@/types";
import { useState } from "react";

export default function UsersPage() {
  const q = useUsers();
  const updateUser = useUpdateUser();
  const createUser = useCreateUser();
  const toast = useAppStore((state) => state.showToast);
  const currentUser = useAppStore((state) => state.user);
  const [creating, setCreating] = useState(false);
  const [newUser, setNewUser] = useState({ name: "", email: "", password: "", role: "LIETOTAJS" as Role });

  const changeRole = (id: number, role: Role) => {
    updateUser.mutate(
      { id, data: { role } },
      {
        onSuccess: () => toast("Lietotāja loma atjaunināta"),
        onError: (error) => toast(error.message, "error"),
      },
    );
  };

  const createAccount = () => {
    if (newUser.name.trim().length < 2 || !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(newUser.email)
      || newUser.password.length < 8 || !/[A-Z]/.test(newUser.password) || !/\d/.test(newUser.password)) {
      toast("Norādiet derīgu vārdu, e-pastu un paroli ar lielo burtu un ciparu", "error");
      return;
    }
    createUser.mutate({ ...newUser, name: newUser.name.trim() }, {
      onSuccess: () => { toast("Lietotājs izveidots"); setCreating(false); setNewUser({ name: "", email: "", password: "", role: "LIETOTAJS" }); },
      onError: (error) => toast(error.message, "error"),
    });
  };

  return (
    <div>
      <SectionHeader title="Lietotāji" subtitle="Sistēmas lietotāju pārvaldība">
        <Button variant="primary" onClick={() => setCreating(true)}>Pievienot lietotāju</Button>
      </SectionHeader>
      <Card>
        {q.isLoading ? (
          <LoadingSpinner />
        ) : q.isError ? (
          <p className="p-6 text-red-700">Datus neizdevās ielādēt: {q.error.message}</p>
        ) : !q.data?.length ? (
          <EmptyState message="Lietotāju vēl nav" />
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm min-w-[760px]">
              <thead>
                <tr className="bg-secondary/60 text-xs text-muted-foreground">
                  <th className="text-left p-3">Vārds</th>
                  <th className="text-left p-3">E-pasts</th>
                  <th className="text-left p-3">Loma</th>
                  <th className="text-left p-3">Statuss</th>
                  <th className="text-left p-3">Darbība</th>
                </tr>
              </thead>
              <tbody className="divide-y">
                {q.data.map((user) => (
                  <tr key={user.id}>
                    <td className="p-3 font-medium">{user.name}</td>
                    <td className="p-3">{user.email}</td>
                    <td className="p-3">
                      <Badge variant={user.role === "ADMIN" ? "purple" : user.role === "VADITAJS" ? "blue" : "gray"}>
                        {roleLabels[user.role]}
                      </Badge>
                    </td>
                    <td className="p-3">
                      <Badge variant={user.isActive ? "green" : "gray"}>
                        {user.isActive ? "Aktīvs" : "Neaktīvs"}
                      </Badge>
                    </td>
                    <td className="p-3">
                      <div className="flex items-center gap-2">
                        <select
                          aria-label={`Mainīt ${user.name} lomu`}
                          value={user.role}
                          disabled={updateUser.isPending || (currentUser?.id === user.id && user.role === "ADMIN")}
                          onChange={(event) => changeRole(user.id, event.target.value as Role)}
                          className="border border-border rounded-md bg-white px-2 py-1.5 text-xs"
                        >
                          <option value="LIETOTAJS">Lietotājs</option>
                          <option value="VADITAJS">Vadītājs</option>
                          <option value="ADMIN">Administrators</option>
                        </select>
                        <Button size="sm" disabled={updateUser.isPending || (currentUser?.id === user.id && user.role === "ADMIN")} onClick={() => updateUser.mutate({ id: user.id, data: { isActive: !user.isActive } }, {
                          onSuccess: () => toast(user.isActive ? "Lietotājs deaktivizēts" : "Lietotājs aktivizēts"),
                          onError: (error) => toast(error.message, "error"),
                        })}>{user.isActive ? "Deaktivizēt" : "Aktivizēt"}</Button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>
      <Modal open={creating} onClose={() => setCreating(false)} title="Pievienot lietotāju" description="Jaunam kontam pēc noklusējuma tiek piešķirta lasīšanas loma." footer={<><Button onClick={() => setCreating(false)}>Atcelt</Button><Button variant="primary" isLoading={createUser.isPending} onClick={createAccount}>Izveidot</Button></>}>
        <div className="space-y-4">
          <FormField label="Vārds" required><input value={newUser.name} onChange={(event) => setNewUser((current) => ({ ...current, name: event.target.value }))} className={inputClass} /></FormField>
          <FormField label="E-pasts" required><input type="email" value={newUser.email} onChange={(event) => setNewUser((current) => ({ ...current, email: event.target.value }))} className={inputClass} /></FormField>
          <FormField label="Sākotnējā parole" required><input type="password" value={newUser.password} onChange={(event) => setNewUser((current) => ({ ...current, password: event.target.value }))} className={inputClass} /></FormField>
          <FormField label="Loma"><select value={newUser.role} onChange={(event) => setNewUser((current) => ({ ...current, role: event.target.value as Role }))} className={selectClass}><option value="LIETOTAJS">Lietotājs</option><option value="VADITAJS">Vadītājs</option><option value="ADMIN">Administrators</option></select></FormField>
        </div>
      </Modal>
    </div>
  );
}
