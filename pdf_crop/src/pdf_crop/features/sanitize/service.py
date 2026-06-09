from collections import Counter
from dataclasses import dataclass, field

from pypdf.generic import NameObject

# Identifying keys on an annotation dictionary: author, mod date, creation
# date, and the free-text contents.
_ANNOT_IDENTIFYING_KEYS = ("/T", "/M", "/CreationDate", "/Contents")


@dataclass
class Inventory:
    """Where identifying data hides in a PDF, grouped so a UI can show counts."""

    info_keys: list[str] = field(default_factory=list)        # /Info dict keys (incl. custom)
    xmp_catalog: bool = False                                 # catalog /Metadata stream
    xmp_pages: list[int] = field(default_factory=list)        # 1-indexed pages with /Metadata
    trailer_id: bool = False                                  # trailer /ID
    piece_info_catalog: bool = False                          # catalog /PieceInfo
    piece_info_pages: list[int] = field(default_factory=list) # 1-indexed pages with /PieceInfo
    annotations: int = 0                                      # annots with identifying keys
    embedded_files: int = 0                                   # /Names /EmbeddedFiles entries
    javascript: bool = False                                  # /Names /JavaScript, /OpenAction, /AA
    outlines: bool = False                                    # /Outlines
    named_dests: int = 0                                      # /Names /Dests entries

    def summary(self) -> dict[str, int]:
        """Counts per source, skipping anything that is empty/absent."""
        counts = {
            "info": len(self.info_keys),
            "xmp": int(self.xmp_catalog) + len(self.xmp_pages),
            "trailer_id": int(self.trailer_id),
            "piece_info": int(self.piece_info_catalog) + len(self.piece_info_pages),
            "annotations": self.annotations,
            "embedded_files": self.embedded_files,
            "javascript": int(self.javascript),
            "outlines": int(self.outlines),
            "named_dests": self.named_dests,
        }
        return {k: v for k, v in counts.items() if v}

    def total(self) -> int:
        return sum(self.summary().values())


def _root(pdf):
    """Catalog dictionary for either a PdfReader or a PdfWriter."""
    if hasattr(pdf, "_root_object"):
        return pdf._root_object
    return pdf.trailer["/Root"]


def _has_trailer_id(pdf) -> bool:
    if hasattr(pdf, "_ID"):  # PdfWriter
        return pdf._ID is not None
    return "/ID" in pdf.trailer  # PdfReader


def _names_subtree_count(root, key: str) -> int:
    """Number of entries under /Names/<key> (an alternating name/value array)."""
    names = root.get("/Names")
    if names is None:
        return 0
    subtree = names.get_object().get(key)
    if subtree is None:
        return 0
    entries = subtree.get_object().get("/Names")
    if entries is None:
        return 0
    return len(entries) // 2


def inventory(pdf) -> Inventory:
    """Inspect `pdf` (a PdfReader or PdfWriter) and report every metadata source."""
    inv = Inventory()
    root = _root(pdf)

    if pdf.metadata:
        inv.info_keys = list(pdf.metadata.keys())

    inv.xmp_catalog = "/Metadata" in root
    inv.trailer_id = _has_trailer_id(pdf)
    inv.piece_info_catalog = "/PieceInfo" in root
    inv.outlines = "/Outlines" in root

    has_open_action = "/OpenAction" in root or "/AA" in root
    inv.javascript = has_open_action or _names_subtree_count(root, "/JavaScript") > 0
    inv.embedded_files = _names_subtree_count(root, "/EmbeddedFiles")
    inv.named_dests = _names_subtree_count(root, "/Dests")

    for i, page in enumerate(pdf.pages, start=1):
        page_obj = page.get_object()
        if "/Metadata" in page_obj:
            inv.xmp_pages.append(i)
        if "/PieceInfo" in page_obj:
            inv.piece_info_pages.append(i)
        for ref in page_obj.get("/Annots", []) or []:
            annot = ref.get_object()
            if any(k in annot for k in _ANNOT_IDENTIFYING_KEYS):
                inv.annotations += 1

    return inv


def sanitize(writer) -> None:
    """Strip every identifying source from `writer` in place, keeping page text."""
    root = writer._root_object

    # /Info dict.
    if writer._info is not None:
        info = writer._info.get_object()
        for key in list(info.keys()):
            del info[key]

    # XMP /Metadata (catalog) and trailer /ID.
    for key in ("/Metadata", "/PieceInfo", "/Names", "/OpenAction", "/AA", "/Outlines"):
        if NameObject(key) in root:
            del root[NameObject(key)]
    writer._ID = None
    if "/PageMode" in root:
        del root[NameObject("/PageMode")]

    # Per-page structure.
    for page in writer.pages:
        page_obj = page.get_object()
        for key in ("/Metadata", "/PieceInfo", "/Annots"):
            if NameObject(key) in page_obj:
                del page_obj[NameObject(key)]
