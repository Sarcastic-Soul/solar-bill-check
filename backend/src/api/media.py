"""Turn an uploaded bill (image or PDF bytes) into Bedrock Converse content blocks.

- File type comes from the bytes (magic numbers), not the name or the upload's content type.
- Images: EXIF rotation applied, long side cut to MAX_EDGE px, re-encoded as JPEG under ~3.5 MB.
- PDFs: pages 1-2 rendered to JPEG with pypdfium2. If pypdfium2 can't load, the PDF is sent as a
  Converse document block instead (only some models accept that; the others fail and the merge
  step carries on with whichever model answered).
- HEIC/HEIF/AVIF: rejected with a clear message (no decoder in the Lambda).
"""

from __future__ import annotations

import io

from .errors import ApiError

MAX_EDGE = 2000
PDF_PAGES = 2
MAX_IMAGE_BYTES = 3_500_000  # Bedrock's limit is 3.75 MB per image


class MediaError(ApiError):
    pass


def sniff(data: bytes) -> str:
    """'jpeg' | 'png' | 'webp' | 'pdf' | 'heic' | 'unknown'."""
    head = data[:16]
    if head.startswith(b"\xff\xd8\xff"):
        return "jpeg"
    if head.startswith(b"\x89PNG\r\n\x1a\n"):
        return "png"
    if head[:4] == b"RIFF" and head[8:12] == b"WEBP":
        return "webp"
    if data[:1024].lstrip().startswith(b"%PDF") or b"%PDF-" in data[:1024]:
        return "pdf"
    if head[4:8] == b"ftyp" and head[8:12] in (b"heic", b"heix", b"hevc", b"hevx", b"heim", b"heis", b"mif1",
                                                b"msf1", b"avif", b"avis"):
        return "heic"
    return "unknown"


def prep_image(data: bytes, max_edge: int = MAX_EDGE) -> tuple[bytes, tuple[int, int]]:
    from PIL import Image, ImageOps

    Image.MAX_IMAGE_PIXELS = 60_000_000  # ~8k x 7.5k; anything bigger is not a phone photo of a bill
    try:
        im = Image.open(io.BytesIO(data))
        im = ImageOps.exif_transpose(im)
    except Exception as e:  # PIL raises many types for broken files
        raise MediaError("IMAGE_UNREADABLE", "We couldn't open this image. Try another photo or a screenshot.") from e
    if im.mode not in ("RGB", "L"):
        im = im.convert("RGB")
    if max(im.size) > max_edge:
        im.thumbnail((max_edge, max_edge), Image.LANCZOS)
    q = 90
    while True:
        buf = io.BytesIO()
        im.save(buf, "JPEG", quality=q)
        if buf.tell() < MAX_IMAGE_BYTES or q <= 50:
            return buf.getvalue(), im.size
        q -= 10


def pdf_pages(data: bytes, max_pages: int = PDF_PAGES, max_edge: int = MAX_EDGE) -> list[bytes]:
    import pypdfium2 as pdfium

    try:
        pdf = pdfium.PdfDocument(data)
    except pdfium.PdfiumError as e:
        if "password" in str(e).lower() or getattr(e, "err_code", None) == 4:
            raise MediaError("PDF_PASSWORD_PROTECTED",
                             "This PDF is password protected. Remove the password or upload a screenshot.") from e
        raise MediaError("PDF_UNREADABLE", "We couldn't open this PDF. Try a screenshot of the bill instead.") from e
    try:
        out = []
        for i in range(min(max_pages, len(pdf))):
            page = pdf[i]
            w, h = page.get_size()
            scale = min(200 / 72, max_edge / max(w, h))
            pil = page.render(scale=scale).to_pil()
            out.append(prep_image_from_pil(pil))
        if not out:
            raise MediaError("PDF_EMPTY", "This PDF has no pages.")
        return out
    finally:
        pdf.close()


def prep_image_from_pil(im) -> bytes:
    if im.mode not in ("RGB", "L"):
        im = im.convert("RGB")
    buf = io.BytesIO()
    im.save(buf, "JPEG", quality=88)
    return buf.getvalue()


def content_blocks(data: bytes) -> tuple[list[dict], dict]:
    """Return (Converse content blocks, info about the input for the response)."""
    kind = sniff(data)
    if kind == "heic":
        raise MediaError("HEIC_NOT_SUPPORTED",
                         "iPhone HEIC photos aren't supported. Upload a JPEG/PNG (or a screenshot of the photo), or "
                         "set Camera > Formats > Most Compatible.", status=415)
    if kind == "unknown":
        raise MediaError("UNSUPPORTED_FILE", "Upload a JPEG, PNG or WebP photo, or a PDF of the bill.", status=415)
    if kind == "pdf":
        try:
            pages = pdf_pages(data)
        except ImportError:  # renderer missing: let models that accept documents read the PDF directly
            return ([{"document": {"format": "pdf", "name": "electricity bill", "source": {"bytes": data}}}],
                    {"kind": "pdf", "sent_as": "pdf_document"})
        return ([{"image": {"format": "jpeg", "source": {"bytes": p}}} for p in pages],
                {"kind": "pdf", "sent_as": "pdf_rendered", "pages": len(pages)})
    jpeg, size = prep_image(data)
    return ([{"image": {"format": "jpeg", "source": {"bytes": jpeg}}}],
            {"kind": kind, "sent_as": "image", "px": list(size), "bytes_sent": len(jpeg)})
