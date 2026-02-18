# qvm-remote Publication Assets

## Build Requirements

| Dependency | Package (Fedora) | Purpose |
|------------|-----------------|---------|
| `pdflatex` | `texlive-latex` | Compile LaTeX paper |
| `python3` | `python3` | Run diagram/post generators |
| `Pillow` | `python3-pillow` | Image generation library |
| TikZ packages | `texlive-pgf`, `texlive-tikz` | LaTeX diagrams |
| `amssymb` | `texlive-amsfonts` | Math symbols |

## Build

```bash
cd paper/
make all      # Build everything and sync to ~/Documents
make paper    # Just recompile the PDF
make diagrams # Just regenerate diagram PNGs
make posts    # Just regenerate social media cards
make sync     # Copy outputs to ~/Documents/qvm-remote/
```

## Generated Files

### Paper (`paper/`)

| File | Type | Description |
|------|------|-------------|
| `qvm-remote.tex` | LaTeX source | Main paper (6 TikZ diagrams embedded) |
| `qvm-remote.pdf` | PDF | Compiled paper (~8 pages, 40+ references) |
| `posts.md` | Markdown | Social media content: X threads, LinkedIn, Dev.to, HN, Reddit |
| `blog-qvm-remote.md` | Markdown | Website-ready blog post with frontmatter |
| `Makefile` | Make | Build automation for all assets |

### Diagrams (`demo/`)

| File | Dimensions | Description | Use |
|------|-----------|-------------|-----|
| `architecture.png` | 1200x675 | Pull-model protocol architecture | README, LinkedIn |
| `security.png` | 1200x675 | Five security layers | X post, r/netsec |
| `auth-flow.png` | 1200x675 | HMAC-SHA256 authentication flow | Dev.to, blog |
| `queue-states.png` | 1200x675 | Command queue state machine | Technical blog |

### Social Media Cards (`~/Documents/qvm-remote/posts/`)

| File | Dimensions | Description | Platform |
|------|-----------|-------------|----------|
| `post-1.png` | 1200x675 | Architecture overview | X post 1/3 |
| `post-2.png` | 1200x675 | Security layers diagram | X post 2/3 |
| `post-3.png` | 1200x675 | Terminal demo session | X post 3/3 |

### Content Formats in `posts.md`

| Format | Audience | Length |
|--------|----------|--------|
| X/Twitter thread (3 posts) | General tech | ~280 chars each |
| LinkedIn article | Professional network | ~800 words |
| Blog post | Website visitors | ~1200 words |
| Dev.to / Medium article | Developer community | ~500 words |
| Hacker News submission | HN community | Title + comment |
| Reddit posts (4 subreddits) | r/QubesOS, r/netsec, r/crypto | ~200 words each |

## Synced Output (`~/Documents/qvm-remote/`)

```
~/Documents/qvm-remote/
├── qvm-remote.pdf          # Paper
├── qvm-remote.tex          # Source
├── posts.md                # Social media content
├── blog-qvm-remote.md      # Blog post
├── diagrams/
│   ├── architecture.png
│   ├── security.png
│   ├── auth-flow.png
│   └── queue-states.png
└── posts/
    ├── post-1.png
    ├── post-2.png
    └── post-3.png
```

## Citation

```bibtex
@misc{risso2026qvmremote,
  author = {Risso, Gabriele},
  title  = {qvm-remote: Authenticated Remote Execution in Qubes OS dom0 via File-Based Queues},
  year   = {2026},
  url    = {https://github.com/GabrieleRisso/qvm-remote}
}
```
