import { useAppStore } from "@/store/useAppStore";

export const API_URL=process.env.NEXT_PUBLIC_API_URL??"http://localhost:8000";
export class ApiError extends Error{constructor(message:string,public status:number,public errors?:unknown){super(message)}}
const translations:Record<string,string>={
 "Company not found":"Uzņēmums nav atrasts.","Company is not active":"Uzņēmums nav aktīvs.",
 "Active approved company membership is required":"Nepieciešama aktīva un apstiprināta dalība uzņēmumā.",
 "Company permission is required":"Jums nav tiesību veikt šo darbību.",
 "A pending join request already exists":"Šim uzņēmumam jau ir neizskatīts pieteikums.",
 "User already has active company membership":"Jums jau ir aktīva dalība šajā uzņēmumā.",
 "Join request has already been reviewed":"Pieteikums jau ir izskatīts.",
 "Users cannot approve their own join requests":"Savu pieteikumu apstiprināt nevar.",
 "Users cannot review their own join requests":"Savu pieteikumu izskatīt nevar.",
 "Managers cannot demote themselves":"Vadītājs nevar pazemināt savu lomu.",
 "Managers cannot revoke their own membership":"Vadītājs nevar atsaukt savu dalību.",
 "The last active manager cannot be demoted":"Pēdējā aktīvā vadītāja lomu nevar pazemināt.",
 "The last active manager cannot be revoked":"Pēdējā aktīvā vadītāja piekļuvi nevar atsaukt.",
 "Company has unresolved transfers or join requests":"Uzņēmumam ir nepabeigti pārvietojumi vai neizskatīti pieteikumi.",
};

export async function api<T>(path:string,options:RequestInit={}):Promise<T>{
 const token=useAppStore.getState().token;
 const response=await fetch(`${API_URL}/api${path}`,{...options,headers:{"Content-Type":"application/json",...(token?{Authorization:`Bearer ${token}`}:{}) ,...options.headers}});
 if(response.status===204)return undefined as T;
 const body=await response.json().catch(()=>({detail:"Servera atbildi nevar nolasīt"}));
 if(!response.ok){
  if(response.status===401&&token)useAppStore.getState().logout();
  const detail=typeof body.detail==="string"?body.detail:"";
  const fallback=response.status===401?"Sesija ir beigusies. Pieslēdzieties vēlreiz.":response.status===403?"Jums nav tiesību veikt šo darbību.":response.status===404?"Pieprasītais resurss nav atrasts.":response.status===409?"Darbību nevar pabeigt datu konflikta dēļ.":response.status===422?"Ievadītie dati nav derīgi.":"Pieprasījumu neizdevās izpildīt.";
  throw new ApiError(translations[detail]??(detail&&/[^\x00-\x7F]/.test(detail)?detail:fallback),response.status,body.errors);
 }
 return body as T;
}
