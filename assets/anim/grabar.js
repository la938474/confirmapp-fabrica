// node grabar.js <html> <query> <segundos> <salida.mp4>  → video 780x1688 a 30 fps, cuadro por cuadro (determinista)
// (ANCHO y ALTO en el entorno cambian el tamaño, p. ej. 1080x1920 para fondo.html)
const {chromium}=require('playwright'), {execFileSync}=require('child_process'), fs=require('fs'), path=require('path');
(async()=>{
  const [html,q,seg,out]=process.argv.slice(2), D=parseFloat(seg), N=Math.round(D*30), dir=out+'.frames';
  fs.rmSync(dir,{recursive:true,force:true}); fs.mkdirSync(dir,{recursive:true});
  const b=await chromium.launch(), p=await b.newPage({viewport:{width:+(process.env.ANCHO||780),height:+(process.env.ALTO||1688)}});
  await p.goto('file://'+path.resolve(html)+'?'+q); await p.waitForTimeout(300);
  for(let i=0;i<N;i++){ await p.evaluate(([t,D])=>pintar(t,D),[i/30,D]);
    await p.screenshot({path:`${dir}/${String(i).padStart(4,'0')}.jpg`,type:'jpeg',quality:92}); }
  await b.close();
  execFileSync('ffmpeg',['-y','-v','error','-framerate','30','-i',`${dir}/%04d.jpg`,'-c:v','libx264','-pix_fmt','yuv420p','-crf','18',out]);
  fs.rmSync(dir,{recursive:true,force:true});
})();
