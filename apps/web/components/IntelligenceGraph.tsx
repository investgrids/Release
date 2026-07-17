"use client";
import { AnimatePresence, motion } from "framer-motion";
import React, { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { API_BASE_URL as API } from "@/lib/api";
import {
  Zap, Landmark, BarChart2, Building2, Globe, Package, Lightbulb,
  TrendingUp, TrendingDown, ArrowLeftRight, Globe2, Activity,
  X, Search, Bookmark, ChevronLeft, ChevronRight,
  Crosshair, RotateCcw, GitFork, Sparkles, Shield,
  AlertTriangle, CalendarDays, Maximize2, Check, Minus,
  MessageCircle, Send, Clock, History, Eye, ExternalLink,
  type LucideIcon,
} from "lucide-react";

// ─── CSS ─────────────────────────────────────────────────────────────────────
const CSS = `
@keyframes igDash{from{stroke-dashoffset:80}to{stroke-dashoffset:0}}
@keyframes igRing{0%{r:97;opacity:.55}100%{r:200;opacity:0}}
@keyframes igRing2{0%{r:97;opacity:.3}100%{r:260;opacity:0}}
@keyframes igGlow{0%,100%{opacity:.7}50%{opacity:1}}
@keyframes igSpin{from{transform:rotate(0deg)}to{transform:rotate(360deg)}}
@keyframes igDot{0%,80%,100%{opacity:.2}40%{opacity:1}}
@keyframes igFloat{0%,100%{transform:translateY(0)}50%{transform:translateY(-4px)}}
`;
function Styles() {
  useEffect(() => {
    if (document.getElementById("ig3")) return;
    const s = Object.assign(document.createElement("style"), { id: "ig3", textContent: CSS });
    document.head.appendChild(s);
    return () => { try { document.head.removeChild(s); } catch {} };
  }, []);
  return null;
}

// ─── Types ────────────────────────────────────────────────────────────────────
interface RawNode { id:string; node_type:string; label:string; ticker?:string; description?:string; }
interface RawEdge { id:string; source:string; target:string; edge_type:string; weight:number; confidence:number; lag_days?:number; }
interface GData    { nodes:RawNode[]; edges:RawEdge[]; }
interface RippleImpact { node:RawNode; depth:number; impact_direction:"positive"|"negative"|"uncertain"; accumulated_weight:number; }
interface RippleResult { source:RawNode; change:string; total_impacted:number; impacts:RippleImpact[]; }
interface LivePrice { price:number; change:number; pct:number; positive:boolean; ticker:string; }
interface LiveData  { prices:Record<string,LivePrice>; topology:{node_count:number;edge_count:number}; updated_at:string; }
interface Snapshot { data:GData; centerId:string; }
interface VP { x:number; y:number; s:number; }
interface ConvoMsg { role:"user"|"assistant"; text:string; highlightIds?:string[]; confidence?:number; }

const TIMELINE=[
  {label:"Yesterday",key:"yesterday",offset:-1},
  {label:"Today",    key:"today",    offset:0 },
  {label:"Tomorrow", key:"tomorrow", offset:1 },
  {label:"+1 Week",  key:"1w",       offset:7 },
  {label:"+1 Month", key:"1m",       offset:30},
  {label:"+3 Months",key:"3m",       offset:90},
];

const HIST_SCENARIOS=[
  {id:"covid",    label:"COVID Crash",     sub:"Mar 2020",color:"#ef4444"},
  {id:"budget25", label:"Budget 2025",     sub:"Feb 2025",color:"#f59e0b"},
  {id:"ukraine",  label:"Ukraine War",     sub:"Feb 2022",color:"#a78bfa"},
  {id:"ratehike", label:"Rate Hike Cycle", sub:"2022–23", color:"#60a5fa"},
  {id:"election", label:"Election 2024",   sub:"Jun 2024",color:"#34d399"},
  {id:"tariff",   label:"Trump Tariffs",   sub:"Apr 2025",color:"#fb923c"},
];

const RANK: Record<string,number> = { event:4, policy:3, theme:2, commodity:1 };

// ─── Tokens ───────────────────────────────────────────────────────────────────
const NT: Record<string,{icon:LucideIcon;color:string;bg:string;border:string;label:string}> = {
  event:     {icon:Zap,            color:"#fbbf24",bg:"rgba(245,158,11,.13)",border:"rgba(245,158,11,.38)", label:"Event"    },
  policy:    {icon:Landmark,       color:"#a78bfa",bg:"rgba(139,92,246,.13)",border:"rgba(139,92,246,.38)", label:"Policy"   },
  sector:    {icon:BarChart2,      color:"#34d399",bg:"rgba(52,211,153,.11)",border:"rgba(52,211,153,.32)", label:"Sector"   },
  company:   {icon:Building2,      color:"#60a5fa",bg:"rgba(96,165,250,.11)",border:"rgba(96,165,250,.32)", label:"Company"  },
  macro:     {icon:Globe,          color:"#34d399",bg:"rgba(52,211,153,.11)",border:"rgba(52,211,153,.32)", label:"Macro"    },
  commodity: {icon:Package,        color:"#fb923c",bg:"rgba(249,115,22,.11)",border:"rgba(249,115,22,.3)",  label:"Commodity"},
  theme:     {icon:Lightbulb,      color:"#2dd4bf",bg:"rgba(45,212,191,.11)",border:"rgba(45,212,191,.3)",  label:"Theme"    },
  index:     {icon:TrendingUp,     color:"#67e8f9",bg:"rgba(103,232,249,.1)",border:"rgba(103,232,249,.3)", label:"Index"    },
  currency:  {icon:ArrowLeftRight, color:"#a3e635",bg:"rgba(163,230,53,.1)", border:"rgba(163,230,53,.28)", label:"Currency" },
  country:   {icon:Globe2,         color:"#818cf8",bg:"rgba(129,140,248,.1)",border:"rgba(129,140,248,.28)",label:"Country"  },
};
const RISK_OVR = { bg:"rgba(185,28,28,.18)",border:"rgba(239,68,68,.42)",color:"#fca5a5" };
function nt(type:string, risk=false) { const t=NT[type]??NT.macro; return risk?{...t,...RISK_OVR}:t; }

const ET: Record<string,{color:string;label:string;pos:boolean}> = {
  benefits:     {color:"#22c55e",label:"Benefits",     pos:true },
  supports:     {color:"#22c55e",label:"Supports",     pos:true },
  stimulates:   {color:"#22c55e",label:"Stimulates",   pos:true },
  boosts:       {color:"#22c55e",label:"Boosts",       pos:true },
  drives:       {color:"#22c55e",label:"Drives",       pos:true },
  enables:      {color:"#22c55e",label:"Enables",      pos:true },
  triggers:     {color:"#a78bfa",label:"Triggers",     pos:true },
  triggered_by: {color:"#a78bfa",label:"Triggered By", pos:true },
  influences:   {color:"#60a5fa",label:"Influences",   pos:true },
  related:      {color:"#60a5fa",label:"Related",      pos:true },
  hurts:        {color:"#ef4444",label:"Hurts",        pos:false},
  damages:      {color:"#ef4444",label:"Damages",      pos:false},
  pressures:    {color:"#ef4444",label:"Pressures",    pos:false},
  risk_factor:  {color:"#ef4444",label:"Risk Factor",  pos:false},
  supplies:     {color:"#fb923c",label:"Supplies",     pos:true },
  depends_on:   {color:"#60a5fa",label:"Depends On",   pos:true },
  competes_with:{color:"#475569",label:"Competes",     pos:false},
};
function et(type:string) { return ET[type]??{color:"#334155",label:type,pos:true}; }

const FILTERS = ["All","Events","Policies","Companies","Sectors","Themes","Macro","Commodities","Countries"];
const FMAP: Record<string,string[]> = {
  Events:["event"],Policies:["policy"],Companies:["company"],
  Sectors:["sector"],Themes:["theme"],
  Macro:["macro","index","currency"],Commodities:["commodity"],Countries:["country"],
};

const AI_STEPS = [
  { title:"Today's Market Catalyst",          desc:"This is the central event driving today's narrative. Every ripple starts here.",
    get:(n:RawNode[],e:RawEdge[],c:string)=>new Set([c]) },
  { title:"What Triggered This",              desc:"These macro conditions and policies set the stage for today's catalyst.",
    get:(_:RawNode[],e:RawEdge[],c:string)=>new Set([c,...e.filter(x=>x.target===c).map(x=>x.source)]) },
  { title:"Sectors Feeling the Impact",       desc:"Lower rates and policy shifts flow directly into these sectors.",
    get:(_:RawNode[],e:RawEdge[],c:string)=>new Set([c,...e.filter(x=>x.source===c&&x.weight>0).map(x=>x.target)]) },
  { title:"Companies at the Frontier",        desc:"These companies have the most direct earnings exposure to today's shift.",
    get:(n:RawNode[],e:RawEdge[],c:string)=>{const s=new Set([c]);e.filter(x=>x.source===c&&x.weight>0).forEach(x=>{s.add(x.target);e.filter(y=>y.source===x.target&&n.find(q=>q.id===y.target)?.node_type==="company").forEach(y=>s.add(y.target));});return s;} },
  { title:"Emerging Themes & Opportunities",  desc:"Structural themes activated by this event — may play out over weeks and months.",
    get:(_:RawNode[],e:RawEdge[],c:string)=>{const s=new Set([c]);const q=[c];while(q.length){const id=q.shift()!;e.filter(x=>x.source===id&&!s.has(x.target)&&x.weight>0.3).forEach(x=>{s.add(x.target);q.push(x.target);});}return s;} },
  { title:"Risks & Headwinds",                desc:"These nodes face negative pressure from today's event. Monitor for volatility.",
    get:(_:RawNode[],e:RawEdge[],c:string)=>{const s=new Set<string>();e.filter(x=>x.weight<-0.1).forEach(x=>{s.add(x.source);s.add(x.target);});return s;} },
];

// ─── Utilities ────────────────────────────────────────────────────────────────
function deg(nodes:RawNode[], edges:RawEdge[]): Record<string,number> {
  const d:Record<string,number>={};
  nodes.forEach(n=>d[n.id]=0);
  edges.forEach(e=>{d[e.source]=(d[e.source]??0)+1;d[e.target]=(d[e.target]??0)+1;});
  return d;
}
function pickCenter(nodes:RawNode[], edges:RawEdge[]): string {
  const d=deg(nodes,edges);
  const pool=nodes.filter(n=>(d[n.id]??0)>=2);
  const arr=pool.length?pool:nodes;
  return[...arr].sort((a,b)=>((RANK[b.node_type]??0)*12+(d[b.id]??0))-((RANK[a.node_type]??0)*12+(d[a.id]??0)))[0]?.id??"";
}
function bfs(startId:string, edges:RawEdge[]): Set<string> {
  const s=new Set([startId]);const q=[startId];
  while(q.length){const id=q.shift()!;edges.filter(e=>e.source===id&&!s.has(e.target)).forEach(e=>{s.add(e.target);q.push(e.target);});}
  edges.filter(e=>e.target===startId).forEach(e=>s.add(e.source));
  return s;
}
function impact(nodeId:string, nodes:RawNode[], edges:RawEdge[]): number {
  const d=deg(nodes,edges);const dv=d[nodeId]??0;
  const c=edges.filter(e=>e.source===nodeId||e.target===nodeId);
  const aw=dv>0?c.reduce((s,e)=>s+e.weight,0)/dv:0;
  return parseFloat(Math.min(10,Math.max(2,aw*8+Math.min(dv*.25,2))).toFixed(1));
}
function conf(nodeId:string, edges:RawEdge[]): number {
  const c=edges.filter(e=>e.source===nodeId||e.target===nodeId);
  return c.length?Math.round(60+c.reduce((s,e)=>s+e.confidence,0)/c.length*40):70;
}

// ─── Panel helpers ────────────────────────────────────────────────────────────
const _WHY: Record<string,string> = {
  event:    "n is a high-impact market event. Its ripple cascades directly into connected sectors and companies, often producing visible price moves within 1–5 trading sessions.",
  policy:   "n changes borrowing costs, regulatory conditions, or fiscal flows across the economy. Effects typically materialise in rate-sensitive sectors over 2–6 weeks.",
  sector:   "n aggregates the earnings exposure of dozens of companies to a shared macro theme. Sector moves often lead individual stock re-ratings by 5–15 days.",
  company:  "n sits at the intersection of multiple macro and sector trends. Its valuation acts as a real-time barometer for connected themes.",
  macro:    "n is a foundational macro variable. Shifts here propagate systematically through commodities, currencies, rates, and ultimately equity valuations.",
  commodity:"n price movements feed directly into corporate input costs and sector-level margin assumptions, with typical earnings revision lags of 1–2 quarters.",
  theme:    "n represents an emerging structural theme that typically unfolds over 6–18 months, compounding across every connected node in the graph.",
  index:    "n is a benchmark index capturing aggregate market sentiment. Moves here affect risk appetite, FII flows, and derivative positioning across the board.",
  currency: "n exchange-rate fluctuations affect import costs, export competitiveness, and FII equity flows — all simultaneously.",
  country:  "n macro environment shapes capital flows, trade balances, and cross-border risk appetite for Indian markets.",
};
function whyItMatters(node:RawNode, data:GData):string {
  const base=(_WHY[node.node_type]??"n has multiple market connections."  ).replace("n",node.label);
  const pos=data.edges.filter(e=>(e.source===node.id||e.target===node.id)&&e.weight>0.3).length;
  const neg=data.edges.filter(e=>(e.source===node.id||e.target===node.id)&&e.weight<-0.1).length;
  return `${base} Currently driving ${pos} positive connections and ${neg} risk vectors in this graph.`;
}
function keyTakeaway(node:RawNode, data:GData):string {
  const conns=data.edges.filter(e=>e.source===node.id||e.target===node.id);
  const top=[...conns].sort((a,b)=>Math.abs(b.weight)-Math.abs(a.weight))[0];
  if(!top)return `Monitor ${node.label} for directional conviction before taking a position.`;
  const othId=top.source===node.id?top.target:top.source;
  const oth=data.nodes.find(n=>n.id===othId);
  const verb=top.weight>0?"directly benefits":"pressures";
  return `${node.label} ${verb} ${oth?.label??"connected nodes"} — a ${et(top.edge_type).label.toLowerCase()} link of ${Math.abs(top.weight).toFixed(2)}.`;
}
const _HIST_REF: Record<string,string> = {
  event:    "During COVID (Mar 2020), event nodes of this type saw 15–25% sector moves within 3 sessions. Budget 2025 showed similar short-duration catalysts producing 8–12% re-ratings.",
  policy:   "The 2022–23 RBI rate hike cycle demonstrated policy nodes driving 20–35% re-rating in banking and NBFC sectors over 9 months.",
  sector:   "Sector nodes in the 2024 election rally appreciated 18–40% in the first 30 days post-result. Trump Tariff shock in Apr 2025 hit export sectors 10–22% in one week.",
  company:  "Q4 2023 earnings season showed company nodes with high impact scores outperforming by 2–4x their sector averages post-results.",
  macro:    "The Ukraine war (Feb 2022) showed macro nodes like this creating cascading 25–40% moves in energy, metals, and defence over 2 months.",
  commodity:"2022 commodity supercycle: nodes like this drove sector-wide earnings upgrades of 15–35% and stock re-ratings of 20–50%.",
  theme:    "The EV/green energy theme node activated in 2021–22 compounded 3–5x returns across connected companies over 18 months.",
};

// ─── Layout ──────────────────────────────────────────────────────────────────
const NW=190, NH=80, HG=55, VG=45;
function layout(nodes:RawNode[], edges:RawEdge[], cId:string): Map<string,{x:number;y:number}> {
  const pos=new Map<string,{x:number;y:number}>();
  pos.set(cId,{x:0,y:0});
  function row(ids:string[],y:number,xOff=0){
    const n=ids.length;if(!n)return;
    const tot=n*NW+(n-1)*HG;
    ids.forEach((id,i)=>{if(!pos.has(id))pos.set(id,{x:xOff-tot/2+i*(NW+HG)+NW/2,y});});
  }
  const toC=[...new Set(edges.filter(e=>e.target===cId&&e.source!==cId).map(e=>e.source))].filter(id=>nodes.some(n=>n.id===id));
  const frC=[...new Set(edges.filter(e=>e.source===cId&&e.target!==cId).map(e=>e.target))].filter(id=>nodes.some(n=>n.id===id));
  const upM=toC.filter(id=>{const n=nodes.find(n=>n.id===id);return n&&["macro","index","currency","commodity","country"].includes(n.node_type);});
  const upP=toC.filter(id=>{const n=nodes.find(n=>n.id===id);return n&&["policy"].includes(n.node_type);});
  const upO=toC.filter(id=>!upM.includes(id)&&!upP.includes(id));
  row([...upM,...upO],-480);row(upP,-240);
  const dS=frC.filter(id=>nodes.find(n=>n.id===id)?.node_type==="sector");
  const dC=frC.filter(id=>nodes.find(n=>n.id===id)?.node_type==="company");
  const dT=frC.filter(id=>nodes.find(n=>n.id===id)?.node_type==="theme");
  const dN=frC.filter(id=>{const e=edges.find(e=>e.source===cId&&e.target===id);return e&&e.weight<-0.05;});
  const dO=frC.filter(id=>!dS.includes(id)&&!dC.includes(id)&&!dT.includes(id)&&!dN.includes(id));
  const h=Math.ceil(dS.length/2);const ls=dS.slice(0,h);const rs=dS.slice(h);
  const SY=180;const SX=525;
  ls.forEach((id,i)=>{const y=(i-(ls.length-1)/2)*SY;if(!pos.has(id))pos.set(id,{x:-SX,y});});
  rs.forEach((id,i)=>{const y=(i-(rs.length-1)/2)*SY;if(!pos.has(id))pos.set(id,{x:SX,y});});
  const ac=[...dC,...dO];
  row(ac.slice(0,Math.ceil(ac.length/2)),290);
  if(ac.length>Math.ceil(ac.length/2))row(ac.slice(Math.ceil(ac.length/2)),290+NH+VG);
  const placed=new Set([cId,...toC,...frC]);
  const l2:string[]=[];
  dS.forEach(sId=>edges.filter(e=>e.source===sId&&!placed.has(e.target)&&nodes.some(n=>n.id===e.target)).forEach(e=>{if(!placed.has(e.target)){l2.push(e.target);placed.add(e.target);}}) );
  const maxCY=ac.length>Math.ceil(ac.length/2)?290+NH+VG:ac.length?290:0;
  if(l2.length){row(l2.slice(0,Math.ceil(l2.length/2)),maxCY+NH+VG+10);if(l2.length>Math.ceil(l2.length/2))row(l2.slice(Math.ceil(l2.length/2)),maxCY+2*(NH+VG)+10);}
  l2.forEach(id=>placed.add(id));
  const maxY=pos.size>1?Math.max(...[...pos.values()].map(p=>p.y)):0;
  row([...dT.filter(id=>!placed.has(id)),...dN.filter(id=>!placed.has(id))],maxY+NH+VG+30);
  const rem=nodes.filter(n=>!pos.has(n.id));
  if(rem.length){const my=Math.max(...[...pos.values()].map(p=>p.y));row(rem.map(n=>n.id),my+NH+VG+10);}
  return pos;
}

// ─── Edge path ────────────────────────────────────────────────────────────────
const CR=97;
function ports(pos:{x:number;y:number},isC:boolean){
  if(isC)return{top:{x:pos.x,y:pos.y-CR},bottom:{x:pos.x,y:pos.y+CR},left:{x:pos.x-CR,y:pos.y},right:{x:pos.x+CR,y:pos.y}};
  const hw=NW/2,hh=NH/2;
  return{top:{x:pos.x,y:pos.y-hh},bottom:{x:pos.x,y:pos.y+hh},left:{x:pos.x-hw,y:pos.y},right:{x:pos.x+hw,y:pos.y}};
}
function edgePath(sp:{x:number;y:number},tp:{x:number;y:number},sC:boolean,tC:boolean):{path:string;mx:number;my:number} {
  const sp2=ports(sp,sC);const tp2=ports(tp,tC);
  const dx=tp.x-sp.x;const dy=tp.y-sp.y;
  let sx:number,sy:number,tx:number,ty:number;
  if(Math.abs(dy)>Math.abs(dx)*0.6){
    if(dy>0){sx=sp2.bottom.x;sy=sp2.bottom.y;tx=tp2.top.x;ty=tp2.top.y;}
    else{sx=sp2.top.x;sy=sp2.top.y;tx=tp2.bottom.x;ty=tp2.bottom.y;}
  }else{
    if(dx>0){sx=sp2.right.x;sy=sp2.right.y;tx=tp2.left.x;ty=tp2.left.y;}
    else{sx=sp2.left.x;sy=sp2.left.y;tx=tp2.right.x;ty=tp2.right.y;}
  }
  const mx=(sx+tx)/2;const my=(sy+ty)/2;
  const absdy=Math.abs(ty-sy);const absdx=Math.abs(tx-sx);
  const path=absdy>absdx
    ?`M ${sx} ${sy} C ${sx} ${my} ${tx} ${my} ${tx} ${ty}`
    :`M ${sx} ${sy} C ${mx} ${sy} ${mx} ${ty} ${tx} ${ty}`;
  return{path,mx,my};
}

// ─── SVG Edges ────────────────────────────────────────────────────────────────
function Edges({nodes,edges,positions,centerId,hoveredId,selectedId,hlIds,rippleMap,filter}:{
  nodes:RawNode[];edges:RawEdge[];positions:Map<string,{x:number;y:number}>;
  centerId:string;hoveredId:string|null;selectedId:string|null;
  hlIds:Set<string>|null;rippleMap:Record<string,string>;filter:string;
}){
  const filterTypes=filter!=="All"?(FMAP[filter]??[]):null;
  return(
    <svg style={{position:"absolute",left:-2000,top:-2000,width:4000,height:4000,overflow:"visible",pointerEvents:"none"}} viewBox="-2000 -2000 4000 4000">
      <defs>
        {["#22c55e","#ef4444","#a78bfa","#60a5fa","#fb923c","#475569","#fbbf24"].map(c=>{
          const id="arr"+c.replace("#","");
          return(
            <marker key={id} id={id} markerWidth="7" markerHeight="7" refX="6" refY="3.5" orient="auto">
              <polygon points="0 0, 7 3.5, 0 7" fill={c} opacity=".9"/>
            </marker>
          );
        })}
      </defs>
      {edges.map(edge=>{
        const sp=positions.get(edge.source);const tp=positions.get(edge.target);
        if(!sp||!tp)return null;
        const sNode=nodes.find(n=>n.id===edge.source);const tNode=nodes.find(n=>n.id===edge.target);
        if(!sNode||!tNode)return null;
        if(filterTypes&&!filterTypes.includes(sNode.node_type)&&!filterTypes.includes(tNode.node_type))return null;
        const {path,mx,my}=edgePath(sp,tp,edge.source===centerId,edge.target===centerId);
        const eType=et(edge.edge_type);
        const color=eType.color;
        const arrId="arr"+color.replace("#","");
        const w=Math.abs(edge.weight);
        const sw=Math.max(1,w*2.6);
        const isHovConn=hoveredId&&(edge.source===hoveredId||edge.target===hoveredId);
        const isSelConn=selectedId&&(edge.source===selectedId||edge.target===selectedId);
        const isHl=hlIds?(hlIds.has(edge.source)&&hlIds.has(edge.target)):true;
        const isRippleConn=rippleMap[edge.source]||rippleMap[edge.target];
        const active=!!(isHovConn||isSelConn||isHl&&!hlIds||(hlIds&&isHl)||(Object.keys(rippleMap).length&&isRippleConn));
        const anyActive=!!(hoveredId||selectedId||hlIds||Object.keys(rippleMap).length);
        const opacity=anyActive?(active?.75:.05):.22;
        const word=w>=0.75?"Strong":w>=0.45?"Moderate":"Mild";
        return(
          <g key={edge.id}>
            {/* Glow */}
            <path d={path} fill="none" stroke={color} strokeWidth={sw+5} opacity={active?.07:.015} strokeLinecap="round"/>
            {/* Main line */}
            <path d={path} fill="none" stroke={color} strokeWidth={sw} opacity={opacity} strokeLinecap="round" markerEnd={`url(#${arrId})`} style={{transition:"opacity .3s"}}/>
            {/* Particle */}
            {active&&<path d={path} fill="none" stroke={color} strokeWidth={2} strokeDasharray="4 20" strokeLinecap="round" opacity={.9} style={{animation:"igDash 1.5s linear infinite"}}/>}
            {/* Label */}
            {active&&(
              <foreignObject x={mx-48} y={my-14} width={96} height={28} style={{overflow:"visible"}}>
                <div style={{background:"rgba(2,6,18,.92)",backdropFilter:"blur(8px)",border:`1px solid ${color}22`,borderRadius:5,padding:"2px 6px",textAlign:"center",pointerEvents:"none"}}>
                  <div style={{fontSize:7.5,fontWeight:700,color:"#334155",letterSpacing:".07em"}}>{eType.label.toUpperCase()}</div>
                  <div style={{fontSize:9.5,fontWeight:800,color}}>{eType.pos?"+":"−"}{w.toFixed(2)}</div>
                </div>
              </foreignObject>
            )}
          </g>
        );
      })}
    </svg>
  );
}

// ─── Center node ──────────────────────────────────────────────────────────────
// ─── Sparkline SVG ────────────────────────────────────────────────────────────
function Sparkline({values,color,width=60,height=18}:{values:number[];color:string;width?:number;height?:number}){
  if(values.length<2)return null;
  const mn=Math.min(...values);const mx=Math.max(...values);const range=mx-mn||1;
  const pts=values.map((v,i)=>`${(i/(values.length-1))*width},${height-((v-mn)/range)*height}`).join(" ");
  const last=values[values.length-1];
  return(
    <svg width={width} height={height} style={{overflow:"visible"}}>
      <polyline points={pts} fill="none" stroke={color} strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" opacity=".8"/>
      <circle cx={(values.length-1)/(values.length-1)*width} cy={height-((last-mn)/range)*height} r="2.5" fill={color}/>
    </svg>
  );
}

function CenterNode({node,pos,imp,cnf,dimmed,selected,livePrice,onClick}:{
  node:RawNode;pos:{x:number;y:number};imp:number;cnf:number;
  dimmed:boolean;selected:boolean;livePrice?:LivePrice;onClick:()=>void;
}){
  const m=nt(node.node_type);
  const hasPrice=!!(livePrice?.price);
  return(
    <motion.div initial={{opacity:0,scale:.7}} animate={{opacity:dimmed?.07:1,scale:1}} transition={{duration:.5,ease:[.16,1,.3,1]}}
      style={{position:"absolute",left:pos.x-97,top:pos.y-97,width:194,height:194,cursor:"pointer",zIndex:5}} onClick={onClick}>
      <svg style={{position:"absolute",inset:"-110px",width:414,height:414,overflow:"visible",pointerEvents:"none"}}>
        <circle cx="207" cy="207" r="97" fill="none" stroke="rgba(139,92,246,.22)" strokeWidth="1.5" style={{transformOrigin:"207px 207px",animation:"igRing 3s ease-out infinite"}}/>
        <circle cx="207" cy="207" r="97" fill="none" stroke="rgba(109,40,217,.12)" strokeWidth="1" style={{transformOrigin:"207px 207px",animation:"igRing2 3s ease-out 1.3s infinite"}}/>
      </svg>
      <motion.div whileHover={{scale:1.04}} style={{
        width:194,height:194,borderRadius:"50%",
        background:"radial-gradient(circle at 38% 32%,rgba(139,92,246,.65) 0%,rgba(79,46,175,.78) 45%,rgba(15,8,45,.97) 100%)",
        border:`1.5px solid rgba(167,139,250,${selected?.8:.55})`,
        boxShadow:`0 0 60px rgba(109,40,217,.55),0 0 130px rgba(109,40,217,.22),inset 0 1px 0 rgba(255,255,255,.1)`,
        display:"flex",flexDirection:"column",alignItems:"center",justifyContent:"center",gap:2,
        animation:"igGlow 3s ease-in-out infinite",
      }}>
        <m.icon size={22} color="#c4b5fd" strokeWidth={1.6} style={{marginBottom:2}}/>
        <div style={{fontSize:8,fontWeight:800,color:"#c4b5fd",letterSpacing:".09em",textTransform:"uppercase"}}>Primary Catalyst</div>
        <div style={{fontSize:12,fontWeight:900,color:"#f5f3ff",textAlign:"center",lineHeight:1.25,padding:"0 12px"}}>{node.label}</div>
        {hasPrice?(
          <>
            <div style={{fontSize:15,fontWeight:900,color:livePrice!.positive?"#4ade80":"#f87171",lineHeight:1,marginTop:2,fontVariantNumeric:"tabular-nums"}}>
              {livePrice!.price.toLocaleString("en-IN",{maximumFractionDigits:2})}
            </div>
            <div style={{fontSize:9.5,fontWeight:700,color:livePrice!.positive?"#4ade80":"#f87171"}}>
              {livePrice!.positive?"+":""}{livePrice!.pct.toFixed(2)}%
            </div>
          </>
        ):(
          <>
            <div style={{fontSize:22,fontWeight:900,color:"#fff",lineHeight:1,marginTop:2}}>{imp}</div>
            <div style={{fontSize:8,color:"#c4b5fd",fontWeight:600}}>Impact Score</div>
          </>
        )}
        <div style={{fontSize:8,color:"rgba(196,181,253,.55)",fontWeight:500}}>{cnf}% conf.</div>
      </motion.div>
    </motion.div>
  );
}

// ─── Intel node card ──────────────────────────────────────────────────────────
function IntelNode({node,pos,imp,cnf,dimmed,selected,rippleDir,livePrice,onHover,onHoverEnd,onClick}:{
  node:RawNode;pos:{x:number;y:number};imp:number;cnf:number;
  dimmed:boolean;selected:boolean;rippleDir?:string;livePrice?:LivePrice;
  onHover:()=>void;onHoverEnd:()=>void;onClick:()=>void;
}){
  const isRisk=rippleDir==="negative";
  const m=nt(node.node_type,isRisk);
  const fill=rippleDir==="positive"?"rgba(34,197,94,.15)":isRisk?"rgba(239,68,68,.17)":m.bg;
  const bdr=selected?m.color:rippleDir==="positive"?"#22c55e":isRisk?"#ef4444":m.border;
  const glow=selected?`0 0 0 1.5px ${m.color}55,0 0 24px ${m.color}22,0 6px 20px rgba(0,0,0,.65)`:`0 4px 18px rgba(0,0,0,.5)`;
  const hasPrice=!!(livePrice?.price);
  const priceColor=hasPrice?(livePrice!.positive?"#4ade80":"#f87171"):m.color;
  // Dynamic height: taller when we show price row
  const cardH=hasPrice?94:NH;
  return(
    <motion.div
      initial={{opacity:0,scale:.85,y:8}} animate={{opacity:dimmed?.07:1,scale:1,y:0}}
      transition={{duration:.45,ease:[.16,1,.3,1]}}
      whileHover={{scale:1.04,y:-3,boxShadow:`0 0 0 1.5px ${m.color}66,0 0 32px ${m.color}28,0 8px 28px rgba(0,0,0,.7)`}}
      style={{position:"absolute",left:pos.x-NW/2,top:pos.y-cardH/2,width:NW,cursor:"pointer",
        background:fill,border:`1px solid ${bdr}`,borderRadius:12,padding:"9px 11px",
        boxShadow:glow,backdropFilter:"blur(18px)",zIndex:4,
      }}
      onClick={onClick} onHoverStart={onHover} onHoverEnd={onHoverEnd}
    >
      <div style={{display:"flex",alignItems:"center",gap:8,marginBottom:hasPrice?4:5}}>
        <div style={{width:27,height:27,borderRadius:8,flexShrink:0,background:`${m.color}18`,border:`1px solid ${m.color}28`,display:"flex",alignItems:"center",justifyContent:"center"}}><m.icon size={13} color={m.color} strokeWidth={1.8}/></div>
        <div style={{flex:1,overflow:"hidden"}}>
          <div style={{fontSize:11.5,fontWeight:800,color:"#f1f5f9",lineHeight:1.2,overflow:"hidden",textOverflow:"ellipsis",whiteSpace:"nowrap"}}>{node.label}</div>
          <div style={{fontSize:8,fontWeight:700,color:m.color,textTransform:"uppercase",letterSpacing:".07em",marginTop:1}}>{m.label}{node.ticker&&<span style={{color:"#334155",marginLeft:4}}>{node.ticker.replace(/\.(NS|BO)$/,"")}</span>}</div>
        </div>
        {rippleDir&&<span style={{flexShrink:0}}>{rippleDir==="positive"?<TrendingUp size={11} color="#4ade80" strokeWidth={2}/>:rippleDir==="negative"?<TrendingDown size={11} color="#f87171" strokeWidth={2}/>:<Minus size={11} color="#94a3b8" strokeWidth={2}/>}</span>}
      </div>
      {hasPrice?(
        <div style={{display:"flex",alignItems:"center",gap:6}}>
          <div>
            <div style={{fontSize:13,fontWeight:900,color:priceColor,fontVariantNumeric:"tabular-nums",lineHeight:1}}>
              {livePrice!.price.toLocaleString("en-IN",{maximumFractionDigits:2})}
            </div>
            <div style={{fontSize:9,fontWeight:700,color:priceColor,marginTop:1}}>
              {livePrice!.positive?"+":""}{livePrice!.pct.toFixed(2)}% today
            </div>
          </div>
          <div style={{marginLeft:"auto",display:"flex",flexDirection:"column",alignItems:"flex-end",gap:2}}>
            <div style={{fontSize:8.5,fontWeight:600,color:"#334155"}}>Conf. {cnf}%</div>
          </div>
        </div>
      ):(
        <div style={{display:"flex",gap:4,alignItems:"center"}}>
          <span style={{fontSize:11,fontWeight:800,color:"#e2e8f0"}}>{imp}</span>
          <span style={{fontSize:8.5,color:"#334155",fontWeight:600}}>Impact</span>
          <span style={{marginLeft:"auto",fontSize:9.5,fontWeight:700,color:"#4b5563"}}>{cnf}%</span>
          <span style={{fontSize:8,color:"#334155"}}>Conf.</span>
        </div>
      )}
    </motion.div>
  );
}

// ─── Node panel ───────────────────────────────────────────────────────────────
function NodePanel({node,data,livePrice,onClose,onRipple,onMakeCenter}:{node:RawNode;data:GData;livePrice?:LivePrice;onClose:()=>void;onRipple:()=>void;onMakeCenter:()=>void}){
  const m=nt(node.node_type);
  const conns=data.edges.filter(e=>e.source===node.id||e.target===node.id);
  const d=conns.length;
  const[bc,bl]=d>=6?["#22c55e","High Impact"]:d>=3?["#f59e0b","Moderate Impact"]:["#64748b","Connected"];
  const imp=impact(node.id,data.nodes,data.edges);
  const cnf=conf(node.id,data.edges);
  const [sparkline,setSparkline]=useState<number[]>([]);
  useEffect(()=>{
    if(!node.ticker)return;
    fetch(`${API}/api/graph/live/sparkline/${encodeURIComponent(node.id)}`).then(r=>r.ok?r.json():{sparkline:[]}).then(d=>setSparkline(d.sparkline??[])).catch(()=>{});
  },[node.id,node.ticker]);

  const affectedCompanies=data.nodes.filter(n=>n.node_type==="company"&&data.edges.some(e=>(e.source===node.id&&e.target===n.id)||(e.source===n.id&&e.target===node.id)));
  const affectedSectors=data.nodes.filter(n=>n.node_type==="sector"&&data.edges.some(e=>(e.source===node.id&&e.target===n.id)||(e.source===n.id&&e.target===node.id)));
  const riskNodes=conns.filter(e=>e.weight<-0.1).map(e=>{const id=e.source===node.id?e.target:e.source;return data.nodes.find(n=>n.id===id);}).filter(Boolean).slice(0,3) as RawNode[];
  const topConns=[...conns].sort((a,b)=>Math.abs(b.weight)-Math.abs(a.weight)).slice(0,4);

  const sh:React.CSSProperties={fontSize:8,fontWeight:800,color:"#1e293b",textTransform:"uppercase",letterSpacing:".08em",marginBottom:7,display:"block"};
  const card:React.CSSProperties={padding:"8px 10px",borderRadius:9,background:"rgba(255,255,255,.025)",border:"1px solid rgba(255,255,255,.04)"};

  const [tab,setTab]=useState<"analysis"|"connections">("analysis");

  return(
    <motion.div initial={{opacity:0,x:24}} animate={{opacity:1,x:0}} exit={{opacity:0,x:24}}
      transition={{duration:.35,ease:[.16,1,.3,1]}}
      style={{position:"absolute",right:12,top:12,bottom:12,width:316,zIndex:30,
        background:"rgba(2,5,18,.98)",backdropFilter:"blur(24px)",
        border:"1px solid rgba(255,255,255,.07)",borderRadius:16,
        boxShadow:"0 24px 80px rgba(0,0,0,.8)",display:"flex",flexDirection:"column",fontFamily:"inherit",
      }}>

      {/* Header */}
      <div style={{padding:"12px 14px 10px",borderBottom:"1px solid rgba(255,255,255,.05)",flexShrink:0}}>
        <div style={{display:"flex",alignItems:"center",justifyContent:"space-between",marginBottom:9}}>
          <span style={{fontSize:8.5,fontWeight:800,color:m.color,letterSpacing:".1em",textTransform:"uppercase"}}>{m.label}</span>
          <div style={{display:"flex",gap:5}}>
            <motion.button whileHover={{scale:1.08}} whileTap={{scale:.92}} onClick={onMakeCenter} style={{padding:"3px 8px",borderRadius:7,border:"1px solid rgba(99,102,241,.28)",background:"rgba(99,102,241,.1)",color:"#818cf8",cursor:"pointer",fontSize:9,fontWeight:700,display:"flex",alignItems:"center",gap:3}}><Crosshair size={9} strokeWidth={2}/>Recenter</motion.button>
            <motion.button whileHover={{scale:1.08}} whileTap={{scale:.92}} onClick={onClose} style={{width:24,height:24,borderRadius:6,border:"1px solid rgba(255,255,255,.07)",background:"rgba(255,255,255,.04)",color:"#475569",cursor:"pointer",display:"flex",alignItems:"center",justifyContent:"center"}}><X size={12} strokeWidth={2}/></motion.button>
          </div>
        </div>
        <div style={{display:"flex",gap:9,alignItems:"flex-start"}}>
          <div style={{width:38,height:38,borderRadius:9,flexShrink:0,background:m.bg,border:`1.5px solid ${m.color}38`,display:"flex",alignItems:"center",justifyContent:"center"}}><m.icon size={17} color={m.color} strokeWidth={1.6}/></div>
          <div style={{flex:1,minWidth:0}}>
            <h2 style={{fontSize:14,fontWeight:900,color:"#f1f5f9",margin:"0 0 2px",lineHeight:1.25,overflow:"hidden",textOverflow:"ellipsis",whiteSpace:"nowrap"}}>{node.label}</h2>
            {node.ticker&&<span style={{fontSize:9.5,color:"#475569",fontWeight:600}}>{node.ticker}</span>}
          </div>
        </div>
        <div style={{marginTop:8,display:"flex",gap:5,flexWrap:"wrap"}}>
          <span style={{padding:"2px 8px",borderRadius:999,fontSize:8.5,fontWeight:700,background:`${bc}12`,color:bc,border:`1px solid ${bc}25`}}>{bl}</span>
          <span style={{padding:"2px 8px",borderRadius:999,fontSize:8.5,fontWeight:700,background:"rgba(255,255,255,.04)",color:"#475569",border:"1px solid rgba(255,255,255,.07)"}}>{d} connections</span>
        </div>
      </div>

      {/* Live price */}
      {livePrice&&(
        <div style={{padding:"9px 14px",borderBottom:"1px solid rgba(255,255,255,.05)",flexShrink:0}}>
          <div style={{display:"flex",alignItems:"center",gap:10,padding:"8px 10px",borderRadius:9,background:"rgba(255,255,255,.025)",border:"1px solid rgba(255,255,255,.04)"}}>
            <div>
              <div style={{fontSize:7,color:"#334155",fontWeight:700,textTransform:"uppercase",letterSpacing:".07em",marginBottom:2}}>Live Price</div>
              <div style={{fontSize:18,fontWeight:900,color:livePrice.positive?"#4ade80":"#f87171",fontVariantNumeric:"tabular-nums",lineHeight:1}}>{livePrice.price.toLocaleString("en-IN",{maximumFractionDigits:2})}</div>
              <div style={{fontSize:9,fontWeight:700,color:livePrice.positive?"#4ade80":"#f87171",marginTop:2}}>{livePrice.positive?"+":""}{livePrice.pct.toFixed(2)}% &nbsp;{livePrice.positive?"+":""}{livePrice.change.toFixed(2)}</div>
            </div>
            <div style={{marginLeft:"auto",flexShrink:0}}>
              <Sparkline values={sparkline.length>=2?sparkline:[livePrice.pct]} color={livePrice.positive?"#4ade80":"#f87171"} width={56} height={22}/>
            </div>
          </div>
        </div>
      )}

      {/* Tabs */}
      <div style={{display:"flex",padding:"8px 14px 0",gap:4,flexShrink:0}}>
        {(["analysis","connections"] as const).map(t=>(
          <button key={t} onClick={()=>setTab(t)} style={{flex:1,padding:"6px 0",borderRadius:8,fontSize:10,fontWeight:tab===t?700:600,cursor:"pointer",
            background:tab===t?"rgba(99,102,241,.18)":"transparent",
            border:tab===t?"1px solid rgba(99,102,241,.35)":"1px solid rgba(255,255,255,.06)",
            color:tab===t?"#a5b4fc":"#475569",transition:"all .15s",textTransform:"capitalize"}}>
            {t}
          </button>
        ))}
      </div>

      {/* Body */}
      <div style={{flex:1,overflowY:"auto",padding:"10px 14px",display:"flex",flexDirection:"column",gap:11}}>

        {/* Metrics row */}
        <div style={{display:"flex",gap:6}}>
          {[["Impact",`${imp}/10`,"#22c55e"],["Confidence",`${cnf}%`,"#818cf8"]].map(([k,v,c])=>(
            <div key={k} style={{flex:1,...card}}>
              <div style={{fontSize:7,color:"#1e293b",fontWeight:700,marginBottom:3,textTransform:"uppercase",letterSpacing:".07em"}}>{k}</div>
              <div style={{fontSize:17,fontWeight:900,color:c as string,lineHeight:1}}>{v}</div>
              {k==="Confidence"&&<div style={{height:2.5,borderRadius:999,background:"rgba(255,255,255,.06)",marginTop:5,overflow:"hidden"}}><motion.div initial={{width:0}} animate={{width:`${cnf}%`}} transition={{duration:.9,ease:"easeOut"}} style={{height:"100%",borderRadius:999,background:"#818cf8"}}/></div>}
            </div>
          ))}
        </div>

        {tab==="analysis"&&<>
          {/* Why This Matters */}
          <div>
            <span style={sh}>Why This Matters</span>
            <p style={{...card,fontSize:11.5,color:"#64748b",lineHeight:1.7,margin:0}}>{whyItMatters(node,data)}</p>
          </div>

          {/* Key Takeaway */}
          <div>
            <span style={sh}>Key Takeaway</span>
            <div style={{...card,display:"flex",gap:8,alignItems:"flex-start"}}>
              <Sparkles size={12} color="#f59e0b" strokeWidth={1.8} style={{flexShrink:0,marginTop:1}}/>
              <p style={{fontSize:11.5,color:"#e2e8f0",lineHeight:1.65,margin:0,fontWeight:600}}>{keyTakeaway(node,data)}</p>
            </div>
          </div>

          {/* Affected */}
          {(affectedSectors.length>0||affectedCompanies.length>0)&&(
            <div>
              <span style={sh}>Affected</span>
              <div style={{display:"flex",flexDirection:"column",gap:4}}>
                {affectedSectors.slice(0,3).map(n=>{const nm=nt(n.node_type);return(
                  <div key={n.id} style={{...card,display:"flex",alignItems:"center",gap:7}}>
                    <nm.icon size={11} color={nm.color} strokeWidth={1.8}/>
                    <span style={{fontSize:11,color:"#cbd5e1",fontWeight:600,flex:1,overflow:"hidden",textOverflow:"ellipsis",whiteSpace:"nowrap"}}>{n.label}</span>
                    <span style={{fontSize:8.5,color:nm.color,fontWeight:700,flexShrink:0}}>Sector</span>
                  </div>
                );})}
                {affectedCompanies.slice(0,3).map(n=>{const nm=nt(n.node_type);return(
                  <div key={n.id} style={{...card,display:"flex",alignItems:"center",gap:7}}>
                    <nm.icon size={11} color={nm.color} strokeWidth={1.8}/>
                    <span style={{fontSize:11,color:"#cbd5e1",fontWeight:600,flex:1,overflow:"hidden",textOverflow:"ellipsis",whiteSpace:"nowrap"}}>{n.label}</span>
                    <span style={{fontSize:8.5,color:nm.color,fontWeight:700,flexShrink:0}}>Company</span>
                  </div>
                );})}
              </div>
            </div>
          )}

          {/* Historical Example */}
          <div>
            <span style={sh}>Historical Reference</span>
            <div style={{...card,display:"flex",gap:8,alignItems:"flex-start"}}>
              <History size={12} color="#60a5fa" strokeWidth={1.8} style={{flexShrink:0,marginTop:1}}/>
              <p style={{fontSize:11,color:"#64748b",lineHeight:1.65,margin:0}}>{_HIST_REF[node.node_type]??"No historical reference available for this node type."}</p>
            </div>
          </div>

          {/* What to Watch */}
          {riskNodes.length>0&&(
            <div>
              <span style={sh}>What to Watch</span>
              <div style={{display:"flex",flexDirection:"column",gap:3}}>
                {riskNodes.map(n=>{const nm=nt(n.node_type);const e=conns.find(e=>(e.source===node.id&&e.target===n.id)||(e.source===n.id&&e.target===node.id));return(
                  <div key={n.id} style={{...card,display:"flex",alignItems:"center",gap:7,borderColor:"rgba(239,68,68,.15)"}}>
                    <AlertTriangle size={11} color="#f87171" strokeWidth={1.8}/>
                    <span style={{fontSize:11,color:"#fca5a5",fontWeight:600,flex:1,overflow:"hidden",textOverflow:"ellipsis",whiteSpace:"nowrap"}}>{n.label}</span>
                    <span style={{fontSize:8.5,color:"#ef4444",fontWeight:800,flexShrink:0}}>{e?Math.abs(e.weight).toFixed(2):""}</span>
                  </div>
                );})}
              </div>
            </div>
          )}
        </>}

        {tab==="connections"&&<>
          {topConns.map(edge=>{
            const oid=edge.source===node.id?edge.target:edge.source;
            const other=data.nodes.find(n=>n.id===oid);if(!other)return null;
            const em=et(edge.edge_type);const nm=nt(other.node_type);const w=Math.abs(edge.weight);
            const dir=edge.source===node.id?"out":"in";
            return(
              <div key={edge.id} style={{...card}}>
                <div style={{display:"flex",alignItems:"center",gap:7,marginBottom:5}}>
                  <nm.icon size={12} color={nm.color} strokeWidth={1.8}/>
                  <span style={{flex:1,fontSize:11.5,color:"#e2e8f0",fontWeight:700,overflow:"hidden",textOverflow:"ellipsis",whiteSpace:"nowrap"}}>{other.label}</span>
                  <span style={{fontSize:8,color:"#334155",flexShrink:0,textTransform:"uppercase",letterSpacing:".05em"}}>{dir==="out"?"→":"←"}</span>
                </div>
                <div style={{display:"flex",alignItems:"center",gap:8}}>
                  <span style={{padding:"2px 7px",borderRadius:999,fontSize:8.5,fontWeight:700,background:`${em.color}12`,color:em.color,border:`1px solid ${em.color}25`}}>
                    {em.label} {em.pos?`+${w.toFixed(2)}`:`−${w.toFixed(2)}`}
                  </span>
                  <span style={{fontSize:8,color:"#334155",marginLeft:"auto"}}>{w>=0.7?"Strong":w>=0.45?"Moderate":"Mild"}</span>
                </div>
              </div>
            );
          })}
          {d>4&&<p style={{fontSize:11,color:"#475569",textAlign:"center"}}>{d-4} more connections — Recenter to explore</p>}
        </>}
      </div>

      {/* Footer */}
      <div style={{padding:"10px 14px",borderTop:"1px solid rgba(255,255,255,.05)",flexShrink:0,display:"flex",flexDirection:"column",gap:5}}>
        <motion.button whileHover={{scale:1.02}} whileTap={{scale:.97}} onClick={onRipple}
          style={{width:"100%",padding:"10px 0",borderRadius:9,fontSize:11.5,fontWeight:800,cursor:"pointer",background:"linear-gradient(135deg,#6d28d9,#4f46e5)",border:"none",color:"#fff",display:"flex",alignItems:"center",justifyContent:"center",gap:6,boxShadow:"0 4px 18px rgba(109,40,217,.38)"}}>
          <GitFork size={12} strokeWidth={2}/> Trace Ripple
        </motion.button>
        <a href={`/intelligence/${encodeURIComponent(node.id)}`}
          style={{width:"100%",padding:"8px 0",borderRadius:9,fontSize:10.5,fontWeight:600,cursor:"pointer",background:"rgba(255,255,255,.03)",border:"1px solid rgba(255,255,255,.07)",color:"#475569",display:"flex",alignItems:"center",justifyContent:"center",gap:5,textDecoration:"none"}}>
          <ExternalLink size={10} strokeWidth={1.8}/> Open Full Analysis
        </a>
      </div>
    </motion.div>
  );
}

// ─── AI Explain ───────────────────────────────────────────────────────────────
function AIExplain({step,onNext,onPrev,onClose}:{step:number;onNext:()=>void;onPrev:()=>void;onClose:()=>void}){
  const s=AI_STEPS[step];const tot=AI_STEPS.length;
  return(
    <motion.div initial={{opacity:0,y:10}} animate={{opacity:1,y:0}} exit={{opacity:0,y:10}} transition={{duration:.3}}
      style={{position:"absolute",left:54,bottom:14,width:292,zIndex:40,background:"rgba(2,5,18,.97)",backdropFilter:"blur(20px)",border:"1px solid rgba(99,102,241,.3)",borderRadius:14,padding:"14px 16px"}}>
      <div style={{display:"flex",alignItems:"center",justifyContent:"space-between",marginBottom:7}}>
        <div style={{display:"flex",alignItems:"center",gap:6}}>
          <div style={{width:7,height:7,borderRadius:"50%",background:"#818cf8",animation:"igGlow 1.5s ease infinite"}}/>
          <span style={{fontSize:8.5,fontWeight:800,color:"#818cf8",letterSpacing:".1em"}}>AI EXPLAIN · {step+1}/{tot}</span>
        </div>
        <button onClick={onClose} style={{background:"none",border:"none",color:"#475569",cursor:"pointer",padding:0,display:"flex"}}><X size={13} strokeWidth={2}/></button>
      </div>
      <div style={{display:"flex",gap:3,marginBottom:10}}>
        {Array.from({length:tot}).map((_,i)=><motion.div key={i} style={{flex:1,height:2.5,borderRadius:999,background:i<=step?"#6366f1":"rgba(255,255,255,.07)"}} animate={{background:i<=step?"#6366f1":"rgba(255,255,255,.07)"}} transition={{duration:.3}}/>)}
      </div>
      <h3 style={{fontSize:13.5,fontWeight:800,color:"#f1f5f9",margin:"0 0 5px"}}>{s.title}</h3>
      <p style={{fontSize:11.5,color:"#475569",lineHeight:1.65,margin:"0 0 12px"}}>{s.desc}</p>
      <div style={{display:"flex",gap:7}}>
        <motion.button whileHover={{scale:1.04}} whileTap={{scale:.96}} onClick={onPrev} disabled={step===0} style={{flex:1,padding:"7px 0",borderRadius:8,fontSize:10.5,fontWeight:700,cursor:step===0?"default":"pointer",background:"rgba(255,255,255,.04)",border:"1px solid rgba(255,255,255,.07)",color:step===0?"#1e293b":"#64748b",opacity:step===0?.35:1,display:"flex",alignItems:"center",justifyContent:"center",gap:4}}><ChevronLeft size={13} strokeWidth={2}/> Back</motion.button>
        <motion.button whileHover={{scale:1.04}} whileTap={{scale:.96}} onClick={onNext} style={{flex:1,padding:"7px 0",borderRadius:8,fontSize:10.5,fontWeight:700,cursor:"pointer",background:"rgba(99,102,241,.2)",border:"1px solid rgba(99,102,241,.38)",color:"#a5b4fc",display:"flex",alignItems:"center",justifyContent:"center",gap:4}}>{step===tot-1?<><Check size={13} strokeWidth={2}/> Done</>:<>Next <ChevronRight size={13} strokeWidth={2}/></>}</motion.button>
      </div>
    </motion.div>
  );
}

// ─── Ripple modal ─────────────────────────────────────────────────────────────
function RippleModal({node,onRun,onClose,loading}:{node:RawNode;onRun:(c:"rise"|"fall"|"shock")=>void;onClose:()=>void;loading:boolean}){
  const m=nt(node.node_type);
  const scenarios=[
    {icon:<TrendingUp size={13} strokeWidth={2}/>,l:"Rise / Increase",c:"rise" as const,col:"#22c55e"},
    {icon:<TrendingDown size={13} strokeWidth={2}/>,l:"Fall / Decrease",c:"fall" as const,col:"#ef4444"},
    {icon:<Zap size={13} strokeWidth={2}/>,l:"Major Shock",c:"shock" as const,col:"#f59e0b"},
  ];
  return(
    <motion.div initial={{opacity:0}} animate={{opacity:1}} exit={{opacity:0}}
      style={{position:"fixed",inset:0,zIndex:100,display:"flex",alignItems:"center",justifyContent:"center",background:"rgba(0,0,0,.72)",backdropFilter:"blur(6px)"}}
      onClick={onClose}>
      <motion.div initial={{scale:.9,y:10}} animate={{scale:1,y:0}} exit={{scale:.9,y:10}} transition={{duration:.3,ease:[.16,1,.3,1]}}
        style={{background:"rgba(4,8,24,.98)",border:"1px solid rgba(255,255,255,.08)",borderRadius:16,padding:24,width:360,boxShadow:"0 32px 80px rgba(0,0,0,.8)"}}
        onClick={e=>e.stopPropagation()}>
        <div style={{display:"flex",alignItems:"center",gap:10,marginBottom:16}}>
          <div style={{width:36,height:36,borderRadius:9,background:m.bg,border:`1px solid ${m.color}35`,display:"flex",alignItems:"center",justifyContent:"center"}}><m.icon size={18} color={m.color} strokeWidth={1.6}/></div>
          <div><div style={{fontSize:12,fontWeight:800,color:"#f1f5f9"}}>Trace Ripple</div><div style={{fontSize:10.5,color:"#475569"}}>{node.label}</div></div>
          <button onClick={onClose} style={{marginLeft:"auto",background:"none",border:"none",color:"#475569",cursor:"pointer",display:"flex"}}><X size={16} strokeWidth={2}/></button>
        </div>
        <p style={{fontSize:11.5,color:"#475569",lineHeight:1.65,margin:"0 0 16px"}}>Simulate a change in <strong style={{color:"#94a3b8"}}>{node.label}</strong> and trace the downstream ripple.</p>
        <div style={{display:"flex",flexDirection:"column",gap:8}}>
          {scenarios.map(s=><motion.button key={s.c} whileHover={{scale:1.02}} whileTap={{scale:.98}} onClick={()=>onRun(s.c)} disabled={loading}
            style={{padding:"12px 14px",borderRadius:10,fontSize:12,fontWeight:700,cursor:"pointer",display:"flex",alignItems:"center",justifyContent:"space-between",
              background:`${s.col}10`,border:`1px solid ${s.col}30`,color:s.col,opacity:loading?.5:1}}>
            <span style={{display:"flex",alignItems:"center",gap:6,color:s.col}}>{s.icon} {s.l}</span>{loading&&<span style={{width:12,height:12,border:"1.5px solid rgba(255,255,255,.2)",borderTopColor:"#fff",borderRadius:"50%",display:"inline-block",animation:"igSpin .7s linear infinite"}}/>}
          </motion.button>)}
        </div>
      </motion.div>
    </motion.div>
  );
}

// ─── Bottom bar ───────────────────────────────────────────────────────────────
function BottomBar({data,centerId,liveData,lastUpdated}:{data:GData;centerId:string;liveData:LiveData|null;lastUpdated:string|null}){
  const{nodes,edges}=data;
  const center=nodes.find(n=>n.id===centerId);
  const sectors=nodes.filter(n=>n.node_type==="sector");
  const companies=nodes.filter(n=>n.node_type==="company");
  const risks=edges.filter(e=>e.weight<-0.1);
  const opps=edges.filter(e=>e.weight>0.6);
  const topS=[...sectors].sort((a,b)=>impact(b.id,nodes,edges)-impact(a.id,nodes,edges))[0];
  const topC=[...companies].sort((a,b)=>impact(b.id,nodes,edges)-impact(a.id,nodes,edges))[0];
  const avgConf=edges.length?Math.round(edges.reduce((s,e)=>s+e.confidence,0)/edges.length*100):0;
  // Best opportunity: highest positive-weight edge target
  const bestOppEdge=[...edges].filter(e=>e.weight>0.5).sort((a,b)=>b.weight-a.weight)[0];
  const bestOpp=bestOppEdge?nodes.find(n=>n.id===bestOppEdge.target):null;
  // Highest risk: most negative weight edge target
  const highRiskEdge=[...edges].filter(e=>e.weight<-0.1).sort((a,b)=>a.weight-b.weight)[0];
  const highRisk=highRiskEdge?nodes.find(n=>n.id===highRiskEdge.target):null;
  // Ripple reach = nodes reachable from center via positive edges
  const reach=edges.filter(e=>e.source===centerId&&e.weight>0).length;

  const updStr=lastUpdated?new Date(lastUpdated).toLocaleTimeString("en-IN",{hour:"2-digit",minute:"2-digit",second:"2-digit"}):"—";
  const priceCount=liveData?Object.keys(liveData.prices).length:0;

  const items:{lb:string;icon:React.ReactNode;v:string;sub:string;accent:string}[]=[
    {lb:"TODAY'S STORY",     icon:<CalendarDays  size={14} color="#a78bfa" strokeWidth={1.6}/>,v:center?.label??"—",               sub:"Primary catalyst",   accent:"#a78bfa"},
    {lb:"BEST OPPORTUNITY",  icon:<TrendingUp    size={14} color="#22c55e" strokeWidth={1.6}/>,v:bestOpp?.label??"—",              sub:bestOppEdge?`+${bestOppEdge.weight.toFixed(2)} weight`:"Strong link", accent:"#22c55e"},
    {lb:"HIGHEST RISK",      icon:<AlertTriangle size={14} color="#ef4444" strokeWidth={1.6}/>,v:highRisk?.label??"—",             sub:highRiskEdge?`${highRiskEdge.weight.toFixed(2)} weight`:"Watch closely",accent:"#ef4444"},
    {lb:"SECTOR IN FOCUS",   icon:<BarChart2     size={14} color="#34d399" strokeWidth={1.6}/>,v:topS?.label??"—",                 sub:topS?`${impact(topS.id,nodes,edges)} impact`:"",  accent:"#34d399"},
    {lb:"COMPANY IN FOCUS",  icon:<Building2     size={14} color="#60a5fa" strokeWidth={1.6}/>,v:topC?.label??"—",                 sub:topC?`${impact(topC.id,nodes,edges)} impact`:"",  accent:"#60a5fa"},
    {lb:"RIPPLE REACH",      icon:<GitFork       size={14} color="#94a3b8" strokeWidth={1.6}/>,v:`${reach} nodes`,                 sub:`${risks.length} risks · ${opps.length} opps`,   accent:"#94a3b8"},
    {lb:"AI CONFIDENCE",     icon:<Shield        size={14} color="#818cf8" strokeWidth={1.6}/>,v:`${avgConf}%`,                    sub:`${priceCount} live prices`,                      accent:"#818cf8"},
    {lb:"LAST UPDATED",      icon:<Clock         size={14} color="#475569" strokeWidth={1.6}/>,v:updStr,                           sub:"Prices every 30s",                               accent:"#475569"},
  ];
  return(
    <div style={{height:55,flexShrink:0,borderTop:"1px solid rgba(255,255,255,.05)",background:"rgba(1,3,10,.99)",display:"flex",alignItems:"stretch",padding:"0 8px",overflowX:"auto",gap:0}}>
      {items.map((item,i)=>(
        <div key={item.lb} style={{display:"flex",alignItems:"center",gap:7,padding:"0 11px",borderRight:i<items.length-1?"1px solid rgba(255,255,255,.04)":"none",flexShrink:0,minWidth:0}}>
          <div style={{width:27,height:27,borderRadius:7,background:`${item.accent}0d`,border:`1px solid ${item.accent}18`,display:"flex",alignItems:"center",justifyContent:"center",flexShrink:0}}>{item.icon}</div>
          <div style={{minWidth:0}}>
            <div style={{fontSize:7,fontWeight:800,color:"#1e293b",letterSpacing:".08em",textTransform:"uppercase",marginBottom:1.5}}>{item.lb}</div>
            <div style={{fontSize:11.5,fontWeight:800,color:"#94a3b8",whiteSpace:"nowrap",overflow:"hidden",textOverflow:"ellipsis",maxWidth:120}}>{item.v}</div>
            {item.sub&&<div style={{fontSize:8.5,color:"#1e293b",fontWeight:600,marginTop:1,whiteSpace:"nowrap"}}>{item.sub}</div>}
          </div>
        </div>
      ))}
    </div>
  );
}

// ─── Minimap ──────────────────────────────────────────────────────────────────
function Minimap({nodes,positions,centerId,vp,cW,cH}:{nodes:RawNode[];positions:Map<string,{x:number;y:number}>;centerId:string;vp:VP;cW:number;cH:number}){
  const W=120,H=80;
  if(!positions.size)return null;
  const xs=[...positions.values()].map(p=>p.x);const ys=[...positions.values()].map(p=>p.y);
  const minX=Math.min(...xs)-120;const maxX=Math.max(...xs)+120;
  const minY=Math.min(...ys)-80;const maxY=Math.max(...ys)+80;
  const gW=maxX-minX;const gH=maxY-minY;
  const sc=Math.min(W/gW,H/gH);
  function toM(x:number,y:number){return{x:(x-minX)*sc,y:(y-minY)*sc};}
  // Viewport rect in graph space
  const vpMinX=(-vp.x)/vp.s;const vpMinY=(-vp.y)/vp.s;
  const vpMaxX=(cW-vp.x)/vp.s;const vpMaxY=(cH-vp.y)/vp.s;
  const vr={x:(vpMinX-minX)*sc,y:(vpMinY-minY)*sc,w:(vpMaxX-vpMinX)*sc,h:(vpMaxY-vpMinY)*sc};
  return(
    <div style={{position:"absolute",left:14,bottom:14,width:W,height:H,background:"rgba(2,6,18,.94)",border:"1px solid rgba(255,255,255,.07)",borderRadius:10,overflow:"hidden",zIndex:20}}>
      <svg width={W} height={H}>
        {[...positions.entries()].map(([id,pos])=>{
          const mp=toM(pos.x,pos.y);const isC=id===centerId;const nd=nodes.find(n=>n.id===id);
          const c=isC?"#a78bfa":(NT[nd?.node_type??""]?.color??"#334155");
          return<circle key={id} cx={mp.x} cy={mp.y} r={isC?4:2.5} fill={c} opacity={isC?1:.7}/>;
        })}
        <rect x={Math.max(0,vr.x)} y={Math.max(0,vr.y)} width={Math.min(W,vr.w)} height={Math.min(H,vr.h)} fill="rgba(99,102,241,.08)" stroke="rgba(99,102,241,.35)" strokeWidth="1" rx="2"/>
      </svg>
    </div>
  );
}

// ─── Zoom controls ────────────────────────────────────────────────────────────
function ZoomCtrls({onZoomIn,onZoomOut,onFit,onReset}:{onZoomIn:()=>void;onZoomOut:()=>void;onFit:()=>void;onReset:()=>void}){
  const btn:React.CSSProperties={width:32,height:32,borderRadius:9,background:"rgba(2,8,22,.9)",border:"1px solid rgba(255,255,255,.08)",cursor:"pointer",color:"#64748b",display:"flex",alignItems:"center",justifyContent:"center",padding:0,backdropFilter:"blur(8px)",fontSize:16};
  return(
    <div style={{position:"absolute",left:14,top:14,display:"flex",flexDirection:"column",gap:4,zIndex:20}}>
      <motion.button whileHover={{scale:1.08}} whileTap={{scale:.92}} style={btn} onClick={onZoomIn}>+</motion.button>
      <motion.button whileHover={{scale:1.08}} whileTap={{scale:.92}} style={btn} onClick={onZoomOut}>−</motion.button>
      <div style={{height:1,background:"rgba(255,255,255,.05)",margin:"2px 0"}}/>
      <motion.button whileHover={{scale:1.08}} whileTap={{scale:.92}} style={btn} onClick={onFit}><Maximize2 size={13} strokeWidth={1.8}/></motion.button>
      <motion.button whileHover={{scale:1.08}} whileTap={{scale:.92}} style={btn} onClick={onReset}><Crosshair size={13} strokeWidth={1.8}/></motion.button>
    </div>
  );
}

// ─── Timeline Slider ─────────────────────────────────────────────────────────
function TimelineSlider({idx,onChange}:{idx:number;onChange:(i:number)=>void}){
  return(
    <div style={{display:"flex",alignItems:"center",gap:3,background:"rgba(255,255,255,.03)",border:"1px solid rgba(255,255,255,.06)",borderRadius:999,padding:"3px 5px"}}>
      <Clock size={10} color="#334155" strokeWidth={1.8} style={{marginLeft:4,flexShrink:0}}/>
      {TIMELINE.map((t,i)=>(
        <button key={t.key} onClick={()=>onChange(i)}
          style={{padding:"3px 9px",borderRadius:999,fontSize:9.5,fontWeight:i===idx?700:500,cursor:"pointer",whiteSpace:"nowrap",
            background:i===idx?"rgba(99,102,241,.25)":"transparent",
            border:i===idx?"1px solid rgba(99,102,241,.45)":"1px solid transparent",
            color:i===idx?"#a5b4fc":i===1?"#64748b":"#334155",transition:"all .15s"}}>
          {t.label}
        </button>
      ))}
    </div>
  );
}

// ─── AI Chat Panel ────────────────────────────────────────────────────────────
function AIChatPanel({open,onClose,messages,loading,onSend,gData,centerId,selectedId}:{
  open:boolean;onClose:()=>void;messages:ConvoMsg[];loading:boolean;
  onSend:(q:string)=>void;gData:GData;centerId:string;selectedId:string|null;
}){
  const [input,setInput]=useState("");
  const endRef=useRef<HTMLDivElement>(null);
  useEffect(()=>{endRef.current?.scrollIntoView({behavior:"smooth"});},[messages]);
  const submit=()=>{if(!input.trim()||loading)return;onSend(input.trim());setInput("");};
  const STARTERS=["Why is the center node significant?","What's the biggest risk in this graph?","Which companies benefit most?","What would happen if oil prices spike?"];
  return(
    <AnimatePresence>
      {open&&(
        <motion.div initial={{opacity:0,y:40}} animate={{opacity:1,y:0}} exit={{opacity:0,y:40}}
          transition={{duration:.3,ease:[.16,1,.3,1]}}
          style={{position:"absolute",right:12,bottom:70,width:320,zIndex:40,
            background:"rgba(2,5,18,.98)",backdropFilter:"blur(24px)",
            border:"1px solid rgba(99,102,241,.2)",borderRadius:14,
            boxShadow:"0 20px 60px rgba(0,0,0,.8)",display:"flex",flexDirection:"column",
            maxHeight:440,fontFamily:"inherit"}}>
          {/* Header */}
          <div style={{padding:"10px 14px",borderBottom:"1px solid rgba(255,255,255,.05)",display:"flex",alignItems:"center",justifyContent:"space-between",flexShrink:0}}>
            <div style={{display:"flex",alignItems:"center",gap:7}}>
              <div style={{width:6,height:6,borderRadius:"50%",background:"#818cf8",animation:"igGlow 1.5s ease infinite"}}/>
              <span style={{fontSize:10,fontWeight:800,color:"#818cf8",letterSpacing:".08em"}}>AI GRAPH ANALYST</span>
            </div>
            <button onClick={onClose} style={{background:"none",border:"none",color:"#475569",cursor:"pointer",display:"flex"}}><X size={13} strokeWidth={2}/></button>
          </div>
          {/* Messages */}
          <div style={{flex:1,overflowY:"auto",padding:"10px 12px",display:"flex",flexDirection:"column",gap:8}}>
            {messages.length===0&&(
              <div style={{display:"flex",flexDirection:"column",gap:5}}>
                <p style={{fontSize:11,color:"#334155",margin:"0 0 6px",textAlign:"center"}}>Ask anything about this graph</p>
                {STARTERS.map(s=>(
                  <button key={s} onClick={()=>onSend(s)} style={{padding:"6px 10px",borderRadius:8,fontSize:10.5,color:"#64748b",background:"rgba(255,255,255,.03)",border:"1px solid rgba(255,255,255,.06)",cursor:"pointer",textAlign:"left"}}>{s}</button>
                ))}
              </div>
            )}
            {messages.map((msg,i)=>(
              <div key={i} style={{display:"flex",flexDirection:"column",alignItems:msg.role==="user"?"flex-end":"flex-start"}}>
                <div style={{maxWidth:"88%",padding:"8px 11px",borderRadius:10,fontSize:11.5,lineHeight:1.65,
                  background:msg.role==="user"?"rgba(99,102,241,.2)":"rgba(255,255,255,.04)",
                  border:msg.role==="user"?"1px solid rgba(99,102,241,.3)":"1px solid rgba(255,255,255,.06)",
                  color:msg.role==="user"?"#c7d2fe":"#cbd5e1"}}>
                  {msg.text}
                </div>
                {msg.confidence!==undefined&&msg.role==="assistant"&&(
                  <span style={{fontSize:8.5,color:"#334155",marginTop:2,marginLeft:2}}>Confidence: {msg.confidence}%</span>
                )}
              </div>
            ))}
            {loading&&(
              <div style={{display:"flex",gap:4,alignItems:"center",padding:"6px 10px"}}>
                {[0,1,2].map(i=><span key={i} style={{width:5,height:5,borderRadius:"50%",background:"#475569",display:"inline-block",animation:`igDot 1.2s ease ${i*.2}s infinite`}}/>)}
              </div>
            )}
            <div ref={endRef}/>
          </div>
          {/* Input */}
          <div style={{padding:"8px 10px",borderTop:"1px solid rgba(255,255,255,.05)",display:"flex",gap:6,flexShrink:0}}>
            <input value={input} onChange={e=>setInput(e.target.value)} onKeyDown={e=>e.key==="Enter"&&!e.shiftKey&&submit()}
              placeholder="Ask about this graph…"
              style={{flex:1,padding:"7px 10px",background:"rgba(255,255,255,.04)",border:"1px solid rgba(255,255,255,.08)",borderRadius:8,color:"#e2e8f0",fontSize:11.5,outline:"none",fontFamily:"inherit"}}/>
            <motion.button whileHover={{scale:1.06}} whileTap={{scale:.94}} onClick={submit} disabled={loading||!input.trim()}
              style={{width:32,height:32,borderRadius:8,background:"rgba(99,102,241,.25)",border:"1px solid rgba(99,102,241,.4)",color:"#a5b4fc",cursor:"pointer",display:"flex",alignItems:"center",justifyContent:"center",opacity:loading||!input.trim()?.4:1}}>
              <Send size={13} strokeWidth={2}/>
            </motion.button>
          </div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}

// ─── Main ─────────────────────────────────────────────────────────────────────
function GraphInner({initialGraph}:{initialGraph:GData|null}){
  const [gData,setGData]=useState<GData>(initialGraph??{nodes:[],edges:[]});
  const [centerId,setCenterId]=useState("");
  const [history,setHistory]=useState<Snapshot[]>([]);
  const [vp,setVp]=useState<VP>({x:0,y:0,s:.85});
  const [transitioning,setTransitioning]=useState(false);
  const [dragging,setDragging]=useState(false);
  const [dragStart,setDragStart]=useState({mx:0,my:0,vx:0,vy:0});
  const [hoveredId,setHoveredId]=useState<string|null>(null);
  const [selectedNode,setSelectedNode]=useState<RawNode|null>(null);
  const [filter,setFilter]=useState("All");
  const [search,setSearch]=useState("");
  const [aiStep,setAiStep]=useState(-1);
  const [ripple,setRipple]=useState<RippleResult|null>(null);
  const [rippleModal,setRippleModal]=useState(false);
  const [rippleLoading,setRippleLoading]=useState(false);
  const [subLoading,setSubLoading]=useState(false);
  const containerRef=useRef<HTMLDivElement>(null);
  const positions=useRef<Map<string,{x:number;y:number}>>(new Map());
  const [containerSize,setContainerSize]=useState({w:1200,h:700});

  // ── Live data ─────────────────────────────────────────────────────────────
  const [liveData,setLiveData]=useState<LiveData|null>(null);
  const [liveStatus,setLiveStatus]=useState<"live"|"stale"|"offline">("stale");
  const [lastUpdated,setLastUpdated]=useState<string|null>(null);
  const prevTopoRef=useRef<string|null>(null);

  // Timeline & historical state
  const [timelineIdx,setTimelineIdx]=useState(1); // 1 = Today
  const [historicalId,setHistoricalId]=useState<string|null>(null);

  // AI chat state
  const [chatOpen,setChatOpen]=useState(false);
  const [chatMessages,setChatMessages]=useState<ConvoMsg[]>([]);
  const [chatLoading,setChatLoading]=useState(false);

  const fetchLive=useCallback(async()=>{
    try{
      const res=await fetch(`${API}/api/graph/live`,{signal:AbortSignal.timeout(12000)});
      if(!res.ok)throw new Error("not ok");
      const data:LiveData=await res.json();
      setLiveData(data);
      setLiveStatus("live");
      setLastUpdated(data.updated_at);
      // Detect topology change → refetch full graph
      const topoKey=`${data.topology.node_count}:${data.topology.edge_count}`;
      if(prevTopoRef.current&&prevTopoRef.current!==topoKey){
        const gr=await fetch(`${API}/api/graph/full`,{signal:AbortSignal.timeout(12000)});
        if(gr.ok){
          const newGraph:GData=await gr.json();
          if(newGraph.nodes.length>=gData.nodes.length){
            setGData(newGraph);
          }
        }
      }
      prevTopoRef.current=topoKey;
    }catch{
      setLiveStatus("offline");
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  },[gData.nodes.length]);

  useEffect(()=>{
    fetchLive();
    const iv=setInterval(fetchLive,30000); // price refresh every 30s
    return()=>clearInterval(iv);
  // eslint-disable-next-line react-hooks/exhaustive-deps
  },[]);

  // AI Chat
  const sendChat=useCallback(async(question:string)=>{
    setChatMessages(m=>[...m,{role:"user",text:question}]);
    setChatLoading(true);
    try{
      const res=await fetch(`${API}/api/graph/chat`,{
        method:"POST",headers:{"Content-Type":"application/json"},
        body:JSON.stringify({question,graph_context:{nodes:gData.nodes,edges:gData.edges,center_id:centerId,selected_id:selectedNode?.id??null}}),
        signal:AbortSignal.timeout(20000),
      });
      if(res.ok){
        const d=await res.json();
        setChatMessages(m=>[...m,{role:"assistant",text:d.answer??"No response.",highlightIds:d.highlight_nodes??[],confidence:d.confidence}]);
      }else{throw new Error("fail");}
    }catch{
      setChatMessages(m=>[...m,{role:"assistant",text:"Unable to reach the AI service. Please try again."}]);
    }
    setChatLoading(false);
  },[gData,centerId,selectedNode]);

  // Init center
  useEffect(()=>{
    if(gData.nodes.length&&!centerId){
      const c=pickCenter(gData.nodes,gData.edges);
      setCenterId(c);
      setSelectedNode(gData.nodes.find(n=>n.id===c)??null);
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  },[gData.nodes.length]);

  // Build layout when data/center changes
  useEffect(()=>{
    if(!gData.nodes.length||!centerId)return;
    positions.current=layout(gData.nodes,gData.edges,centerId);
    // Fit view after layout
    if(containerRef.current){
      const{clientWidth:cw,clientHeight:ch}=containerRef.current;
      setContainerSize({w:cw,h:ch});
      const xs=[...positions.current.values()].map(p=>p.x);
      const ys=[...positions.current.values()].map(p=>p.y);
      if(!xs.length)return;
      const minX=Math.min(...xs)-150;const maxX=Math.max(...xs)+150;
      const minY=Math.min(...ys)-100;const maxY=Math.max(...ys)+100;
      const sc=Math.min(cw/(maxX-minX),ch/(maxY-minY),.95)*.88;
      const cx=(minX+maxX)/2;const cy=(minY+maxY)/2;
      setTransitioning(true);
      setVp({x:cw/2-cx*sc,y:ch/2-cy*sc,s:sc});
      setTimeout(()=>setTransitioning(false),700);
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  },[centerId,gData]);

  // Container resize
  useEffect(()=>{
    const ro=new ResizeObserver(entries=>{const{width:w,height:h}=entries[0].contentRect;setContainerSize({w,h});});
    if(containerRef.current)ro.observe(containerRef.current);
    return()=>ro.disconnect();
  },[]);

  // Wheel zoom
  useEffect(()=>{
    const el=containerRef.current;if(!el)return;
    const onWheel=(e:WheelEvent)=>{
      e.preventDefault();
      const rect=el.getBoundingClientRect();
      const mx=e.clientX-rect.left;const my=e.clientY-rect.top;
      const factor=e.deltaY>0?.88:1.13;
      setVp(v=>{
        const ns=Math.max(.15,Math.min(3,v.s*factor));
        const sd=ns/v.s;
        return{x:mx-(mx-v.x)*sd,y:my-(my-v.y)*sd,s:ns};
      });
    };
    el.addEventListener("wheel",onWheel,{passive:false});
    return()=>el.removeEventListener("wheel",onWheel);
  },[]);

  const flyTo=useCallback((pos:{x:number;y:number},newScale?:number)=>{
    const{w,h}=containerSize;
    const s=newScale??vp.s;
    setTransitioning(true);
    setVp({x:w/2-pos.x*s,y:h/2-pos.y*s,s});
    setTimeout(()=>setTransitioning(false),600);
  },[containerSize,vp.s]);

  const fitAll=useCallback(()=>{
    if(!positions.current.size)return;
    const{w,h}=containerSize;
    const xs=[...positions.current.values()].map(p=>p.x);
    const ys=[...positions.current.values()].map(p=>p.y);
    const minX=Math.min(...xs)-150;const maxX=Math.max(...xs)+150;
    const minY=Math.min(...ys)-100;const maxY=Math.max(...ys)+100;
    const sc=Math.min(w/(maxX-minX),h/(maxY-minY),.95)*.88;
    const cx=(minX+maxX)/2;const cy=(minY+maxY)/2;
    setTransitioning(true);
    setVp({x:w/2-cx*sc,y:h/2-cy*sc,s:sc});
    setTimeout(()=>setTransitioning(false),600);
  },[containerSize]);

  // Pan
  const onPanDown=useCallback((e:React.MouseEvent)=>{
    if((e.target as HTMLElement).closest("[data-node]"))return;
    setDragging(true);setDragStart({mx:e.clientX,my:e.clientY,vx:vp.x,vy:vp.y});
  },[vp]);
  const onPanMove=useCallback((e:React.MouseEvent)=>{
    if(!dragging)return;
    setVp(v=>({...v,x:dragStart.vx+e.clientX-dragStart.mx,y:dragStart.vy+e.clientY-dragStart.my}));
  },[dragging,dragStart]);
  const onPanUp=useCallback(()=>setDragging(false),[]);

  // Adjacency
  const adj=useMemo(()=>{
    const a:Record<string,Set<string>>={};
    gData.nodes.forEach(n=>a[n.id]=new Set());
    gData.edges.forEach(e=>{a[e.source]?.add(e.target);a[e.target]?.add(e.source);});
    return a;
  },[gData]);

  // Recenter
  const recenterOn=useCallback(async(nodeId:string)=>{
    if(nodeId===centerId||subLoading)return;
    setSubLoading(true);
    try{
      const res=await fetch(`${API}/api/graph/subgraph/${encodeURIComponent(nodeId)}?hops=2`);
      if(res.ok){
        const sub=await res.json() as GData;
        if(sub.nodes.length>=4){
          setHistory(h=>[...h,{data:gData,centerId}]);
          setGData(sub);setCenterId(nodeId);
          setSelectedNode(sub.nodes.find(n=>n.id===nodeId)??null);
          setRipple(null);
        }
      }
    }catch{}
    setSubLoading(false);
  },[centerId,gData,subLoading]);

  const goBack=useCallback(()=>{
    if(!history.length)return;
    const prev=history[history.length-1];
    setHistory(h=>h.slice(0,-1));
    setGData(prev.data);setCenterId(prev.centerId);
    setSelectedNode(prev.data.nodes.find(n=>n.id===prev.centerId)??null);
    setRipple(null);
  },[history]);

  const runRipple=useCallback(async(change:"rise"|"fall"|"shock")=>{
    if(!selectedNode)return;setRippleLoading(true);
    try{const res=await fetch(`${API}/api/graph/ripple/${encodeURIComponent(selectedNode.id)}?change=${change}`);if(res.ok)setRipple(await res.json());}catch{}
    setRippleLoading(false);setRippleModal(false);
  },[selectedNode]);

  // Search: fly to + auto-panel on match
  const prevSearchRef=useRef("");
  useEffect(()=>{
    if(!search||search===prevSearchRef.current)return;
    prevSearchRef.current=search;
    const sl=search.toLowerCase();
    const m=gData.nodes.find(n=>n.label.toLowerCase().includes(sl)||n.ticker?.toLowerCase().includes(sl));
    if(m){
      setSelectedNode(m);
      const pos=positions.current.get(m.id);
      if(pos)flyTo(pos,Math.max(vp.s,.85));
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  },[search,gData.nodes]);

  // Derived state
  const filterTypes=filter!=="All"?(FMAP[filter]??[]):null;
  // Chat-highlighted IDs from latest assistant message
  const chatHlIds:Set<string>|null=chatMessages.length?new Set(chatMessages[chatMessages.length-1]?.highlightIds??[]):null;
  let hlIds:Set<string>|null=null;
  if(aiStep>=0&&aiStep<AI_STEPS.length)hlIds=AI_STEPS[aiStep].get(gData.nodes,gData.edges,centerId);
  else if(search){const sl=search.toLowerCase();const m=gData.nodes.find(n=>n.label.toLowerCase().includes(sl)||n.ticker?.toLowerCase().includes(sl));if(m)hlIds=bfs(m.id,gData.edges);}
  else if(chatHlIds&&chatHlIds.size>0)hlIds=chatHlIds;
  const rippleMap:Record<string,string>={};
  if(ripple)ripple.impacts.forEach(imp=>rippleMap[imp.node.id]=imp.impact_direction);
  const anyActive=!!(hoveredId||hlIds||Object.keys(rippleMap).length);

  function nodeDimmed(nodeId:string,nodeType:string):boolean{
    if(filterTypes&&!filterTypes.includes(nodeType))return true;
    if(hoveredId&&hoveredId!==nodeId&&!adj[hoveredId]?.has(nodeId))return true;
    if(hlIds&&!hlIds.has(nodeId))return true;
    if(Object.keys(rippleMap).length&&nodeId!==ripple?.source.id&&!rippleMap[nodeId])return true;
    return false;
  }

  const handleNodeClick=(n:RawNode)=>{
    setSelectedNode(n);setAiStep(-1);setHoveredId(null);
    const pos=positions.current.get(n.id);
    if(pos)flyTo(pos);
    if(n.id!==centerId)recenterOn(n.id);
  };

  const handleReset=()=>{
    setFilter("All");setSearch("");setAiStep(-1);setRipple(null);setHoveredId(null);
    setSelectedNode(gData.nodes.find(n=>n.id===centerId)??null);
    setHistory([]);fitAll();
  };

  return(
    <div style={{height:"calc(100vh - 68px)",display:"flex",flexDirection:"column",background:"#050a18",overflow:"hidden",fontFamily:"Inter,-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif"}}>

      {/* Header */}
      <div style={{flexShrink:0,padding:"10px 20px 0",background:"rgba(3,6,16,.98)"}}>
        <div style={{display:"flex",alignItems:"center",gap:6,marginBottom:4}}>
          <span style={{fontSize:11,color:"#334155",fontWeight:600}}>Intelligence</span>
          <span style={{fontSize:10,color:"#1e293b"}}>›</span>
          <span style={{fontSize:11,color:"#475569",fontWeight:700}}>Market Intelligence Graph</span>
        </div>
        <div style={{display:"flex",alignItems:"flex-end",justifyContent:"space-between"}}>
          <div>
            <div style={{display:"flex",alignItems:"center",gap:10,marginBottom:2}}>
              <h1 style={{fontSize:22,fontWeight:900,color:"#f1f5f9",margin:0,letterSpacing:"-.03em"}}>Market Intelligence Graph</h1>
              <span style={{display:"flex",alignItems:"center",gap:4,padding:"3px 9px",borderRadius:999,fontSize:9,fontWeight:800,
                background:liveStatus==="live"?"rgba(34,197,94,.12)":liveStatus==="offline"?"rgba(239,68,68,.12)":"rgba(245,158,11,.12)",
                border:`1px solid ${liveStatus==="live"?"rgba(34,197,94,.3)":liveStatus==="offline"?"rgba(239,68,68,.3)":"rgba(245,158,11,.3)"}`,
                color:liveStatus==="live"?"#4ade80":liveStatus==="offline"?"#f87171":"#fbbf24",
                letterSpacing:".08em",textTransform:"uppercase" as const}}>
                <span style={{width:5,height:5,borderRadius:"50%",background:"currentColor",display:"inline-block",animation:liveStatus==="live"?"igGlow 1.5s ease infinite":"none"}}/>
                {liveStatus==="live"?"LIVE":liveStatus==="offline"?"OFFLINE":"LOADING"}
              </span>
              {liveData&&<span style={{fontSize:10,color:"#334155",fontWeight:600}}>{gData.nodes.length} nodes · {gData.edges.length} edges</span>}
            </div>
            <p style={{fontSize:11.5,color:"#334155",margin:0}}>Understand today's market relationships and ripple effects. Prices refresh every 30 seconds.</p>
          </div>
          <div style={{display:"flex",gap:5,paddingBottom:3,alignItems:"center",flexWrap:"wrap"}}>
            {history.length>0&&<motion.button whileHover={{scale:1.04}} whileTap={{scale:.96}} onClick={goBack} style={{display:"flex",alignItems:"center",gap:5,padding:"7px 11px",borderRadius:9,fontSize:11,fontWeight:700,cursor:"pointer",background:"rgba(255,255,255,.06)",border:"1px solid rgba(255,255,255,.1)",color:"#94a3b8"}}><ChevronLeft size={12} strokeWidth={2}/> Back</motion.button>}
            {[
              {icon:<Sparkles     size={11} strokeWidth={1.8}/>, l:"AI Explain",   act:()=>setAiStep(aiStep>=0?-1:0),active:aiStep>=0,    color:"rgba(99,102,241,"},
              {icon:<MessageCircle size={11} strokeWidth={1.8}/>,l:"Ask AI",       act:()=>setChatOpen(o=>!o),        active:chatOpen,      color:"rgba(139,92,246,"},
              {icon:<Crosshair    size={11} strokeWidth={1.8}/>, l:"Fit",          act:fitAll,                        active:false,         color:"rgba(255,255,255,"},
              {icon:<RotateCcw    size={11} strokeWidth={1.8}/>, l:"Reset",        act:handleReset,                   active:false,         color:"rgba(255,255,255,"},
            ].map(b=><motion.button key={b.l} whileHover={{scale:1.04}} whileTap={{scale:.96}} onClick={b.act}
              style={{display:"flex",alignItems:"center",gap:4,padding:"7px 11px",borderRadius:9,fontSize:11,fontWeight:b.active?700:600,cursor:"pointer",
                background:b.active?`${b.color}.22)`:`${b.color}.04)`,
                border:`1px solid ${b.active?`${b.color}.45)`:`${b.color}.08)`}`,
                color:b.active?"#c7d2fe":"#64748b"}}>{b.icon}{b.l}</motion.button>)}
            <TimelineSlider idx={timelineIdx} onChange={setTimelineIdx}/>
          </div>
        </div>
      </div>

      {/* Historical Replay Bar */}
      <div style={{flexShrink:0,background:"rgba(2,4,14,.98)",padding:"5px 20px",borderBottom:"1px solid rgba(255,255,255,.04)",display:"flex",alignItems:"center",gap:6,overflowX:"auto"}}>
        <span style={{fontSize:8.5,fontWeight:700,color:"#1e293b",letterSpacing:".07em",textTransform:"uppercase",whiteSpace:"nowrap",display:"flex",alignItems:"center",gap:4,flexShrink:0}}><History size={10} color="#334155" strokeWidth={1.8}/> Historical Replay</span>
        <span style={{width:1,height:14,background:"rgba(255,255,255,.05)",flexShrink:0}}/>
        {HIST_SCENARIOS.map(s=>(
          <button key={s.id} onClick={()=>setHistoricalId(historicalId===s.id?null:s.id)}
            style={{display:"flex",flexDirection:"column",padding:"3px 9px",borderRadius:7,fontSize:9,fontWeight:historicalId===s.id?700:500,cursor:"pointer",whiteSpace:"nowrap",flexShrink:0,
              background:historicalId===s.id?`${s.color}18`:"transparent",
              border:historicalId===s.id?`1px solid ${s.color}35`:"1px solid rgba(255,255,255,.05)",
              color:historicalId===s.id?s.color:"#334155",transition:"all .15s"}}>
            <span>{s.label}</span>
            <span style={{fontSize:7.5,opacity:.65,fontWeight:400}}>{s.sub}</span>
          </button>
        ))}
        {historicalId&&<span style={{marginLeft:"auto",fontSize:8.5,color:"#f59e0b",fontWeight:700,letterSpacing:".06em",flexShrink:0,display:"flex",alignItems:"center",gap:4}}>
          <span style={{width:5,height:5,borderRadius:"50%",background:"#f59e0b",animation:"igGlow 1.5s ease infinite",display:"inline-block"}}/>HISTORICAL MODE — LIVE DATA MAY DIFFER
        </span>}
      </div>

      {/* Search + Filters + Legend */}
      <div style={{flexShrink:0,background:"rgba(3,6,16,.98)",padding:"7px 20px",borderBottom:"1px solid rgba(255,255,255,.05)",display:"flex",alignItems:"center",gap:10}}>
        <div style={{position:"relative",flexShrink:0}}>
          <span style={{position:"absolute",left:10,top:"50%",transform:"translateY(-50%)",color:"#334155",pointerEvents:"none",display:"flex"}}><Search size={12} strokeWidth={1.8}/></span>
          <input value={search} onChange={e=>setSearch(e.target.value)} placeholder="Search anything (e.g. RBI, Oil, HDFC Bank...)"
            style={{width:268,padding:"7px 36px 7px 30px",background:"rgba(255,255,255,.04)",border:"1px solid rgba(255,255,255,.08)",borderRadius:9,color:"#e2e8f0",fontSize:11.5,outline:"none",fontFamily:"inherit"}}/>
          <div style={{position:"absolute",right:8,top:"50%",transform:"translateY(-50%)",padding:"1px 5px",borderRadius:5,background:"rgba(255,255,255,.06)",border:"1px solid rgba(255,255,255,.08)"}}>
            <span style={{fontSize:9,color:"#334155",fontWeight:700}}>⌘K</span>
          </div>
        </div>
        <div style={{display:"flex",gap:3,overflowX:"auto"}}>
          {FILTERS.map(f=><motion.button key={f} whileHover={{scale:1.04}} whileTap={{scale:.96}} onClick={()=>{setFilter(f);setRipple(null);}} style={{padding:"5px 11px",borderRadius:999,fontSize:11,fontWeight:600,cursor:"pointer",whiteSpace:"nowrap",background:filter===f?"rgba(99,102,241,.22)":"transparent",border:filter===f?"1px solid rgba(99,102,241,.45)":"1px solid rgba(255,255,255,.07)",color:filter===f?"#a5b4fc":"#334155",transition:"all .15s"}}>{f}</motion.button>)}
        </div>
        <div style={{marginLeft:"auto",display:"flex",gap:12,alignItems:"center",flexShrink:0}}>
          {[{c:"#22c55e",l:"Positive Impact"},{c:"#ef4444",l:"Negative Impact"},{c:"#60a5fa",l:"Related"},{c:"#a78bfa",l:"Triggers"},{c:"#475569",l:"Weak Relation"}].map(({c,l})=>(
            <span key={l} style={{display:"flex",alignItems:"center",gap:4,fontSize:9.5,color:"#334155",whiteSpace:"nowrap"}}>
              <span style={{width:7,height:7,borderRadius:"50%",background:c,flexShrink:0,display:"inline-block"}}/>
              {l}
            </span>
          ))}
        </div>
      </div>

      {/* Canvas */}
      <div ref={containerRef} style={{flex:1,position:"relative",overflow:"hidden",cursor:dragging?"grabbing":"default"}}
        onMouseDown={onPanDown} onMouseMove={onPanMove} onMouseUp={onPanUp} onMouseLeave={onPanUp}>

        {/* Background vignette */}
        <div style={{position:"absolute",inset:0,pointerEvents:"none",zIndex:0,
          background:"radial-gradient(ellipse 80% 70% at 50% 50%,transparent 40%,rgba(2,5,14,.5) 100%)"}}/>
        {/* Dot grid */}
        <svg style={{position:"absolute",inset:0,width:"100%",height:"100%",pointerEvents:"none",zIndex:0}} xmlns="http://www.w3.org/2000/svg">
          <defs><pattern id="dots" x="0" y="0" width="36" height="36" patternUnits="userSpaceOnUse"><circle cx="18" cy="18" r="1" fill="rgba(255,255,255,.018)"/></pattern></defs>
          <rect width="100%" height="100%" fill="url(#dots)"/>
        </svg>

        {/* Camera */}
        <div style={{
          position:"absolute",left:0,top:0,
          transform:`translate(${vp.x}px,${vp.y}px) scale(${vp.s})`,
          transformOrigin:"0 0",
          transition:transitioning?"transform .55s cubic-bezier(.16,1,.3,1)":"none",
          willChange:"transform",
        }}>
          {/* Purple bloom behind center */}
          <div style={{position:"absolute",left:-200,top:-200,width:400,height:400,borderRadius:"50%",background:"radial-gradient(circle,rgba(99,102,241,.07) 0%,transparent 70%)",pointerEvents:"none"}}/>
          {/* Edges SVG */}
          <Edges nodes={gData.nodes} edges={gData.edges} positions={positions.current} centerId={centerId}
            hoveredId={hoveredId} selectedId={selectedNode?.id??null} hlIds={hlIds} rippleMap={rippleMap} filter={filter}/>
          {/* Nodes */}
          <AnimatePresence>
            {gData.nodes.map(node=>{
              const pos=positions.current.get(node.id);if(!pos)return null;
              const isC=node.id===centerId;
              const dimmed=nodeDimmed(node.id,node.node_type);
              const imp=impact(node.id,gData.nodes,gData.edges);
              const cnf=conf(node.id,gData.edges);
              const lp=liveData?.prices[node.id];
              if(isC)return<CenterNode key={node.id} node={node} pos={pos} imp={imp} cnf={cnf} dimmed={dimmed} selected={selectedNode?.id===node.id} livePrice={lp} onClick={()=>{setSelectedNode(node);const p=positions.current.get(node.id);if(p)flyTo(p);}}/>;
              return<IntelNode key={node.id} node={node} pos={pos} imp={imp} cnf={cnf} dimmed={dimmed} selected={selectedNode?.id===node.id}
                rippleDir={rippleMap[node.id]} livePrice={lp}
                onHover={()=>setHoveredId(node.id)} onHoverEnd={()=>setHoveredId(null)}
                onClick={()=>handleNodeClick(node)}/>;
            })}
          </AnimatePresence>
        </div>

        {/* HUD elements (not scaled) */}
        <ZoomCtrls onZoomIn={()=>setVp(v=>({...v,s:Math.min(3,v.s*1.15)}))} onZoomOut={()=>setVp(v=>({...v,s:Math.max(.15,v.s*.87)}))} onFit={fitAll} onReset={handleReset}/>
        <Minimap nodes={gData.nodes} positions={positions.current} centerId={centerId} vp={vp} cW={containerSize.w} cH={containerSize.h}/>

        {/* Loading overlay */}
        <AnimatePresence>
          {subLoading&&<motion.div initial={{opacity:0}} animate={{opacity:1}} exit={{opacity:0}} style={{position:"absolute",inset:0,zIndex:50,background:"rgba(5,10,24,.75)",backdropFilter:"blur(4px)",display:"flex",alignItems:"center",justifyContent:"center",flexDirection:"column",gap:12}}>
            <div style={{width:36,height:36,border:"2.5px solid rgba(139,92,246,.2)",borderTopColor:"#a78bfa",borderRadius:"50%",animation:"igSpin .8s linear infinite"}}/>
            <p style={{fontSize:12,color:"#64748b",fontWeight:600,margin:0}}>Loading subgraph…</p>
          </motion.div>}
        </AnimatePresence>

        {/* AI Explain */}
        <AnimatePresence>
          {aiStep>=0&&<AIExplain step={aiStep} onNext={()=>{if(aiStep<AI_STEPS.length-1)setAiStep(s=>s+1);else setAiStep(-1);}} onPrev={()=>{if(aiStep>0)setAiStep(s=>s-1);}} onClose={()=>setAiStep(-1)}/>}
        </AnimatePresence>

        {/* Node panel */}
        <AnimatePresence>
          {selectedNode&&<NodePanel key={selectedNode.id} node={selectedNode} data={gData} livePrice={liveData?.prices[selectedNode.id]} onClose={()=>setSelectedNode(null)} onRipple={()=>setRippleModal(true)} onMakeCenter={()=>recenterOn(selectedNode.id)}/>}
        </AnimatePresence>

        {/* AI Chat */}
        <AIChatPanel open={chatOpen} onClose={()=>setChatOpen(false)} messages={chatMessages} loading={chatLoading} onSend={sendChat} gData={gData} centerId={centerId} selectedId={selectedNode?.id??null}/>

        {/* Historical mode overlay tint */}
        {historicalId&&<div style={{position:"absolute",inset:0,pointerEvents:"none",zIndex:2,background:"rgba(245,158,11,.04)",border:"1px solid rgba(245,158,11,.06)",borderRadius:0}}/>}

        {/* Timeline projection overlay */}
        {timelineIdx!==1&&<div style={{position:"absolute",top:8,left:"50%",transform:"translateX(-50%)",zIndex:22,padding:"4px 14px",borderRadius:999,background:"rgba(99,102,241,.18)",border:"1px solid rgba(99,102,241,.35)",fontSize:9.5,fontWeight:700,color:"#a5b4fc",letterSpacing:".06em",whiteSpace:"nowrap",pointerEvents:"none"}}>
          {timelineIdx<1?"HISTORICAL VIEW":"PROJECTION"} · {TIMELINE[timelineIdx].label.toUpperCase()} · DATA SIMULATED
        </div>}
      </div>

      {/* Ripple modal */}
      <AnimatePresence>
        {rippleModal&&selectedNode&&<RippleModal node={selectedNode} onRun={runRipple} onClose={()=>setRippleModal(false)} loading={rippleLoading}/>}
      </AnimatePresence>

      {/* Bottom bar */}
      <BottomBar data={gData} centerId={centerId} liveData={liveData} lastUpdated={lastUpdated}/>

      {/* Footer */}
      <div style={{height:26,flexShrink:0,background:"rgba(1,3,10,.99)",borderTop:"1px solid rgba(255,255,255,.04)",display:"flex",alignItems:"center",justifyContent:"space-between",padding:"0 16px"}}>
        <span style={{fontSize:9.5,color:"#1e293b",display:"flex",alignItems:"center",gap:5}}>
          <span style={{width:6,height:6,borderRadius:"50%",
            background:liveStatus==="live"?"#22c55e":liveStatus==="offline"?"#ef4444":"#f59e0b",
            display:"inline-block",
            boxShadow:liveStatus==="live"?"0 0 6px #22c55e":liveStatus==="offline"?"0 0 6px #ef4444":"none"}}/>
          {liveStatus==="live"&&lastUpdated
            ?`Live · updated ${new Date(lastUpdated).toLocaleTimeString("en-IN",{hour:"2-digit",minute:"2-digit",second:"2-digit"})}`
            :liveStatus==="offline"?"Offline — retrying…":"Connecting…"}
          {liveData&&<span style={{marginLeft:8,color:"#1e293b"}}>· {Object.keys(liveData.prices).length} prices</span>}
        </span>
        <span style={{fontSize:9.5,color:"#1e293b",display:"flex",alignItems:"center",gap:10}}>
          {liveData&&<span>{liveData.topology.node_count} nodes · {liveData.topology.edge_count} edges</span>}
          <span>Data: NSE, BSE, RBI, yfinance · Prices cached 2 min</span>
        </span>
      </div>
    </div>
  );
}

export function IntelligenceGraph({initialGraph}:{initialGraph:GData|null}){
  return(
    <>
      <Styles/>
      <GraphInner initialGraph={initialGraph}/>
    </>
  );
}
