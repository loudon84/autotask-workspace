"""验证阿里企业邮箱 IMAP 读取能力。参数只从 Task `.env` 读，不要把授权码写进本文件。

跑法（在 service/ 目录）：
  python scripts/probe_ali_mail.py
"""

from __future__ import annotations

import imaplib
import os
import re
import sys
import email
from email.header import decode_header
from email.utils import parseaddr
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[1] / ".env")


def _env(name: str, default: str = "") -> str:
    return str(os.getenv(name, default) or "").strip()


# 非密钥默认值可以写在这里；USER / AUTH 必须来自环境变量。
CONFIG = {
    "host": _env("ALI_MAIL_HOST", "imap.qiye.aliyun.com"),
    "port": int(_env("ALI_MAIL_PORT", "993") or "993"),
    "user": _env("ALI_MAIL_USER"),
    "auth": _env("ALI_MAIL_AUTH"),
    "folder": _env("ALI_MAIL_FOLDER", "BOE-SRM一站式平台-验证码"),
    "readonly": _env("ALI_MAIL_READONLY", "true").lower() not in {"0", "false", "no"},
    "top_n": int(_env("ALI_MAIL_TOP_N", "5") or "5"),
}


def _decode(value):
    if not value:
        return ""
    out = []
    for text, charset in decode_header(value):
        if isinstance(text, bytes):
            out.append(text.decode(charset or "utf-8", errors="replace"))
        else:
            out.append(text)
    return "".join(out)


def _body(msg):
    if msg.is_multipart():
        for part in msg.walk():
            if part.get_content_type() == "text/plain":
                raw = part.get_payload(decode=True)
                if raw:
                    return raw.decode(part.get_content_charset() or "utf-8", errors="replace")
        for part in msg.walk():
            if part.get_content_type() == "text/html":
                raw = part.get_payload(decode=True)
                if raw:
                    html = raw.decode(part.get_content_charset() or "utf-8", errors="replace")
                    return re.sub(r"<[^>]+>", " ", html)
    raw = msg.get_payload(decode=True)
    if raw:
        return raw.decode(msg.get_content_charset() or "utf-8", errors="replace")
    return ""


def _extract_code(text):
    if not text:
        return None
    m = re.search(r"验证码[^\d]{0,30}(\d{6})", text)
    if m:
        return m.group(1)
    all6 = re.findall(r"\b\d{6}\b", text)
    return all6[-1] if all6 else None


def _imap_utf7_decode(text):
    """把 IMAP modified UTF-7 字符串解码回 Unicode（仅用于显示文件夹列表）。"""
    import base64, re
    def repl(m):
        b64 = m.group(1).replace(",", "+")
        try:
            # base64 末尾的 = 可能被去掉，补回来
            pad = "=" * (-len(b64) % 4)
            return base64.b64decode(b64 + pad).decode("utf-16-be", errors="replace")
        except Exception:
            return m.group(0)
    return re.sub(r"&([^-]*)-", repl, text).replace("&-", "&")


def _imap_utf7_encode(text):
    """把文件夹名编码成 IMAP modified UTF-7（中文文件夹必须用这个）。"""
    # 非 ASCII 部分用 UTF-16 BE 再 base64，base64 用的是 modified 字符集（/, 不是 +）
    import base64
    out = []
    for ch in text:
        if 0x20 <= ord(ch) <= 0x7e:
            if ch == "&":
                out.append("&-")
            else:
                out.append(ch)
        else:
            # 找到连续的非 ASCII 段
            pass
    # 简化实现：按段切分
    result = []
    buf = []
    def flush_buf():
        if buf:
            b = "".join(buf).encode("utf-16-be")
            # modified UTF-7：base64 去掉 = 填充，+ 换成 ,
            b64 = base64.b64encode(b).decode("ascii").replace("+", ",").rstrip("=")
            result.append("&" + b64 + "-")
            buf.clear()
    for ch in text:
        if 0x20 <= ord(ch) <= 0x7e:
            flush_buf()
            if ch == "&":
                result.append("&-")
            else:
                result.append(ch)
        else:
            buf.append(ch)
    flush_buf()
    return "".join(result)


def main():
    if not CONFIG["user"] or not CONFIG["auth"]:
        print("❌ 先在 service/.env 填 ALI_MAIL_USER 和 ALI_MAIL_AUTH（客户端授权码，不是登录密码）")
        return 2

    print(f"[1/4] 连接 {CONFIG['host']}:{CONFIG['port']} ...")
    try:
        mail = imaplib.IMAP4_SSL(CONFIG["host"], CONFIG["port"])
    except OSError as e:
        print(f"❌ 连不上：{e}")
        print("   → 检查公司网络 / 防火墙 993 端口 / DNS 解析")
        return 10

    print(f"[2/4] LOGIN {CONFIG['user']} ...")
    try:
        mail.login(CONFIG["user"], CONFIG["auth"])
    except imaplib.IMAP4.error as e:
        print(f"❌ LOGIN 失败：{e}")
        print("   → 授权码错了？还是用了登录密码？还是管理员没开 IMAP？")
        mail.logout()
        return 11

    print(f"[3/4] SELECT '{CONFIG['folder']}' (readonly={CONFIG['readonly']}) ...")
    # 中文文件夹名需要 IMAP modified UTF-7 编码
    folder = _imap_utf7_encode(CONFIG["folder"])
    status, data = mail.select(folder, readonly=CONFIG["readonly"])
    if status != "OK":
        print(f"❌ SELECT 失败：{data}")
        print("   → 先看看邮箱里到底有哪些文件夹：")
        ok, flist = mail.list()
        if ok == "OK":
            for f in flist:
                raw = f.decode() if isinstance(f, bytes) else f
                # 文件夹名可能是 modified UTF-7，尝试解码成中文
                decoded = _imap_utf7_decode(raw)
                print(f"     {raw}   →   {decoded}")
        mail.logout()
        return 13

    total = int(data[0])
    print(f"   → 该文件夹共 {total} 封邮件")

    if total == 0:
        print("⚠️ 空的。等 BOE 发一次验证码过来让策略转发再试。")
        mail.logout()
        return 0

    print(f"[4/4] 读最新 {min(CONFIG['top_n'], total)} 封：\n")
    start = max(1, total - CONFIG["top_n"] + 1)
    for idx in range(start, total + 1):
        ok, payload = mail.fetch(str(idx), "(RFC822)")
        if ok != "OK":
            print(f"  [{idx}] FETCH 失败")
            continue
        msg = email.message_from_bytes(payload[0][1])
        subject = _decode(msg.get("Subject"))
        _, from_addr = parseaddr(msg.get("From", ""))
        _, to_addr = parseaddr(msg.get("To", ""))
        date = msg.get("Date")
        body = _body(msg)
        code = _extract_code(body)

        print(f"  [{idx}] Date   : {date}")
        print(f"        From  : {from_addr}")
        print(f"        To    : {to_addr}")
        print(f"        Subj  : {subject}")
        preview = body[:300].replace("\r", " ").replace("\n", " ")
        print(f"        Body  : {preview}{'…' if len(body) > 300 else ''}")
        print(f"        Code  : {'✅ ' + code if code else '❌ 没找到'}")
        print()

    mail.logout()
    print("✅ 读完了")
    return 0


if __name__ == "__main__":
    sys.exit(main())
