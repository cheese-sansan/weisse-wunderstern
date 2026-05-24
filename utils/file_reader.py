"""
零依赖文件读取模块

使用 Python 标准库读取常见文档格式的文本内容。
支持：TXT, MD, JSON（原生）
可选：PDF, DOCX（需安装对应第三方库，否则给出提示）
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
      "content": str,       # 提取的文本内容
      "file_name": str,     # 文件名
      "file_type": str,     # 文件扩展名
      "file_size": int,     # 文件字节数
      "error": str | None   # 错误信息（仅在失败时）
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

  handlers = {
      ".txt": _read_text,
      ".md": _read_text,
      ".markdown": _read_text,
      ".json": _read_json,
      ".pdf": _read_pdf,
      ".docx": _read_docx,
  }

  handler = handlers.get(ext)
  if handler is None:
    # 未知格式，尝试按纯文本读取
    handler = _read_text

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


def _read_text(file_path: str) -> str:
  """读取纯文本文件，自动检测编码"""
  # 优先 UTF-8，回退 GBK（Windows 中文环境常见）
  for encoding in ("utf-8", "gbk", "latin-1"):
    try:
      with open(file_path, "r", encoding=encoding) as f:
        return f.read()
    except UnicodeDecodeError:
      continue
  # 最终兜底
  with open(file_path, "r", encoding="utf-8", errors="replace") as f:
    return f.read()


def _read_json(file_path: str) -> str:
  """读取 JSON 文件并格式化输出"""
  with open(file_path, "r", encoding="utf-8") as f:
    data = json.load(f)
  return json.dumps(data, ensure_ascii=False, indent=2)


def _read_pdf(file_path: str) -> str:
  """
  读取 PDF 文件。

  优先使用 pymupdf(fitz)，其次 pdfplumber，最后 PyPDF2。
  若均未安装，返回清晰的安装提示。
  """
  # 尝试 pymupdf (fitz)
  try:
    import fitz  # type: ignore
    doc = fitz.open(file_path)
    pages = []
    for page in doc:
      pages.append(page.get_text())
    doc.close()
    text = "\n\n".join(pages)
    if text.strip():
      return text.strip()
  except ImportError:
    pass
  except Exception:
    pass

  # 尝试 pdfplumber
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

  # 尝试 PyPDF2
  try:
    from PyPDF2 import PdfReader  # type: ignore
    reader = PdfReader(file_path)
    pages = []
    for page in reader.pages:
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

  raise ImportError(
      "读取 PDF 需要安装第三方库。请执行以下任一命令：\n"
      "  pip install pymupdf\n"
      "  pip install pdfplumber\n"
      "  pip install PyPDF2"
  )


def _read_docx(file_path: str) -> str:
  """
  读取 DOCX 文件。

  需要 python-docx，若未安装则给出提示。
  """
  try:
    from docx import Document  # type: ignore
    doc = Document(file_path)
    paragraphs = [p.text for p in doc.paragraphs if p.text.strip()]
    return "\n\n".join(paragraphs)
  except ImportError:
    raise ImportError(
        "读取 DOCX 需要安装 python-docx。请执行：\n"
        "  pip install python-docx"
    )
