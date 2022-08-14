
build:
	python ./main.py

clean: clean_html

clean_all: clean_cache clean_output

# Misc actions

clean_html:
	rm -rf .cache/web

clean_cache:
	rm -rf .cache

clean_output:
	rm -rf output

publish_gh: build
	git checkout gh_pages
	cp -r ./output/* ./
	git add index.html images thumbs
	git add 
	git commit -m "Update gh_pages"
	git push
	git checkout master


publish_cp:


output.zip: build
	zip -r output.zip output/*
