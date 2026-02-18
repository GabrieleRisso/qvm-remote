PAPER    = qvm-remote
DEMO     = ../demo
DOCS     = $(HOME)/Documents/qvm-remote

.PHONY: all paper diagrams posts sync clean

all: paper diagrams posts sync

paper: $(PAPER).pdf

$(PAPER).pdf: $(PAPER).tex
	pdflatex -interaction=nonstopmode $(PAPER).tex
	pdflatex -interaction=nonstopmode $(PAPER).tex

diagrams:
	python3 $(DEMO)/generate-diagrams.py $(DEMO)/

posts:
	mkdir -p $(DOCS)/posts
	python3 $(DEMO)/generate-posts.py $(DOCS)/posts/

sync: $(PAPER).pdf
	mkdir -p $(DOCS)/diagrams $(DOCS)/posts
	cp $(PAPER).pdf $(PAPER).tex posts.md blog-qvm-remote.md $(DOCS)/
	cp $(DEMO)/architecture.png $(DEMO)/security.png $(DEMO)/auth-flow.png $(DEMO)/queue-states.png $(DOCS)/diagrams/

clean:
	rm -f $(PAPER).aux $(PAPER).log $(PAPER).out $(PAPER).pdf

help:
	@echo "Targets:"
	@echo "  all       - Build everything and sync to ~/Documents"
	@echo "  paper     - Compile LaTeX (two passes for refs)"
	@echo "  diagrams  - Regenerate PNG architecture diagrams"
	@echo "  posts     - Regenerate social media card PNGs"
	@echo "  sync      - Copy all outputs to ~/Documents/qvm-remote/"
	@echo "  clean     - Remove LaTeX build artifacts"
