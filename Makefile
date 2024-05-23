# Builds graphbook by installing dependencies and building the web app
# Usage: make [web|docs]

# Note: Python dependencies are installed in the requirements.txt and are left to the user to install

.PHONY: all web docs

all: web docs

web:
	cd web; npm install
	cd web; npm run build

docs:
	$(MAKE) -C docs html
