# Builds graphbook by installing dependencies and building the web app
# Usage: make [web|docs|package]

# Note: Python dependencies are installed in the requirements.txt and are left to the user to install

.PHONY: all web docs package

all: web docs package

web:
	cd web; npm install
	cd web; npm run build

docs:
	$(MAKE) -C docs html

package: web
	cp -r web/dist graphbook/web
	poetry build
	rm -r graphbook/web
