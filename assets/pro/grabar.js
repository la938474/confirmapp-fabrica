// node assets/pro/grabar.js <pagina.html> <segundos> <salida.mp4>  → 1080x1920 a 30 fps, cuadro por cuadro con pintar(t)
// Para ver cuadros sueltos antes: node assets/pro/grabar.js <pagina.html> --fotos 0 4.5 12 <carpeta>
const {chromium}=require('playwright'),{execFileSync}=require('child_process'),fs=require('fs'),path=require('path');
(async()=>{const a=process.argv.slice(2),html=path.resolve(a[0]);
 const b=await chromium.launch(),p=await b.newPage({viewport:{width:1080,height:1920}});
 let src=fs.readFileSync(html,'utf8');
 const icon=path.resolve(__dirname,'..','icon-192.png');src=src.replace('src="ICON"','src="data:image/png;base64,'+fs.readFileSync(icon).toString('base64')+'"');
 const tmp=html.replace(/\.html$/,'')+'.tmp.html';fs.writeFileSync(tmp,src);
 await p.goto('file://'+tmp);await p.waitForTimeout(400);
 if(a[1]==='--fotos'){const dir=a[a.length-1];fs.mkdirSync(dir,{recursive:true});
   for(const t of a.slice(2,-1)){await p.evaluate(t=>pintar(t),parseFloat(t));await p.screenshot({path:`${dir}/t${t}.jpg`,type:'jpeg',quality:85});}
 }else{const D=parseFloat(a[1]),N=Math.round(D*30),out=a[2],dir=out+'.cuadros';fs.rmSync(dir,{recursive:true,force:true});fs.mkdirSync(dir,{recursive:true});
   for(let i=0;i<N;i++){await p.evaluate(t=>pintar(t),i/30);await p.screenshot({path:`${dir}/${String(i).padStart(4,'0')}.jpg`,type:'jpeg',quality:92});}
   execFileSync('ffmpeg',['-y','-v','error','-framerate','30','-i',`${dir}/%04d.jpg`,'-c:v','libx264','-preset','medium','-pix_fmt','yuv420p','-crf','20',out.replace(/\.mp4$/,'.tmp.mp4')]);
   fs.renameSync(out.replace(/\.mp4$/,'.tmp.mp4'),out);fs.rmSync(dir,{recursive:true,force:true});}
 await b.close();fs.rmSync(tmp,{force:true});})();
