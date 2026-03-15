# Builds graphbook by installing dependencies and building the web app
# Usage: make [web|web-beta|docs|package]

# Note: Python dependencies are installed in the requirements.txt and are left to the user to install

.PHONY: all web web-beta docs package

all: web web-beta docs package

web:
	cd web; npm install
	cd web; npm run build

web-beta:
	cd web_beta; npm install
	cd web_beta; npm run build

docs:
	$(MAKE) -C docs html

package: web web-beta
	cp -r web/dist graphbook/web
	cp -r web_beta/dist/* graphbook/beta/server/static/
	uv build
	rm -r graphbook/web
