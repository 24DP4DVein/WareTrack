"use client";
import Link from "next/link";
import { useCurrentCompany } from "@/hooks/useCompanies";
import { LoadingSpinner } from "@/components/shared/ui";

export default function CompanyGuard({children}:{children:React.ReactNode}){
 const {companyId,company,isLoading,isError}=useCurrentCompany();
 if(!companyId)return <div className="rounded-xl border bg-white p-6 text-red-700">Nederīgs uzņēmuma identifikators. <Link className="text-blue-600" href="/companies">Atgriezties pie uzņēmumiem</Link>.</div>;
 if(isLoading)return <LoadingSpinner/>;
 if(isError||!company)return <div className="rounded-xl border bg-white p-6"><h2 className="font-semibold">Uzņēmums nav pieejams</h2><p className="mt-2 text-sm text-muted-foreground">Jums nav aktīvas piekļuves šim uzņēmumam vai uzņēmums vairs nav aktīvs.</p><Link className="mt-4 inline-block text-sm text-blue-600" href="/companies">Atgriezties pie uzņēmumiem</Link></div>;
 return <>{children}</>;
}
