
build:
	python ./main.py

clean:
	rm -rf images
	rm -rf .cache
	rm index.html

publish_gh: build
	git checkout gh_pages
	cp -r ./output/* ./
	git add index.html images thumbs
	git add 
	git commit -m "Update gh_pages"
	git push
	git checkout master
