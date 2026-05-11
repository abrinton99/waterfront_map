# Waterfront Photo Map

An interactive, embeddable map that displays geotagged photos as clickable pins. Built with Leaflet + OpenStreetMap. No backend or API keys required.

---

## Quick start

### 1. Generate the photo manifest

Install dependencies (once):

```bash
pip install Pillow
```

Run the script against your photo folder:

```bash
python generate_manifest.py /path/to/your/photos
```

This scans all `.jpg`, `.jpeg`, `.png`, `.heic`, and `.tiff` files, extracts GPS coordinates from EXIF data, and writes `photos.json` to the current directory.

**Optional descriptions:** place a `descriptions.csv` file inside the photo folder with two columns:

```
filename,description
DSC_0042.jpg,Morning fog over the bay
IMG_1234.jpg,Low tide at the north jetty
```

Photos without GPS data are skipped with a warning.

---

### 2. Host the photos

[GitHub Pages](https://pages.github.com/) is the recommended free host — it serves files with permissive CORS headers and supports direct file URLs.

1. Create a public GitHub repository (e.g. `yourrepo`).
2. Place your photos in a `photos/` subfolder.
3. Place `index.html` and `photos.json` at the repo root.
4. Enable GitHub Pages in **Settings → Pages → Branch: main → / (root)**.

Your files will be live at `https://yourusername.github.io/yourrepo/`.

Cloudinary is another good option. Avoid raw S3 buckets unless you configure CORS explicitly.

---

### 3. Update BASE_URL in the manifest generator

Open `generate_manifest.py` and set `BASE_URL` near the top to match your host:

```python
BASE_URL = "https://yourusername.github.io/yourrepo/photos/"
```

Then re-run the script to regenerate `photos.json` with correct URLs.

---

### 4. Replace the placeholder polygon

The map draws an outline of your geographic area and fits its initial view to it.

1. Go to **[geojson.io](https://geojson.io)**.
2. Draw a polygon around your area using the polygon tool.
3. Copy the GeoJSON from the right-hand panel.
4. Open `index.html` and find the `AREA_GEOJSON` constant (marked with a comment near the top of the `<script>` block).
5. Replace the placeholder coordinates with your copied GeoJSON.

---

### 5. Embed in Squarespace

In Squarespace, add an **Embed Block** (or a **Code Block**) and paste:

```html
<iframe
  src="https://yourusername.github.io/yourrepo/index.html"
  style="width: 100%; height: 70vh; border: 0;"
  loading="lazy"
  allow="geolocation"
></iframe>
```

Adjust the `height` value to taste (`60vh`, `80vh`, a fixed `px` value, etc.).

---

## Testing checklist

Before publishing, verify in each environment:

- [ ] **iOS Safari** — pinch-zoom works; two-finger pan works; page scroll is not hijacked by the map; popups open and display images correctly
- [ ] **Android Chrome** — same as above
- [ ] **Desktop Chrome / Firefox / Safari** — scroll-to-zoom shows the hint overlay; Ctrl+scroll zooms; popup links open in a new tab
- [ ] **Images load** — thumbnails appear in popups; full-size link opens the correct image
- [ ] **No console errors** — open DevTools → Console and confirm a clean load
- [ ] **Cluster behaviour** — zoom out to confirm nearby pins group; zoom in to ungroup
- [ ] **Polygon** — the area outline is visible and the initial view fits within it

---

## File overview

| File | Purpose |
|---|---|
| `generate_manifest.py` | Scans photos, extracts GPS EXIF, writes `photos.json` |
| `index.html` | Self-contained interactive map (Leaflet + clustering + gesture handling) |
| `photos.json` | Generated manifest — consumed by `index.html` at runtime |
| `descriptions.csv` | Optional sidecar file mapping filenames to descriptions |
