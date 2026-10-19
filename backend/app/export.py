"""Publishing (F19-F21): PDF, self-contained animated web page, EPUB,
PNG set, and .mov video - one function per format, each taking a Novella
and an output path and writing exactly that file.

Layout choice (recorded here since there's no DECISIONS.md yet): one scene
per page/frame, image full-bleed with the scene summary as a caption box
in the top-left corner echoing the app's own Panel lettering style
(parchment background, hard shadow) - the simplest reading of spec 5.7's
"choose a simple default" for comic-page layout, applied consistently
across every format rather than inventing a different layout per export.
"""

import base64
import html
import shutil
import subprocess
import tempfile
import textwrap
import zipfile
from pathlib import Path

from ebooklib import epub
from PIL import Image
from reportlab.lib.pagesizes import letter
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas

from .models import Novella

CAPTION_BG = (240, 233, 224)  # cream-dark
INK = (14, 13, 12)
SECONDS_PER_SCENE = 3  # .mov: minimal acceptable default per spec 5.7


def _illustrated_scenes(novella: Novella) -> list:
    return [s for s in novella.scenes if s.image_path]


def _scene_image_path(data_dir: Path, novella: Novella, scene) -> Path:
    return data_dir / "images" / novella.id / f"{scene.id}.png"


def export_pdf(novella: Novella, data_dir: Path, output_path: Path) -> None:
    scenes = _illustrated_scenes(novella)
    if not scenes:
        raise ValueError("No generated images to publish yet")

    c = canvas.Canvas(str(output_path), pagesize=letter)
    page_w, page_h = letter

    for scene in scenes:
        img_path = _scene_image_path(data_dir, novella, scene)
        if not img_path.exists():
            continue
        reader = ImageReader(str(img_path))
        iw, ih = reader.getSize()
        scale = min(page_w / iw, page_h / ih)
        draw_w, draw_h = iw * scale, ih * scale
        x, y = (page_w - draw_w) / 2, (page_h - draw_h) / 2
        c.drawImage(reader, x, y, width=draw_w, height=draw_h)

        # Caption box, top-left, echoing the app's own lettering style.
        caption = scene.summary or ""
        if caption:
            c.setFont("Helvetica-Oblique", 11)
            lines = textwrap.wrap(caption, width=70)[:3]
            box_w = min(page_w - 80, 420)
            box_h = 18 * len(lines) + 14
            box_x, box_y = x + 12, y + draw_h - box_h - 12
            c.setFillColorRGB(*(v / 255 for v in CAPTION_BG))
            c.rect(box_x, box_y, box_w, box_h, fill=1, stroke=1)
            c.setFillColorRGB(*(v / 255 for v in INK))
            for i, line in enumerate(lines):
                c.drawString(box_x + 8, box_y + box_h - 16 - (i * 16), line)
        c.showPage()

    c.save()


def export_png_set(novella: Novella, data_dir: Path, output_path: Path) -> None:
    scenes = _illustrated_scenes(novella)
    if not scenes:
        raise ValueError("No generated images to publish yet")

    with zipfile.ZipFile(output_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for i, scene in enumerate(scenes, start=1):
            img_path = _scene_image_path(data_dir, novella, scene)
            if img_path.exists():
                zf.write(img_path, arcname=f"scene_{i:02d}{img_path.suffix}")


def export_epub(novella: Novella, data_dir: Path, output_path: Path) -> None:
    scenes = _illustrated_scenes(novella)
    if not scenes:
        raise ValueError("No generated images to publish yet")

    book = epub.EpubBook()
    book.set_identifier(novella.id)
    book.set_title(novella.title)
    book.set_language("en")

    chapters = []
    for i, scene in enumerate(scenes, start=1):
        img_path = _scene_image_path(data_dir, novella, scene)
        if not img_path.exists():
            continue
        image_filename = f"images/scene_{i:02d}.png"
        book.add_item(
            epub.EpubItem(
                uid=f"img_{i}",
                file_name=image_filename,
                media_type="image/png",
                content=img_path.read_bytes(),
            )
        )
        chapter = epub.EpubHtml(
            title=f"Scene {i}", file_name=f"scene_{i:02d}.xhtml", lang="en"
        )
        chapter.content = (
            f"<html><body>"
            f"<img src='{image_filename}' style='max-width:100%' />"
            f"<p><em>{html.escape(scene.summary or '')}</em></p>"
            f"</body></html>"
        )
        book.add_item(chapter)
        chapters.append(chapter)

    book.toc = chapters
    book.add_item(epub.EpubNcx())
    book.add_item(epub.EpubNav())
    book.spine = ["nav"] + chapters
    epub.write_epub(str(output_path), book)


def export_animated_web(novella: Novella, data_dir: Path, output_path: Path) -> None:
    """Self-contained single HTML file - everything (images, styles, script)
    embedded inline, no network access needed to view it, per spec 5.7.
    Generic font stacks only (no Google Fonts CDN) so it still renders
    correctly completely offline."""
    scenes = _illustrated_scenes(novella)
    if not scenes:
        raise ValueError("No generated images to publish yet")

    slides = []
    for scene in scenes:
        img_path = _scene_image_path(data_dir, novella, scene)
        if not img_path.exists():
            continue
        b64 = base64.b64encode(img_path.read_bytes()).decode("ascii")
        caption = html.escape(scene.summary or "")
        slides.append(
            f'<div class="slide"><img src="data:image/png;base64,{b64}" alt="{caption}">'
            f'<p class="caption">{caption}</p></div>'
        )

    html_doc = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>{html.escape(novella.title)}</title>
<style>
  body {{ margin: 0; background: #0E0D0C; font-family: Georgia, "Times New Roman", serif; }}
  .slideshow {{ position: relative; width: 100vw; height: 100vh; overflow: hidden; }}
  .slide {{ position: absolute; inset: 0; opacity: 0; transition: opacity 1.2s ease; display: flex;
            align-items: center; justify-content: center; flex-direction: column; }}
  .slide.active {{ opacity: 1; }}
  .slide img {{ max-width: 92vw; max-height: 82vh; object-fit: contain; box-shadow: 0 30px 80px rgba(0,0,0,.6); }}
  .caption {{ color: #FAF6F1; font-style: italic; font-size: clamp(14px, 2vw, 20px); margin-top: 16px;
              max-width: 70vw; text-align: center; }}
  .title {{ position: fixed; top: 24px; left: 32px; color: #D4246E; font-size: 14px;
            letter-spacing: .14em; text-transform: uppercase; font-family: sans-serif; }}
</style>
</head>
<body>
<div class="title">{html.escape(novella.title)}</div>
<div class="slideshow">
  {''.join(slides)}
</div>
<script>
  const slides = document.querySelectorAll('.slide');
  let i = 0;
  slides[0]?.classList.add('active');
  setInterval(() => {{
    slides[i].classList.remove('active');
    i = (i + 1) % slides.length;
    slides[i].classList.add('active');
  }}, {SECONDS_PER_SCENE * 1000});
</script>
</body>
</html>"""
    output_path.write_text(html_doc, encoding="utf-8")


def ffmpeg_available() -> bool:
    return shutil.which("ffmpeg") is not None


def export_mov(novella: Novella, data_dir: Path, output_path: Path) -> None:
    if not ffmpeg_available():
        raise ValueError(
            "ffmpeg is not installed - install it (e.g. `brew install ffmpeg`) to "
            "enable video export"
        )
    scenes = _illustrated_scenes(novella)
    if not scenes:
        raise ValueError("No generated images to publish yet")

    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        concat_lines = []
        last_frame_name = None
        for i, scene in enumerate(scenes):
            img_path = _scene_image_path(data_dir, novella, scene)
            if not img_path.exists():
                continue
            # ffmpeg's concat demuxer needs every frame to share one size -
            # pad/crop each source image onto a fixed canvas up front rather
            # than fighting per-source aspect ratios inside the filter graph.
            frame = Image.open(img_path).convert("RGB")
            canvas_img = Image.new("RGB", (1024, 1024), (14, 13, 12))
            frame.thumbnail((1024, 1024))
            offset = ((1024 - frame.width) // 2, (1024 - frame.height) // 2)
            canvas_img.paste(frame, offset)
            frame_path = tmp_path / f"frame_{i:03d}.png"
            canvas_img.save(frame_path)
            last_frame_name = frame_path.name
            concat_lines.append(f"file '{last_frame_name}'")
            concat_lines.append(f"duration {SECONDS_PER_SCENE}")
        # ffmpeg's concat demuxer ignores the last entry's duration, so the
        # final file must be repeated once more with no duration line or
        # the last frame's hold time is silently dropped.
        if last_frame_name:
            concat_lines.append(f"file '{last_frame_name}'")

        concat_file = tmp_path / "concat.txt"
        concat_file.write_text("\n".join(concat_lines))

        result = subprocess.run(
            [
                "ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(concat_file),
                "-vf", "fps=24,format=yuv420p", "-c:v", "libx264", "-movflags", "+faststart",
                str(output_path),
            ],
            cwd=tmp_path,
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            raise ValueError(f"ffmpeg failed: {result.stderr[-500:]}")
