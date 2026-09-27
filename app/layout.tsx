import "./globals.css";
export const metadata = { title: "StudyRAG", description: "Multimodal RAG study assistant" };
export default function RootLayout({children}:{children:React.ReactNode}) {
  return <html lang="en" suppressHydrationWarning><body>{children}</body></html>;
}
