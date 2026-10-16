"""从终稿文本与计算源程序生成 build/paper/论文终稿.docx。"""
from pathlib import Path
import re,json
from docx import Document
from docx.shared import Cm,Pt,RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH,WD_BREAK
from docx.enum.section import WD_SECTION_START
from docx.enum.style import WD_STYLE_TYPE
from docx.oxml import OxmlElement,parse_xml
from docx.oxml.ns import qn
from latex2mathml.converter import convert as latex_math
from mathml2omml import convert as math_omml
ROOT=Path(__file__).resolve().parents[1]
SOURCE=ROOT/'paper/final'
OUT=ROOT/'build/paper'
OUT.mkdir(parents=True,exist_ok=True)
LAYOUT=ROOT/'paper/layout'
reference=ROOT/'docs/templates/论文写作参考模板.docx'
d=Document(reference)
body=d._element.body
for child in list(body): body.remove(child)
# Reuse template styles; define only absent roles.
for name in ['Title','Caption','Code','TOCEntry']:
 if name not in d.styles: d.styles.add_style(name,WD_STYLE_TYPE.PARAGRAPH)
for st in d.styles:
 if st.type==WD_STYLE_TYPE.PARAGRAPH:
  st.font.color.rgb=RGBColor(0,0,0)
  pr=st.element.find(qn('w:pPr'))
  if pr is not None:
   for el in list(pr):
    if el.tag in [qn('w:pBdr'),qn('w:numPr')]: pr.remove(el)
def style(name,size,east='Songti SC',bold=False):
 st=d.styles[name]; st.font.name='Times New Roman'; st.font.size=Pt(size); st.font.bold=bold; st.font.italic=False
 st._element.get_or_add_rPr().get_or_add_rFonts().set(qn('w:eastAsia'),east)
 pf=st.paragraph_format; pf.space_before=Pt(0); pf.space_after=Pt(5); pf.line_spacing=1.2; pf.first_line_indent=Cm(0)
 return st
style('Normal',11); style('Title',16,'Heiti SC',True); style('Heading 1',14,'Heiti SC',True); style('Heading 2',12,'Heiti SC',True); style('Caption',10); style('TOCEntry',11); style('Code',8)
for name in ['Heading 1','Heading 2']:
 pf=d.styles[name].paragraph_format; pf.keep_with_next=True; pf.space_before=Pt(10); pf.space_after=Pt(6)
d.styles['Code'].font.name='Menlo'; d.styles['Code'].paragraph_format.line_spacing=Pt(10); d.styles['Code'].paragraph_format.space_after=Pt(0)
sect=OxmlElement('w:sectPr'); body.append(sect)
sec=d.sections[0]
for attr in ['top_margin','bottom_margin','left_margin','right_margin']: setattr(sec,attr,Cm(2.5))
sec.page_width=Cm(21); sec.page_height=Cm(29.7); sec.footer_distance=Cm(1.25); sec.header_distance=Cm(1.25)
for s in d.sections:
 for part in [s.header,s.footer]:
  for p in part.paragraphs: p.clear()
d.core_properties.author=''; d.core_properties.last_modified_by=''; d.core_properties.title='光伏电站出力特性与融合气象信息的功率预测'
def math(p,tex):
 xml=math_omml(latex_math(tex)); el=parse_xml('<root xmlns:m="http://schemas.openxmlformats.org/officeDocument/2006/math">'+xml+'</root>')
 for rad in el.iter(qn('m:rad')):
  pr=OxmlElement('m:radPr'); hide=OxmlElement('m:degHide'); hide.set(qn('m:val'),'1'); pr.append(hide); rad.insert(0,pr); rad.insert(1,OxmlElement('m:deg'))
 for child in list(el): p._p.append(child)
def inline(p,text):
 for part in re.split(r'(\$[^$]+\$)',text):
  if part.startswith('$') and part.endswith('$'): math(p,part[1:-1])
  else: p.add_run(part.replace('`',''))
def para(text,sty='Normal'):
 p=d.add_paragraph(style=sty); inline(p,text)
 if sty=='Normal': p.paragraph_format.first_line_indent=Cm(.74)
 return p
def field(p,instr):
 r=OxmlElement('w:r'); f=OxmlElement('w:fldSimple'); f.set(qn('w:instr'),instr); r2=OxmlElement('w:r'); t=OxmlElement('w:t'); t.text='1'; r2.append(t); f.append(r2); p._p.append(f)
def new_section():
 ss=d.add_section(WD_SECTION_START.NEW_PAGE); ss.header.is_linked_to_previous=False; ss.footer.is_linked_to_previous=False
 for part in [ss.header,ss.footer]:
  for pp in part.paragraphs: pp.clear()
 return ss
text=(SOURCE/'论文终稿.md').read_text(); abstract,main=text.split('## 一、问题重述',1)
main='## 一、问题重述'+main
for line in abstract.splitlines():
 if not line.strip():continue
 if line.startswith('# '):
  p=para(line[2:],'Title'); p.alignment=WD_ALIGN_PARAGRAPH.CENTER; p.paragraph_format.space_after=Pt(14)
 elif line.startswith('作者：'):
  p=para(line); p.alignment=WD_ALIGN_PARAGRAPH.CENTER; p.paragraph_format.first_line_indent=Cm(0); p.paragraph_format.space_after=Pt(5); p.paragraph_format.line_spacing=1.0; p.paragraph_format.keep_with_next=True
  d.core_properties.author=line.removeprefix('作者：').replace('　','; ')
 elif line=='摘要':
  p=para('摘　要','Heading 1'); p.alignment=WD_ALIGN_PARAGRAPH.CENTER
 else:
  p=para(line); p.paragraph_format.space_after=Pt(7);p.paragraph_format.line_spacing=1.2
new_section(); p=para('目　录','Title');p.alignment=WD_ALIGN_PARAGRAPH.CENTER
heads=re.findall(r'^## (.+)$',main,re.M)
pages=json.loads((LAYOUT/'toc_pages.json').read_text()) if (LAYOUT/'toc_pages.json').exists() else {}
for h in heads:
 p=para(h,'TOCEntry'); p.paragraph_format.space_after=Pt(12)
 tabs=p.paragraph_format.tab_stops
 from docx.enum.text import WD_TAB_ALIGNMENT,WD_TAB_LEADER
 tabs.add_tab_stop(Cm(15.5),WD_TAB_ALIGNMENT.RIGHT,WD_TAB_LEADER.DOTS)
 p.add_run('\t'+str(pages.get(h,'—')))
sec=new_section(); n=OxmlElement('w:pgNumType'); n.set(qn('w:start'),'1'); sec._sectPr.append(n)
p=sec.footer.paragraphs[0];p.alignment=WD_ALIGN_PARAGRAPH.CENTER; field(p,'PAGE')
def splitrow(s):
 chunks=[]
 def save(m):chunks.append(m.group(0));return f'@@M{len(chunks)-1}@@'
 s=re.sub(r'\$[^$]+\$',save,s)
 cells=s.strip().strip('|').split('|')
 return [re.sub(r'@@M(\d+)@@',lambda m:chunks[int(m.group(1))],v.strip()) for v in cells]
def table(lines):
 rows=[splitrow(l) for l in lines if not re.match(r'^\|[\s:|\-]+\|$',l)]
 n=len(rows[0]);assert all(len(row)==n for row in rows),rows
 t=d.add_table(rows=0,cols=n);t.autofit=False
 widths=([3,13] if n==2 else ([2.8,11.6,1.6] if rows[0][0]=='符号' else [5,5.5,5.5]) if n==3 else ([3.5]+[(16-3.5)/(n-1)]*(n-1)))
 for col,w in zip(t.columns,widths):col.width=Cm(w)
 for ri,row in enumerate(rows):
  cells=t.add_row().cells
  for ci,(c,txt) in enumerate(zip(cells,row)):
   c.width=Cm(widths[ci]); p=c.paragraphs[0];p.alignment=WD_ALIGN_PARAGRAPH.LEFT;p.paragraph_format.space_after=Pt(4);p.paragraph_format.space_before=Pt(4);p.paragraph_format.line_spacing=1.05
   inline(p,txt)
   for run in p.runs:run.font.size=Pt(9 if n>=6 else 10);run.font.bold=ri==0
   tcpr=c._tc.get_or_add_tcPr(); borders=OxmlElement('w:tcBorders')
   for edge in ['top','left','bottom','right']:
    b=OxmlElement('w:'+edge); b.set(qn('w:val'),'single' if (edge=='top' and ri==0) or (edge=='bottom' and ri in [0,len(rows)-1]) else 'nil');b.set(qn('w:sz'),'6');borders.append(b)
   tcpr.append(borders)
  trpr=t.rows[-1]._tr.get_or_add_trPr();trpr.append(OxmlElement('w:cantSplit'))
  if ri==0:trpr.append(OxmlElement('w:tblHeader'))
  if len(rows)<=6 and ri<len(rows)-1:
   for c in cells:
    for p in c.paragraphs:p.paragraph_format.keep_with_next=True
 d.add_paragraph().paragraph_format.space_after=Pt(0)
lines=main.splitlines();i=0;eq=0
while i<len(lines):
 line=lines[i].strip();i+=1
 if not line:continue
 if line.startswith('## '):
  h=line[3:]
  if h in ['参考文献','附录']: d.add_page_break()
  p=para(h,'Heading 1')
  if h=='四、符号说明':p.paragraph_format.page_break_before=True
 elif line.startswith('### '):para(line[4:],'Heading 2')
 elif line.startswith('|'):
  ls=[line]
  while i<len(lines) and lines[i].startswith('|'):ls.append(lines[i]);i+=1
  table(ls)
 elif line.startswith('$$'):
  eq+=1;p=d.add_paragraph();p.alignment=WD_ALIGN_PARAGRAPH.CENTER;p.paragraph_format.space_after=Pt(8)
  math(p,line.strip('$'));p.add_run(f'　（{eq}）')
 elif line.startswith('!['):
  path=re.search(r'\]\((.*?)\)',line).group(1);path=(SOURCE/path).resolve()
  p=d.add_paragraph();p.alignment=WD_ALIGN_PARAGRAPH.CENTER;p.paragraph_format.keep_with_next=True;p.add_run().add_picture(str(path),width=Cm(15.8))
 elif re.match(r'^[图表] \d+',line):
  p=para(line,'Caption');p.alignment=WD_ALIGN_PARAGRAPH.CENTER;p.paragraph_format.keep_with_next=line.startswith('表')
 elif line.startswith('```'):
  while i<len(lines) and not lines[i].startswith('```'):
   para(lines[i],'Code');i+=1
  i+=1
 else:para(line)
# Fully include all computational and test sources, retaining every character.
def chunks_visual(line,limit=94):
 acc='';w=0
 for ch in line.expandtabs(4):
  cw=2 if ord(ch)>255 else 1
  if w+cw>limit:yield acc;acc='';w=0
  acc+=ch;w+=cw
 yield acc
for f in sorted((ROOT/'src').glob('*.py'))+sorted((ROOT/'tests').glob('*.py')):
 d.add_page_break();para(str(f.relative_to(ROOT)),'Heading 2')
 for line in f.read_text().splitlines():
  p=d.add_paragraph(style='Code')
  for j,part in enumerate(chunks_visual(line)):
   if j:p.add_run().add_break()
   p.add_run(part)
# Remove inherited headers, paragraph borders and red source-format metadata.
for sec in d.sections:
 for p in sec.header.paragraphs:p.clear()
for st in d.styles:
 if st.type==WD_STYLE_TYPE.PARAGRAPH:
  st.font.color.rgb=RGBColor(0,0,0)
settings=d.settings.element
u=OxmlElement('w:updateFields');u.set(qn('w:val'),'false');settings.append(u)
d.save(OUT/'论文终稿.docx')
print('saved',len(d.paragraphs),'paragraphs',len(d.tables),'tables',eq,'equations')
