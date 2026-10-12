import { clsx,type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";
export const cn=(...inputs:ClassValue[])=>twMerge(clsx(inputs));
export const formatCurrency=(v:number)=>new Intl.NumberFormat("lv-LV",{style:"currency",currency:"EUR"}).format(v);
export const formatNumber=(v:number)=>new Intl.NumberFormat("lv-LV").format(v);
export const formatDate=(v:string)=>new Intl.DateTimeFormat("lv-LV",{day:"2-digit",month:"short",year:"numeric"}).format(new Date(v));
export const formatDateTime=(v:string)=>new Intl.DateTimeFormat("lv-LV",{dateStyle:"short",timeStyle:"short"}).format(new Date(v));
export function generateSKU(name:string){return `${name.trim().toUpperCase().split(/\s+/).slice(0,3).map(w=>w.slice(0,3)).join("-")}-${Date.now().toString().slice(-4)}`}
