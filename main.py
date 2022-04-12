import os

import sources.dev_diary as dd
import markdown

from util import get_output_dir

all_items = dd.grab_all()

out_fname = os.path.join(get_output_dir(), 'index.html')
out_file = open(out_fname, 'w')

def writeout(stri):
    print(stri, file=out_file)

writeout("""
<!DOCTYPE html> 
<html>
 
   <head> 
      <title>HTML Internal CSS</title> 
      
      <style type = "text/css"> 
         img { 
          display: block;
          margin-left: auto;
          margin-right: auto;
          width: 50%;
         } 
         .dev-item{ 
            
          width: 950px;
          margin: auto;
          border: 3px solid #4287f5;
          border-radius: 10px;
         } 
      </style> 
   </head>
	
   <body> 
""")

for item in all_items:
    md = item.as_markdown()
    classname = item.__class__.__name__.lower()
    writeout(f"""<div class="dev-item {classname}">""")
    writeout(markdown.markdown(md))
    writeout(r"</div>")
    writeout("\n\n")


writeout("</body></html>")
