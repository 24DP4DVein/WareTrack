"use client";
import { useEffect } from "react";
import { usePathname,useRouter } from "next/navigation";
import Sidebar from "./Sidebar";
import Topbar from "./Topbar";
import ToastContainer from "@/components/shared/ToastContainer";
import { useAppStore } from "@/store/useAppStore";
import { api } from "@/lib/api";
import type { User } from "@/types";

const publicRoutes=["/login","/register"];
export default function AppShell({children}:{children:React.ReactNode}){
 const pathname=usePathname(),router=useRouter();
 const {token,user,hydrated,setAuth}=useAppStore();
 const isPublic=publicRoutes.includes(pathname);
 useEffect(()=>{if(hydrated&&!token&&!isPublic)router.replace("/login");if(hydrated&&token&&(pathname==="/login"||pathname==="/register"))router.replace("/")},[hydrated,token,isPublic,pathname,router]);
 useEffect(()=>{if(hydrated&&token)api<User>("/auth/me").then(current=>setAuth(token,current)).catch(()=>{})},[hydrated,token,pathname,setAuth]);
 useEffect(()=>{if(hydrated&&token&&user?.role!=="ADMIN"&&(pathname==="/users"||pathname==="/settings")){useAppStore.getState().showToast("Darbība nav atļauta šai lietotāja lomai","error");router.replace("/")}},[hydrated,token,user,pathname,router]);
 if(!hydrated)return <div className="min-h-screen grid place-items-center text-sm text-muted-foreground">Ielādē WareTrack…</div>;
 if(isPublic)return <>{children}<ToastContainer/></>;
 if(!token)return null;
 return <div className="flex min-h-screen bg-background"><Sidebar/><div className="min-w-0 flex-1 flex flex-col md:ml-[220px]"><Topbar/><main className="flex-1 p-4 md:p-6">{children}</main></div><ToastContainer/></div>;
}
