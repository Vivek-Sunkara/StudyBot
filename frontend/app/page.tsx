"use client";

import { useEffect, useRef, useState } from "react";

type Source = {document:string;page:number;score:number;chunk_id:number};
type Message = {role:"user"|"assistant";content:string;sources?:Source[];time:string};
type KnowledgeDocument = {id:number;filename:string;file_type:string;chunks:number};
type Theme = "light"|"dark";

const LIMIT = 4;

export default function Home() {
  const [messages,setMessages] = useState<Message[]>([]);
  const [input,setInput] = useState("");
  const [busy,setBusy] = useState(false);
  const [status,setStatus] = useState("Ready to explore");
  const [documents,setDocuments] = useState<KnowledgeDocument[]>([]);
  const [theme,setTheme] = useState<Theme>("dark");
  const conversationId = useRef<string>(crypto.randomUUID());
  const docs = useRef<HTMLInputElement>(null);
  const image = useRef<HTMLInputElement>(null);
  const video = useRef<HTMLInputElement>(null);

  const now=()=>new Date().toLocaleTimeString([], {hour:"2-digit",minute:"2-digit"});
  const focusChat=()=>document.querySelector(".chat")?.scrollIntoView({behavior:"smooth",block:"center"});
  const newChat=()=>{setMessages([]);setInput("");setStatus("New study session");focusChat();};

  function toggleTheme() {
    setTheme(current=>{const next=current==="dark"?"light":"dark";document.documentElement.dataset.theme=next;localStorage.setItem("studyrag-theme",next);return next;});
  }

  async function refreshKnowledge() { const response=await fetch("/api/documents");if(response.ok)setDocuments(await response.json()); }

  async function chat(e:React.FormEvent) {
    e.preventDefault(); const text=input.trim(); if(!text||busy)return;
    setMessages(m=>[...m,{role:"user",content:text,time:now()}]);setInput("");setBusy(true);setStatus("Thinking with your sources...");
    try {
      const response=await fetch("/api/chat",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({message:text,conversation_id:conversationId.current})});
      const data=await response.json();if(!response.ok)throw new Error(data.detail||"Request failed");
      setMessages(m=>[...m,{role:"assistant",content:data.answer,sources:data.sources,time:now()}]);setStatus(data.mode==="groq+local-rag"?"Grounded response ready":"Local knowledge response ready");
    } catch(err) {setMessages(m=>[...m,{role:"assistant",content:String(err),time:now()}]);setStatus("Connection issue");}
    finally {setBusy(false);}
  }

  async function upload(file:File, endpoint:string) {
    if(file.size>LIMIT*1024*1024){setStatus(`Maximum file size is ${LIMIT} MB`);return;}
    setBusy(true);setStatus(`Reading ${file.name}...`);
    try {
      const form=new FormData();form.append("file",file);const response=await fetch(endpoint,{method:"POST",body:form});const data=await response.json();if(!response.ok)throw new Error(data.detail||"Processing failed");
      const content=endpoint.endsWith("documents")?`${file.name} is now searchable in your study space. ${data.chunks} knowledge chunks indexed.`:endpoint.endsWith("image")?(data.description||data.note):data.note;
      setMessages(m=>[...m,{role:"assistant",content,time:now()}]);setStatus(endpoint.endsWith("documents")?"Document indexed":endpoint.endsWith("image")?(data.indexed?"Image understood and indexed":"Image diagnostics ready"):"Video analysis ready");await refreshKnowledge();
    } catch(err){setStatus(String(err));} finally{setBusy(false);}
  }

  useEffect(()=>{
    const saved=localStorage.getItem("studyrag-theme") as Theme|null;const initial=saved==="light"?"light":"dark";setTheme(initial);document.documentElement.dataset.theme=initial;
    Promise.all([fetch("/api/health"),fetch("/api/documents")]).then(async ([health,docsResponse])=>{const data=await health.json();if(docsResponse.ok)setDocuments(await docsResponse.json());setStatus(`Ready · ${data.documents} documents · ${data.chunks} chunks`);}).catch(()=>setStatus("Backend unavailable"));
  },[]);

  return <main className="app-shell">
    <aside className="sidebar"><div className="sidebar-brand"><div className="logo-orbit"><span>S</span></div><div><strong>StudyRAG</strong><small>Midnight Scholar</small></div></div><button className="new-chat" onClick={newChat}><span>＋</span> New chat</button><nav className="nav-group" aria-label="StudyRAG navigation"><span className="nav-label">Workspace</span><button className="nav-item active" onClick={focusChat}><span>✦</span> Chat <kbd>⌘ 1</kbd></button><button className="nav-item" onClick={()=>document.querySelector(".document-list")?.scrollIntoView({behavior:"smooth"})}><span>▤</span> Documents <em>{documents.length}</em></button><button className="nav-item" onClick={()=>image.current?.click()}><span>◌</span> Images</button><button className="nav-item" onClick={()=>video.current?.click()}><span>▣</span> Videos</button><button className="nav-item" onClick={()=>{setInput("Calculate ");focusChat()}}><span>⌁</span> Calculator</button></nav><div className="sidebar-history"><span className="nav-label">Recent chats</span><button className="history-item active-history" onClick={focusChat}>✦ <span>Current study session</span></button><span className="history-date">Today</span></div><div className="sidebar-bottom"><button className="nav-item" onClick={()=>setStatus("Settings are ready in this workspace")}><span>⚙</span> Settings</button><div className="profile"><div className="profile-avatar">S</div><div><strong>Study student</strong><small>{status}</small></div></div></div></aside>
    <section className="workspace"><header className="workspace-header"><div><span className="live-dot"></span><span className="header-status">AI study space <b>·</b> {documents.length} sources indexed</span></div><button className="theme-toggle" onClick={toggleTheme} aria-label={`Switch to ${theme==="dark"?"light":"dark"} mode`} title="Toggle light and dark mode"><span className="eclipse"><i></i></span><span>{theme==="dark"?"Dark":"Light"}</span></button></header><div className="conversation">
      {!messages.length&&<section className="welcome"><div className="welcome-orb"><span>✦</span></div><span className="eyebrow">YOUR INTELLIGENT STUDY COMPANION</span><h1>Make your knowledge<br/><strong>come alive.</strong></h1><p>Ask questions, explore ideas, and turn your study material into clear understanding.</p><div className="action-grid"><button className="action-card cyan" onClick={focusChat}><span className="action-icon">✦</span><strong>Chat with your sources</strong><small>Ask anything about your material</small><b>→</b></button><button className="action-card violet" onClick={()=>docs.current?.click()}><span className="action-icon">▤</span><strong>Upload a document</strong><small>PDF, DOCX, TXT, or Markdown</small><b>→</b></button><button className="action-card blue" onClick={()=>image.current?.click()}><span className="action-icon">◌</span><strong>Analyze an image</strong><small>Describe and index visual content</small><b>→</b></button><button className="action-card lavender" onClick={()=>video.current?.click()}><span className="action-icon">▣</span><strong>Analyze a video</strong><small>Inspect frames and scenes</small><b>→</b></button><button className="action-card gold" onClick={()=>{setInput("Calculate ");focusChat()}}><span className="action-icon">⌁</span><strong>Use calculator</strong><small>Safe, precise arithmetic</small><b>→</b></button><button className="action-card pink" onClick={()=>{setInput("Summarize the uploaded material");focusChat()}}><span className="action-icon">≋</span><strong>Summarize</strong><small>Find the essential ideas</small><b>→</b></button></div></section>}
      {messages.map((message,index)=><article className={`message ${message.role}`} key={`${message.time}-${index}`}><div className="message-head"><div className="message-avatar">{message.role==="assistant"?"S":"Y"}</div><div><b>{message.role==="assistant"?"StudyRAG":"You"}</b><time>{message.time}</time></div></div><div className="message-copy">{message.content}</div>{message.sources?.length?<div className="sources"><div className="sources-heading">Grounded sources</div>{message.sources.map(source=><div className="source-item" key={source.chunk_id}><span className="source-file">▤</span><div><strong>{source.document}</strong><small>Page {source.page} · relevance {source.score}</small></div></div>)}</div>:null}</article>)}
      {busy&&<div className="typing"><span></span><span></span><span></span><em>{status}</em></div>}
    </div><form onSubmit={chat} className="composer"><div className="composer-shell"><div className="attach-group"><button type="button" className="icon-button" onClick={()=>docs.current?.click()} aria-label="Upload document" title="Upload document">＋</button><button type="button" className="icon-button" onClick={()=>image.current?.click()} aria-label="Analyze image" title="Analyze image">◌</button><button type="button" className="icon-button" onClick={()=>video.current?.click()} aria-label="Analyze video" title="Analyze video">▣</button></div><textarea value={input} onChange={e=>setInput(e.target.value)} rows={1} placeholder="Ask StudyRAG anything..." disabled={busy}/><button className="send-button" disabled={busy||!input.trim()} aria-label="Send message">{busy?"…":"↑"}</button></div><small className="composer-hint">StudyRAG can make mistakes. Check important information in your sources.</small></form></section>
    <input ref={docs} hidden type="file" accept=".pdf,.docx,.txt,.md" onChange={e=>{const file=e.target.files?.[0];e.target.value="";if(file)upload(file,"/api/documents")}}/><input ref={image} hidden type="file" accept="image/*" onChange={e=>{const file=e.target.files?.[0];e.target.value="";if(file)upload(file,"/api/analyze-image")}}/><input ref={video} hidden type="file" accept="video/*" onChange={e=>{const file=e.target.files?.[0];e.target.value="";if(file)upload(file,"/api/analyze-video")}}/>
  </main>;
}
