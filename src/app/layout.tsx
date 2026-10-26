import type { Metadata } from "next";
import "./globals.css";
import Providers from "@/components/Providers";
export const metadata:Metadata={title:"WareTrack",description:"Noliktavas vadības sistēma"};
export default function RootLayout({children}:{children:React.ReactNode}){return <html lang="lv"><body><Providers>{children}</Providers></body></html>}
