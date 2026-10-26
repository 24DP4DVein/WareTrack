"use client";
import { QueryClient,QueryClientProvider } from "@tanstack/react-query";
import { useState } from "react";
import AppShell from "@/components/layout/AppShell";
export default function Providers({children}:{children:React.ReactNode}){const [client]=useState(()=>new QueryClient({defaultOptions:{queries:{retry:1,refetchOnWindowFocus:false}}}));return <QueryClientProvider client={client}><AppShell>{children}</AppShell></QueryClientProvider>}
