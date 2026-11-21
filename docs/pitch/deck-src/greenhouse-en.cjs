// Build with pptxgenjs 3.12.0. Export the same PPTX to PDF in PowerPoint.
const pptxgen = require(process.env.SUTECH_PPTXGENJS || 'pptxgenjs');
const pptx = new pptxgen();
pptx.layout = 'LAYOUT_WIDE';
pptx.title = 'Su-Tech greenhouse irrigation pilot';
pptx.author = 'Su-Tech';
pptx.lang = 'en-US';

const ink = '143A2D', green = '146B4A', light = 'F3F7F1', muted = '48695D', lime = 'B9E474';
const T = (slide, text, x, y, w, h, fontSize, options = {}) => slide.addText(text, {
  x,y,w,h,fontSize,fontFace:'Aptos',margin:0,breakLine:false,color:ink,valign:'mid',...options,
});
const rect = (slide,x,y,w,h,color) => slide.addShape(pptx.ShapeType.rect,{x,y,w,h,line:{transparency:100},fill:{color}});
function frame(label,title){
  const slide=pptx.addSlide();slide.background={color:light};
  rect(slide,.62,.49,.43,.1,green);T(slide,label,1.16,.39,11,.28,12,{bold:true,color:green});
  T(slide,title,.62,.92,12.1,.84,35,{bold:true});
  rect(slide,.62,7.01,12.1,.015,'CDDAD0');
  T(slide,'SU-TECH  /  GREENHOUSE PILOT',.62,7.10,10,.20,9,{bold:true,color:muted});
  T(slide,String(pptx._slides.length).padStart(2,'0'),12.07,7.10,.65,.2,9,{align:'right',color:muted});
  return slide;
}
function row(slide,y,heading,body){
  rect(slide,.63,y,.055,.90,green);T(slide,heading,.85,y,3.02,.83,21,{bold:true});
  T(slide,body,4.02,y,8.48,.9,19,{color:muted});
}

{
 const s=pptx.addSlide();s.background={color:ink};
 rect(s,.66,.58,.48,.105,lime);
 T(s,'SU-TECH',1.26,.42,7,.41,18,{color:lime,bold:true});
 T(s,'Irrigation advice\nfor soil greenhouses',.68,1.40,11.65,2.34,51,{color:'FFFFFF',bold:true});
 T(s,'A working demo and a proposed measurement pilot',.7,4.16,11,.55,23,{color:'DAE9DF'});
 T(s,'Student project · November 2026',.7,6.83,11,.28,13,{color:'DAE9DF'});
}
{
 const s=frame('WORKED EXAMPLES','Three greenhouse cases');
 row(s,2.05,'Unheated soil','The worked tomato example estimates indoor ET₀ as 70% of outdoor ET₀. Outdoor rain is excluded.');
 row(s,3.42,'Heated soil','Use measured indoor ET₀. The demo uses an illustrative 2.6 mm/day to show how the input works.');
 row(s,4.79,'Substrate','The soil balance withholds irrigation advice. Discuss drainage and conductivity with your agronomist.');
 T(s,'Open the browser demo to reproduce all three cases.',.86,6.35,11.7,.35,15,{color:green,bold:true,
   hyperlink:{url:'https://app8796056339.tgcloud.ai/demo.html?example=greenhouse&lang=en'}});
}
{
 const s=frame('EVIDENCE','What can be verified today');
 row(s,2.05,'Calculation','The browser and bot use the same FAO-56-based engine. Review water volume, root-zone assumptions and the reason for the recommendation.');
 row(s,3.42,'Simulation','15–28% water savings appeared in selected historical cotton and maize simulations with specified baselines and yield assumptions.');
 row(s,4.79,'Greenhouse pilot','Greenhouse savings and accuracy still require measurements of applied water, soil condition and crop outcomes.');
 T(s,'The code was written with an AI assistant.',.86,6.35,11.7,.35,15,{color:green,bold:true});
}
{
 const s=frame('ILLUSTRATIVE ECONOMICS','What changes the seasonal cost?');
 const format={x:.63,y:1.99,w:12.07,h:3.4,colW:[3.73,2.71,2.81,2.82],rowH:.46,
   fontSize:16,fontFace:'Aptos',border:{type:'solid',pt:.6,color:'D3DED3'},margin:[4,9,4,9],color:ink};
 const header=['Seasonal inputs','Calendar','Su-Tech / same pump','Su-Tech / new pump'].map(text=>({text,options:{color:'FFFFFF',fill:green,bold:true}}));
 const data=[header,['Water, m³','120','102','102'],['Electricity, kWh','24.0','20.4','15.3'],['Labour, h','12','11','11'],
   ['Service + equipment, KZT','0','1,200','1,700'],['Total, KZT','24,720','23,412','23,759']];
 s.addTable(data,format);
 T(s,'Assumed rates: 50 KZT/m³, 30 KZT/kWh, 1,500 KZT/h. Pump flow: 2 m³/h.',.72,5.34,11.9,.45,17,{color:muted});
 T(s,'Same pump: −1,308 KZT. Pump swap alone: +347 KZT after equipment cost.',.72,5.99,11.9,.50,20,{bold:true,color:green});
}
{
 const s=frame('FIELD DISCUSSION','Agree on the pilot before measuring');
 row(s,2.05,'Characterize','Crop and variety, rooting medium, greenhouse heating, current schedule and how water is measured.');
 row(s,3.42,'Compare','Keep hardware and crop conditions comparable. Record applied water, drainage where relevant, and comparable crop outcomes.');
 row(s,4.79,'Decide','Agree on dates and the minimum acceptable crop outcome before the first observation. Discuss when to stop the trial.');
}
{
 const s=frame('PRIMARY REFERENCES','Where the method comes from');
 for(const [i,[title,description,url]] of [
   ['FAO Irrigation and Drainage Paper 56','Allen, Pereira, Raes & Smith (1998). Reference ET, crop coefficients and the root-zone water balance.','https://www.fao.org/4/x0490e/x0490e00.htm'],
   ['FAO Irrigation and Drainage Paper 66','Steduto, Hsiao, Fereres & Raes (2012). Chapter 2 presents the original FAO yield-response equation.','https://www.fao.org/4/i2800e/i2800e02.pdf'],
   ['Pump Life Cycle Costs','Hydraulic Institute, Europump and US DOE. Energy and equipment costs at the operating point.','https://www.energy.gov/sites/prod/files/2014/05/f16/pumplcc_1001.pdf'],
 ].entries()){
   const y=2.0+i*1.35;T(s,title,.83,y,11.1,.35,21,{bold:true,color:green,hyperlink:{url}});
   T(s,description,.83,y+.40,11.1,.52,18,{color:muted});
 }
}

pptx.writeFile({fileName:process.argv[2] || 'Su-Tech-Greenhouse-EN.pptx'}).catch(error=>{console.error(error);process.exitCode=1;});
