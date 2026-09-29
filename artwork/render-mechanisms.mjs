import { createRequire } from 'node:module';
import { writeFile } from 'node:fs/promises';
const sharp = createRequire(import.meta.url)('sharp');
const colors = { ink:'#2a2422', muted:'#756b67', coral:'#c35a52', purple:'#7a62a9', gold:'#b37c22', teal:'#289783', line:'#e7ddd6' };
const escape = s => String(s).replaceAll('&','&amp;').replaceAll('<','&lt;').replaceAll('>','&gt;');
const family = 'Arial, Helvetica, sans-serif';
const parts = [];
const cache = new Map();
let checkedLines = 0;
async function width(text, size, weight) {
  const key = `${size}/${weight}/${text}`;
  if (!cache.has(key)) {
    const sample = `<svg xmlns="http://www.w3.org/2000/svg" width="2400" height="180"><text x="10" y="110" font-family="${family}" font-size="${size}" font-weight="${weight}">${escape(text)}</text></svg>`;
    const { info } = await sharp(Buffer.from(sample)).trim().png().toBuffer({resolveWithObject:true});
    cache.set(key, info.width + 6);
  }
  return cache.get(key);
}
async function text(value, x, y, maxWidth, {size=20, weight=400, color=colors.ink, lineHeight=size*1.3, bottom=1180}={}) {
  const lines=[]; let line='';
  for (const word of value.split(' ')) {
    const candidate = line ? `${line} ${word}` : word;
    if (await width(candidate,size,weight) > maxWidth && line) { lines.push(line); line=word; }
    else line=candidate;
  }
  if(line) lines.push(line);
  for (const line of lines) {
    if (await width(line,size,weight)>maxWidth || y+5>bottom) throw Error(`Text exceeds its box at y=${y}, bottom=${bottom}: ${line}`);
    parts.push(`<text x="${x}" y="${y}" font-size="${size}" font-weight="${weight}" fill="${color}">${escape(line)}</text>`);
    checkedLines++; y += lineHeight;
  }
  return y;
}
function rect(x,y,w,h,fill='#fff',radius=18) { parts.push(`<rect x="${x}" y="${y}" width="${w}" height="${h}" rx="${radius}" fill="${fill}" stroke="${colors.line}" stroke-width="1.5"/>`); }
function line(x1,y1,x2,y2) { parts.push(`<path d="M${x1} ${y1}H${x2}" fill="none" stroke="${colors.line}" stroke-width="1.5"/>`); }
async function centered(value,cx,y,size,color,weight=700) { parts.push(`<text x="${cx}" y="${y}" text-anchor="middle" font-size="${size}" font-weight="${weight}" fill="${color}">${escape(value)}</text>`); }
const cards=[{x:58,w:300,color:colors.coral,title:'LIGHT EXPOSURE'},{x:406,w:310,color:colors.purple,title:'POSSIBLE LIGHT TARGETS'},{x:764,w:310,color:colors.gold,title:'EARLY CELL SIGNALS'},{x:1122,w:420,color:colors.teal,title:'DOWNSTREAM EFFECTS'}];
parts.push(`<svg xmlns="http://www.w3.org/2000/svg" width="1600" height="1200" viewBox="0 0 1600 1200" role="img" aria-labelledby="title description"><title id="title">How might photobiomodulation affect cells?</title><desc id="description">Light exposure, possible targets, early signals and downstream responses, with six factors that shape the response.</desc><defs><linearGradient id="spectrum"><stop offset="0" stop-color="#c35a52"/><stop offset="0.48" stop-color="#d36f79"/><stop offset="1" stop-color="#7a62a9"/></linearGradient></defs><g font-family="${family}">`);
rect(12,12,1576,1176,'#fcfbf9',28);
await text('GRAPHICAL ABSTRACT',58,69,900,{size:20,weight:700,color:colors.coral});
await text('How might photobiomodulation affect cells?',58,128,1484,{size:44,weight:700});
await text('A working model from light absorption to context-dependent cell responses',58,172,1484,{size:24,color:colors.muted});
rect(1270,47,270,48,'#f7f0ec',24);
await centered('CONCEPTUAL OVERVIEW',1405,77,17,colors.muted);
for (let i=0;i<cards.length;i++) {
  const c=cards[i]; rect(c.x,220,c.w,610);
  parts.push(`<rect x="${c.x}" y="220" width="${c.w}" height="8" rx="4" fill="${c.color}"/><circle cx="${c.x+38}" cy="273" r="25" fill="${c.color}"/>`);
  await centered(`0${i+1}`,c.x+38,281,23,'#fff');
  await text(c.title,c.x+26,334,c.w-52,{size:24,weight:700,color:c.color,lineHeight:29,bottom:383});
  if(i<cards.length-1) {
    const start=c.x+c.w+12, end=cards[i+1].x-12;
    parts.push(`<path d="M${start} 508H${end}M${end-8} 501L${end} 508L${end-8} 515" fill="none" stroke="${colors.coral}" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"/>`);
  }
}
// Exposure: generous line lengths and a separate conditions list.
await text('Red and near-infrared',84,412,248,{size:22,color:colors.muted});
parts.push('<rect x="84" y="438" width="248" height="20" rx="10" fill="url(#spectrum)"/>');
await text('Visible red',84,489,110,{size:18,color:colors.muted});
await text('Near-infrared',216,489,116,{size:18,color:colors.muted});
line(84,515,332,515);
await text('EXPOSURE CONDITIONS',84,550,248,{size:18,weight:700,color:colors.coral});
for (const [i,s] of ['Wavelength','Irradiance','Exposure time'].entries()) {
  parts.push(`<circle cx="91" cy="591" r="4" fill="${colors.coral}" transform="translate(0 ${i*44})"/>`);
  await text(s,108,598+i*44,224,{size:23});
}
await text('Equal radiant exposure may still produce different effects.',84,749,248,{size:20,lineHeight:25,color:colors.muted,bottom:810});
// Targets: shared text layout measures all headings and descriptions.
let y=await text('First absorber is unsettled',432,412,258,{size:19,lineHeight:25,color:colors.muted});
y+=24;
for (const [heading,body] of [['CCO / mitochondria','Leading proposal; not settled'],['Nitric oxide (NO)','Binding, release or production'],['Other proposed routes','Opsins, ion channels, water interfaces']]) {
  y=await text(heading,432,y,258,{size:22,weight:700,lineHeight:28,bottom:809});
  y=await text(body,432,y+5,258,{size:20,lineHeight:25,color:colors.muted,bottom:809});
  y+=24;
}
// Signals: same four signals, without long unwrapped lines.
for (const [i,label] of ['ATP','ROS','NO','Ca2+'].entries()) {
  const x=790+(i%2)*135, yy=402+Math.floor(i/2)*76;
  rect(x,yy,123,60,['#f7f0ec','#f4eff9','#edf6f4','#fbf4e8'][i],15);
  await centered(label,x+61.5,yy+40,29,[colors.coral,colors.purple,colors.teal,colors.gold][i]);
}
y=570;
for (const s of ['ATP reflects production and use','ROS can signal; excess can harm','NO affects respiration and vessels','Ca2+ carries ion-channel signals']) {
  y=await text(s,790,y,258,{size:18,lineHeight:23,color:colors.muted,bottom:781}); y+=4;
}
await text('Direction and timing vary by context.',790,y+5,258,{size:18,weight:700,lineHeight:23,bottom:810});
// Downstream: one readable column replaces cramped two-column cells.
y=412;
for (const [heading,body] of [['Energy metabolism','ATP turnover, respiration and redox balance'],['Gene / protein activity','NF-κB, TGF-β1 and antioxidant responses'],['Cell behavior','Proliferation, migration and differentiation'],['Tissue response','Inflammation, remodeling and repair']]) {
  y=await text(heading,1148,y,368,{size:23,weight:700,lineHeight:29,bottom:778});
  y=await text(body,1148,y+2,368,{size:20,lineHeight:25,color:colors.muted,bottom:778}); y+=15;
}
await text('These downstream changes can outlast light exposure.',1148,y+7,368,{size:18,lineHeight:23,color:colors.muted,bottom:811});
// Context cards: wrap using the same renderer metrics as the exported image.
rect(58,856,1484,270,'#f7f0ec',20);
await text('FACTORS THAT SHAPE THE RESPONSE',84,898,1432,{size:22,weight:700,color:colors.coral});
const factors=[['Wavelength','810 and 980 nm implicated different routes in one cell model.'],['Dose & duration','Intensity and time may interact; some responses are biphasic.'],['Cell state','Baseline stress shifted the direction of ROS change in cultured neurons.'],['Delivery & depth','Pulsing, beam area and tissue depth shape target exposure.'],['Time & sleep','ATP and tumour outcomes differed by time or sleep in animal studies.'],['Glucose','In mouse fibroblasts, ATP/ROS changed only with glucose available.']];
for(const [i,[heading,body]] of factors.entries()) {
  const x=84+i*240; rect(x,922,228,184,'#fff',15);
  let fy=await text(heading,x+16,957,196,{size:21,weight:700,lineHeight:26,bottom:989});
  await text(body,x+16,fy+9,196,{size:18,lineHeight:23,color:colors.muted,bottom:1090});
}
await text('Proposed mechanisms and responses vary across experimental models and biological contexts.',58,1164,1484,{size:18,color:colors.muted});
parts.push('</g></svg>');
const svg=parts.join('\n');
await writeFile(new URL('pbm-mechanisms-graphical-abstract.svg',import.meta.url),svg+'\n');
const info=await sharp(Buffer.from(svg)).png({compressionLevel:9}).toFile(new URL('../dist/articles/pbm-mechanisms/graphical-abstract.png',import.meta.url).pathname);
console.log(JSON.stringify({checkedLines,dimensions:[info.width,info.height],bytes:info.size}));
