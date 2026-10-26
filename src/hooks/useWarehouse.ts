import { useMutation,useQuery,useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import type { Category,CategoryInput,DashboardData,Item,ItemInput,ItemList,Location,LocationInput,ReportData,Supplier,SupplierInput,Transfer,TransferInput,TransferStatus,User } from "@/types";
const q={items:["items"] as const,categories:["categories"] as const,suppliers:["suppliers"] as const,locations:["locations"] as const,transfers:["transfers"] as const,dashboard:["dashboard"] as const,reports:["reports"] as const,users:["users"] as const};
const json=(method:string,data?:unknown):RequestInit=>({method,body:data===undefined?undefined:JSON.stringify(data)});
const invalidate=(qc:ReturnType<typeof useQueryClient>)=>Promise.all([qc.invalidateQueries({queryKey:q.items}),qc.invalidateQueries({queryKey:q.locations}),qc.invalidateQueries({queryKey:q.dashboard}),qc.invalidateQueries({queryKey:q.reports}),qc.invalidateQueries({queryKey:q.transfers})]);
export function useItems(filters:{search?:string;category?:number;status?:string;page?:number;pageSize?:number}={}){const p=new URLSearchParams();Object.entries(filters).forEach(([k,v])=>{if(v!==undefined&&v!=="")p.set(k,String(v))});return useQuery({queryKey:[...q.items,filters],queryFn:()=>api<ItemList>(`/items?${p}`)})}
export const useCategories=()=>useQuery({queryKey:q.categories,queryFn:()=>api<Category[]>("/categories")});
export const useSuppliers=()=>useQuery({queryKey:q.suppliers,queryFn:()=>api<Supplier[]>("/suppliers")});
export const useLocations=()=>useQuery({queryKey:q.locations,queryFn:()=>api<Location[]>("/locations")});
export const useDashboard=()=>useQuery({queryKey:q.dashboard,queryFn:()=>api<DashboardData>("/dashboard")});
export const useReports=()=>useQuery({queryKey:q.reports,queryFn:()=>api<ReportData>("/reports")});
export const useUsers=()=>useQuery({queryKey:q.users,queryFn:()=>api<User[]>("/users")});
export function useTransfers(status="all"){return useQuery({queryKey:[...q.transfers,status],queryFn:()=>api<Transfer[]>(`/transfers?status=${status}`)})}
export function useSaveItem(){const qc=useQueryClient();return useMutation({mutationFn:({id,data}:{id?:number;data:ItemInput})=>api<Item>(id?`/items/${id}`:"/items",json(id?"PUT":"POST",data)),onSuccess:()=>invalidate(qc)})}
export function useDeleteItem(){const qc=useQueryClient();return useMutation({mutationFn:(id:number)=>api<void>(`/items/${id}`,{method:"DELETE"}),onSuccess:()=>invalidate(qc)})}
export function useSaveCategory(){const qc=useQueryClient();return useMutation({mutationFn:({id,data}:{id?:number;data:CategoryInput})=>api<Category>(id?`/categories/${id}`:"/categories",json(id?"PUT":"POST",data)),onSuccess:()=>{qc.invalidateQueries({queryKey:q.categories});invalidate(qc)}})}
export function useDeleteCategory(){const qc=useQueryClient();return useMutation({mutationFn:(id:number)=>api<void>(`/categories/${id}`,{method:"DELETE"}),onSuccess:()=>qc.invalidateQueries({queryKey:q.categories})})}
export function useSaveLocation(){const qc=useQueryClient();return useMutation({mutationFn:({id,data}:{id?:number;data:LocationInput})=>api<Location>(id?`/locations/${id}`:"/locations",json(id?"PUT":"POST",data)),onSuccess:()=>{qc.invalidateQueries({queryKey:q.locations});qc.invalidateQueries({queryKey:q.items})}})}
export function useDeleteLocation(){const qc=useQueryClient();return useMutation({mutationFn:(id:number)=>api<void>(`/locations/${id}`,{method:"DELETE"}),onSuccess:()=>qc.invalidateQueries({queryKey:q.locations})})}
export function useSaveSupplier(){const qc=useQueryClient();return useMutation({mutationFn:({id,data}:{id?:number;data:SupplierInput})=>api<Supplier>(id?`/suppliers/${id}`:"/suppliers",json(id?"PUT":"POST",data)),onSuccess:()=>qc.invalidateQueries({queryKey:q.suppliers})})}
export function useDeleteSupplier(){const qc=useQueryClient();return useMutation({mutationFn:(id:number)=>api<void>(`/suppliers/${id}`,{method:"DELETE"}),onSuccess:()=>qc.invalidateQueries({queryKey:q.suppliers})})}
export function useCreateUser(){const qc=useQueryClient();return useMutation({mutationFn:(data:{name:string;email:string;password:string;role:User["role"]})=>api<User>("/users",json("POST",data)),onSuccess:()=>qc.invalidateQueries({queryKey:q.users})})}
export function useAddTransfer(){const qc=useQueryClient();return useMutation({mutationFn:(data:TransferInput)=>api<Transfer>("/transfers",json("POST",data)),onSuccess:()=>{qc.invalidateQueries({queryKey:q.transfers});invalidate(qc)}})}
export function useUpdateTransferStatus(){const qc=useQueryClient();return useMutation({mutationFn:({id,status}:{id:number;status:TransferStatus})=>api<Transfer>(`/transfers/${id}`,json("PATCH",{status})),onSuccess:()=>{qc.invalidateQueries({queryKey:q.transfers});invalidate(qc)}})}
export function useUpdateUser(){const qc=useQueryClient();return useMutation({mutationFn:({id,data}:{id:number;data:{role?:User["role"];isActive?:boolean}})=>api<User>(`/users/${id}`,json("PATCH",data)),onSuccess:()=>qc.invalidateQueries({queryKey:q.users})})}
