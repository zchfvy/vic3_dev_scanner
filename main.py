from util import get_cache_dir, get_page_cached, cache_result

import sources.dev_diary as dd
import markdown

all_items = dd.grab_all()

print("""
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
    print(f"""<div class="dev-item {classname}">""")
    print(markdown.markdown(md))
    print(r"</div>")
    print("\n\n")


print("</body></html>")
