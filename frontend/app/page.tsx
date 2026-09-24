"use client";

import { useEffect, useRef, useState } from "react";

type Source = {document:string;page:number;score:number;chunk_id:number};
type Message = {role:"user"|"assistant";content:string;sources?:Source[]};

const LIMIT = 4;

export default function Home() {
  const [messages,setMessages] = useState<Message[]>([]);
  const [input,setInput] = useState("");
  const [busy,setBusy] = useState(false);
  const [status,setStatus] = useState("Ready");
  const docs = useRef<HTMLInputElement>(null);
  const image = useRef<HTMLInputElement>(null);
  const video = useRef<HTMLInputElement>(null);

  async function chat(e:React.FormEvent) {
    e.preventDefault();
    const text=input.trim();
    if(!text||busy)return;
    setMessages(m=>[...m,{role:"user",content:text}]);
    setInput(""); setBusy(true); setStatus("Retrieving...");
    try {
      const r=await fetch("/api/chat",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({message:text})});
      const d=await r.json(); if(!r.ok)throw new Error(d.detail||"Request failed");
      setMessages(m=>[...m,{role:"assistant",content:d.answer,sources:d.sources}]);
      setStatus(d.mode);
    } catch(err) { setMessages(m=>[...m,{role:"assistant",content:String(err)}]); setStatus("Error"); }
    finally {setBusy(false);}
  }

  async function upload(file:File, endpoint:string) {
    if(file.size>LIMIT*1024*1024){setStatus(`Maximum file size is ${LIMIT} MB`);return;}
    setBusy(true);setStatus(`Processing ${file.name}...`);
    try {
      const form=new FormData();form.append("file",file);
      const r=await fetch(endpoint,{method:"POST",body:form});
      const d=await r.json();if(!r.ok)throw new Error(d.detail||"Processing failed");
      if(endpoint.endsWith("documents")) setStatus(`Indexed ${d.chunks} chunks`);
      else {
        const text=endpoint.endsWith("image")
          ? `Image analysis\nDimensions: ${d.width} × ${d.height}\nBrightness: ${d.brightness}\nContrast: ${d.contrast_std}\nSharpness: ${d.sharpness_score}\nEdge density: ${d.edge_density}\nContours: ${d.significant_contours}\n\n${d.note}`
          : `Video analysis\nDuration: ${d.duration_seconds}s\nFPS: ${d.fps}\nFrames: ${d.frame_count}\nSampled: ${d.sampled_frames.length}\n\n${d.note}`;
        setMessages(m=>[...m,{role:"assistant",content:text}]);setStatus("Analysis complete");
      }
    } catch(err){setStatus(String(err));}
    finally{setBusy(false);}
  }

  useEffect(()=>{fetch("/api/health").then(r=>r.json()).then(d=>setStatus(`Ready · ${d.documents} documents · ${d.chunks} chunks`)).catch(()=>setStatus("Backend unavailable"));},[]);

  return <main className="shell">
    <header><div><div className="eyebrow">MULTIMODAL · RAG · TOOL CALLING</div><h1>StudyRAG</h1><p>Search your study material, calculate safely, and inspect images/video with deterministic computer vision.</p></div><div className="status">{status}</div></header>
    <div className="layout">
      <aside>
        <h2>Knowledge Base</h2><p>Upload PDF, DOCX, TXT or Markdown notes.</p>
        <button onClick={()=>docs.current?.click()} disabled={busy}>Upload study material</button>
        <input ref={docs} hidden type="file" accept=".pdf,.docx,.txt,.md" onChange={e=>{const f=e.target.files?.[0];e.target.value="";if(f)upload(f,"/api/documents")}}/>
        <h2>Multimodal</h2>
        <button onClick={()=>image.current?.click()} disabled={busy}>Analyze image</button>
        <input ref={image} hidden type="file" accept="image/*" onChange={e=>{const f=e.target.files?.[0];e.target.value="";if(f)upload(f,"/api/analyze-image")}}/>
        <button onClick={()=>video.current?.click()} disabled={busy}>Analyze video</button>
        <input ref={video} hidden type="file" accept="video/*" onChange={e=>{const f=e.target.files?.[0];e.target.value="";if(f)upload(f,"/api/analyze-video")}}/>
        <div className="note">Upload limit: {LIMIT} MB. No pretrained vision, speech, OCR, or embedding model is used.</div>
      </aside>
      <section className="chat">
        <div className="messages">
          {!messages.length&&<div className="empty"><h2>Ask your study question</h2><p>Upload study material first. Try “What is overfitting?” or “Calculate the accuracy if 437 of 512 predictions are correct.”</p></div>}
          {messages.map((m,i)=><article className={`message ${m.role}`} key={i}><b>{m.role==="user"?"You":"StudyRAG"}</b><div>{m.content}</div>{m.sources?.length?<div className="sources"><b>Sources</b>{m.sources.map(s=><div key={s.chunk_id}>{s.document} · page {s.page} · score {s.score}</div>)}</div>:null}</article>)}
        </div>
        <form onSubmit={chat} className="composer"><textarea value={input} onChange={e=>setInput(e.target.value)} rows={3} placeholder="Ask a question..." disabled={busy}/><button disabled={busy||!input.trim()}>{busy?"Working...":"Send"}</button></form>
      </section>
    </div>
  </main>
}
