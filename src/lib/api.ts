import { useAppStore } from "@/store/useAppStore";
export const API_URL=process.env.NEXT_PUBLIC_API_URL??"http://localhost:8000";
export class ApiError extends Error{constructor(message:string,public status:number){super(message)}}
export async function api<T>(path:string,options:RequestInit={}):Promise<T>{
 const token=useAppStore.getState().token;
 const response=await fetch(`${API_URL}/api${path}`,{...options,headers:{"Content-Type":"application/json",...(token?{Authorization:`Bearer ${token}`}:{}),...options.headers}});
 if(response.status===204)return undefined as T;
 const body=await response.json().catch(()=>({detail:"Servera atbilde nav nolasāma"}));
 if(!response.ok){if(response.status===401&&token)useAppStore.getState().logout();throw new ApiError(typeof body.detail==="string"?body.detail:"Pieprasījumu neizdevās izpildīt",response.status)}
 return body as T;
}
