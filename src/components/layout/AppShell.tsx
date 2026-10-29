"use client";
import { useEffect } from "react";
import { usePathname,useRouter } from "next/navigation";
import Sidebar from "./Sidebar";
import Topbar from "./Topbar";
import ToastContainer from "@/components/shared/ToastContainer";
import { useAppStore } from "@/store/useAppStore";

const publicRoutes=["/login","/register","/catalog"];
const legacyRoutes=["/","/items","/categories","/locations","/transfers","/suppliers","/reports"];
export default function AppShell({children}:{children:React.ReactNode}){
 const pathname=usePathname(),router=useRouter();
 const {token,user,hydrated}=useAppStore();
 const isPublic=publicRoutes.includes(pathname);
 const legacy=legacyRoutes.includes(pathname);
 useEffect(()=>{
  if(!hydrated)return;
  if(!token&&!isPublic)router.replace("/login");
  else if(token&&(pathname==="/login"||pathname==="/register"||legacy))router.replace("/companies");
  else if(token&&pathname.startsWith("/admin")&&user?.role!=="ADMIN")router.replace("/companies");
  else if(token&&(pathname==="/users"||pathname==="/settings")&&user?.role!=="ADMIN")router.replace("/companies");
 },[hydrated,token,user,pathname,isPublic,legacy,router]);
 if(!hydrated)return <div className="min-h-screen grid place-items-center text-sm text-muted-foreground">Ielādē WareTrack…</div>;
 if(isPublic)return <>{children}<ToastContainer/></>;
 if(!token||legacy||(pathname.startsWith("/admin")&&user?.role!=="ADMIN"))return null;
 return <div className="flex min-h-screen bg-background"><Sidebar/><div className="min-w-0 flex-1 flex flex-col md:ml-[220px]"><Topbar/><main className="flex-1 p-4 md:p-6">{children}</main></div><ToastContainer/></div>;
}
