"use client";
import Link from "next/link";
import { Building2,RefreshCw } from "lucide-react";
import { useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { useMyCompanies,useMyRequests,usePublicCompanies,useSubmitJoinRequest,companyKeys } from "@/hooks/useCompanies";
import { useAppStore } from "@/store/useAppStore";
import { Badge,Button,Card,LoadingSpinner,SectionHeader } from "@/components/shared/ui";
import { formatDate } from "@/lib/utils";

const roleName={ADMIN:"Sistēmas administrators",VADITAJS:"Vadītājs",LIETOTAJS:"Lietotājs"};
export default function CompaniesPage(){
 const mine=useMyCompanies(),requests=useMyRequests(),publicCompanies=usePublicCompanies(),submit=useSubmitJoinRequest(),toast=useAppStore(s=>s.showToast),userId=useAppStore(s=>s.user?.id),qc=useQueryClient();
 const [selected,setSelected]=useState(0);
 const pending=requests.data?.filter(r=>r.status==="PENDING")??[],rejected=requests.data?.filter(r=>r.status==="REJECTED")??[];
 const unavailable=new Set([...(mine.data?.map(c=>c.id)??[]),...pending.map(r=>r.companyId)]);
 const available=publicCompanies.data?.filter(c=>!unavailable.has(c.id))??[];
 const refresh=()=>Promise.all([qc.invalidateQueries({queryKey:companyKeys.mine(userId)}),qc.invalidateQueries({queryKey:companyKeys.myRequests(userId)}),qc.invalidateQueries({queryKey:companyKeys.public})]);
 if(mine.isLoading||requests.isLoading)return <LoadingSpinner/>;
 return <div><SectionHeader title="Jūsu uzņēmumi" subtitle="Izvēlieties uzņēmumu vai pārbaudiet pieteikuma statusu"><Button onClick={refresh}><RefreshCw size={13}/>Atjaunot</Button></SectionHeader>{mine.isError||requests.isError?<p className="mb-4 rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-700">Datus neizdevās ielādēt. Mēģiniet vēlreiz.</p>:null}<div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">{mine.data?.map(company=><Card key={company.id} className="p-5"><div className="flex items-start gap-3"><span className="rounded-lg bg-blue-50 p-2 text-blue-600"><Building2 size={18}/></span><div className="flex-1"><h2 className="font-semibold">{company.name}</h2><p className="mt-1 text-xs text-muted-foreground">{roleName[company.role]}</p></div></div><Link href={`/companies/${company.id}`} className="mt-5 inline-flex rounded-md border border-blue-600 bg-blue-600 px-3.5 py-1.5 text-xs font-medium text-white">Atvērt uzņēmumu</Link></Card>)}</div>{!mine.data?.length&&<Card className="mt-4 p-6 text-sm text-muted-foreground">Jums vēl nav pieejamu uzņēmumu.</Card>}
 {pending.length>0&&<section className="mt-8"><h2 className="mb-3 font-semibold">Gaida apstiprinājumu</h2><div className="space-y-2">{pending.map(r=><Card key={r.id} className="p-4"><div className="flex items-center gap-3"><div className="flex-1"><b className="text-sm">{r.companyName}</b><p className="text-xs text-muted-foreground">Jūsu pieteikums gaida apstiprinājumu. Iesniegts {formatDate(r.requestedAt)}.</p></div><Badge variant="amber">Gaida</Badge></div></Card>)}</div></section>}
 {rejected.length>0&&<section className="mt-8"><h2 className="mb-3 font-semibold">Noraidītie pieteikumi</h2><div className="space-y-2">{rejected.map(r=><Card key={r.id} className="p-4"><b className="text-sm">{r.companyName}</b><p className="text-xs text-muted-foreground">{r.rejectionReason||"Pieteikums tika noraidīts."}</p></Card>)}</div></section>}
 {available.length>0&&<section className="mt-8"><h2 className="mb-3 font-semibold">Pieteikties citam uzņēmumam</h2><Card className="flex flex-col gap-3 p-4 sm:flex-row"><select className="flex-1 rounded-md border px-3 py-2 text-sm" value={selected} onChange={e=>setSelected(Number(e.target.value))}><option value={0}>Izvēlieties uzņēmumu</option>{available.map(c=><option key={c.id} value={c.id}>{c.name}</option>)}</select><Button variant="primary" disabled={!selected} isLoading={submit.isPending} onClick={()=>submit.mutate(selected,{onSuccess:()=>{toast("Pieteikums nosūtīts");setSelected(0)},onError:e=>toast(e.message,"error")})}>Nosūtīt pieteikumu</Button></Card></section>}
 </div>;
}
