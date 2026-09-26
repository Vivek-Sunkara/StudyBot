"use client";

import { useEffect, useRef, useState } from "react";

type Source = {document:string;page:number;score:number;chunk_id:number};
type Message = {role:"user"|"assistant";content:string;sources?:Source[];time:string;media?:{type:string;url:string;name:string}[]};
type KnowledgeDocument = {id:number|string;filename:string;file_type:string;kind:string;chunks:number;created_at?:string};
type Conversation = {id:string;title:string;message_count:number;updated_at:string};
type Theme = "light"|"dark";

type IconName = "chat"|"document"|"image"|"video"|"calculator"|"settings"|"attach"|"send"|"play"|"list"|"sparkle";

function Icon({name, style}:{name:IconName; style?:React.CSSProperties}) {
  const p = {width:"1em",height:"1em",viewBox:"0 0 24 24",fill:"none" as const,stroke:"currentColor",strokeWidth:1.8,strokeLinecap:"round" as const,strokeLinejoin:"round" as const,style,"aria-hidden":true as const,focusable:"false" as const};
  switch(name){
    case "chat": return <svg {...p}><path d="M4 5h16v11H8l-4 4V5Z"/><path d="M8 9h8M8 12.5h5"/></svg>;
    case "document": return <svg {...p}><path d="M7 3h7l5 5v13H7V3Z"/><path d="M14 3v5h5"/><path d="M9.3 12h5.4M9.3 15.5h5.4"/></svg>;
    case "image": return <svg {...p}><rect x="3" y="4" width="18" height="16" rx="2.2"/><circle cx="8.6" cy="9.6" r="1.5" fill="currentColor" stroke="none"/><path d="M21 16.2l-5.3-5.3a1.5 1.5 0 0 0-2.12 0L4 19.5"/></svg>;
    case "video": return <svg {...p}><rect x="2.5" y="6" width="13" height="12" rx="2.2"/><path d="M15.5 10.2 21 7v10l-5.5-3.2Z"/></svg>;
    case "calculator": return <svg {...p}><rect x="5" y="3" width="14" height="18" rx="2.2"/><path d="M8 7.2h8"/><path d="M8 11.2h.01M12 11.2h.01M16 11.2h.01M8 14.8h.01M12 14.8h.01M16 14.8h.01M8 18.4h.01M12 18.4h.01" strokeWidth={2.6}/></svg>;
    case "settings": return <svg {...p}><circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 1 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 1 1-4 0v-.1a1.65 1.65 0 0 0-1-1.5 1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 1 1-2.83-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 1 1 0-4h.1a1.65 1.65 0 0 0 1.5-1 1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 1 1 2.83-2.83l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 1 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 1 1 2.83 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 1 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1Z"/></svg>;
    case "attach": return <svg {...p}><path d="M17 7.2 9.4 14.8a2.6 2.6 0 0 1-3.68-3.68l7.6-7.6a4 4 0 1 1 5.66 5.66L11 17.14a1.4 1.4 0 0 1-1.98-1.98L15.5 8.7"/></svg>;
    case "send": return <svg {...p} strokeWidth={2}><path d="M4 12 20 4l-5.3 16-3.3-6.8L4 12Z"/></svg>;
    case "play": return <svg {...p} fill="currentColor" stroke="none"><path d="M8 5v14l11-7L8 5Z"/></svg>;
    case "list": return <svg {...p}><path d="M9 6h12M9 12h12M9 18h12"/><path d="M4 6h.01M4 12h.01M4 18h.01" strokeWidth={3}/></svg>;
    case "sparkle": return <svg {...p}><path d="M12 3.5 13.9 9l5.6 1.9-5.6 1.9L12 18.4l-1.9-5.6L4.5 10.9 10.1 9 12 3.5Z"/></svg>;
    default: return null;
  }
}

const LIMIT = 4;

export default function Home() {
  const [messages,setMessages] = useState<Message[]>([]);
  const [input,setInput] = useState("");
  const [busy,setBusy] = useState(false);
  const [status,setStatus] = useState("Ready to explore");
  const [documents,setDocuments] = useState<KnowledgeDocument[]>([]);
  const [chats,setChats] = useState<Conversation[]>([]);
  const [view,setView] = useState<"chat"|"dashboard">("chat");
  const [editingKey,setEditingKey] = useState<string|null>(null);
  const [editingName,setEditingName] = useState("");
  const [theme,setTheme] = useState<Theme>("dark");
  const [isMobile,setIsMobile] = useState(false);
  const conversationId = useRef<string>(crypto.randomUUID());
  const docs = useRef<HTMLInputElement>(null);
  const image = useRef<HTMLInputElement>(null);
  const video = useRef<HTMLInputElement>(null);
  const dashboardDocs = useRef<HTMLInputElement>(null);
  const dashboardImages = useRef<HTMLInputElement>(null);
  const dashboardVideos = useRef<HTMLInputElement>(null);

  const now=()=>new Date().toLocaleTimeString([], {hour:"2-digit",minute:"2-digit"});
  const focusChat=()=>document.querySelector(".chat")?.scrollIntoView({behavior:"smooth",block:"center"});
  const newChat=()=>{conversationId.current=crypto.randomUUID();setMessages([]);setInput("");setView("chat");setStatus("New study session");focusChat();};

  function toggleTheme() {
    setTheme(current=>{const next=current==="dark"?"light":"dark";document.documentElement.dataset.theme=next;localStorage.setItem("studyrag-theme",next);return next;});
  }

  async function refreshKnowledge() { const response=await fetch("/api/documents");if(response.ok)setDocuments(await response.json()); }
  async function refreshChats() { const response=await fetch("/api/chats");if(response.ok)setChats(await response.json()); }
  async function openChat(id:string) {
    const response=await fetch(`/api/chats/${id}`); if(!response.ok)return;
    const data=await response.json(); conversationId.current=id; setMessages(data.messages.map((m:{role:"user"|"assistant";content:string},i:number)=>({...m,time:`History ${i+1}`}))); setView("chat");
  }
  function beginRename(item:KnowledgeDocument|Conversation, type:"library"|"chat") {
    const name=type === "library" ? (item as KnowledgeDocument).filename : (item as Conversation).title;
    setEditingKey(`${type}:${item.id}`);setEditingName(name);
  }
  async function renameItem(item:KnowledgeDocument|Conversation, type:"library"|"chat") {
    const name=editingName.trim();
    if(!name){setStatus("Name cannot be empty");return;}
    const response=await fetch(`/api/${type === "library" ? "library" : "chats"}/${item.id}`,{method:"PATCH",headers:{"Content-Type":"application/json"},body:JSON.stringify({name})});
    if(!response.ok){const data=await response.json().catch(()=>({}));setStatus(data.detail||"Rename failed");return;}
    setEditingKey(null);setEditingName("");setStatus("Renamed successfully");
    await (type === "library" ? refreshKnowledge() : refreshChats());
  }
  async function deleteItem(item:KnowledgeDocument) {
    if(!window.confirm(`Delete ${item.filename}?`))return;
    await fetch(`/api/library/${item.id}`,{method:"DELETE"}); await refreshKnowledge();
  }

  async function chat(e:React.FormEvent) {
    e.preventDefault(); const text=input.trim(); if(!text||busy)return;
    setMessages(m=>[...m,{role:"user",content:text,time:now()}]);setInput("");setBusy(true);setStatus("Thinking with your sources...");
    try {
      const response=await fetch("/api/chat",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({message:text,conversation_id:conversationId.current})});
      const data=await response.json();if(!response.ok)throw new Error(data.detail||"Request failed");
      setMessages(m=>[...m,{role:"assistant",content:data.answer,sources:data.sources,time:now()}]);setStatus(data.mode==="groq+local-rag"?"Grounded response ready":"Local knowledge response ready");await refreshChats();
    } catch(err) {setMessages(m=>[...m,{role:"assistant",content:String(err),time:now()}]);setStatus("Connection issue");}
    finally {setBusy(false);}
  }

  async function upload(file:File, endpoint:string, showInChat=true) {
    if(file.size>LIMIT*1024*1024){setStatus(`Maximum file size is ${LIMIT} MB`);return;}
    setBusy(true);setStatus(`Reading ${file.name}...`);
    try {
      const form=new FormData();form.append("file",file);const response=await fetch(endpoint,{method:"POST",body:form});const data=await response.json();if(!response.ok)throw new Error(data.detail||"Processing failed");
      const content=endpoint.endsWith("documents")?`${file.name} is now searchable in your study space. ${data.chunks} knowledge chunks indexed.`:endpoint.endsWith("image")?(data.description||data.note):data.note;
      const mediaType = endpoint.endsWith("documents")?"document":endpoint.endsWith("image")?"image":"video";
      const mediaUrl = URL.createObjectURL(file);
      if(showInChat)setMessages(m=>[...m,{role:"assistant",content,time:now(),media:[{type:mediaType,url:mediaUrl,name:file.name}]}]);setStatus(endpoint.endsWith("documents")?"Document indexed":endpoint.endsWith("image")?(data.indexed?"Image understood and indexed":"Image diagnostics ready"):"Video analysis ready");await refreshKnowledge();await refreshChats();
    } catch(err){setStatus(String(err));} finally{setBusy(false);}
  }

  useEffect(()=>{
    const saved=localStorage.getItem("studyrag-theme") as Theme|null;const initial=saved==="light"?"light":"dark";setTheme(initial);document.documentElement.dataset.theme=initial;
    
    const checkMobile = () => {
      setIsMobile(window.innerWidth <= 700);
    };
    checkMobile();
    window.addEventListener("resize", checkMobile);
    
    Promise.all([fetch("/api/health"),fetch("/api/documents"),fetch("/api/chats")]).then(async ([health,docsResponse,chatsResponse])=>{const data=await health.json();if(docsResponse.ok)setDocuments(await docsResponse.json());if(chatsResponse.ok)setChats(await chatsResponse.json());setStatus(`Ready · ${data.documents} documents · ${data.chunks} chunks`);}).catch(()=>setStatus("Backend unavailable"));
    
    return () => window.removeEventListener("resize", checkMobile);
  },[]);

  const getGreeting = () => "Let's study something new.";

  const libraryGroups=["document","image","video"] as const;
  return <main className="app-shell">
    <aside className="sidebar"><div className="sidebar-brand"><div className="logo-orbit"><span>S</span></div><div><strong>StudyRAG</strong><small>Midnight Scholar</small></div></div><button className="new-chat" onClick={newChat}><span>＋</span> New chat</button><nav className="nav-group" aria-label="StudyRAG navigation"><span className="nav-label">Workspace</span><button className={`nav-item ${view==="chat"?"active":""}`} onClick={()=>{setView("chat");focusChat()}}><span><Icon name="chat"/></span> Chat <kbd>⌘ 1</kbd></button><button className={`nav-item ${view==="dashboard"?"active":""}`} onClick={()=>setView("dashboard")}><span><Icon name="document"/></span> Library <em>{documents.length}</em></button></nav><div className="sidebar-history"><span className="nav-label">Recent chats</span>{chats.slice(0,5).map(chat=><button className="history-item" key={chat.id} onClick={()=>openChat(chat.id)}><span><Icon name="chat"/></span> <span>{chat.title}</span></button>)}</div><div className="sidebar-bottom"><div className="profile"><div className="profile-avatar">S</div><div><strong>Study student</strong><small>{status}</small></div></div></div></aside>
    <section className="workspace"><header className="workspace-header"><div style={{visibility:"hidden"}}><span className="live-dot"></span><span className="header-status">AI study space</span></div><button className="theme-toggle" onClick={toggleTheme} aria-label={`Switch to ${theme==="dark"?"light":"dark"} mode`} title={`Switch to ${theme==="dark"?"light":"dark"} mode`}><span className="sun-icon">☀️</span><span className="moon-icon">🌙</span><span className="eclipse"><i></i></span></button></header>
      {view==="dashboard"&&<section className="dashboard-panel">
        <div className="dashboard-heading"><div><span className="nav-label">Workspace</span><h1>Study library</h1><p>Manage your study materials and return to any conversation.</p></div><button className="new-chat" onClick={newChat}>＋ New chat</button></div>
        <div className="dashboard-grid"><section className="dashboard-section"><div className="section-heading"><div><h2>Library</h2><p>{documents.length} uploaded items</p></div><div className="library-add"><button className="icon-button" onClick={()=>dashboardDocs.current?.click()} title="Add document" aria-label="Add document"><Icon name="document"/></button><button className="icon-button" onClick={()=>dashboardImages.current?.click()} title="Add image" aria-label="Add image"><Icon name="image"/></button><button className="icon-button" onClick={()=>dashboardVideos.current?.click()} title="Add video" aria-label="Add video"><Icon name="video"/></button></div></div>
          <div className="library-list">{libraryGroups.map(kind=><div className="library-group" key={kind}><h3><Icon name={kind}/>{kind}s</h3>{documents.filter(item=>item.kind===kind).map(item=>{const key=`library:${item.id}`;return <div className="library-item" key={String(item.id)}><span className="library-item-icon"><Icon name={kind}/></span><div>{editingKey===key?<input className="rename-input" value={editingName} onChange={e=>setEditingName(e.target.value)} onKeyDown={e=>{if(e.key==="Enter")renameItem(item,"library");if(e.key==="Escape")setEditingKey(null)}} autoFocus/>:<><strong>{item.filename}</strong><small>{kind === "document" ? `${item.chunks} chunks` : "Uploaded media"}</small></>}</div>{editingKey===key?<><button className="icon-button" onClick={()=>renameItem(item,"library")} title="Save name" aria-label="Save name">✓</button><button className="icon-button" onClick={()=>setEditingKey(null)} title="Cancel" aria-label="Cancel rename">×</button></>:<><button className="icon-button" onClick={()=>beginRename(item,"library")} title="Rename" aria-label={`Rename ${item.filename}`}>✎</button><button className="icon-button danger" onClick={()=>deleteItem(item)} title="Delete" aria-label={`Delete ${item.filename}`}>×</button></>}</div>})}{!documents.some(item=>item.kind===kind)&&<p className="empty-state">No {kind}s uploaded yet.</p>}</div>)}</div>
        </section><section className="dashboard-section"><div className="section-heading"><div><h2>Previous chats</h2><p>Open or rename a study session</p></div></div><div className="chat-history-list">{chats.map(chat=>{const key=`chat:${chat.id}`;return <div className="library-item" key={chat.id}><span className="library-item-icon"><Icon name="chat"/></span><div>{editingKey===key?<input className="rename-input" value={editingName} onChange={e=>setEditingName(e.target.value)} onKeyDown={e=>{if(e.key==="Enter")renameItem(chat,"chat");if(e.key==="Escape")setEditingKey(null)}} autoFocus/>:<><strong>{chat.title}</strong><small>{chat.message_count} messages</small></>}</div>{editingKey===key?<><button className="icon-button" onClick={()=>renameItem(chat,"chat")} title="Save name" aria-label="Save name">✓</button><button className="icon-button" onClick={()=>setEditingKey(null)} title="Cancel" aria-label="Cancel rename">×</button></>:<><button className="icon-button" onClick={()=>openChat(chat.id)} title="Open chat" aria-label={`Open ${chat.title}`}><Icon name="chat"/></button><button className="icon-button" onClick={()=>beginRename(chat,"chat")} title="Rename" aria-label={`Rename ${chat.title}`}>✎</button></>}</div>})}{!chats.length&&<p className="empty-state">No previous chats yet.</p>}</div></section></div>
      </section>}
      <div className={`conversation chat ${view==="dashboard"?"dashboard-hidden":""}`}>
      {!messages.length&&<section className="welcome">
        <div style={{marginBottom: "16px", display: "flex", alignItems: "center", justifyContent: "center"}}>
          <div className="welcome-orb" style={{
            width: "80px",
            height: "80px",
            borderRadius: "50%",
            background: "radial-gradient(circle at 30% 20%, #9bc8ff, #5e8cff 40%, #6b5cff 80%)",
            display: "grid",
            placeItems: "center",
            boxShadow: "0 0 40px rgba(107, 92, 255, 0.5)",
            border: "2px solid rgba(150, 200, 255, 0.4)",
            fontSize: "36px"
          }}><Icon name="sparkle" style={{color:"#fff",filter:"drop-shadow(0 2px 6px rgba(255,255,255,.5))"}}/></div>
        </div>
        <h1>{getGreeting()}</h1><p>Learn Smarter with Your AI Study Assistant</p><div className="action-grid">
          <button className="action-card cyan" onClick={focusChat}><span className="action-icon"><Icon name="chat"/></span><strong>Chat with your sources</strong><b>→</b></button>
          <button className="action-card blue" onClick={()=>docs.current?.click()}><span className="action-icon"><Icon name="document"/></span><strong>Upload a document</strong><b>→</b></button>
          <button className="action-card violet" onClick={()=>image.current?.click()}><span className="action-icon"><Icon name="image"/></span><strong>Analyze an image</strong><b>→</b></button>
          <button className="action-card lavender" onClick={()=>video.current?.click()}><span className="action-icon"><Icon name="video"/></span><strong>Analyze a video</strong><b>→</b></button>
          <button className="action-card gold" onClick={()=>{setInput("Calculate ");focusChat()}}><span className="action-icon"><Icon name="calculator"/></span><strong>Use calculator</strong><b>→</b></button>
          <button className="action-card pink" onClick={()=>{setInput("Summarize the uploaded material");focusChat()}}><span className="action-icon"><Icon name="list"/></span><strong>Summarize</strong><b>→</b></button>
        </div>
      </section>}
      {messages.map((message,index)=><article className={`message ${message.role}`} key={`${message.time}-${index}`}><div className="message-head"><div className="message-avatar">{message.role==="assistant"?"S":"Y"}</div><div><b>{message.role==="assistant"?"StudyRAG":"You"}</b><time>{message.time}</time></div></div>{message.media?.length?<div className="message-media">{message.media.map((m,i)=>m.type==="document"?<div className="media-item document-preview" key={i}><div className="doc-icon"><Icon name="document"/></div><div className="doc-info"><strong>{m.name}</strong><small>Document</small></div></div>:m.type==="image"?<div className="media-item image-preview" key={i}><img src={m.url} alt={m.name} /><div className="media-label">{m.name}</div></div>:<div className="media-item video-preview" key={i}><div className="video-placeholder"><Icon name="play"/></div><div className="media-label">{m.name}</div></div>)}</div>:null}<div className="message-copy">{message.content}</div>{message.sources?.length?<div className="sources"><div className="sources-heading">Grounded sources</div>{message.sources.map(source=><div className="source-item" key={source.chunk_id}><span className="source-file"><Icon name="document"/></span><div><strong>{source.document}</strong><small>Page {source.page} · relevance {source.score}</small></div></div>)}</div>:null}</article>)}
      {busy&&<div className="typing"><span></span><span></span><span></span><em>{status}</em></div>}
    </div><form onSubmit={chat} className={`composer ${view==="dashboard"?"dashboard-hidden":""}`}><div className="composer-shell"><div className="attach-group"><button type="button" className="icon-button" onClick={()=>docs.current?.click()} aria-label="Upload document" title="Upload document"><Icon name="attach"/></button><button type="button" className="icon-button" onClick={()=>image.current?.click()} aria-label="Analyze image" title="Analyze image"><Icon name="image"/></button><button type="button" className="icon-button" onClick={()=>video.current?.click()} aria-label="Analyze video" title="Analyze video"><Icon name="video"/></button></div><textarea value={input} onChange={e=>setInput(e.target.value)} rows={1} placeholder="Ask StudyRAG anything..." disabled={busy}/><button className="send-button" disabled={busy||!input.trim()} aria-label="Send message">{busy?<span className="send-spinner"/>:<Icon name="send"/>}</button></div><small className="composer-hint">StudyRAG can make mistakes. Check important information in your sources.</small></form>
      
      {documents.length > 0 && <section className="document-list" style={{marginTop: "24px", paddingTop: "16px", borderTop: "1px solid var(--line)"}}>
        <h3 style={{margin: "0 0 12px", fontSize: "12px", color: "var(--muted)", fontWeight: 600, letterSpacing: ".08em", textTransform: "uppercase"}}>Indexed Documents</h3>
        <div style={{display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(120px, 1fr))", gap: "10px"}}>
          {documents.map(doc => (
            <div key={doc.id} style={{
              padding: "12px",
              borderRadius: "10px",
              background: "rgba(63,124,231,.12)",
              border: "1px solid rgba(110,231,255,.2)",
              textAlign: "center",
              transition: "all .3s ease",
              cursor: "pointer"
            }} onClick={()=>setView("dashboard")} onMouseEnter={(e) => {e.currentTarget.style.background = "rgba(63,124,231,.22)"; e.currentTarget.style.transform = "translateY(-2px)"}} onMouseLeave={(e) => {e.currentTarget.style.background = "rgba(63,124,231,.12)"; e.currentTarget.style.transform = "translateY(0)"}}>
              <div style={{fontSize: "24px", marginBottom: "6px", color: "var(--cyan)", opacity: 0.8, display:"flex", justifyContent:"center"}}><Icon name="document"/></div>
              <strong style={{display: "block", fontSize: "9px", color: "var(--text)", wordBreak: "break-word", maxHeight: "24px", overflow: "hidden"}}>{doc.filename}</strong>
              <small style={{display: "block", fontSize: "8px", color: "var(--muted)", marginTop: "4px"}}>{doc.chunks} chunks</small>
            </div>
          ))}
        </div>
      </section>}
      {isMobile && <nav className="bottom-nav">
        <button className="nav-item-mobile active" onClick={focusChat} title="Chat">
          <span><Icon name="chat"/></span>
          <span>Chat</span>
        </button>
        <button className="nav-item-mobile" onClick={()=>setView("dashboard")} title="Library">
          <span><Icon name="document"/></span>
          <span>Library</span>
        </button>
      </nav>}
    </section>
    <input ref={docs} hidden type="file" accept=".pdf,.docx,.txt,.md" onChange={e=>{const file=e.target.files?.[0];e.target.value="";if(file)upload(file,"/api/documents")}}/><input ref={image} hidden type="file" accept="image/*" onChange={e=>{const file=e.target.files?.[0];e.target.value="";if(file)upload(file,"/api/analyze-image")}}/><input ref={video} hidden type="file" accept="video/*" onChange={e=>{const file=e.target.files?.[0];e.target.value="";if(file)upload(file,"/api/analyze-video")}}/><input ref={dashboardDocs} hidden type="file" accept=".pdf,.docx,.txt,.md" onChange={e=>{const file=e.target.files?.[0];e.target.value="";if(file)upload(file,"/api/documents",false)}}/><input ref={dashboardImages} hidden type="file" accept="image/*" onChange={e=>{const file=e.target.files?.[0];e.target.value="";if(file)upload(file,"/api/analyze-image",false)}}/><input ref={dashboardVideos} hidden type="file" accept="video/*" onChange={e=>{const file=e.target.files?.[0];e.target.value="";if(file)upload(file,"/api/analyze-video",false)}}/>
  </main>;
}
