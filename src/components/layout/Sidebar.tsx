"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { ArrowLeftRight,BarChart2,BookOpen,Building2,ClipboardList,LayoutDashboard,MapPin,Package,Settings,Tag,Truck,Users,Warehouse,X } from "lucide-react";
import { cn } from "@/lib/utils";
import { useAppStore } from "@/store/useAppStore";
import { useCurrentCompany } from "@/hooks/useCompanies";

export default function Sidebar(){
 const path=usePathname(),{user,sidebarOpen,closeSidebar}=useAppStore(),{companyId,company}=useCurrentCompany();
 const base=companyId?`/companies/${companyId}`:"",manager=company?.role==="VADITAJS"||company?.role==="ADMIN";
 const groups=[
  {section:"Uzņēmumi",links:[["/companies","Jūsu uzņēmumi",Building2]]},
  ...(company?[{section:company.name,links:[[base,"Informācijas panelis",LayoutDashboard],[`${base}/items`,"Preces",Package],[`${base}/categories`,"Kategorijas",Tag],[`${base}/locations`,"Noliktavas vietas",MapPin],[`${base}/transfers`,"Pārvietošana",ArrowLeftRight],[`${base}/suppliers`,"Piegādātāji",Truck],[`${base}/reports`,"Atskaites",BarChart2],...(manager?[[`${base}/requests`,"Pieteikumi",ClipboardList],[`${base}/members`,"Lietotāji",Users]]:[])]}]:[]),
  ...(user?.role==="ADMIN"?[{section:"Sistēma",links:[["/admin/companies","Uzņēmumu administrēšana",Settings],["/users","Globālie lietotāji",Users]]}]:[]),
  {section:"Palīdzība",links:[["/help","Lietotāja instrukcija",BookOpen]]},
 ];
 return <><button aria-label="Aizvērt izvēlni" onClick={closeSidebar} className={cn("fixed inset-0 z-40 bg-black/40 md:hidden",!sidebarOpen&&"hidden")}/><aside className={cn("sidebar transition-transform md:translate-x-0",sidebarOpen?"translate-x-0":"-translate-x-full")}><div className="px-4 py-5 border-b border-white/10 flex items-center gap-3"><span className="w-8 h-8 rounded-lg bg-blue-600 grid place-items-center"><Warehouse size={16}/></span><div className="flex-1 min-w-0"><b className="font-mono text-sm">WareTrack</b><p className="text-[10px] text-white/40 truncate">{company?.name??"Noliktavas vadība"}</p></div><button onClick={closeSidebar} className="md:hidden"><X size={18}/></button></div><nav className="flex-1 overflow-y-auto py-3">{groups.map(g=><div key={g.section} className="mb-2"><p className="px-4 py-2 text-[10px] text-white/30 uppercase tracking-widest truncate">{g.section}</p>{g.links.map((link:any)=>{const [href,label,Icon]=link;const active=href===base&&base?path===base:href==="/companies"?path==="/companies":path.startsWith(href);return <Link key={href} href={href} onClick={closeSidebar} className={cn("flex items-center gap-3 mx-2 px-3 py-2 rounded-md text-[13px]",active?"bg-blue-600 text-white":"text-white/60 hover:text-white hover:bg-white/5")}><Icon size={15}/><span>{label}</span></Link>})}</div>)}</nav><div className="p-4 border-t border-white/10"><p className="text-xs font-medium truncate">{user?.name}</p><p className="text-[10px] text-white/40">{user?.role==="ADMIN"?"Sistēmas administrators":"Lietotājs"}</p></div></aside></>;
}
