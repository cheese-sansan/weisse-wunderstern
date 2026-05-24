"""
多格式文件读取模块

支持主流文档格式的文本内容提取。
原生支持（零依赖）：TXT, MD, JSON, CSV, HTML, XML, LOG, RST, TEX
可选依赖：PDF, DOCX, XLSX, PPTX, ODT/ODS/ODP, EPUB, RTF, 图片OCR
"""

import os
import json


def read_file(file_path: str) -> dict:
  """
  读取文件并返回其文本内容和元信息。

  参数:
    file_path: 文件路径

  返回:
    dict: {
      "success": bool,
      "content": str,
      "file_name": str,
      "file_type": str,
      "file_size": int,
      "error": str | None
    }
  """
  if not os.path.exists(file_path):
    return _error(file_path, f"文件不存在: {file_path}")

  if not os.path.isfile(file_path):
    return _error(file_path, f"路径不是文件: {file_path}")

  file_name = os.path.basename(file_path)
  _, ext = os.path.splitext(file_name)
  ext = ext.lower()
  file_size = os.path.getsize(file_path)

  # ── 纯文本类（Python 标准库，零依赖）──
  text_formats = {
      ".txt", ".md", ".markdown", ".csv", ".html", ".htm", ".xml",
      ".log", ".rst", ".tex", ".ini", ".cfg", ".conf", ".yaml", ".yml",
      ".toml", ".properties",
  }

  # ── 结构化文本 ──
  json_formats = {".json"}

  # ── 办公文档（可选第三方库）──
  office_formats = {
      ".pdf":  _read_pdf,
      ".docx": _read_docx,
      ".xlsx": _read_xlsx,
      ".pptx": _read_pptx,
      ".odt":  _read_odt,
      ".ods":  _read_odt,
      ".odp":  _read_odt,
  }

  # ── 电子书 ──
  ebook_formats = {".epub": _read_epub}

  # ── 富文本 ──
  rtf_formats = {".rtf": _read_rtf}

  # ── 图片 OCR ──
  image_formats = {
      ".png", ".jpg", ".jpeg", ".bmp", ".tiff", ".tif", ".gif", ".webp",
  }

  # 选择处理器
  if ext in json_formats:
    handler = _read_json
  elif ext in office_formats:
    handler = office_formats[ext]
  elif ext in ebook_formats:
    handler = ebook_formats[ext]
  elif ext in rtf_formats:
    handler = rtf_formats[ext]
  elif ext in image_formats:
    handler = _read_image_ocr
  elif ext in text_formats:
    handler = _read_text
  else:
    handler = _read_text  # 未知格式尝试当纯文本

  try:
    content = handler(file_path)
    return {
        "success": True,
        "content": content,
        "file_name": file_name,
        "file_type": ext,
        "file_size": file_size,
        "error": None,
    }
  except Exception as e:
    return _error(file_path, str(e))


def _error(file_path: str, message: str) -> dict:
  file_name = os.path.basename(file_path) if os.path.exists(file_path) else os.path.basename(file_path) if "/" in file_path or "\\" in file_path else file_path
  return {
      "success": False,
      "content": "",
      "file_name": file_name,
      "file_type": "",
      "file_size": 0,
      "error": message,
  }


# ═══════════════════════════════════════════════════════════════════
# 原生支持（Python 标准库，零依赖）
# ═══════════════════════════════════════════════════════════════════

def _read_text(file_path: str) -> str:
  """读取纯文本文件，自动检测编码（UTF-8 → GBK → latin-1）"""
  for encoding in ("utf-8", "gbk", "latin-1"):
    try:
      with open(file_path, "r", encoding=encoding) as f:
        return f.read()
    except UnicodeDecodeError:
      continue
  with open(file_path, "r", encoding="utf-8", errors="replace") as f:
    return f.read()


def _read_json(file_path: str) -> str:
  """读取 JSON 文件并格式化输出"""
  with open(file_path, "r", encoding="utf-8") as f:
    data = json.load(f)
  return json.dumps(data, ensure_ascii=False, indent=2)


# ═══════════════════════════════════════════════════════════════════
# PDF（可选依赖：pymupdf > pdfplumber > PyPDF2）
# ═══════════════════════════════════════════════════════════════════

def _read_pdf(file_path: str) -> str:
  # pymupdf (fitz)
  try:
    import fitz  # type: ignore
    doc = fitz.open(file_path)
    pages = [page.get_text() for page in doc]
    doc.close()
    text = "\n\n".join(pages)
    if text.strip():
      return text.strip()
  except ImportError:
    pass
  except Exception:
    pass

  # pdfplumber
  try:
    import pdfplumber  # type: ignore
    pages = []
    with pdfplumber.open(file_path) as pdf:
      for page in pdf.pages:
        t = page.extract_text()
        if t:
          pages.append(t)
    text = "\n\n".join(pages)
    if text.strip():
      return text.strip()
  except ImportError:
    pass
  except Exception:
    pass

  # PyPDF2
  try:
    from PyPDF2 import PdfReader  # type: ignore
    reader = PdfReader(file_path)
    pages = [page.extract_text() for page in reader.pages if page.extract_text()]
    text = "\n\n".join(pages)
    if text.strip():
      return text.strip()
  except ImportError:
    pass
  except Exception:
    pass

  raise ImportError(
      "读取 PDF 需要安装第三方库。请执行以下任一命令：\n"
      "  pip install pymupdf\n"
      "  pip install pdfplumber\n"
      "  pip install PyPDF2"
  )


# ═══════════════════════════════════════════════════════════════════
# DOCX（可选依赖：python-docx）
# ═══════════════════════════════════════════════════════════════════

def _read_docx(file_path: str) -> str:
  try:
    from docx import Document  # type: ignore
    doc = Document(file_path)
    paragraphs = [p.text for p in doc.paragraphs if p.text.strip()]
    # 也提取表格中的文本
    for table in doc.tables:
      for row in table.rows:
        for cell in row.cells:
          if cell.text.strip():
            paragraphs.append(cell.text.strip())
    return "\n\n".join(paragraphs)
  except ImportError:
    raise ImportError(
        "读取 DOCX 需要安装 python-docx。请执行：\n"
        "  pip install python-docx"
    )


# ═══════════════════════════════════════════════════════════════════
# XLSX（可选依赖：openpyxl）
# ═══════════════════════════════════════════════════════════════════

def _read_xlsx(file_path: str) -> str:
  try:
    from openpyxl import load_workbook  # type: ignore
    wb = load_workbook(file_path, read_only=True, data_only=True)
    parts = []
    for sheet_name in wb.sheetnames:
      ws = wb[sheet_name]
      parts.append(f"--- Sheet: {sheet_name} ---")
      for row in ws.iter_rows(values_only=True):
        row_text = "\t".join(str(c) if c is not None else "" for c in row)
        if row_text.strip():
          parts.append(row_text)
    wb.close()
    return "\n".join(parts)
  except ImportError:
    raise ImportError(
        "读取 XLSX 需要安装 openpyxl。请执行：\n"
        "  pip install openpyxl"
    )


# ═══════════════════════════════════════════════════════════════════
# PPTX（可选依赖：python-pptx）
# ═══════════════════════════════════════════════════════════════════

def _read_pptx(file_path: str) -> str:
  try:
    from pptx import Presentation  # type: ignore
    prs = Presentation(file_path)
    slides_out = []
    for i, slide in enumerate(prs.slides, 1):
      lines = [f"--- Slide {i} ---"]
      for shape in slide.shapes:
        if shape.has_text_frame:
          for para in shape.text_frame.paragraphs:
            if para.text.strip():
              lines.append(para.text.strip())
        if shape.has_table:
          table = shape.table
          for row in table.rows:
            row_text = "\t".join(cell.text for cell in row.cells)
            if row_text.strip():
              lines.append(row_text)
      slides_out.append("\n".join(lines))
    return "\n\n".join(slides_out)
  except ImportError:
    raise ImportError(
        "读取 PPTX 需要安装 python-pptx。请执行：\n"
        "  pip install python-pptx"
    )


# ═══════════════════════════════════════════════════════════════════
# ODT / ODS / ODP（可选依赖：odfpy）
# ═══════════════════════════════════════════════════════════════════

def _read_odt(file_path: str) -> str:
  try:
    from odf.opendocument import load  # type: ignore
    from odf import text as odf_text, table as odf_table  # type: ignore

    doc = load(file_path)
    parts = []

    def _walk(element):
      if isinstance(element, odf_text.P):
        txt = ""
        for node in element.childNodes:
          if node.nodeType == element.TEXT_NODE:
            txt += node.data
        if txt.strip():
          parts.append(txt.strip())
      for child in element.childNodes:
        _walk(child)

    _walk(doc.text)
    return "\n\n".join(parts)
  except ImportError:
    raise ImportError(
        "读取 ODT/ODS/ODP 需要安装 odfpy。请执行：\n"
        "  pip install odfpy"
    )


# ═══════════════════════════════════════════════════════════════════
# EPUB（可选依赖：ebooklib）
# ═══════════════════════════════════════════════════════════════════

def _read_epub(file_path: str) -> str:
  try:
    import ebooklib  # type: ignore
    from ebooklib import epub  # type: ignore
    from html.parser import HTMLParser

    class _Stripper(HTMLParser):
      def __init__(self):
        super().__init__()
        self.parts = []

      def handle_data(self, data):
        self.parts.append(data)

    book = epub.read_epub(file_path)
    chapters = []
    for item in book.get_items():
      if item.get_type() == ebooklib.ITEM_DOCUMENT:
        content = item.get_content().decode("utf-8", errors="replace")
        stripper = _Stripper()
        stripper.feed(content)
        text = "".join(stripper.parts).strip()
        if text:
          chapters.append(text)

    if not chapters:
      return "[EPUB] 未提取到文本内容，可能为纯图片电子书"
    return "\n\n---\n\n".join(chapters)
  except ImportError:
    raise ImportError(
        "读取 EPUB 需要安装 ebooklib。请执行：\n"
        "  pip install ebooklib"
    )


# ═══════════════════════════════════════════════════════════════════
# RTF（可选依赖：striprtf）
# ═══════════════════════════════════════════════════════════════════

def _read_rtf(file_path: str) -> str:
  try:
    from striprtf.striprtf import rtf_to_text  # type: ignore
    with open(file_path, "r", encoding="utf-8", errors="replace") as f:
      rtf_content = f.read()
    return rtf_to_text(rtf_content)
  except ImportError:
    raise ImportError(
        "读取 RTF 需要安装 striprtf。请执行：\n"
        "  pip install striprtf"
    )


# ═══════════════════════════════════════════════════════════════════
# 图片 OCR（可选依赖：Pillow + pytesseract）
# ═══════════════════════════════════════════════════════════════════

def _read_image_ocr(file_path: str) -> str:
  try:
    from PIL import Image  # type: ignore

    try:
      import pytesseract  # type: ignore
    except ImportError:
      raise ImportError(
          "图片 OCR 需要安装 pytesseract。请执行：\n"
          "  pip install pytesseract Pillow\n"
          "  并安装 Tesseract 引擎：https://github.com/tesseract-ocr/tesseract"
      )

    img = Image.open(file_path)
    text = pytesseract.image_to_string(img, lang="chi_sim+eng")
    if not text.strip():
      return "[OCR] 图片中未检测到文字"
    return text.strip()
  except ImportError as e:
    raise ImportError(str(e))
