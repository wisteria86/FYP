// Deterministic, editable diagram. node render-session-flow.cjs [path-to-sharp]
const fs=require('fs'),path=require('path')
const sharp=require(process.argv[2]||'sharp')
const C={browser:'#168b9a',backend:'#315c96',llm:'#7744a5',optional:'#b77516',success:'#328255',ink:'#24334b',wine:'#800d2e'}
const esc=s=>s.replaceAll('&','&amp;').replaceAll('<','&lt;')
const shapes=[]
function text(x,y,lines,size=29,color=C.ink,weight=400){
  shapes.push(`<text x="${x}" y="${y}" font-family="Segoe UI, Arial, sans-serif" font-size="${size}" font-weight="${weight}" fill="${color}">${lines.map((line,i)=>`<tspan x="${x}" dy="${i?size*1.4:0}">${esc(line)}</tspan>`).join('')}</text>`)
}
function line(points,color=C.wine,dashed=false,label){
  shapes.push(`<polyline points="${points.map(p=>p.join(',')).join(' ')}" fill="none" stroke="${color}" stroke-width="5" stroke-linejoin="round" ${dashed?'stroke-dasharray="12 10"':''} marker-end="url(#arrow-${Object.keys(C).find(k=>C[k]===color)})"/>`)
  if(label)text(label[0],label[1],[label[2]],25,color,600)
}
function icon(type,x,y,color){
  const start=shapes.length
  if(type==='mic')shapes.push('<rect x="25" y="8" width="30" height="56" rx="15"/><path d="M12 48v10a28 28 0 0 0 56 0V48M40 87v18M23 105h34"/>')
  else if(type==='database')shapes.push('<ellipse cx="43" cy="20" rx="35" ry="14"/><path d="M8 20v65c0 19 70 19 70 0V20M8 50c0 19 70 19 70 0"/>')
  else if(type==='book')shapes.push('<path d="M42 23C27 10 10 12 4 17v72c13-8 27-7 38 4 11-11 25-12 38-4V17c-6-5-23-7-38 6v70M14 35h16M14 49h16M54 35h16M54 49h16"/>')
  else if(type==='speaker')shapes.push('<path d="M8 38h18l24-22v80L26 74H8zM61 33q27 23 0 46M73 19q42 37 0 75"/>')
  else if(type==='people')shapes.push('<circle cx="43" cy="26" r="16"/><path d="M17 91V76a26 26 0 0 1 52 0v15zM9 20a12 12 0 1 0 0 24M77 20a12 12 0 1 1 0 24M5 58v27M81 58v27"/>')
  else if(type==='wave')shapes.push('<path d="M7 49v14M20 31v50M33 15v82M46 37v38M59 24v64M72 42v28M85 48v15"/>')
  else if(type==='camera')shapes.push('<rect x="7" y="30" width="76" height="60" rx="8"/><path d="M20 30l9-15h30l8 15"/><circle cx="45" cy="59" r="19"/>')
  else if(type==='brain')shapes.push('<path d="M43 14c-18-13-33 0-29 15-16 4-16 29-3 35-8 20 14 35 32 22 18 13 40-2 32-22 13-6 13-31-3-35 4-15-11-28-29-15v72M17 34l17 13M69 34L52 47M13 64l20-7M74 64l-20-7"/>')
  else if(type==='chart')shapes.push('<path d="M6 95h80M16 88V62h13v26M40 88V42h13v46M64 88V18h13v70M13 36l24-15 18 6L80 5"/>')
  else if(type==='key')shapes.push('<circle cx="25" cy="31" r="21"/><circle cx="25" cy="31" r="6"/><path d="M40 47l38 38-10 10-10-10 8-8-9-9-8 8-10-10"/>')
  else shapes.push('<rect x="9" y="7" width="66" height="90" rx="7"/><path d="M23 30l5 5 10-12M45 30h17M23 55l5 5 10-12M45 55h17M23 80h39"/>')
  const content=shapes.splice(start).join('')
  shapes.push(`<g transform="translate(${x},${y}) scale(.85)" fill="none" stroke="${color}" stroke-width="5" stroke-linecap="round" stroke-linejoin="round">${content}</g>`)
}
const steps=[
 ['Sign in','Authenticate learner and load preferences.','key','browser'],
 ['Choose a lesson','Skill, language, proficiency and roleplay type.','book','browser'],
 ['Prepare a scenario','Adapt to history, weak skills and prior feedback.','brain','backend'],
 ['Review the briefing','Learner role, objectives and AI participants.','people','browser'],
 ['Create the session','Freeze scenario snapshot; save opening turn.','database','backend'],
 ['Join the voice call','Play opening; request selected microphone.','speaker','browser'],
 ['Prepare microphone audio','Capture constraints → optional gain → RNNoise.','wave','browser'],
 ['Capture learner speech','Manual: Stop & send. Auto: Silero detects pause.','mic','browser'],
 ['Recognize speech','Nemotron live or recorded; Whisper ONNX selectable.','wave','backend'],
 ['Validate the transcript','Empty / uncertain: retry. Valid: submit the turn.','check','backend'],
 ['Save learner turn','Apply ready review of prior turn at safe boundary.','database','backend'],
 ['Check objective evidence','Use current saved review; otherwise local rules.','check','backend'],
 ['Build scenario-specific context','History, persona, speaker role and optional sources.','book','backend'],
 ['Generate the next AI response','External LLM; ordered, role-specific AI speakers.','brain','llm'],
 ['Deliver and save the reply','Filter reasoning → selected TTS → browser playback.','speaker','browser'],
 ['Objectives achieved?','No word / turn quota; evidence determines outcome.','check','success'],
 ['Finish the closing reply','Wait for playback, stop capture and end the call.','speaker','success'],
 ['Assess and save feedback','Transcript-grounded scores; optional posture data.','check','backend'],
 ['Update the learning journey','History, skill progress and recommended activities.','chart','success'],
]
const X=610,W=1100,H=130,Y=340,GAP=185
const cy=i=>Y+i*GAP+H/2
function side(x,y,w,title,lines,color,type='check'){
 shapes.push(`<rect x="${x}" y="${y}" width="${w}" height="${115+lines.length*40}" rx="22" fill="white" stroke="${color}" stroke-width="3"/>`)
 icon(type,x+20,y+20,color)
 text(x+110,y+48,[title],29,color,700)
 text(x+24,y+135,lines,26)
}
// Main cards and numbered pictograms.
steps.forEach(([title,body,type,kind],i)=>{
 const y=Y+i*GAP,col=C[kind]
 shapes.push(`<rect x="${X}" y="${y}" width="${W}" height="${H}" rx="23" fill="white" stroke="${col}" stroke-width="3"/>`)
 shapes.push(`<rect x="${X}" y="${y}" width="12" height="${H}" rx="5" fill="${col}"/>`)
 icon(type,X+25,y+16,col)
 text(X+135,y+47,[`${String(i+1).padStart(2,'0')}  ${title}`],35,col,700)
 text(X+135,y+94,[body],27)
 if(i<steps.length-1)line([[X+W/2,y+H],[X+W/2,y+GAP]],i===15?C.success:C.wine,false,i===15?[X+W/2+28,y+H+37,'YES']:null)
})
// Retry and continuation loops: routed outside the main column.
line([[X,cy(9)],[535,cy(9)],[535,cy(7)],[X,cy(7)]],C.wine)
text(65,cy(8)-20,['Retry empty /','uncertain speech'],27,C.wine,600)
line([[X,cy(15)],[470,cy(15)],[470,cy(7)-38],[X,cy(7)-38]],C.wine)
text(65,cy(15)-62,['NOT YET','Continue targeted practice.','Next learner turn.'],27,C.wine,700)
// Closing shortcut remains separate from normal response generation.
line([[X+W,cy(11)],[1750,cy(11)],[1750,cy(14)-35],[X+W,cy(14)-35]],C.success)
text(1790,cy(11)-15,['Already successful?','Use a closing reply;','skip another LLM question.'],26,C.success,600)
// Optional and parallel services.
side(1800,Y+9*GAP,530,'Background review',[
 'Meaning-based objective check.', 'Exact learner quotes required.',
 'Runs alongside conversation.', 'Applied at next turn boundary.',
 'Company policy keeps local rules.'
],C.llm,'brain')
line([[X+W,cy(10)],[1800,cy(10)]],C.llm,true)
line([[1800,cy(10)+38],[X+W,cy(10)+38]],C.llm,true)
side(1800,Y+12*GAP,530,'Optional RAG',[
 'Lesson-controlled documents.', 'Owner / organization checks.', 'Retrieve relevant passages.'
],C.optional,'book')
line([[1800,cy(12)],[X+W,cy(12)]],C.optional,true)
side(1800,Y+16*GAP,530,'Optional posture',[
 'Lesson-enabled camera only.', 'Browser extracts landmarks.', 'Backend computes indicators.'
],C.optional,'camera')
line([[1800,Y+16*GAP+235],[1765,Y+16*GAP+235],[1765,cy(17)],[X+W,cy(17)]],C.optional,true)
side(65,Y+10*GAP,350,'Chat mode',[
 'Typed messages', 'join at step 11.', 'No ASR required.'
],C.browser,'wave')
line([[415,Y+10*GAP+180],[X,cy(10)]],C.browser,true)
side(65,Y+13*GAP,350,'Manual exit',[
 'Release devices.', 'Cancel active work.', 'Not a successful', 'lesson completion.'
],C.ink,'speaker')
line([[X,cy(14)],[415,cy(14)]],C.ink,true)
// Introductory legend, callouts and phase labels.
text(70,100,['Hikari — Training Session Flow'],66,C.wine,700)
text(72,160,['Current implementation • Browser client + local Python backend'],33)
text(72,215,['Solid arrows: main flow / decisions     Dashed arrows: optional, parallel or alternate input'],28)
;[['browser','Browser'],['backend','Backend'],['llm','External LLM'],['optional','Optional'],['success','Success']].forEach(([kind,label],i)=>{
 const x=75+i*440
 shapes.push(`<rect x="${x}" y="258" width="28" height="28" rx="7" fill="${C[kind]}"/>`)
 text(x+42,282,[label],27,C[kind],600)
})
text(70,Y+50,['01 / PREPARE'],32,C.wine,700)
text(70,Y+5*GAP+50,['02 / CAPTURE'],32,C.wine,700)
text(70,Y+10*GAP-38,['03 / CONVERSE'],32,C.wine,700)
text(70,Y+15*GAP-50,['04 / RESOLVE'],32,C.wine,700)
side(1800,Y+4*GAP,530,'Session capabilities',[
 'Scenario frozen for continuity.', 'One or several AI participants.', 'Native-language captions for', 'beginner English when enabled.'
],C.backend,'people')
side(1800,Y+7*GAP,530,'Speech choices',[
 'Manual input is the default.', 'Automatic input is optional.', 'Live recognition is optional.', 'Explicit Nemotron does not', 'automatically fall back to Whisper.'
],C.browser,'mic')
side(1800,Y+14*GAP,530,'Speech playback',[
 'Kokoro / Piper / Kitten / ChatTTS', 'Selected engine generates audio.', 'Engine-specific buffering.', 'Captions translated separately.'
],C.browser,'speaker')
text(70,4080,['Runtime monitoring spans every phase: microphone levels • ASR • LLM • TTS • errors • CPU / GPU / RAM'],29,C.backend,600)
text(70,4140,['Assessment can run server-side alongside closing playback. This is not the proposed remote-host deployment.'],26)
const defs=Object.entries(C).map(([k,v])=>`<marker id="arrow-${k}" markerWidth="12" markerHeight="12" refX="10" refY="5" orient="auto" markerUnits="strokeWidth"><path d="M0,0 L10,5 L0,10z" fill="${v}"/></marker>`).join('')
const svg=`<svg xmlns="http://www.w3.org/2000/svg" width="2400" height="4200" viewBox="0 0 2400 4200"><defs>${defs}</defs><rect width="2400" height="4200" fill="#fffaf4"/>${shapes.join('')}</svg>`
fs.writeFileSync(path.join(__dirname,'hikari-session-flow.svg'),svg)
sharp(Buffer.from(svg)).png().toFile(path.join(__dirname,'hikari-session-flow.png')).then(info=>console.log(info)).catch(error=>{console.error(error);process.exitCode=1})
