import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useParams } from "next/navigation";
import { api } from "@/lib/api";
import { useAppStore } from "@/store/useAppStore";
import type { Company, CompanyMembership, JoinRequest, ManagedJoinRequest, MyCompany, PublicCompany, User } from "@/types";

const json = (method:string, body?:unknown):RequestInit => ({method, body:body === undefined ? undefined : JSON.stringify(body)});
export const companyKeys = {
  public: ["companies", "public"] as const,
  mine: (userId?:number) => [userId, "companies", "mine"] as const,
  myRequests: (userId?:number) => [userId, "companies", "my-requests"] as const,
  requests: (userId:number|undefined, companyId:number, status?:string) => [userId, companyId, "join-requests", status ?? "all"] as const,
  members: (userId:number|undefined, companyId:number) => [userId, companyId, "members"] as const,
  adminCompanies: (userId?:number) => [userId, "admin", "companies"] as const,
  adminRequests: (userId?:number) => [userId, "admin", "join-requests"] as const,
};

export function useRouteCompanyId(){const params=useParams<{companyId?:string}>();const id=Number(params?.companyId);return Number.isInteger(id)&&id>0?id:0;}
export const usePublicCompanies=()=>useQuery({queryKey:companyKeys.public,queryFn:()=>api<PublicCompany[]>("/companies/public")});
export function useMyCompanies(){const id=useAppStore(s=>s.user?.id);return useQuery({queryKey:companyKeys.mine(id),queryFn:()=>api<MyCompany[]>("/companies/mine"),enabled:!!id});}
export function useMyRequests(){const id=useAppStore(s=>s.user?.id);return useQuery({queryKey:companyKeys.myRequests(id),queryFn:()=>api<JoinRequest[]>("/companies/my-requests"),enabled:!!id});}
export function useCurrentCompany(){const companyId=useRouteCompanyId(),q=useMyCompanies();return {companyId,company:q.data?.find(c=>c.id===companyId),isLoading:q.isLoading,isError:q.isError,error:q.error};}
export function useSubmitJoinRequest(){const qc=useQueryClient(),userId=useAppStore(s=>s.user?.id);return useMutation({mutationFn:(companyId:number)=>api<JoinRequest>(`/companies/${companyId}/join-requests`,{method:"POST"}),onSuccess:()=>Promise.all([qc.invalidateQueries({queryKey:companyKeys.myRequests(userId)}),qc.invalidateQueries({queryKey:companyKeys.mine(userId)})])});}
export function useCompanyRequests(status?:string){const userId=useAppStore(s=>s.user?.id),companyId=useRouteCompanyId();return useQuery({queryKey:companyKeys.requests(userId,companyId,status),queryFn:()=>api<ManagedJoinRequest[]>(`/companies/${companyId}/join-requests${status?`?status=${status}`:""}`),enabled:!!userId&&companyId>0});}
export function useReviewRequest(){const qc=useQueryClient(),userId=useAppStore(s=>s.user?.id),companyId=useRouteCompanyId();return useMutation({mutationFn:({requestId,decision,reason}:{requestId:number;decision:"approve"|"reject";reason?:string})=>api<CompanyMembership|ManagedJoinRequest>(`/companies/${companyId}/join-requests/${requestId}/${decision}`,json("POST",decision==="reject"?{reason:reason||null}:undefined)),onSuccess:()=>Promise.all([qc.invalidateQueries({queryKey:[userId,companyId,"join-requests"]}),qc.invalidateQueries({queryKey:companyKeys.members(userId,companyId)}),qc.invalidateQueries({queryKey:[userId,companyId,"activity"]})])});}
export function useCompanyMembers(){const userId=useAppStore(s=>s.user?.id),companyId=useRouteCompanyId();return useQuery({queryKey:companyKeys.members(userId,companyId),queryFn:()=>api<CompanyMembership[]>(`/companies/${companyId}/members`),enabled:!!userId&&companyId>0});}
export function useUpdateMembership(){const qc=useQueryClient(),userId=useAppStore(s=>s.user?.id),companyId=useRouteCompanyId();return useMutation({mutationFn:({membershipId,role}:{membershipId:number;role:"LIETOTAJS"|"VADITAJS"})=>api<CompanyMembership>(`/companies/${companyId}/members/${membershipId}`,json("PATCH",{role})),onSuccess:()=>qc.invalidateQueries({queryKey:companyKeys.members(userId,companyId)})});}
export function useRevokeMembership(){const qc=useQueryClient(),userId=useAppStore(s=>s.user?.id),companyId=useRouteCompanyId();return useMutation({mutationFn:(membershipId:number)=>api<CompanyMembership>(`/companies/${companyId}/members/${membershipId}/revoke`,{method:"POST"}),onSuccess:()=>Promise.all([qc.invalidateQueries({queryKey:companyKeys.members(userId,companyId)}),qc.invalidateQueries({queryKey:companyKeys.mine(userId)})])});}
export function useAdminCompanies(){const id=useAppStore(s=>s.user?.id);return useQuery({queryKey:companyKeys.adminCompanies(id),queryFn:()=>api<Company[]>("/admin/companies"),enabled:!!id});}
export function useAdminRequests(){const id=useAppStore(s=>s.user?.id);return useQuery({queryKey:companyKeys.adminRequests(id),queryFn:()=>api<ManagedJoinRequest[]>("/admin/join-requests"),enabled:!!id});}
export function useAdminUsers(){const id=useAppStore(s=>s.user?.id);return useQuery({queryKey:[id,"admin","users"],queryFn:()=>api<User[]>("/users"),enabled:!!id});}
export function useCreateCompany(){const qc=useQueryClient(),id=useAppStore(s=>s.user?.id);return useMutation({mutationFn:(data:{name:string;slug:string;initialManagerUserId:number})=>api<Company>("/admin/companies",json("POST",data)),onSuccess:()=>Promise.all([qc.invalidateQueries({queryKey:companyKeys.adminCompanies(id)}),qc.invalidateQueries({queryKey:companyKeys.mine(id)})])});}
export function useUpdateCompany(){const qc=useQueryClient(),id=useAppStore(s=>s.user?.id);return useMutation({mutationFn:({companyId,data}:{companyId:number;data:{name?:string;isActive?:boolean}})=>api<Company>(`/admin/companies/${companyId}`,json("PATCH",data)),onSuccess:()=>Promise.all([qc.invalidateQueries({queryKey:companyKeys.adminCompanies(id)}),qc.invalidateQueries({queryKey:companyKeys.mine(id)})])});}
export function useAppointInitialManager(){const qc=useQueryClient(),id=useAppStore(s=>s.user?.id);return useMutation({mutationFn:({companyId,userId}:{companyId:number;userId:number})=>api<CompanyMembership>(`/admin/companies/${companyId}/initial-manager`,json("POST",{userId})),onSuccess:()=>qc.invalidateQueries({queryKey:companyKeys.adminCompanies(id)})});}
