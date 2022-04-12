
build:
	python ./main.py > index.html

clean:
	rm -rf images
	rm -rf .cache
	rm index.html

publish_gh: build
	cp index.html /tmp/v3_index.html
	git checkout gh_pages
	cp /tmp/v3_index.html index.html
	git add index.html
	git commit -m "Update gh_pages"
	git push
	git checkout master
