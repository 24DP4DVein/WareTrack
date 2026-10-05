"use client";
import { useEffect } from "react";
import { usePathname,useRouter } from "next/navigation";
import Sidebar from "./Sidebar";
import Topbar from "./Topbar";
import ToastContainer from "@/components/shared/ToastContainer";
import { useAppStore } from "@/store/useAppStore";

const publicRoutes=["/login","/register","/catalog"];
export default function AppShell({children}:{children:React.ReactNode}){
 const pathname=usePathname(),router=useRouter();
 const {token,user,hydrated}=useAppStore();
 const isPublic=publicRoutes.includes(pathname);
 useEffect(()=>{if(hydrated&&!token&&!isPublic)router.replace("/login");if(hydrated&&token&&(pathname==="/login"||pathname==="/register"))router.replace("/")},[hydrated,token,isPublic,pathname,router]);
 useEffect(()=>{if(hydrated&&token&&user?.role!=="ADMIN"&&(pathname==="/users"||pathname==="/settings"))router.replace("/")},[hydrated,token,user,pathname,router]);
 if(!hydrated)return <div className="min-h-screen grid place-items-center text-sm text-muted-foreground">Ielādē WareTrack…</div>;
 if(isPublic)return <>{children}<ToastContainer/></>;
 if(!token)return null;
 return <div className="flex min-h-screen bg-background"><Sidebar/><div className="min-w-0 flex-1 flex flex-col md:ml-[220px]"><Topbar/><main className="flex-1 p-4 md:p-6">{children}</main></div><ToastContainer/></div>;
}
