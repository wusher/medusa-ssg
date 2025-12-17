# TODOs

- Add linting (ruff/black pre-commit hook)
- Build out code pages section
- Configure GitHub Pages deployment

## GitHub Pages setup
1) Enable GitHub Actions in the repository settings.
2) Add a workflow (e.g., `.github/workflows/pages.yml`) that:
   - Checks out the repo.
   - Sets up Python 3.10+.
   - Installs dependencies: `pip install .`.
   - Builds the site: `medusa build`.
   - Uploads `output/` as a Pages artifact.
3) In GitHub Pages settings, select “GitHub Actions” as the source.
4) If you want a custom domain, add a `CNAME` file into `output/` or set it in Pages settings; ensure the CNAME matches DNS.
5) For HTTPS, keep “Enforce HTTPS” enabled once the certificate is provisioned.
