"use client";
import { QueryClient,QueryClientProvider,useQueryClient } from "@tanstack/react-query";
import { useEffect,useRef,useState } from "react";
import AppShell from "@/components/layout/AppShell";
import { api } from "@/lib/api";
import { useAppStore } from "@/store/useAppStore";
import type { User } from "@/types";

function SessionManager(){
 const qc=useQueryClient(),{hydrated,token,user,setAuth,logout}=useAppStore();
 const identity=token&&user?`${user.id}:${token}`:"guest",previous=useRef(identity);
 useEffect(()=>{if(previous.current!==identity){qc.clear();previous.current=identity}},[identity,qc]);
 useEffect(()=>{if(!hydrated||!token)return;let active=true;api<User>("/auth/me").then(current=>{if(active)setAuth(token,current)}).catch(()=>{if(active){logout();qc.clear()}});return()=>{active=false}},[hydrated,token,setAuth,logout,qc]);
 return null;
}

export default function Providers({children}:{children:React.ReactNode}){
 const [client]=useState(()=>new QueryClient({defaultOptions:{queries:{retry:(count,error:any)=>error?.status===401||error?.status===403?false:count<1,refetchOnWindowFocus:true}}}));
 return <QueryClientProvider client={client}><SessionManager/><AppShell>{children}</AppShell></QueryClientProvider>;
}
