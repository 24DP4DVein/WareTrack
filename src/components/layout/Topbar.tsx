"use client";
import { LogOut,Menu,RefreshCw } from "lucide-react";
import { usePathname,useRouter } from "next/navigation";
import { useQueryClient } from "@tanstack/react-query";
import { useAppStore } from "@/store/useAppStore";
import { useCurrentCompany } from "@/hooks/useCompanies";

function title(path:string){if(path==="/companies")return "Jūsu uzņēmumi";if(path==="/admin/companies")return "Uzņēmumu administrēšana";const suffix=path.split("/").pop();return ({items:"Preces",categories:"Kategorijas",locations:"Noliktavas vietas",transfers:"Pārvietošana",suppliers:"Piegādātāji",reports:"Atskaites",members:"Lietotāji",requests:"Pieteikumi"} as Record<string,string>)[suffix??""]??(path.match(/^\/companies\/\d+$/)?"Informācijas panelis":"WareTrack")}
export default function Topbar(){const path=usePathname(),router=useRouter(),qc=useQueryClient(),{toggleSidebar,logout}=useAppStore(),{company}=useCurrentCompany();return <header className="sticky top-0 z-30 bg-white border-b h-14 flex items-center px-4 md:px-6 gap-3"><button aria-label="Atvērt izvēlni" onClick={toggleSidebar} className="md:hidden p-2"><Menu size={18}/></button><div className="flex-1 min-w-0"><h1 className="text-[15px] font-semibold truncate">{title(path)}</h1>{company&&<p className="text-[10px] text-muted-foreground truncate">{company.name}</p>}</div><button title="Atjaunot datus" onClick={()=>qc.invalidateQueries()} className="w-8 h-8 border rounded-md grid place-items-center text-muted-foreground"><RefreshCw size={14}/></button><button title="Izrakstīties" onClick={()=>{logout();qc.clear();router.push("/login")}} className="w-8 h-8 border rounded-md grid place-items-center text-muted-foreground"><LogOut size={14}/></button></header>}
